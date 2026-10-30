"""Reranker service: loads a cross-encoder on demand and scores (query, text) pairs over HTTP.

POST /rerank {"query": str, "texts": [str]} -> {"scores": [float], "seconds": float}
POST /warm   -> {"status": "ok", "loaded": true, "seconds": float}  -- loads the model
               without scoring anything, so a caller can pay the load cost ahead of a
               user's actual search instead of on it.
GET  /health -> {"status": "ok", "loaded": bool, "device": "cuda" | "cpu"}

Idle unload: after RERANK_IDLE_SECONDS of no /rerank or /warm calls, the model is
dropped from GPU memory so it stops costing anything on a shared machine -- the same
behavior Ollama already has by default (measured 2026-10-29: Ollama evicts an idle
model after 5 minutes). The next call reloads it (measured warm-cache load: ~5
seconds -- the 2-minute figure seen once was a one-time model download, not a normal
reload). Set RERANK_IDLE_SECONDS=0 to disable eviction entirely (Tyler's "admin-only
always-on" case) -- not exposed as a CLI flag on purpose, since an ordinary deployment
should not need it.
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
HOST = os.environ.get("RERANK_HOST", "0.0.0.0")
PORT = int(os.environ.get("RERANK_PORT", "8732"))
IDLE_SECONDS = float(os.environ.get("RERANK_IDLE_SECONDS", "900"))  # 0 = never unload
PREWARM_ON_START = os.environ.get("RERANK_PREWARM_ON_START", "1") not in ("0", "", "false", "False")
MAX_LENGTH = 256
BATCH = 16

_lock = threading.Lock()
_tokenizer = None
_model = None
_device = None
_last_used = 0.0
_busy = 0  # count of requests currently using the model -- never unload while > 0


def _ensure_loaded():
    """Load the model if it isn't already, and record this as recent use. Thread-safe --
    concurrent requests arriving while unloaded must not each start their own load."""
    global _tokenizer, _model, _device, _last_used
    with _lock:
        _last_used = time.monotonic()
        if _model is not None:
            return
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"loading {MODEL} on {_device} ...", flush=True)
        t0 = time.time()
        _tokenizer = AutoTokenizer.from_pretrained(MODEL)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval().to(_device)
        print(f"ready ({time.time() - t0:.1f}s)", flush=True)


def _unload_if_idle():
    """Background loop: drop the model from GPU memory after IDLE_SECONDS of no use.
    Disabled entirely when IDLE_SECONDS <= 0. Never unloads while a request is actively
    using the model (_busy > 0) -- a slow or large single request must not have its
    model pulled out from under it mid-flight."""
    global _tokenizer, _model
    if IDLE_SECONDS <= 0:
        return
    while True:
        time.sleep(min(30, IDLE_SECONDS))
        with _lock:
            if _model is not None and _busy == 0 and time.monotonic() - _last_used >= IDLE_SECONDS:
                import torch
                print("idle timeout -- unloading model", flush=True)
                _tokenizer = None
                _model = None
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()


def score(query: str, texts: list[str]) -> list[float]:
    global _busy, _last_used
    import torch
    _ensure_loaded()
    with _lock:
        _busy += 1
    try:
        out: list[float] = []
        with torch.no_grad():
            for start in range(0, len(texts), BATCH):
                batch = texts[start:start + BATCH]
                enc = _tokenizer([query] * len(batch), batch, padding=True, truncation=True,
                                  max_length=MAX_LENGTH, return_tensors="pt").to(_device)
                out.extend(_model(**enc).logits.view(-1).tolist())
        return out
    finally:
        with _lock:
            _busy -= 1
            _last_used = time.monotonic()  # restart the idle clock from completion, not start


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok", "loaded": _model is not None, "device": _device})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/rerank":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                t0 = time.time()
                scores = score(body["query"], body["texts"])
                self._send(200, {"scores": scores, "seconds": time.time() - t0})
            except Exception as exc:
                self._send(400, {"error": str(exc)})
        elif self.path == "/warm":
            t0 = time.time()
            _ensure_loaded()
            self._send(200, {"status": "ok", "loaded": True, "seconds": time.time() - t0})
        else:
            self._send(404, {"error": "not found"})

    def _send(self, code: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    threading.Thread(target=_unload_if_idle, daemon=True).start()
    if PREWARM_ON_START:
        # Pay the load cost at container startup, well before any real user search,
        # rather than on the first /rerank call.
        threading.Thread(target=_ensure_loaded, daemon=True).start()
    print(f"listening on {HOST}:{PORT} (idle unload: "
          f"{'disabled' if IDLE_SECONDS <= 0 else f'{IDLE_SECONDS:.0f}s'})", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

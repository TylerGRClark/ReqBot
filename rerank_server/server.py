"""Reranker service: loads a cross-encoder once and scores (query, text) pairs over HTTP.

POST /rerank {"query": str, "texts": [str]} -> {"scores": [float], "seconds": float}
GET  /health -> {"status": "ok", "device": "cuda" | "cpu"}
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
HOST = os.environ.get("RERANK_HOST", "0.0.0.0")
PORT = int(os.environ.get("RERANK_PORT", "8732"))
MAX_LENGTH = 256
BATCH = 16

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"loading {MODEL} on {device} ...", flush=True)
tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval().to(device)
print("ready", flush=True)


def score(query: str, texts: list[str]) -> list[float]:
    out: list[float] = []
    with torch.no_grad():
        for start in range(0, len(texts), BATCH):
            batch = texts[start:start + BATCH]
            enc = tokenizer([query] * len(batch), batch, padding=True, truncation=True,
                            max_length=MAX_LENGTH, return_tensors="pt").to(device)
            out.extend(model(**enc).logits.view(-1).tolist())
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok", "device": device})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/rerank":
            self._send(404, {"error": "not found"})
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            t0 = time.time()
            scores = score(body["query"], body["texts"])
            self._send(200, {"scores": scores, "seconds": time.time() - t0})
        except Exception as exc:
            self._send(400, {"error": str(exc)})

    def _send(self, code: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

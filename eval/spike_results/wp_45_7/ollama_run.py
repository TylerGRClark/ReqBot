"""WP-45.7: the shared Ollama call and the scratch ledger for the discovery and resolver runners (scratch only).

- `generate` calls /api/generate with a pinned num_ctx, a temperature argument and an optional JSON Schema `format`, and returns
  the text plus Ollama's own token counts and timings. Nothing here reads or writes the production cache.
- `Ledger` is one JSONL file per run label. A record is keyed by what determines the answer (input, prompt hash, model DIGEST and
  run label), so a second repeat or the 14B arm can never reuse an earlier answer: each repeat and each model has its own run
  label and its own file. A record whose status is `failed` is redone on resume; every other status is kept.
- `classify` gives a call its status: untreatable (never sent), failed, truncated (hit the output allowance),
  window_overrun (prompt plus answer reached num_ctx: Ollama drops the start of an over-long prompt without an error), or complete.
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

DEFAULT_SCRATCH = Path.home() / "wp45_7_scratch"
NUM_CTX = 8192
STATUSES = ("complete", "truncated", "window_overrun", "untreatable", "failed")
DONE = ("complete", "truncated", "window_overrun", "untreatable")  # failed is redone on resume


def sha(text, n=16):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def model_digest(ollama_url, model, timeout=10):
    """The digest Ollama reports for the exact model file (a sha256 of its manifest), from /api/tags."""
    r = requests.get(f"{ollama_url}/api/tags", timeout=timeout)
    r.raise_for_status()
    for m in r.json().get("models", []):
        if m.get("name") == model or m.get("model") == model:
            return m.get("digest") or ""
    raise RuntimeError(f"model {model!r} is not on {ollama_url}")


def generate(prompt, model, ollama_url, *, num_ctx=NUM_CTX, num_predict=4096, temperature=0.1, schema=None,
             timeout=300, retries=2):
    """One non-streaming generation. Returns (text, meta); raises requests.RequestException after the retries."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict, "num_ctx": num_ctx},
    }
    if schema is not None:
        payload["format"] = schema
    for attempt in range(retries + 1):
        started = time.time()
        try:
            resp = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            meta = {k: data.get(k) for k in ("done_reason", "prompt_eval_count", "eval_count", "total_duration", "load_duration")}
            meta["wall_seconds"] = round(time.time() - started, 3)
            return data["response"], meta
        except requests.RequestException as e:
            if attempt == retries:
                raise
            wait = 2 ** (attempt + 1)
            log.warning("Ollama request failed (%s); retrying in %ds", e, wait)
            time.sleep(wait)


def classify(meta, num_ctx=NUM_CTX):
    """complete, truncated or window_overrun from a finished call's metadata."""
    used = (meta.get("prompt_eval_count") or 0) + (meta.get("eval_count") or 0)
    if used >= num_ctx:
        return "window_overrun"
    if meta.get("done_reason") == "length":
        return "truncated"
    return "complete"


class Ledger:
    """One JSONL file per run label, appended and flushed per record, loaded on start for resume."""

    def __init__(self, path):
        self.path = Path(path)
        self.records = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.records[rec["key"]] = rec

    def done(self, key):
        rec = self.records.get(key)
        return rec is not None and rec.get("status") in DONE

    def get(self, key):
        return self.records.get(key)

    def append(self, rec):
        if rec.get("status") not in STATUSES:
            raise ValueError(f"unknown status {rec.get('status')!r}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.records[rec["key"]] = rec  # a later record for the same key (a redo of a failure) wins


def discovery_key(document, chunk_id, prompt_hash, digest, run_label):
    return sha(f"discovery|{document}|{chunk_id}|{prompt_hash}|{digest}|{run_label}", 24)


def resolver_key(document, quote_hash, bundle_hash, prompt_hash, digest, run_label):
    return sha(f"resolver|{document}|{quote_hash}|{bundle_hash}|{prompt_hash}|{digest}|{run_label}", 24)

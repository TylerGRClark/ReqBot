#!/usr/bin/env python3
"""WP-45.12: the per-paragraph duty arm (P1) and its ledger, plus the chunk sets the arms run on (scratch only; docs/PHASE45_WP4512_PLAN.md).

P1 asks one question per paragraph of a chunk: does it tell someone to do something, not do something, or permit or recommend something an auditor could check? A paragraph
judged yes becomes a candidate whose `source_quote` is the paragraph's own text without its leading number or bullet, so no text is generated. The ledger has the shape of
`wp_45_7/run_discovery.py`'s (one record per chunk, `raw_response` = a Step C-shaped JSON answer), so `score_discovery.score_run` reads it unchanged.
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_7"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import ollama_run as OR  # noqa: E402  (wp_45_7: the shared Ollama call and ledger)

from services import checklist_missed as M  # noqa: E402

MODEL = "llama3.1:8b-instruct-q4_K_M"
MIN_UNIT_CHARS = 40
P1_PROMPT = """You are checking one paragraph of a regulation for an auditor.

Question: does this paragraph tell someone to do something, not to do something, or permit or recommend something that an auditor could check?

Answer true for:
- shall / must / will / should / may statements
- commands, for example "Identify the likely root cause of the incident."
- statements of a duty with no modal verb, for example "Provides functional expertise to the Program Office."
- prohibitions, recommendations and permissions

Answer false for:
- definitions, and background or explanation of how something works
- headings and titles
- scope or purpose statements
- statements of what something is or where it is located
- a bare cross-reference
- a lead-in that ends with a colon and has no content of its own

Heading: {heading}
Paragraph: {paragraph}

Answer as JSON: {{"duty": true}} or {{"duty": false}}."""
SCHEMA = {"type": "object", "properties": {"duty": {"type": "boolean"}}, "required": ["duty"]}
_LEAD = re.compile(r"^\W*(?:\d+(?:\.\d+)*\.?|[A-Za-z]\.|\([A-Za-z0-9]{1,3}\))?\s*")


def prompt_hash():
    return hashlib.sha256((P1_PROMPT + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()[:16]


def units_of(chunk, seen=None):
    """[(unit text, quote text, ref)] for a chunk: the paragraph units of its raw text, 40+ characters, not seen before in the document (`seen` is the document's set)."""
    out = []
    for unit in M.paragraph_units(chunk.get("raw_text") or ""):
        norm = M.normalize(unit)
        if len(norm) < MIN_UNIT_CHARS or (seen is not None and norm in seen):
            continue
        if seen is not None:
            seen.add(norm)
        ref = (re.match(r"^\W*(\d+(?:\.\d+)+)\.?\s", unit) or [None, ""])[1]
        quote = _LEAD.sub("", unit, count=1).strip() or unit
        out.append((unit, quote, ref))
    return out


def run_chunks(chunks, *, model, digest, run_label, ledger, ollama_url, log=print):
    """chunks: [(document, chunk)]. One record per chunk; a chunk whose every call finished is `complete`, otherwise `failed` (redone on resume)."""
    phash = prompt_hash()
    seen_by_doc, calls = {}, 0
    for document, chunk in chunks:
        key = OR.discovery_key(document, chunk["chunk_id"], phash, digest, run_label)
        seen = seen_by_doc.setdefault(document, set())
        units = units_of(chunk, seen)
        if ledger.done(key):
            continue
        heading = ((chunk.get("section_title_path") or [""])[-1]) or "(none)"
        answers, reqs, ok = [], [], True
        for unit, quote, ref in units:
            try:
                text, meta = OR.generate(P1_PROMPT.format(heading=heading, paragraph=unit[:1500]), model, ollama_url, num_ctx=2048, num_predict=20, temperature=0.1,
                                         schema=SCHEMA, timeout=120)
                duty = bool(json.loads(text).get("duty"))
            except Exception as e:  # noqa: BLE001  (a request or format failure is a recorded failure, never a "no")
                ok, duty, meta = False, None, {"error": str(e)}
            calls += 1
            answers.append({"unit": unit, "duty": duty, "seconds": meta.get("wall_seconds")})
            if duty:
                reqs.append({"source_quote": quote, "source_ref": ref})
        ledger.append({
            "entry_id": key, "kind": "discovery", "run_label": run_label, "arm": "P1", "model": model, "digest": digest, "document": document, "chunk_id": chunk["chunk_id"],
            "prompt_hash": phash, "prompt_chars": len(P1_PROMPT), "estimated_prompt_tokens": 0, "num_ctx": 2048, "num_predict": 20, "temperature": 0.1,
            "timestamp": datetime.now(timezone.utc).isoformat(), "status": "complete" if ok else "failed", "raw_response": json.dumps({"requirements": reqs}),
            "meta": {"wall_seconds": round(sum(a["seconds"] or 0 for a in answers), 3), "prompt_eval_count": 0, "eval_count": 0}, "unit_answers": answers})
        log(f"{document} chunk {chunk['chunk_id']}: {len(units)} units, {len(reqs)} duty, {'ok' if ok else 'FAILED'}")
    return calls


def afi_chunks(document):
    """[(document, chunk)] for a whole document from the merged table-fix chunking (T2_256) cache."""
    path = Path.home() / "wp45_10_cache/d2.94.0/chunks/T2_256" / f"{document}_chunks.jsonl"
    return [(document, json.loads(x)) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

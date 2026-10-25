#!/usr/bin/env python3
"""PREREG11 driver: label the table chunks of whole documents with one arm's context and save labels and timing. One model job at a time.
Arms: control (production), control2 (repeat), header (table context for grid lines). Only the context string differs; the prompt file is the frozen one.

    python3 eval/clause_labeling/table_hdr_run.py --arm control --out ~/reqbot-work/scratch/table_hdr
"""
import argparse
import glob
import json
import os
import re
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import clause_labeling as CL  # noqa: E402
import table_header as TH  # noqa: E402

DOCS = ["CNSSI_No1253", "dafman17-1203", "dafpam90-803", "afi17-203", "afi10-2402", "dafi36-2903"]
ARMS = {"control": False, "control2": False, "header": True}


def clause_block(items: list[dict]) -> str:
    """Production clause_block plus the table context field (after the lead-in field) when the clause carries one."""
    parts = []
    for i, c in enumerate(items, 1):
        ctx = []
        if c["heading"]:
            ctx.append("Heading: " + c["heading"][:CL.HEADING_CHARS])
        if c["ref"]:
            ctx.append("Paragraph: " + c["ref"][:CL.PARAGRAPH_CHARS])
        if c["ctx_lead"]:
            ctx.append("Lead-in line above: " + c["ctx_lead"][:CL.LEAD_IN_CHARS])
        if c.get("ctx_table"):
            ctx.append("Table context: " + c["ctx_table"][:TH.MAX_CHARS])
        parts.append("[%d]\nContext: %s\nClause: %s" % (i, " | ".join(ctx) if ctx else "(none)", re.sub(r"[ \t]{2,}", " ", c["text"])[:CL.CLAUSE_CHARS]))
    return "\n\n".join(parts)


def chunk_path(doc: str, out: Path) -> Path:
    snap = out / "chunks" / f"{doc}_chunks.jsonl"
    if not snap.exists():
        src = sorted(glob.glob(os.path.expanduser(f"~/documents/processed/{doc}_20*/{doc}_chunks.jsonl")))[-1]
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_bytes(Path(src).read_bytes())
    return snap


def doc_clauses(chunks: list[dict], header: bool) -> list[dict]:
    allc = CL.document_clauses(chunks)  # production: ctx_lead set
    TH.document_table_context(chunks, allc)
    tc = {c["chunk_id"] for c in allc if c["text"].lstrip().startswith("|")}
    out = [c for c in allc if c["chunk_id"] in tc]
    for c in out:
        c["is_grid"] = c["text"].lstrip().startswith("|")
        c["ctx_table_rule"] = c["ctx_table"]
        if not header:
            c["ctx_table"] = None
    return out


def run_doc(doc: str, arm: str, out: Path, ollama_url: str, model: str) -> None:
    res_path = out / arm / f"{doc}.json"
    if res_path.exists():
        return
    chunks = [json.loads(ln) for ln in open(chunk_path(doc, out), encoding="utf-8") if ln.strip()]
    clauses = doc_clauses(chunks, ARMS[arm])
    for c in clauses:  # the copy of clause_block must equal production when there is no table context
        if not c["ctx_table"]:
            assert clause_block([c]) == CL.clause_block([c])
    template = CL.load_prompt()
    batches = CL.make_batches(clauses, size=CL.BATCH_SIZE)
    call = lambda p: CL.ollama_chat(p, model=model, ollama_url=ollama_url, timeout=600)  # noqa: E731
    call("Reply with the single word OK.")  # warm-up
    labels, recs = {}, []
    t0 = time.time()
    for b in batches:
        rec = CL.label_batch(b, template.replace("{CLAUSES}", clause_block(b["clauses"])), model=model, call=call)
        recs.append({k: rec[k] for k in ("batch_id", "clause_keys", "status", "attempts", "prompt_sha", "labels")})
        if rec["labels"]:
            for k, lab in zip(rec["clause_keys"], rec["labels"]):
                labels[f"{k[0]}:{k[1]}"] = lab
    secs = time.time() - t0
    res = {"doc": doc, "arm": arm, "model": model, "seconds": secs, "batches": len(batches), "clauses": len(clauses),
           "unparsed": sum(r["status"] == CL.STATUS_UNPARSED for r in recs), "failed": sum(r["status"] == CL.STATUS_FAILED for r in recs),
           "prompt_sha": CL.PROMPT_SHA256, "labels": labels, "ledger": recs,
           "clauses_meta": [{"key": f"{c['chunk_id']}:{c['clause_index']}", "text": c["text"], "start": c["start"], "is_grid": c["is_grid"],
                             "ctx_table_rule": c["ctx_table_rule"], "ctx_table": c["ctx_table"], "ctx_lead": c["ctx_lead"]} for c in clauses]}
    res_path.parent.mkdir(parents=True, exist_ok=True)
    res_path.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(arm, doc, f"{secs:.0f}s", "batches", len(batches), "unparsed", res["unparsed"], "failed", res["failed"], flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(ARMS))
    ap.add_argument("--docs", nargs="*", default=None)
    ap.add_argument("--out", default=str(Path.home() / "reqbot-work/scratch/table_hdr"))
    a = ap.parse_args()
    cfgf = json.load(open(Path.home() / ".config/reqbot/config.json"))
    for doc in (a.docs or DOCS):
        run_doc(doc, a.arm, Path(a.out), cfgf["ollama_url"], cfgf["extraction_model"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

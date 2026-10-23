#!/usr/bin/env python3
"""PREREG8 driver: label whole documents with one arm's settings and save labels, timing and parse status. Uses the production functions of
pipeline/clause_labeling.py; the only things an arm changes are listed in ARMS. Writes <out>/<arm>/<doc>.json (resumable per document). One model job at a time.

    python3 eval/clause_labeling/label_ctx_run.py --arm control --out ~/reqbot-work/scratch/label_ctx
"""
import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from pipeline import clause_labeling as CL  # noqa: E402
from pipeline.clauses import _as_list, chunk_clauses  # noqa: E402
from pipeline.lead_in import find_lead_in  # noqa: E402

DOCS = ["afi17-203", "afi13-550", "DODI 5200.01", "afi17-101", "afman17-204", "DODI 5200.48", "DODI 8551.01"]
ARMS = {  # arm -> settings
    "control": dict(rule=False, size=4, num_ctx=8192, num_predict=300),
    "control2": dict(rule=False, size=4, num_ctx=8192, num_predict=300),
    "rule": dict(rule=True, size=4, num_ctx=8192, num_predict=300),
    "b8": dict(rule=False, size=8, num_ctx=8192, num_predict=300),
    "b16": dict(rule=False, size=16, num_ctx=8192, num_predict=300),
    "c4096": dict(rule=False, size=4, num_ctx=4096, num_predict=300),
    "p100": dict(rule=False, size=4, num_ctx=8192, num_predict=100),
}


def chunk_path(doc: str, out: Path) -> Path:
    snap = out / "chunks" / f"{doc}_chunks.jsonl"
    if not snap.exists():
        src = sorted(glob.glob(os.path.expanduser(f"~/documents/processed/{doc}_20*/{doc}_chunks.jsonl")))[-1]
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_bytes(Path(src).read_bytes())
    return snap


def doc_clauses(chunks: list[dict], rule: bool) -> list[dict]:
    raw = {c["chunk_id"]: c.get("raw_text") or c.get("text") or "" for c in chunks}
    sec = {c["chunk_id"]: (tuple(_as_list(c.get("section_ref_path"))), tuple(_as_list(c.get("section_title_path")))) for c in chunks}
    out = []
    for c in chunks:
        cid = c["chunk_id"]
        prev = cid - 1
        pr = raw.get(prev, "") if prev in sec and sec[prev] == sec[cid] else ""
        for cl in chunk_clauses(c):
            cl["ctx_control"] = cl["ctx_lead"]
            cl["ctx_rule"] = find_lead_in(raw[cid], cl["start"], pr)
            if rule:
                cl["ctx_lead"] = cl["ctx_rule"]
            out.append(cl)
    return out


def run_doc(doc: str, arm: str, out: Path, ollama_url: str, model: str) -> None:
    res_path = out / arm / f"{doc}.json"
    if res_path.exists():
        return
    cfg = ARMS[arm]
    CL.NUM_CTX, CL.NUM_PREDICT = cfg["num_ctx"], cfg["num_predict"]
    chunks = [json.loads(ln) for ln in open(chunk_path(doc, out), encoding="utf-8") if ln.strip()]
    clauses = doc_clauses(chunks, cfg["rule"])
    template = CL.load_prompt()
    batches = CL.make_batches(clauses, size=cfg["size"])
    call = lambda p: CL.ollama_chat(p, model=model, ollama_url=ollama_url, timeout=600)  # noqa: E731
    call("Reply with the single word OK.")  # warm-up: model load is not timed
    labels, recs = {}, []
    t0 = time.time()
    for b in batches:
        rec = CL.label_batch(b, CL.build_prompt(template, b["clauses"]), model=model, call=call)
        recs.append({k: rec[k] for k in ("batch_id", "clause_keys", "status", "attempts", "prompt_sha", "labels")})
        if rec["labels"]:
            for k, lab in zip(rec["clause_keys"], rec["labels"]):
                labels[f"{k[0]}:{k[1]}"] = lab
    secs = time.time() - t0
    res = {"doc": doc, "arm": arm, "cfg": cfg, "model": model, "seconds": secs, "batches": len(batches), "clauses": len(clauses),
           "unparsed": sum(r["status"] == CL.STATUS_UNPARSED for r in recs), "failed": sum(r["status"] == CL.STATUS_FAILED for r in recs),
           "prompt_sha": CL.PROMPT_SHA256, "labels": labels, "ledger": recs,
           "clauses_meta": [{"key": f"{c['chunk_id']}:{c['clause_index']}", "text": c["text"], "start": c["start"], "ctx_control": c["ctx_control"], "ctx_rule": c["ctx_rule"]} for c in clauses]}
    res_path.parent.mkdir(parents=True, exist_ok=True)
    res_path.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(arm, doc, f"{secs:.0f}s", "batches", len(batches), "unparsed", res["unparsed"], "failed", res["failed"], flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(ARMS))
    ap.add_argument("--out", default=str(Path.home() / "reqbot-work/scratch/label_ctx"))
    a = ap.parse_args()
    cfgf = json.load(open(Path.home() / ".config/reqbot/config.json"))
    for doc in DOCS:
        run_doc(doc, a.arm, Path(a.out), cfgf["ollama_url"], cfgf["extraction_model"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

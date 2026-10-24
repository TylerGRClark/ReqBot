#!/usr/bin/env python3
"""PREREG10 driver (adapted from the PREREG8/9 driver): label whole documents in one arm and save labels, timing and parse status. Uses the production functions of
pipeline/clause_labeling.py. Arm `control` = the lead-in as main builds it without the section heading (find_lead_in with no heading_path); arm `heading` = the production
`document_clauses` (heading lead-in on). Everything else is identical. Writes <out>/<arm>/<doc>.json (resumable per document). One model job at a time.

    python3 eval/clause_labeling/heading_run.py --arm control --out ~/reqbot-work/scratch/heading_lead/run
    python3 eval/clause_labeling/heading_run.py --count-only   # no model: how many clauses get a different lead-in
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

DOCS = ["afi17-203", "afi13-550", "DODI 5200.01", "afi17-101", "afman17-204", "DODI 5200.48", "DODI 8551.01", "dafman17-1301", "dafman17-1203", "NIST.SP.800-125", "CNSSI_No1253"]
SECONDARY = ["DODI 8410.03", "CJCSI 6510.02G", "DODI 5200.44"]
SNAPSHOTS = [Path.home() / "reqbot-work/scratch/label_ctx/chunks", Path.home() / "reqbot-work/scratch/label_ctx9/chunks"]  # the chunk files the PREREG8/9 arms read
ARMS = {  # arm -> settings
    "control": dict(heading=False, size=4, num_ctx=8192, num_predict=300),
    "heading": dict(heading=True, size=4, num_ctx=8192, num_predict=300),
}


def chunk_path(doc: str, out: Path) -> Path:
    snap = out / "chunks" / f"{doc}_chunks.jsonl"
    if not snap.exists():
        old = [d / f"{doc}_chunks.jsonl" for d in SNAPSHOTS if (d / f"{doc}_chunks.jsonl").exists()]
        src = str(old[0]) if old else sorted(glob.glob(os.path.expanduser(f"~/documents/processed/{doc}_20*/{doc}_chunks.jsonl")))[-1]
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_bytes(Path(src).read_bytes())
    return snap


def doc_clauses(chunks: list[dict], heading: bool) -> list[dict]:
    """The production clause list (CL.document_clauses). Control: ctx_lead = the finder without the heading; heading: ctx_lead as production builds it."""
    raw = {c["chunk_id"]: c.get("raw_text") or c.get("text") or "" for c in chunks}
    sec = {c["chunk_id"]: (tuple(_as_list(c.get("section_ref_path"))), tuple(_as_list(c.get("section_title_path")))) for c in chunks}
    paths = {c["chunk_id"]: _as_list(c.get("section_title_path")) for c in chunks}
    out = CL.document_clauses(chunks)
    for cl in out:
        cid = cl["chunk_id"]
        pr = raw.get(cid - 1, "") if (cid - 1) in sec and sec[cid - 1] == sec[cid] else ""
        cl["ctx_heading"] = cl["ctx_lead"]  # production value
        cl["ctx_control"] = find_lead_in(raw[cid], cl["start"], pr)  # main's value: no heading_path
        if not heading:
            cl["ctx_lead"] = cl["ctx_control"]
    return out


def run_doc(doc: str, arm: str, out: Path, ollama_url: str, model: str) -> None:
    res_path = out / arm / f"{doc}.json"
    if res_path.exists():
        return
    cfg = ARMS[arm]
    CL.NUM_CTX, CL.NUM_PREDICT = cfg["num_ctx"], cfg["num_predict"]
    chunks = [json.loads(ln) for ln in open(chunk_path(doc, out), encoding="utf-8") if ln.strip()]
    clauses = doc_clauses(chunks, cfg["heading"])
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
           "clauses_meta": [{"key": f"{c['chunk_id']}:{c['clause_index']}", "text": c["text"], "start": c["start"], "ctx_control": c["ctx_control"], "ctx_heading": c["ctx_heading"]} for c in clauses]}
    res_path.parent.mkdir(parents=True, exist_ok=True)
    res_path.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(arm, doc, f"{secs:.0f}s", "batches", len(batches), "unparsed", res["unparsed"], "failed", res["failed"], flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(ARMS))
    ap.add_argument("--count-only", action="store_true")
    ap.add_argument("--secondary", action="store_true", help="the three report-only heading-rich documents instead of the eleven")
    ap.add_argument("--docs", nargs="*", default=None)
    ap.add_argument("--out", default=str(Path.home() / "reqbot-work/scratch/heading_lead/run"))
    a = ap.parse_args()
    docs = a.docs or (SECONDARY if a.secondary else DOCS)
    if a.count_only:
        tot = chg = 0
        for doc in docs:
            chunks = [json.loads(ln) for ln in open(chunk_path(doc, Path(a.out)), encoding="utf-8") if ln.strip()]
            cls = doc_clauses(chunks, True)
            n = sum((c["ctx_control"] or "").strip() != (c["ctx_heading"] or "").strip() for c in cls)
            print(f"{doc}: {len(cls)} clauses, {n} get a different lead-in")
            tot, chg = tot + len(cls), chg + n
        print("total", tot, "changed", chg)
        return 0
    if not a.arm:
        ap.error("--arm is required unless --count-only")
    cfgf = json.load(open(Path.home() / ".config/reqbot/config.json"))
    for doc in docs:
        run_doc(doc, a.arm, Path(a.out), cfgf["ollama_url"], cfgf["extraction_model"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

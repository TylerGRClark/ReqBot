#!/usr/bin/env python3
"""Anchoring report (docs/PIPELINE_REDESIGN_PLAN.md, step 4): run Step D (normalizing and checking) on copies of the newest processed runs of the 13 reference documents and report
how the roots anchor, and check that anchoring changed nothing else. Offline (no model); writes only under a scratch directory and outputs/.

  PYTHONPATH=. python3 eval/spike_results/pipeline_redesign/anchor_report.py
"""
import collections
import glob
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from pipeline import parse_and_normalize as PN  # noqa: E402

DOCS = ["CJCSI 6510.02G", "DODI 5200.01", "DODI 5200.44", "DODI 5200.48", "DODI 8410.03", "DODI 8551.01", "NIST.SP.800-125", "afi10-2402", "afi13-550", "afi17-203", "afman17-2101", "afpd_17-1", "dafman17-1305"]
PROCESSED = Path.home() / "documents" / "processed"


def read(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    out = {"documents": {}, "total": collections.Counter()}
    for doc in DOCS:
        run_dir = sorted(glob.glob(str(PROCESSED / f"{doc}_2026*")))[-1]
        with tempfile.TemporaryDirectory() as tmp:
            for suffix in ("_chunks.jsonl", "_extracted_requirements.jsonl"):
                shutil.copy2(Path(run_dir) / f"{doc}{suffix}", tmp)
            pdf = ROOT / "raw_pdfs" / f"{doc}.pdf"
            norm = PN.run(str(Path(tmp) / f"{doc}_extracted_requirements.jsonl"), str(Path(tmp) / f"{doc}_chunks.jsonl"), str(pdf), tmp)
            new = read(norm)
        old = read(Path(run_dir) / f"{doc}_requirements_normalized.jsonl")
        strip = lambda rs: [{k: v for k, v in r.items() if not k.startswith("anchor_") and k != "run_timestamp"} for r in rs]  # noqa: E731
        # the old file also carries parent_stem/embedding_text from the same reconstruction; compare everything except the new anchor fields and the timestamp
        same = strip(new) == strip(old)
        c = collections.Counter(r.get("anchor_status", "none") for r in new)
        out["documents"][doc] = {"records": len(new), "same_accepted_records_otherwise": same, "status": dict(c)}
        out["total"].update(c)
    out["total"] = dict(out["total"])
    path = Path(__file__).resolve().parent / "outputs" / "anchor_report.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    n = sum(out["total"].values())
    print(json.dumps({"records": n, "status": out["total"], "all_documents_otherwise_identical": all(d["same_accepted_records_otherwise"] for d in out["documents"].values())}, indent=1))
    for doc, d in out["documents"].items():
        print(f"{doc:18s} {d['records']:4d} identical={d['same_accepted_records_otherwise']} {d['status']}")


if __name__ == "__main__":
    main()

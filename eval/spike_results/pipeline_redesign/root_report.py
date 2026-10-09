#!/usr/bin/env python3
"""Root and explained-layer report (docs/PIPELINE_REDESIGN_PLAN.md, step 4, second PR): re-run Step D on copies of the newest runs of the 13 reference documents and check the plan's rules.

  (a) the root invariant: every record's source_quote is a quote requirement finding returned (trimmed);
  (b) coverage of the labeled obligations in the three sample documents, counted three ways: the existing run (October 9 morning: the sentence rule had replaced source_quote), the new
      records by their root, and the new records by their explained text. Not lower than the existing run by more than the WP-45.11 paired-loss limit of 4;
  (c) records kept, merged, and explained statuses.
Offline (no model); writes only outputs/root_report.json.

  PYTHONPATH=. python3 eval/spike_results/pipeline_redesign/root_report.py
"""
import collections
import glob
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "eval/spike_results/wp_45_1e", ROOT / "eval/spike_results/wp_45_11"):
    sys.path.insert(0, str(p))

import score as S  # noqa: E402
import score_arms as SA  # noqa: E402

from pipeline import parse_and_normalize as PN  # noqa: E402

DOCS = ["CJCSI 6510.02G", "DODI 5200.01", "DODI 5200.44", "DODI 5200.48", "DODI 8410.03", "DODI 8551.01", "NIST.SP.800-125", "afi10-2402", "afi13-550", "afi17-203", "afman17-2101", "afpd_17-1", "dafman17-1305"]
PROCESSED = Path.home() / "documents" / "processed"
PAIRED_LOSS_LIMIT = 4


def read(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(path).exists() else []


def main():
    index, ids = SA.obligations()
    cov = lambda runs: sum(1 for t in S.trace_all(ids, index, runs, None).values() if t["status"].get("survived_step_d") == "covered")  # noqa: E731
    report = {"documents": {}, "coverage": {}}
    existing, by_root, by_explained = {}, {}, {}
    with tempfile.TemporaryDirectory() as tmp_all:
        for doc in DOCS:
            run_dir = Path(sorted(glob.glob(str(PROCESSED / f"{doc}_2026*")))[-1])
            tmp = Path(tmp_all) / doc
            tmp.mkdir()
            for suffix in ("_chunks.jsonl", "_extracted_requirements.jsonl", "_normalization_failures.jsonl", "_parse_failures.jsonl", "_description_gate_failures.jsonl"):
                if (run_dir / f"{doc}{suffix}").exists():
                    shutil.copy2(run_dir / f"{doc}{suffix}", tmp)
            new = read(PN.run(str(tmp / f"{doc}_extracted_requirements.jsonl"), str(tmp / f"{doc}_chunks.jsonl"), str(ROOT / "raw_pdfs" / f"{doc}.pdf"), str(tmp)))
            returned = {(r.get("source_quote") or "").strip() for r in read(tmp / f"{doc}_extracted_requirements.jsonl")}
            invariant = all(r["source_quote"] in returned for r in new)
            notes = collections.Counter(n for r in new for n in r.get("explain_notes", []))
            report["documents"][doc] = {"records": len(new), "existing_records": len(read(run_dir / f"{doc}_requirements_normalized.jsonl")), "root_invariant_holds": invariant,
                                        "merged_into_another": sum(len(r.get("merged_roots", [])) for r in new), "explain_notes": dict(notes),
                                        "repeated_ids": len(new) - len({r["requirement_id"] for r in new})}
            if doc in SA.SAMPLE_DOCS:
                base = S.load_run(tmp, doc)
                existing[doc] = S.load_run(run_dir, doc)
                by_root[doc] = {**base, "normalized": new}
                by_explained[doc] = {**base, "normalized": [{**r, "source_quote": r.get("explained_text") or r["source_quote"]} for r in new]}
    report["coverage"] = {"obligations": len(ids), "existing_run": cov(existing), "new_by_root": cov(by_root), "new_by_explained_text": cov(by_explained), "paired_loss_limit": PAIRED_LOSS_LIMIT}
    report["rules"] = {"a_root_invariant_all_documents": all(d["root_invariant_holds"] for d in report["documents"].values()),
                       "b_coverage_by_explained_text_not_lower_by_more_than_limit": report["coverage"]["new_by_explained_text"] >= report["coverage"]["existing_run"] - PAIRED_LOSS_LIMIT,
                       "ids_unique": all(d["repeated_ids"] == 0 for d in report["documents"].values())}
    path = Path(__file__).resolve().parent / "outputs" / "root_report.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"coverage": report["coverage"], "rules": report["rules"]}, indent=1))
    for doc, d in report["documents"].items():
        print(f"{doc:18s} records {d['records']:4d} (existing {d['existing_records']:4d}) merged {d['merged_into_another']:3d} invariant={d['root_invariant_holds']} repeated_ids={d['repeated_ids']}")


if __name__ == "__main__":
    main()

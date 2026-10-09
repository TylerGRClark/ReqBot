#!/usr/bin/env python3
"""WP-45.14: measure the whole-sentence rule on the Step D survivors of T2a, T2b (current prompt) and D1x (inclusive prompt) by the rules of docs/PHASE45_WP4514_PLAN.md (offline; nothing is written
to the pipeline, the scratch arms or Qdrant).

  PYTHONPATH=. python3 eval/spike_results/wp_45_14/evaluate.py
"""
import collections
import json
import random
import statistics
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_11", _ROOT / "eval/spike_results/wp_45_1e", _ROOT / "eval/spike_results/wp_45_audit"):
    sys.path.insert(0, str(_p))

import score as S  # noqa: E402  (wp_45_1e: loading a run and tracing the labeled obligations)
import score_arms as SA  # noqa: E402

from pipeline import sentence_expand as SE  # noqa: E402
from services.checklist_service import generate  # noqa: E402

ARMS = ("T2a", "T2b", "D1x")
SCRATCH = Path.home() / "wp45_11_scratch"
SEED, SAMPLE = 4514, 30
SAMPLE_ARMS = ("T2a", "D1x")


def read(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(path).exists() else []


def norm(text):
    return SE.tidy(text).lower()


def expand_arm(arm):
    """{doc: (original records, expanded and merged records, per-record details)} for one arm."""
    out = {}
    for doc in sorted(SA.common.pinned_documents()):
        d = SCRATCH / arm / doc
        raw = {c["chunk_id"]: c.get("raw_text") or "" for c in read(d / f"{doc}_chunks.jsonl")}
        originals = read(d / f"{doc}_requirements_normalized.jsonl")
        merged, seen, details = [], {}, []
        for rec in originals:
            text, status = SE.expand(rec.get("source_quote") or "", raw.get(rec.get("chunk_id"), ""))
            details.append({"requirement_id": rec.get("requirement_id"), "chunk_id": rec.get("chunk_id"), "original": rec.get("source_quote") or "", "expanded": text, "status": status})
            key = (rec.get("chunk_id"), norm(text))
            if key in seen:
                continue
            new = dict(rec)
            new["source_quote"] = text
            seen[key] = len(merged)
            merged.append(new)
        out[doc] = (originals, merged, details)
    return out


def recall(arm, expanded):
    index, ids = SA.obligations()
    runs, before_runs = {}, {}
    for doc in SA.SAMPLE_DOCS:
        run = S.load_run(SCRATCH / arm / doc, doc)
        before_runs[doc] = run
        runs[doc] = {**run, "normalized": expanded[doc][1]}
    cov = lambda r: sum(1 for t in S.trace_all(ids, index, r, None).values() if t["status"].get("survived_step_d") == "covered")  # noqa: E731
    return {"before": cov(before_runs), "after": cov(runs), "obligations": len(ids)}


def checklist_view(arm, expanded):
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for doc in ("afi17-203", "afi13-550", "afi10-2402"):
            run = Path(tmp) / f"{doc}_20260101_000000"
            run.mkdir()
            (run / f"{doc}_chunks.jsonl").write_text((SCRATCH / arm / doc / f"{doc}_chunks.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            for label, records in (("before", expanded[doc][0]), ("after", expanded[doc][1])):
                (run / f"{doc}_requirements_normalized.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
                r = generate(Path(tmp), doc, "cybersecurity")
                out.setdefault(doc, {})[label] = {"rows": len(r["items"]), "flags": dict(collections.Counter(f for i in r["items"] for f in i["item_flags"] if f in
                                                  ("starts_mid_sentence", "table_fragment", "quote_not_located_in_passage", "no_stated_actor", "list_item")))}
    return out


def main():
    expanded = {arm: expand_arm(arm) for arm in ARMS}
    report = {"arms": {}}
    changed_pool = []
    for arm in ARMS:
        details = [x for doc in expanded[arm].values() for x in doc[2]]
        before = sum(len(doc[0]) for doc in expanded[arm].values())
        after = sum(len(doc[1]) for doc in expanded[arm].values())
        status = collections.Counter(x["status"] for x in details)
        usable = [x for x in details if x["status"] in ("expanded", "unchanged", "too_short")]  # a one-word quote is left as given and still counts
        inc_before = sum(1 for x in usable if not SE.is_complete(x["original"]))
        inc_after = sum(1 for x in usable if not SE.is_complete(x["expanded"]))
        lengths = [len(x["expanded"]) for x in usable]
        report["arms"][arm] = {
            "survivors_before": before, "survivors_after_merge": after, "status": dict(status),
            "incomplete_before": inc_before, "incomplete_after": inc_after, "could_be_expanded": len(usable),
            "incomplete_share_after": round(inc_after / len(usable), 4) if usable else None,
            "quote_chars_median_before": statistics.median(len(x["original"]) for x in details), "quote_chars_median_after": statistics.median(lengths) if lengths else None,
            "per_document": {d: {"before": len(v[0]), "after": len(v[1])} for d, v in expanded[arm].items()},
            "recall_of_74_by_survivors": recall(arm, expanded[arm]),
        }
        if arm in SAMPLE_ARMS:
            changed_pool += [(arm, d, x) for d, v in expanded[arm].items() for x in v[2] if x["status"] == "expanded"]
    report["checklist_view"] = {arm: checklist_view(arm, expanded[arm]) for arm in SAMPLE_ARMS}
    picked = sorted(random.Random(SEED).sample(sorted(changed_pool, key=lambda t: (t[0], t[1], str(t[2]["requirement_id"]))), min(SAMPLE, len(changed_pool))), key=lambda t: (t[1], str(t[2]["requirement_id"])))
    lines = [f"# WP-45.14 — {len(picked)} quotes that the whole-sentence rule changed (seeded sample of {len(changed_pool)} from T2a and D1x)", "",
             "Rate the expanded text against the original: **better** / **same** / **worse**.", ""]
    for n, (arm, doc, x) in enumerate(picked, 1):
        lines += [f"## {n}. {doc} ({arm})", "", f"**Original:** {x['original']}", "", f"**Expanded:** {x['expanded']}", "", "**Rating:** ", "", "---", ""]
    out = _HERE / "outputs"
    out.mkdir(exist_ok=True)
    (out / "sentence_rule_sample_after_fixes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["sample_size"] = len(picked)
    (out / "sentence_rule_report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for arm, v in report["arms"].items():
        print(arm, {k: v[k] for k in ("survivors_before", "survivors_after_merge", "status", "incomplete_before", "incomplete_after", "could_be_expanded", "incomplete_share_after",
                                      "quote_chars_median_before", "quote_chars_median_after", "recall_of_74_by_survivors")})
    print(json.dumps(report["checklist_view"], indent=1))


if __name__ == "__main__":
    main()

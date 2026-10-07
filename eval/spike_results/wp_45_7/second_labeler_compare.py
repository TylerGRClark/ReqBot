#!/usr/bin/env python3
"""WP-45.7e after the verdict: a second labeler's agreement with the first, and a sensitivity rescore of the saved answers (offline; no LLM).

The second labeler is a blind Claude subagent given only the pack and rubric (`fresh_labels_second/`). This reads both label sets, reports agreement
(pass A: complete / needs a lead-in / not a requirement, the location, the lead-in text; pass B: the verdict on the production stem), builds a gold
from the second labeler's labels with the same builder and rubric checker as the frozen gold (`fresh_gold.build`), and scores the **saved** one-shot
answers (`outputs/eval_v6_run`, never re-run) against both golds with the registered gates. It is a sensitivity analysis, not a verdict: the verdict
was registered against the first labels and is unchanged.

  python3 eval/spike_results/wp_45_7/second_labeler_compare.py            # prints the report
  python3 eval/spike_results/wp_45_7/second_labeler_compare.py --write    # also writes outputs/second_labeler_report.json
"""

import argparse
import collections
import json
import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parents[2]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import fresh_gold as FG  # noqa: E402
import score_resolver as SR  # noqa: E402

FIRST = FG.LABELS
SECOND = _HERE / "fresh_labels_second"
RUN = _HERE / "outputs" / "eval_v6_run"
FROZEN = FG.FROZEN
REPORT = _HERE / "outputs" / "second_labeler_report.json"


def _by_id(path):
    return FG._jsonl(path)  # {card id: label}


def agreement(first=FIRST, second=SECOND):
    a1, a2 = _by_id(first / "labels_claude_a.jsonl"), _by_id(second / "labels_claude2_a.jsonl")
    b1, b2 = _by_id(first / "labels_claude_b.jsonl"), _by_id(second / "labels_claude2_b.jsonl")
    ids = sorted(a1)
    both = [i for i in ids if a1[i]["standalone"] == a2[i]["standalone"] == "needs_lead_in"]
    pairs = lambda x, y, ks, f: {" -> ".join(map(str, k)): v for k, v in sorted(collections.Counter((x[i][f], y[i][f]) for i in ks).items(), key=str)}  # noqa: E731
    return {
        "pass_a_cards": len(ids),
        "standalone_agree": sum(a1[i]["standalone"] == a2[i]["standalone"] for i in ids),
        "standalone_pairs": pairs(a1, a2, ids, "standalone"),
        "both_need_lead_in": len(both),
        "location_agree": sum(a1[i]["lead_in_location"] == a2[i]["lead_in_location"] for i in both),
        "location_pairs": pairs(a1, a2, both, "lead_in_location"),
        "lead_in_text_identical": sum((a1[i]["lead_in_text"] or "") == (a2[i]["lead_in_text"] or "") for i in both),
        "pass_b_cards": len(b1),
        "stem_verdict_agree": sum(b1[i]["stem_verdict"] == b2[i]["stem_verdict"] for i in b1),
        "stem_verdict_pairs": pairs(b1, b2, sorted(b1), "stem_verdict"),
    }


def second_gold(second=SECOND):
    """The gold the second labeler's labels give, built exactly as the frozen one (the builder expects the first labeler's file names)."""
    with tempfile.TemporaryDirectory() as tmp:
        for part in ("a", "b"):
            shutil.copy(second / f"labels_claude2_{part}.jsonl", Path(tmp) / f"labels_claude_{part}.jsonl")
        return FG.build(labels=Path(tmp))


def rescore(gold, run=RUN):
    half = SR.score_run(str(run), gold)["evaluation"]
    gates, _ = SR.selection_gates(half, None, SR.V4_RELATIVE)
    return {"attachment": dict(half["audit"]["attachment"]), "baseline_attachment": dict(half["audit"]["baseline_attachment"]),
            "gates": {k: {"value": v[0], "threshold": v[1], "passed": bool(v[2])} for k, v in gates.items()}}


def per_candidate(first_gold, other_gold, run=RUN):
    """How each candidate's resolver attachment class moves between the two golds (unscored = attachment not scored under that gold)."""
    records = SR.load_ledger(str(run))
    one, two = {g["candidate_id"]: g for g in first_gold["gold"]}, {g["candidate_id"]: g for g in other_gold["gold"]}

    def cls(g, cid):
        if not SR.attachment_scored(g):
            return "unscored"
        answer = (records.get(cid) or {}).get("answer")
        return SR.attachment(answer, g) if answer else "failed"

    moves = collections.Counter((cls(one[c], c), cls(two[c], c)) for c in one)
    return {" -> ".join(k): v for k, v in sorted(moves.items())}


def report():
    first = json.loads(FROZEN.read_text(encoding="utf-8"))
    second = second_gold()
    return {
        "note": "sensitivity analysis on the saved one-shot answers; not a verdict (the verdict was registered against the first labels)",
        "agreement": agreement(),
        "gold_counts": {"first": first["counts"], "second": second["counts"]},
        "rescored": {"first_labels": rescore(first), "second_labels": rescore(second)},
        "resolver_attachment_moves_first_to_second": per_candidate(first, second),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help=f"also write {REPORT.name}")
    args = ap.parse_args()
    text = json.dumps(report(), indent=1, sort_keys=True)
    print(text)
    if args.write:
        REPORT.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

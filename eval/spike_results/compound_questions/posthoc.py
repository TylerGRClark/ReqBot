"""Exploratory, NOT pre-registered: three extra looks at the frozen TEST results (and the TUNE ones), written after the test run so nothing here can change a result.

  python3 posthoc.py            # prints counts, writes outputs/posthoc_<set>.json

1. added hedge: a lead / part says "as appropriate", "as required", "when applicable" ... that is in neither today's question nor the source quote (an invented qualifier
   makes a duty sound optional). The v2 prompt's own worked example used "as appropriate", which the model may have copied.
2. broken lead: the lead ends in a dangling preposition or "to" ("... in accordance with?", "... to ensure?").
3. no gain: the longest piece is more than 80% of today's question.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checks  # noqa: E402

HEDGE = re.compile(r"\b(?:as appropriate|as required|when applicable|if applicable|as applicable|as necessary|as needed|when appropriate|where appropriate|when required)\b", re.IGNORECASE)
DANGLING = re.compile(r"\b(?:to|of|in|with|for|by|on|at|from|under|than|according to|accordance with|ensure|the|a|an|and|or|are|is)\s*\?\s*$", re.IGNORECASE)


def looks(rows: list[dict]) -> dict:
    out = {"passing_splits": 0, "added_hedge": [], "broken_lead": [], "no_gain": []}
    for r in rows:
        if r["final"] != "split":
            continue
        out["passing_splits"] += 1
        base = (r["today"] or "") + " " + (r["source_quote"] or "")
        have = {m.group(0).lower() for m in HEDGE.finditer(base)}
        new = {m.group(0).lower() for p in [r["lead"]] + r["parts"] for m in HEDGE.finditer(p)} - have
        if new:
            out["added_hedge"].append({"id": r["id"], "citation": r["citation"], "added": sorted(new)})
        if DANGLING.search(r["lead"] or "") and "all of the following" not in (r["lead"] or "").lower():
            out["broken_lead"].append({"id": r["id"], "citation": r["citation"], "lead": r["lead"]})
        if checks.check_gain(r["today"], r["lead"], r["parts"]):
            out["no_gain"].append(r["id"])
    return out


def main() -> None:
    for which in ("tune", "test"):
        f = HERE / "outputs" / f"results_v2_{which}.json"
        rows = json.loads(f.read_text())["rows"]
        res = looks(rows)
        (HERE / "outputs" / f"posthoc_{which}.json").write_text(json.dumps(res, indent=1))
        clean = res["passing_splits"] - len({x["id"] for x in res["added_hedge"]} | {x["id"] for x in res["broken_lead"]} | set(res["no_gain"]))
        print(which, "passing splits", res["passing_splits"], "| added hedge", len(res["added_hedge"]), "| broken lead", len(res["broken_lead"]), "| no gain", len(res["no_gain"]),
              "| none of the three", clean)


if __name__ == "__main__":
    main()

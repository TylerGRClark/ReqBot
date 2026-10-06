#!/usr/bin/env python3
"""WP-45.7: score resolver runs against the development gold (offline; no LLM). See `resolver_gold.py` for the gold and its halves.

Per run (a tier and a model), over the candidates of one half:

- **Valid answers.** Only `complete` calls count toward quality; an overrun, truncation, failure or untreatable candidate is a failed
  resolution, counted by status (plan 4.3 and 4.5).
- **Status.** A real requirement should get a requirement status (obligation, recommendation, permission, prohibition); a non-requirement
  should get `not_a_requirement` or `scope_or_context`. `unresolved` counts as neither, and is reported on its own.
- **Attachment** (audit records only, gold complete or needs a lead-in). Gold needs a lead-in: the answer is *right* when its parent or its actor
  overlaps Tyler's adjudicated lead-in text, *incomplete* when it names neither, *misleading* when it names a parent or actor that does not
  overlap. Gold complete: right when no parent is given, misleading when one is. The paired baseline is today's production stem on the same
  records, scored from Tyler's own verdict on that stem (right; any wrong kind, or one that was not needed, is misleading) and, where
  production attached nothing, by the gold (needs a lead-in is incomplete; complete is right).
- **Fidelity.** Answers with a modality error code, answers with an added token or an actor or parent outside the cited spans (the
  invented-party-or-number rate), shape conformance, tokens and time.

Choosing the configuration (fixed here, before any run is scored): from the **selection halves only**, take the configurations whose
selection-half numbers satisfy every gate that applies to them (G2 in the plan, the thresholds in `GATES`); among those, the highest
attachment-right rate on the audit selection half; ties go to the lower tier and then the smaller model. If none passes, the one with the
highest right rate is chosen and reported as failing G2. The evaluation halves are never read to choose.
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bundle as B  # noqa: E402
import check_resolution as C  # noqa: E402
import ollama_run as OR  # noqa: E402
import resolver as R  # noqa: E402

GOLD = _HERE / "outputs" / "resolver_gold.json"
OVERLAP = 0.5  # of the shorter text's content words
GATES = {
    "max_real_rejected": 0.05,        # at most 5% of real requirements returned not_a_requirement
    "max_real_scope_or_unresolved": 0.10,  # and at most 10% returned scope_or_context or unresolved, together
    "min_non_requirement_rejected": 0.60,  # at least 60% of non-requirements returned not_a_requirement or scope_or_context
    "max_invented": 0.02,             # invented party or number rate
    "max_incomplete_over_baseline": 0.05,  # incomplete at most the baseline's plus 5 points
}
BASELINE_MISLEADING = ("wrong_sibling", "fragment_chain", "wrong_other", "not_needed")
INVENTED_CODES = ("added_token", "not_in_cited_span")


_WORD = re.compile(r"[a-z0-9]+")
_FUNCTION = set(C._STOP) | {"shall", "must", "will", "should", "may", "following", "responsibilities", "responsible"}


def _content(text):
    """Content words only: lowercase alphanumeric tokens without function words and modals, so "The ... shall:" never matches."""
    return {w for w in _WORD.findall(B.normalize(text or "").lower()) if w not in _FUNCTION}


def overlaps(value, text):
    """True if at least half of the shorter text's content words are in the other, and at least one is."""
    a, b = _content(value), _content(text)
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= OVERLAP


def attachment(answer, gold):
    """right, misleading or incomplete for an audit record (None when attachment is not scored for it)."""
    if gold["standalone"] == "not_a_requirement":
        return None
    parent = (answer["parent"]["value"] or "").strip()
    actor = (answer["actor"]["value"] or "").strip()
    if gold["standalone"] == "complete":
        return "misleading" if parent else "right"
    if overlaps(parent, gold["lead_in_text"]) or overlaps(actor, gold["lead_in_text"]):
        return "right"
    return "misleading" if (parent or actor) else "incomplete"


def baseline_attachment(gold):
    if gold["standalone"] == "not_a_requirement":
        return None
    if gold["production_stem"]:
        return "right" if gold["stem_verdict"] == "right" else "misleading"
    return "incomplete" if gold["standalone"] == "needs_lead_in" else "right"


def is_real(gold):
    return gold["standalone"] in ("complete", "needs_lead_in") if gold["set"] == "audit" else bool(gold["real_requirement"])


def score_half(records, golds):
    """Score one run's ledger records against the gold of one half. `records` is {candidate_id: ledger record}."""
    out = {"candidates": len(golds), "status": collections.Counter(), "real": collections.Counter(), "non_requirement": collections.Counter(),
           "attachment": collections.Counter(), "baseline_attachment": collections.Counter(), "modality_error_answers": 0,
           "invented_answers": 0, "shape_conformant": 0, "valid": 0, "answers_with_no_error": 0}
    for g in golds:
        rec = records.get(g["candidate_id"])
        out["status"][rec["status"] if rec else "not_run"] += 1
        base = baseline_attachment(g) if g["set"] == "audit" else None
        if base:
            out["baseline_attachment"][base] += 1
        if not rec or rec["status"] != "complete" or rec.get("answer") is None:
            if is_real(g):
                out["real"]["failed"] += 1
            else:
                out["non_requirement"]["failed"] += 1
            if base:
                out["attachment"]["failed"] += 1
            continue
        out["valid"] += 1
        ans, issues = rec["answer"], rec["issues"]
        if not any(i["code"] == "shape" for i in issues):
            out["shape_conformant"] += 1
        if not any(i["severity"] == "error" for i in issues):
            out["answers_with_no_error"] += 1
        if any(i["severity"] == "error" and i["code"] in C.MODALITY_ERROR_CODES for i in issues):
            out["modality_error_answers"] += 1
        if any(i["severity"] == "error" and i["code"] in INVENTED_CODES for i in issues):
            out["invented_answers"] += 1
        status = ans["status"]["value"]
        bucket = "requirement" if status in R.REQUIREMENT_STATUS else status
        (out["real"] if is_real(g) else out["non_requirement"])[bucket] += 1
        if g["set"] == "audit":
            a = attachment(ans, g)
            if a:
                out["attachment"][a] += 1
    return {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in out.items()}


def rate(counter, key, total=None):
    total = sum(counter.values()) if total is None else total
    return round(counter.get(key, 0) / total, 3) if total else None


def gate_report(s, base_counts):
    """The selection-half gate checks that apply, as {name: (value, threshold, passed)}."""
    out = {}
    real, non = s["real"], s["non_requirement"]
    nr, nn = sum(real.values()), sum(non.values())
    if nr:
        rejected = rate(real, "not_a_requirement", nr)
        soft = round((real.get("scope_or_context", 0) + real.get("unresolved", 0)) / nr, 3)
        out["real_rejected"] = (rejected, GATES["max_real_rejected"], rejected <= GATES["max_real_rejected"])
        out["real_scope_or_unresolved"] = (soft, GATES["max_real_scope_or_unresolved"], soft <= GATES["max_real_scope_or_unresolved"])
    if nn:
        good = round((non.get("not_a_requirement", 0) + non.get("scope_or_context", 0)) / nn, 3)
        out["non_requirement_rejected"] = (good, GATES["min_non_requirement_rejected"], good >= GATES["min_non_requirement_rejected"])
    if s["valid"]:
        inv = round(s["invented_answers"] / s["valid"], 3)
        out["invented"] = (inv, GATES["max_invented"], inv <= GATES["max_invented"])
        mod = s["modality_error_answers"]
        out["modality_errors"] = (mod, 0, mod == 0)
    att, nb = s["attachment"], sum(base_counts.values())
    if sum(att.values()) and nb:
        inc, binc = rate(att, "incomplete"), rate(base_counts, "incomplete", nb)
        out["incomplete"] = (inc, round(binc + GATES["max_incomplete_over_baseline"], 3), inc <= binc + GATES["max_incomplete_over_baseline"])
    return out


def load_ledger(directory):
    ledger = OR.Ledger(Path(directory).expanduser() / "resolver.jsonl")
    return {r["candidate_id"]: r for r in ledger.records.values()}


def score_run(directory, gold):
    records = load_ledger(directory)
    result = {}
    for which in ("selection", "evaluation"):
        golds = [g for g in gold["gold"] if g["half"] == which]
        if not any(g["candidate_id"] in records for g in golds):
            continue
        result[which] = {}
        for name, subset in (("audit", [g for g in golds if g["set"] == "audit"]), ("cards", [g for g in golds if g["set"] == "cards"]),
                             ("all", golds)):
            if subset and any(g["candidate_id"] in records for g in subset):
                result[which][name] = score_half(records, subset)
    return result


def choose(configs):
    """The configuration to freeze, from {name: {"tier", "model_size", "selection": score_run()["selection"]}} (selection halves only)."""
    best = None
    for name, c in configs.items():
        sel = c["selection"]
        audit = sel.get("audit")
        if not audit:
            continue
        base = audit["baseline_attachment"]
        gates = {**gate_report(sel["all"], base)}
        passed = all(v[2] for v in gates.values())
        right = rate(audit["attachment"], "right", sum(audit["attachment"].values()))
        key = (passed, right or 0, -["R0", "R1", "R2"].index(c["tier"]), -c["model_size"])
        if best is None or key > best[0]:
            best = (key, name, passed, right, gates)
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", nargs="+", required=True, metavar="NAME=DIR")
    ap.add_argument("--out")
    args = ap.parse_args()
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    results = {}
    for spec in args.runs:
        name, _, directory = spec.partition("=")
        results[name] = score_run(directory, gold)
    text = json.dumps(results, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

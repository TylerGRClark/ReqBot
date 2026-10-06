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
from fractions import Fraction
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
OVERLAP = 0.8  # of the answer value's distinctive words that must be in the gold lead-in
GATES = {
    "max_real_rejected": 0.05,        # at most 5% of real requirements returned not_a_requirement
    "max_real_scope_or_unresolved": 0.10,  # and at most 10% returned scope_or_context or unresolved, together
    "min_non_requirement_rejected": 0.60,  # at least 60% of non-requirements returned not_a_requirement or scope_or_context
    "max_invented": 0.02,             # invented party or number rate
    "max_incomplete_over_baseline": 0.05,  # incomplete (failures included) at most the baseline's plus 5 points
    "min_valid_share": 0.95,          # at least 95% of the candidates resolved by a complete, well-shaped answer
}
BASELINE_MISLEADING = ("wrong_sibling", "fragment_chain", "wrong_other", "not_needed")
INVENTED_CODES = ("added_token",)  # a number, acronym or name the cited spans lack, in a generated sentence
INVENTED_FIELDS = ("actor", "parent")  # plus a party (actor or parent) that no cited span contains


_WORD = re.compile(r"[a-z0-9]+")
_FUNCTION = set(C._STOP) | {"shall", "must", "will", "should", "may", "following", "responsibilities", "responsible"}
# Role words every office has: "Director" alone does not identify which one, so it carries no weight in a match.
_GENERIC = {"director", "directors", "chief", "officer", "officers", "secretary", "commander", "commanders", "head", "heads",
            "component", "components", "department", "office", "agency", "program", "manager", "managers", "staff", "chairman"}


def _distinctive(text):
    """Identifying words: lowercase alphanumerics of two or more characters, without function words, modals and generic role
    words, so "The ... shall:" and a bare "Director" never match, and one-letter fragments of an abbreviation (USD(R&E) -> r, e) are dropped."""
    return {w for w in _WORD.findall(B.normalize(text or "").lower()) if len(w) >= 2 and w not in _FUNCTION and w not in _GENERIC}


def overlaps(value, text):
    """True if the value names the gold text: it has distinctive words, at least one is in the gold text, and at least `OVERLAP`
    (here 0.8) of its distinctive words are. A value with extra, unrelated identifying words does not match."""
    a, b = _distinctive(value), _distinctive(text)
    if not a or not b:
        return False
    return len(a & b) >= 1 and len(a & b) / len(a) >= OVERLAP


def attachment(answer, gold):
    """right, misleading or incomplete for an audit record (None when attachment is not scored for it)."""
    if gold["standalone"] == "not_a_requirement" or (gold["standalone"] == "needs_lead_in" and not gold["lead_in_text"]):
        return None  # no adjudicated lead-in text to compare with: not scored for attachment
    parent = (answer["parent"]["value"] or "").strip()
    actor = (answer["actor"]["value"] or "").strip()
    if gold["standalone"] == "complete":
        return "misleading" if parent else "right"
    if overlaps(parent, gold["lead_in_text"]) or overlaps(actor, gold["lead_in_text"]):
        return "right"
    return "misleading" if (parent or actor) else "incomplete"


def attachment_scored(gold):
    """Attachment is scored for audit records that are requirements and, when they need a lead-in, have adjudicated lead-in text."""
    return not (gold["standalone"] == "not_a_requirement" or (gold["standalone"] == "needs_lead_in" and not gold["lead_in_text"]))


def baseline_attachment(gold):
    if gold["standalone"] == "not_a_requirement" or (gold["standalone"] == "needs_lead_in" and not gold["lead_in_text"]):
        return None
    if gold["production_stem"]:
        return "right" if gold["stem_verdict"] == "right" else "misleading"
    return "incomplete" if gold["standalone"] == "needs_lead_in" else "right"


def is_real(gold):
    return gold["standalone"] in ("complete", "needs_lead_in") if gold["set"] == "audit" else bool(gold["real_requirement"])


def score_half(records, golds):
    """Score one run's ledger records against the gold of one half. `records` is {candidate_id: ledger record}.

    A candidate is *usable* only if its call was `complete`, its answer parsed, and the answer has the schema's shape. Everything else
    (an overrun, a truncation, a failure, a missing record, a malformed answer) is a failed resolution: it stays in every denominator
    and is counted in a `failed` bucket, never dropped and never able to make a gate look better.
    """
    out = {"candidates": len(golds), "status": collections.Counter(), "real": collections.Counter(), "non_requirement": collections.Counter(),
           "attachment": collections.Counter(), "baseline_attachment": collections.Counter(), "modality_error_answers": 0,
           "invented_answers": 0, "shape_conformant": 0, "nonconformant": 0, "parsed": 0, "valid": 0, "answers_with_no_error": 0}
    for g in golds:
        rec = records.get(g["candidate_id"])
        out["status"][rec["status"] if rec else "not_run"] += 1
        base = baseline_attachment(g) if g["set"] == "audit" else None
        if base:
            out["baseline_attachment"][base] += 1
        answer = rec.get("answer") if rec else None
        issues = (rec or {}).get("issues") or []
        if rec and rec["status"] == "complete" and answer is not None:
            out["parsed"] += 1
        shape_bad = answer is not None and any(i["code"] == "shape" for i in issues)
        if shape_bad:
            out["nonconformant"] += 1
        if not (rec and rec["status"] == "complete" and answer is not None and not shape_bad):
            (out["real"] if is_real(g) else out["non_requirement"])["failed"] += 1
            if g["set"] == "audit" and attachment_scored(g):
                out["attachment"]["failed"] += 1
            continue
        out["valid"] += 1
        out["shape_conformant"] += 1
        if not any(i["severity"] == "error" for i in issues):
            out["answers_with_no_error"] += 1
        if any(i["severity"] == "error" and i["code"] in C.MODALITY_ERROR_CODES for i in issues):
            out["modality_error_answers"] += 1
        if any(i["severity"] == "error" and (i["code"] in INVENTED_CODES or (i["code"] == "not_in_cited_span" and i["field"] in INVENTED_FIELDS))
               for i in issues):
            out["invented_answers"] += 1
        status = answer["status"]["value"]
        bucket = "requirement" if status in R.REQUIREMENT_STATUS else status
        (out["real"] if is_real(g) else out["non_requirement"])[bucket] += 1
        if g["set"] == "audit":
            a = attachment(answer, g)
            if a:
                out["attachment"][a] += 1
    return {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in out.items()}


def rate(counter, key, total=None):
    total = sum(counter.values()) if total is None else total
    return round(counter.get(key, 0) / total, 3) if total else None


def _check(exact, threshold, upper=True):
    """(reported value rounded to three places, threshold, passed). The comparison uses the exact quotient: 2 of 99 is 2.02%, not 2.0%."""
    passed = exact <= threshold if upper else exact >= threshold
    return (round(exact, 3), round(threshold, 3), passed)


def gate_report(s, base_counts):
    """The selection-half gate checks that apply, as {name: (value, threshold, passed)}. A failed resolution counts AGAINST every
    max-style gate (rejected, scope or unresolved, incomplete) and in the denominator of every min-style gate, and a separate gate
    requires almost every candidate to be resolved at all, so a configuration that fails its calls cannot look like it passes.
    Every comparison is made on the exact fraction; only the reported value is rounded."""
    out = {}
    real, non = s["real"], s["non_requirement"]
    nr, nn = sum(real.values()), sum(non.values())
    if s["candidates"]:
        out["valid_answers"] = _check(s["valid"] / s["candidates"], GATES["min_valid_share"], upper=False)
    if nr:
        out["real_rejected"] = _check((real.get("not_a_requirement", 0) + real.get("failed", 0)) / nr, GATES["max_real_rejected"])
        out["real_scope_or_unresolved"] = _check(
            (real.get("scope_or_context", 0) + real.get("unresolved", 0) + real.get("failed", 0)) / nr, GATES["max_real_scope_or_unresolved"])
    if nn:
        out["non_requirement_rejected"] = _check(
            (non.get("not_a_requirement", 0) + non.get("scope_or_context", 0)) / nn, GATES["min_non_requirement_rejected"], upper=False)
    if s["valid"]:
        out["invented"] = _check(s["invented_answers"] / s["valid"], GATES["max_invented"])
        mod = s["modality_error_answers"]
        out["modality_errors"] = (mod, 0, mod == 0)
    att, nb = s["attachment"], sum(base_counts.values())
    if sum(att.values()) and nb:
        inc = (att.get("incomplete", 0) + att.get("failed", 0)) / sum(att.values())
        out["incomplete"] = _check(inc, base_counts.get("incomplete", 0) / nb + GATES["max_incomplete_over_baseline"])
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


def _check_fraction(exact, threshold, upper=True):
    """Like `_check`, with both sides exact `Fraction`s: (value rounded to three places, threshold rounded, passed)."""
    passed = exact <= threshold if upper else exact >= threshold
    return (round(float(exact), 3), round(float(threshold), 3), passed)


def selection_gates(sel, min_right=None, relative=None):
    """The selection-half gates of one configuration: `gate_report` plus, when `min_right` is given (the WP-45.7b registry), a gate that the
    audit attachment-right rate is at least that exact fraction, and, when `relative` is given (the WP-45.7c registry, `V4_RELATIVE`),
    two gates anchored to the production stems on the same records: the right rate at least production's plus `min_gain`, and the
    misleading rate (a failed resolution counts as misleading) at most production's plus `max_misleading_margin`. Every comparison is on
    exact fractions. Works on either half's result dict (`sel["all"]`, `sel["audit"]`). Returns ({name: (value, threshold, passed)}, the right rate)."""
    audit = sel["audit"]
    gates = {**gate_report(sel["all"], audit["baseline_attachment"])}
    att = audit["attachment"]
    right = rate(att, "right", sum(att.values()))
    if min_right is not None:  # the exact fraction, as in every other gate: 35 of 55 is 0.63636, which `rate` rounds to 0.636
        total = sum(att.values())
        gates["attachment_right"] = _check(att.get("right", 0) / total if total else 0.0, min_right, upper=False)
    if relative:
        base = audit["baseline_attachment"]
        nb, total = sum(base.values()), sum(att.values())
        if nb and total:
            gates["attachment_gain_over_production"] = _check_fraction(
                Fraction(att.get("right", 0), total), Fraction(base.get("right", 0), nb) + relative["min_gain"], upper=False)
            gates["misleading"] = _check_fraction(
                Fraction(att.get("misleading", 0) + att.get("failed", 0), total),
                Fraction(base.get("misleading", 0), nb) + relative["max_misleading_margin"])
        else:  # nothing to compare (no attachment-scored records, or no production baseline): the gates exist and FAIL, never vanish
            gates["attachment_gain_over_production"] = (0.0, 1.0, False)
            gates["misleading"] = (1.0, 0.0, False)
    return gates, right


def choose(configs, min_right=None, relative=None):
    """The configuration to freeze, from {name: {"tier", "model_size", "selection": score_run()["selection"]}} (selection halves only)."""
    best = None
    for name, c in configs.items():
        sel = c["selection"]
        audit = sel.get("audit")
        if not audit:
            continue
        gates, right = selection_gates(sel, min_right, relative)
        passed = all(v[2] for v in gates.values())
        key = (passed, right or 0, -["R0", "R1", "R2"].index(c["tier"]), -c["model_size"])
        if best is None or key > best[0]:
            best = (key, name, passed, right, gates)
    return best


REGISTERED_CONFIGS = frozenset(f"{t}_{m}" for t in ("r0", "r1", "r2") for m in ("8b", "14b"))  # the six the rule was registered for
# WP-45.7b (docs/PHASE45_WP457B_PLAN.md section 3): four configurations (R0 supplies no context and is dropped), the same gates, plus
# attachment right of at least 35 of 55, the best generative (v2) result, 63.6%.
REGISTRIES = {
    "v2": REGISTERED_CONFIGS,
    "v3": frozenset(f"{t}_{m}" for t in ("r1", "r2") for m in ("8b", "14b")),
    "v4": frozenset(f"{t}_{m}" for t in ("r1", "r2") for m in ("8b", "14b")),  # WP-45.7c: the same four, a different bar
}
V3_MIN_RIGHT = 35 / 55
# WP-45.7c (docs/PHASE45_WP457C_PLAN.md section 2): the bar is derived from production, not from the generative resolver: right at least
# 20 points above the production stems' rate on the same records, and misleading at most production's plus 5 points.
V4_RELATIVE = {"min_gain": Fraction(1, 5), "max_misleading_margin": Fraction(1, 20)}


def parse_config(name):
    """"r1_8b" -> ("R1", 8): the tier and the model size encoded in a run name."""
    tier, _, size = name.partition("_")
    if tier.upper() not in ("R0", "R1", "R2") or not size.endswith("b") or not size[:-1].isdigit():
        raise SystemExit(f"--choose needs run names like r1_8b or r2_14b, got {name!r}")
    return tier.upper(), int(size[:-1])


def choose_report(results, registry="v2"):
    """Apply the pre-registered rule (docstring) to {name: score_run()} and return the full report: every configuration's selection-half
    gates, and the chosen one. Only the selection halves are read."""
    names = {n.lower() for n in results}
    registered = REGISTRIES[registry]
    min_right = V3_MIN_RIGHT if registry == "v3" else None
    relative = V4_RELATIVE if registry == "v4" else None
    if names != registered or len(names) != len(results):
        raise SystemExit(
            f"the pre-registered rule ({registry}) applies to exactly these {'six' if len(registered) == 6 else 'four'} runs: " + ", ".join(sorted(registered))
            + f"; got {sorted(results)} (missing {sorted(registered - names)}, unexpected {sorted(names - registered)})"
        )
    configs, report = {}, {"configs": {}}
    for name, r in results.items():
        tier, size = parse_config(name)
        sel = r.get("selection")
        if not sel or "audit" not in sel:
            raise SystemExit(f"{name} has no selection-half audit results")
        configs[name] = {"tier": tier, "model_size": size, "selection": sel}
        audit = sel["audit"]
        gates, _ = selection_gates(sel, min_right, relative)
        att = audit["attachment"]
        report["configs"][name] = {
            "gates": {k: {"value": v[0], "threshold": v[1], "passed": bool(v[2])} for k, v in gates.items()},
            "all_gates_pass": all(v[2] for v in gates.values()),
            "attachment": att, "attachment_right_rate": rate(att, "right", sum(att.values())),
            "baseline_attachment": audit["baseline_attachment"],
        }
    best = choose(configs, min_right, relative)
    report["chosen"] = None if best is None else {"name": best[1], "passes_every_gate": bool(best[2]), "attachment_right_rate": best[3]}
    report["rule"] = "from the selection halves only: configurations passing every gate, then the highest audit attachment-right rate, ties to the lower tier then the smaller model; if none passes, the best right rate, reported as failing"
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", nargs="+", required=True, metavar="NAME=DIR")
    ap.add_argument("--out")
    ap.add_argument("--choose", action="store_true", help="apply the pre-registered choice rule (run names like r1_8b) and print the report")
    ap.add_argument("--registry", choices=sorted(REGISTRIES), default="v2",
                    help="which registered rule --choose applies to: v2 (six configurations, WP-45.7), v3 (four, WP-45.7b) or v4 (the same four with the WP-45.7c bar)")
    args = ap.parse_args()
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    results = {}
    for spec in args.runs:
        name, sep, directory = spec.partition("=")
        if not sep or not name or not directory:
            sys.exit(f"--runs takes NAME=DIR, got {spec!r}")
        results[name] = score_run(directory, gold)
    if args.choose:
        results = choose_report(results, args.registry)
    text = json.dumps(results, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

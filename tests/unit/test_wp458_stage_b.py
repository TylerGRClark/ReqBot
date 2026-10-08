import importlib.util
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    folder = ROOT / "eval/spike_results/wp_45_8"
    for p in (folder, ROOT / "eval/spike_results/wp_45_1c", ROOT / "eval"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


RUN, AN = _load("stage_b_run"), _load("stage_b_analyze")
logging.disable(logging.NOTSET)  # the apparatus' run_test.py turns logging off when imported; do not leak that into other tests
PAYLOAD = {"source_quote": "(a) Report findings.", "embedding_text": "Old stem:", "source_ref": "1.2", "requirement_id": "REQ-1"}


def test_strings_exclude_flagged_rows_non_verbatim_spans_and_empty_strings(tmp_path):
    shadow, report = tmp_path / "s.jsonl", tmp_path / "r.json"
    rows = [
        {"requirement_id": "a", "flag": None, "resolver_string": "The Director shall:"},
        {"requirement_id": "b", "flag": "checker error", "resolver_string": "x"},
        {"requirement_id": "c", "flag": None, "resolver_string": None},
        {"requirement_id": "d", "flag": None, "resolver_string": "not verbatim"},
    ]
    shadow.write_text("".join(json.dumps(r) + "\n" for r in rows))
    report.write_text(json.dumps({"spans_not_in_document": [{"requirement_id": "d"}]}))
    strings, evaluated = RUN.resolver_strings(shadow, report)
    assert strings == {"a": "The Director shall:"} and evaluated == {"a", "b", "c", "d"}  # evaluated ids include the abstentions, so unseen ids can be told apart


def test_resolver_text_uses_the_string_or_the_quote_alone_and_hybrid_falls_back_to_production():
    with_string = RUN.resolver_text(PAYLOAD, "The Director shall:")
    assert "The Director shall:\n(a) Report findings." in with_string and "Old stem:" not in with_string
    alone = RUN.resolver_text(PAYLOAD, "")
    assert "Old stem:" not in alone and "(a) Report findings." in alone
    assert RUN.hybrid_text(PAYLOAD, "") == RUN.V.production_text(PAYLOAD) and "Old stem:" in RUN.hybrid_text(PAYLOAD, "")
    assert RUN.hybrid_text(PAYLOAD, "The Director shall:") == with_string


def cell(mean, lo, hi, n=20, mean_worst=None, lo_w=None, hi_w=None):
    w = {"n": n, "mean": mean if mean_worst is None else mean_worst, "lo": lo if lo_w is None else lo_w, "hi": hi if hi_w is None else hi_w}
    return {"best": {"n": n, "mean": mean, "lo": lo, "hi": hi}, "worst": w}


def _table(per_run):
    """per_run: {run: {style: {group: cell}}}; groups not given are a flat 0 cell."""
    flat = AN.classify(cell(0.0, -0.05, 0.05))
    return {run: {s: {g: AN.classify(per_run.get(run, {}).get(s, {}).get(g, cell(0.0, -0.05, 0.05))) if g in per_run.get(run, {}).get(s, {}) else flat for g in AN.GROUP_NAMES}
                  for s in AN.STYLES} for run in AN.RUNS}


GOLD_OK = {run: {"hi": 0.0} for run in AN.RUNS}


def test_classify_marks_wide_intervals_inconclusive_and_needs_both_tie_readings():
    assert AN.classify(cell(-0.2, -0.5, 0.2))["inconclusive"]  # interval wider than 0.40
    assert AN.classify(cell(-0.2, -0.3, -0.1))["meaningful"] == "decrease"
    assert AN.classify(cell(-0.2, -0.3, -0.1, mean_worst=-0.05, lo_w=-0.2, hi_w=0.1))["meaningful"] is None  # worst reading disagrees
    assert AN.classify(cell(0.15, 0.05, 0.3))["meaningful"] == "increase"


def test_h_needs_two_runs_on_the_same_style_and_ignores_inconclusive_cells():
    dec = cell(-0.2, -0.3, -0.1)
    wide = cell(-0.2, -0.5, 0.2)
    one = _table({"plain": {"topic": {"right": dec}}})
    assert not AN.evaluate(one, GOLD_OK)["H"]
    two = _table({"plain": {"topic": {"right": dec}}, "prod_r1": {"topic": {"right": dec}}})
    assert AN.evaluate(two, GOLD_OK)["H"][0]["group"] == "right"
    mixed = _table({"plain": {"topic": {"right": dec}}, "prod_r1": {"party": {"right": dec}}})
    assert not AN.evaluate(mixed, GOLD_OK)["H"]
    skipped = _table({"plain": {"topic": {"right": dec}}, "prod_r1": {"topic": {"right": wide}}})
    assert not AN.evaluate(skipped, GOLD_OK)["H"]


def test_r_needs_all_four_runs_point_estimates_even_when_intervals_are_wide():
    bad = cell(-0.15, -0.6, 0.3)
    allfour = _table({run: {"topic": {"control": bad}} for run in AN.RUNS})
    assert AN.evaluate(allfour, GOLD_OK)["R"][0]["group"] == "control"
    three = _table({run: {"topic": {"control": bad}} for run in AN.RUNS[:3]})
    assert not AN.evaluate(three, GOLD_OK)["R"]


def test_g_needs_three_runs_and_c_needs_two_runs_wholly_below_the_floor():
    inc = cell(0.2, 0.1, 0.35)
    g3 = _table({run: {"party": {"bare": inc}} for run in AN.RUNS[:3]})
    assert AN.evaluate(g3, GOLD_OK)["outcome"] == "proposal for integration"
    g2 = _table({run: {"party": {"bare": inc}} for run in AN.RUNS[:2]})
    assert AN.evaluate(g2, GOLD_OK)["outcome"] == "no demonstrated benefit"
    gold_low = {**GOLD_OK, "plain": {"hi": -0.03}, "prod_r1": {"hi": -0.021}}
    out = AN.evaluate(g3, gold_low)
    assert out["C"] and out["outcome"].startswith("no proposal: C")
    assert not AN.evaluate(g3, {**GOLD_OK, "plain": {"hi": -0.03}})["C"]  # one run is not enough
    assert not AN.evaluate(g3, {**GOLD_OK, "plain": {"hi": -0.02}, "prod_r1": {"hi": -0.01}})["C"]  # an interval that reaches -0.02 does not trigger


def test_analyze_runs_end_to_end_on_synthetic_results(tmp_path):
    import random

    groups = json.loads((ROOT / "eval/spike_results/wp_45_1c/groups.json").read_text())
    rng = random.Random(1)
    for run in AN.RUNS:
        rows = []
        for g, rids in groups["groups"].items():
            for rid in rids:
                for style in AN.STYLES:
                    base = rng.randint(1, 30)
                    for arm, mode in (("production", "base"), ("resolver", "target_only"), ("hybrid", "target_only")):
                        rank = base if arm == "production" else max(1, base - rng.randint(0, 3))
                        rows.append({"rid": rid, "style": style, "arm": arm, "mode": mode, "group": g, "no_party": False, "has_string": rng.random() < 0.8,
                                     "best_rank": rank, "worst_rank": rank, "score": 0.1})
        gold = []
        for q in range(35):
            for arm, mode in (("production", "base"), ("resolver", "cohort"), ("hybrid", "cohort")):
                gold.append({"query_id": f"g{q}", "arm": arm, "mode": mode, "recall@10": float(q % 2), "mrr": 0.5})
        (tmp_path / f"stageb_results_{run}.json").write_text(json.dumps({"manifest": {"snapshot": {}, "strings": {}, "excluded_not_in_live_index": []}, "rows": rows, "gold": gold}))
    verdict, detail = AN.analyze(tmp_path, "resolver")
    assert verdict["outcome"] in ("no demonstrated benefit", "proposal for integration") or verdict["outcome"].startswith("no proposal")
    assert set(detail["plain"]["other_metrics"]) == {"recall@5", "recall@20", "mrr"}
    cov = detail["plain"]["string_coverage"]["bare"]
    assert cov["with_string"] + cov["without_string"] == len(groups["groups"]["bare"])

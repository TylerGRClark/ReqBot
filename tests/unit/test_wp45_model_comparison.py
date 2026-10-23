"""WP-45.6: the pure pieces of the extraction-model comparison (matching rule, per-side overlap counts).

Tests that load a script importing the deleted list-writing extraction step or parent-stem finders were removed when clause labeling replaced
that step (WP-4 of the extraction replacement; see eval/README.md). The scripts themselves are frozen and unchanged.
"""

import argparse
import importlib.util
import logging
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_6"


def _load(name):
    sys.path.insert(0, str(_DIR))
    try:
        spec = importlib.util.spec_from_file_location(f"wp456_{name}", _DIR / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        logging.disable(logging.NOTSET)  # census.py silences logging at import
        return module
    finally:
        sys.path.remove(str(_DIR))


# ------------------------------------------------------------------------------------------------ scoring and pack


@pytest.fixture(scope="module")
def score():
    return _load("score")


@pytest.fixture(scope="module")
def run_model():
    return _load("run_model")


def _sh(new_only, base_only, both):
    def one(vals):
        return {"genuine": vals, "complete": [1] * len(vals), "n": len(vals)}

    return {"new_only": one(new_only), "base_only": one(base_only), "both": one(both)}


def test_net_gain_weights_genuine_shares_by_set_size(score):
    pop = {"new_only": 40, "base_only": 100, "base_matched": 200}
    G, L, N8, net = score.net_gain({"new_only": 0.9, "base_only": 0.5, "both": 0.95}, pop)
    assert (G, L) == (36.0, 50.0) and N8 == pytest.approx(200 * 0.95 + 50)
    assert net == pytest.approx((36 - 50) / 240)


def test_evaluate_applies_each_pre_set_rule(score):
    # the 14B finds many genuine extras and loses few: (a) passes; the other criteria are set up to pass too
    sh = _sh([1] * 19 + [0], [1, 0] * 10, [1] * 19 + [0])
    pop = {"new_only": 60, "base_only": 20, "base_matched": 100, "new_matched": 100, "base_survivors": 120, "new_survivors": 160,
           "base_fragments": 20, "new_fragments": 10, "chunks": 100, "new_lost": 1}
    control = {**pop, "new_lost": 1}
    rows, ok = score.evaluate(sh, pop, control, net14=0.40, net_control=0.0)
    assert {k: p for k, _, p in rows} == {"a": True, "b": True, "c": True, "d": True, "e": True} and ok
    # a model that finds far fewer records fails (a) and (e) even if everything else is fine
    rows, ok = score.evaluate(sh, {**pop, "new_only": 5, "base_only": 80}, control, net14=-0.3, net_control=0.0)
    verdict = {k: p for k, _, p in rows}
    assert not ok and not verdict["a"] and not verdict["e"]
    # more junk among the 14B-only records than the 8B-only ones by over 0.10 fails (b)
    junky = _sh([1] * 10 + [0] * 10, [1] * 19 + [0], [1] * 20)
    assert not {k: p for k, _, p in score.evaluate(junky, pop, control, 0.4, 0.0)[0]}["b"]
    # more lost chunks than the fresh 8B by more than 5 points fails (d)
    assert not {k: p for k, _, p in score.evaluate(sh, {**pop, "new_lost": 10}, control, 0.4, 0.0)[0]}["d"]


def test_wilson_and_rate_difference_are_sane(score):
    lo, hi = score.wilson(5, 10)
    assert 0.2 < lo < 0.5 < hi < 0.8 and score.wilson(0, 10)[0] == 0.0
    diff, lo, hi = score.rate_difference(10, 100, 20, 100)
    assert diff == pytest.approx(-0.10) and lo < diff < hi < 0.05


def test_empty_groups_give_nan_and_fail_the_criterion_instead_of_raising(score):
    nan = score.diff_interval([], [1, 0])
    assert all(x != x for x in nan) and all(x != x for x in score.diff_interval([1], []))
    assert all(x != x for x in score.rate_difference(0, 0, 3, 10))
    assert all(x != x for x in score.rate_difference(3, 10, 0, 0))
    # a run with no 14B-only records and no 14B survivors: (b) and (c) are undefined, so neither passes
    sh = _sh([], [1, 0] * 10, [1] * 20)
    pop = {"new_only": 0, "base_only": 20, "base_matched": 100, "new_matched": 100, "base_survivors": 120, "new_survivors": 0,
           "base_fragments": 20, "new_fragments": 0, "chunks": 100, "new_lost": 1}
    verdict = {k: p for k, _, p in score.evaluate(sh, pop, pop, -0.2, 0.0)[0]}
    assert not verdict["b"] and not verdict["c"]


def test_run_model_rejects_non_positive_numbers(run_model):
    assert run_model._positive_int("5") == 5
    for bad in ("0", "-3"):
        with pytest.raises(argparse.ArgumentTypeError):
            run_model._positive_int(bad)


def test_step_c_summary_reports_states_and_no_token_counts(run_model, tmp_path):
    ledger = tmp_path / "raw.jsonl"
    ledger.write_text(
        '{"chunk_id": 1, "status": "complete", "done_reason": "stop", "prompt_hash": "h"}\n'
        '{"chunk_id": 2, "status": "truncated", "done_reason": "length", "prompt_hash": "h"}\n',
        encoding="utf-8",
    )
    out = run_model.status_summary(ledger)
    assert out["status"] == {"complete": 1, "truncated": 1} and out["prompt_hashes"] == ["h"]
    assert out["done_reason"] == {"stop": 1, "length": 1}
    assert "prompt_tokens" not in out and "output_tokens" not in out

"""WP-45.6: the pure pieces of the extraction-model comparison (matching rule, per-side overlap counts)."""

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


@pytest.fixture(scope="module")
def cmp():
    return _load("compare")


def _rec(rid, chunk, quote):
    return {"requirement_id": rid, "chunk_id": chunk, "source_quote": quote}


def test_same_record_needs_the_same_chunk_and_equal_or_contained_quotes(cmp):
    a, b = cmp.prepare([_rec("A", 1, "The CIO shall  update the list."), _rec("B", 1, "The CIO shall update the list.")])
    assert cmp.same_record(a, b)  # equal after whitespace normalization
    short = cmp.prepare([_rec("S", 1, "The CIO shall update the list")])[0]  # no final period: a clause of the longer quote
    long_ = cmp.prepare([_rec("L", 1, "The CIO shall update the list and report it quarterly.")])[0]
    assert cmp.same_record(short, long_) and cmp.same_record(long_, short)  # one contains the other, either way round
    assert not cmp.same_record(a, long_)  # a full sentence with its period is not a substring of a longer sentence
    other_chunk = cmp.prepare([_rec("O", 2, "The CIO shall update the list.")])[0]
    assert not cmp.same_record(a, other_chunk)
    different = cmp.prepare([_rec("D", 1, "Components shall comply.")])[0]
    assert not cmp.same_record(a, different)
    empty = cmp.prepare([_rec("E", 1, "")])[0]
    assert not cmp.same_record(a, empty) and not cmp.same_record(empty, empty)


def test_overlap_counts_each_side_and_handles_merges_and_splits(cmp):
    base = cmp.prepare(
        [
            _rec("b1", 1, "Ensure X is done."),  # matched exactly
            _rec("b2", 2, "Ensure Y is done."),  # two base quotes inside one new quote (a merge)
            _rec("b3", 2, "Report Z quarterly."),
            _rec("b4", 3, "Only the 8B found this one."),
        ]
    )
    new = cmp.prepare(
        [
            _rec("n1", 1, "Ensure X is done."),
            _rec("n2", 2, "Ensure Y is done. Report Z quarterly."),
            _rec("n3", 4, "Only the 14B found this one."),
        ]
    )
    ov = cmp.overlap(base, new)
    assert ov["base_matched"] == ["b1", "b2", "b3"] and ov["base_only"] == ["b4"]
    assert ov["new_matched"] == ["n1", "n2"] and ov["new_only"] == ["n3"]  # 3 base records matched by 2 new ones
    assert ov["exact_equal_pairs"] == 1


# ------------------------------------------------------------------------------------------------ scoring and pack


@pytest.fixture(scope="module")
def score():
    return _load("score")


@pytest.fixture(scope="module")
def pack():
    return _load("pack")


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


def test_pack_draw_is_seeded_extendable_and_ids_hide_the_set(pack):
    frame = {
        "new_only": [("d", "new", f"N{i}") for i in range(60)],
        "base_only": [("d", "base", f"B{i}") for i in range(50)],
        "both": [("d", "new", f"M{i}") for i in range(10)],  # smaller than the sample: taken whole
    }
    a, b = pack.draw(frame), pack.draw(frame)
    assert a == b and [len(a[k]) for k in ("new_only", "base_only", "both")] == [40, 40, 10]
    small = pack.draw(frame, sample={"new_only": 5, "base_only": 5, "both": 5})
    assert a["new_only"][:5] == small["new_only"]  # the first n of the same shuffle, so a sample can be extended
    ids = pack.assign_ids(a)
    assert sorted(ids) == [f"R{i:03d}" for i in range(1, 91)]
    sets_in_id_order = [ids[k]["set"] for k in sorted(ids)]
    assert sets_in_id_order != sorted(sets_in_id_order)  # ids are shuffled, not grouped by set
    assert pack.assign_ids(a) == ids  # deterministic

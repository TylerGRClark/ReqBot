"""WP-45.1(b): the audit scorer's statistics and its adjudication bookkeeping.

The scorer runs for real on the committed labels and answer key; these tests pin the pieces whose mistakes would
silently change a reported number: kappa, the Wilson interval, stratum weighting, the answer-file grammar, and how a
disagreement, a spot-check change and a later correction are told apart.
"""

import importlib.util
import math
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_1/score_audit.py"


@pytest.fixture(scope="module")
def sa():
    spec = importlib.util.spec_from_file_location("wp45_score_audit", _PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wp45_score_audit"] = module
    spec.loader.exec_module(module)
    return module


def test_kappa_is_one_for_perfect_agreement_and_zero_at_chance(sa):
    assert sa.kappa([("a", "a"), ("b", "b"), ("a", "a"), ("b", "b")]) == 1.0
    chance = [("a", "a"), ("a", "b"), ("b", "a"), ("b", "b")]
    assert sa.kappa(chance) == pytest.approx(0.0)
    assert math.isnan(sa.kappa([]))


def test_wilson_interval_brackets_the_proportion_and_stays_in_range(sa):
    lo, hi = sa.wilson(5, 10)
    assert 0.2 < lo < 0.5 < hi < 0.8
    assert sa.wilson(0, 10)[0] == 0.0 and sa.wilson(10, 10)[1] == 1.0
    assert math.isnan(sa.wilson(0, 0)[0])


def test_weighted_pooling_follows_stratum_populations(sa):
    population = {"big": 900, "small": 100}
    sample = {"big": 10, "small": 10}
    estimate, lo, hi, total = sa.weighted(
        ["big", "small"], sample, {"big": 1, "small": 9}, population
    )
    assert estimate == pytest.approx((900 * 0.1 + 100 * 0.9) / 1000)
    assert total == pytest.approx(180.0)
    assert 0.0 <= lo < estimate < hi <= 1.0


def test_answers_need_a_pass_letter_and_accept_comments(sa, tmp_path):
    path = tmp_path / "answers.txt"
    path.write_text(
        "# header\nR012 a: codex  # why\nR019 b: claude\nR031 a: other needs_lead_in same_chunk :: The PM:\nR007 a: ok\n",
        encoding="utf-8",
    )
    answers = sa.parse_answers(path)
    assert answers[("R012", "a")] == "codex"
    assert answers[("R019", "b")] == "claude"
    assert answers[("R031", "a")] == ("other", ["needs_lead_in", "same_chunk"], "The PM:")
    assert answers[("R007", "a")] == "ok"
    path.write_text("R012: codex\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        sa.parse_answers(path)


@pytest.mark.parametrize(
    "line",
    [
        "R012 a: other",
        "R012 a: other maybe",
        "R012 a: other needs_lead_in",
        "R012 a: other needs_lead_in elsewhere",
        "R012 a: other needs_lead_in same_chunk",
        "R012 a: other needs_lead_in not_shown :: text",
        "R012 a: other complete :: text",
        "R012 b: other right :: text",
        "R012 a: other complete same_chunk",
        "R012 b: other",
        "R012 b: other right wrong_other",
        "R012 b: other complete",
        "R012 a: approve",
    ],
)
def test_malformed_answers_stop_with_a_message(sa, tmp_path, line):
    path = tmp_path / "answers.txt"
    path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="line 1"):
        sa.parse_answers(path)


def _a(standalone="complete", location=None, text=None):
    return {"standalone": standalone, "lead_in_location": location, "lead_in_text": text}


def _setup():
    a_pairs = {
        "R001": (_a(), _a("needs_lead_in", "previous_chunk", "x")),  # disagreement
        "R002": (_a(), _a()),  # agreed, in the spot-check
        "R003": (_a("not_a_requirement"), _a("not_a_requirement")),  # agreed, not sampled
    }
    b_pairs = {"R001": ({"stem_verdict": "right"}, {"stem_verdict": "fragment_chain"})}
    return a_pairs, b_pairs, ["R001"], ["R001"], [("R002", "a")]


def test_resolve_applies_answers_and_separates_changes_from_corrections(sa):
    a_pairs, b_pairs, dis_a, dis_b, spot = _setup()
    answers = {
        ("R001", "a"): "codex",
        ("R001", "b"): "claude",
        ("R002", "a"): ("other", ["needs_lead_in", "same_chunk"], "The PM:"),
        ("R003", "a"): ("other", ["needs_lead_in", "same_chunk"], "The PM:"),
    }
    ra, rb, unresolved, spot_changes, corrections = sa.resolve(
        a_pairs, b_pairs, dis_a, dis_b, spot, answers
    )
    assert unresolved == []
    assert ra["R001"][:2] == ("needs_lead_in", "previous_chunk") and rb["R001"] == "right"
    assert ra["R002"][:3] == ("needs_lead_in", "same_chunk", "The PM:") and spot_changes == [
        ("R002", "a")
    ]
    assert ra["R003"][:3] == ("needs_lead_in", "same_chunk", "The PM:") and corrections == [
        ("R003", "a")
    ]


def test_resolve_reports_unanswered_disagreements_and_ignores_ok(sa):
    a_pairs, b_pairs, dis_a, dis_b, spot = _setup()
    answers = {("R002", "a"): "ok"}
    ra, rb, unresolved, spot_changes, corrections = sa.resolve(
        a_pairs, b_pairs, dis_a, dis_b, spot, answers
    )
    assert sorted(unresolved) == [("R001", "a"), ("R001", "b")]
    assert ra["R002"][0] == "complete" and spot_changes == [] and corrections == []


def test_policy_resolves_every_disagreement_to_one_labeler(sa):
    a_pairs, b_pairs, dis_a, dis_b, spot = _setup()
    ra, rb, unresolved, *_ = sa.resolve(a_pairs, b_pairs, dis_a, dis_b, spot, {}, "codex")
    assert unresolved == []
    assert ra["R001"][1] == "previous_chunk" and rb["R001"] == "fragment_chain"


def test_ok_on_a_disputed_item_is_an_error_not_a_silent_default(sa):
    a_pairs, b_pairs, dis_a, dis_b, spot = _setup()
    with pytest.raises(SystemExit, match="disputed"):
        sa.resolve(
            a_pairs, b_pairs, dis_a, dis_b, spot, {("R001", "a"): "ok", ("R001", "b"): "claude"}
        )


def test_answers_for_missing_items_or_agreed_items_are_rejected(sa):
    a_pairs, b_pairs, dis_a, dis_b, spot = _setup()
    full = {("R001", "a"): "codex", ("R001", "b"): "claude"}
    with pytest.raises(SystemExit, match="do not exist"):
        sa.resolve(a_pairs, b_pairs, dis_a, dis_b, spot, {**full, ("R999", "a"): "codex"})
    with pytest.raises(SystemExit, match="do not exist"):
        sa.resolve(
            a_pairs, b_pairs, dis_a, dis_b, spot, {**full, ("R002", "b"): "ok"}
        )  # R002 has no pass B
    with pytest.raises(SystemExit, match="agreed by both"):
        sa.resolve(a_pairs, b_pairs, dis_a, dis_b, spot, {**full, ("R002", "a"): "codex"})

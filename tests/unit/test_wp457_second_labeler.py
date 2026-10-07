"""WP-45.7e: the second labeler's agreement and the sensitivity rescore (offline; committed files only, no LLM)."""

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "eval/spike_results/wp_45_7"


def _load():
    for p in (_DIR, _ROOT, _ROOT / "eval/spike_results/wp_45_1", _ROOT / "eval/spike_results/wp_45_audit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("wp457e_second_labeler_compare", _DIR / "second_labeler_compare.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["wp457e_second_labeler_compare"] = module
    spec.loader.exec_module(module)
    return module


SL = _load()


def test_the_rescore_under_the_first_labels_reproduces_the_verdict():
    first = SL.rescore(json.loads(SL.FROZEN.read_text(encoding="utf-8")))
    assert first["attachment"] == {"right": 65, "misleading": 39}
    assert first["baseline_attachment"] == {"right": 41, "misleading": 36, "incomplete": 27}
    assert all(g["passed"] for g in first["gates"].values())


def test_the_second_labelers_gold_is_built_by_the_same_builder_and_rubric():
    gold = SL.second_gold()
    assert gold["counts"]["candidates"] == 114
    assert gold["sufficiency"]["met"]


def test_agreement_counts():
    a = SL.agreement()
    assert (a["standalone_agree"], a["location_agree"], a["stem_verdict_agree"]) == (109, 59, 44)
    assert a["pass_a_cards"] == 114 and a["pass_b_cards"] == 58


def test_under_the_second_labels_as_submitted_two_gates_fail():
    second = SL.rescore(SL.second_gold())
    failed = sorted(k for k, g in second["gates"].items() if not g["passed"])
    assert failed == ["attachment_gain_over_production", "misleading"]
    assert second["attachment"] == {"right": 58, "misleading": 42}


def test_correcting_the_actorless_right_verdicts_leaves_only_the_misleading_gate_failing():
    for extra, limit in ((SL.ACTORLESS_RIGHT, 0.4), (SL.ACTORLESS_RIGHT + SL.ARGUABLE, 0.41)):
        gold = SL.second_gold(fragment_chain=extra)
        assert sum(g["stem_verdict"] == "fragment_chain" for g in gold["gold"]) == 3 + len(extra)  # the second labeler's own three, plus the corrected cards
        result = SL.rescore(gold)
        assert [k for k, g in result["gates"].items() if not g["passed"]] == ["misleading"]
        assert result["gates"]["misleading"]["threshold"] == limit and result["gates"]["misleading"]["value"] == 0.42


def test_the_corrected_cards_are_right_in_the_submitted_file_and_are_not_edited_there():
    rows = SL._by_id(SL.SECOND / "labels_claude2_b.jsonl")
    assert all(rows[c]["stem_verdict"] == "right" for c in SL.ACTORLESS_RIGHT + SL.ARGUABLE)


def test_the_committed_report_is_the_recomputed_one():
    assert json.loads(SL.REPORT.read_text(encoding="utf-8")) == json.loads(json.dumps(SL.report()))

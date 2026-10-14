"""HyPE spike round 2 (PREREGISTRATION_V2.md): target matching, the gate, the paired bootstrap and the rule."""
import importlib.util
from pathlib import Path

_DIR = Path(__file__).resolve().parents[2] / "eval" / "spike_results" / "hype"
_spec = importlib.util.spec_from_file_location("hype_lib_v2", _DIR / "hype_lib.py")
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)


def test_target_hit_by_id_or_anchor_text():
    anchor = H.normalise("The author may contact the Wing Information Protection Office.")
    assert H.target_hit({"requirement_id": "R1"}, ["R1"], anchor)
    assert H.target_hit({"requirement_id": "R9", "explained_text": "Note: the AUTHOR may contact the  Wing Information Protection Office. More."}, [], anchor)
    assert not H.target_hit({"requirement_id": "R9", "source_quote": "Something else."}, ["R1"], anchor)
    assert not H.target_hit({"requirement_id": "R9", "source_quote": "x"}, [], "")  # an empty anchor never matches


def test_gate_from_checklist_rows_with_draft_question():
    docs = [{"items": [{"audit_question": "Does the unit X?", "requirement_ids": ["R1", "R2"]},
                       {"audit_question": "  ", "requirement_ids": ["R3"]},
                       {"requirement_ids": ["R4"]}]}, {"items": []}]
    gate = H.gated_ids(docs)
    assert gate == {"R1", "R2"}
    long_text = "x" * 70
    assert H.gate_c({"requirement_id": "R1", "source_quote": long_text}, gate, 60)
    assert not H.gate_c({"requirement_id": "R1", "source_quote": "short"}, gate, 60)
    assert H.gate_c({"requirement_id": "R1", "source_quote": "short"}, gate)
    assert not H.gate_c({"requirement_id": "R3", "source_quote": long_text}, gate)


def test_paired_bootstrap_is_deterministic_and_brackets_the_mean():
    diffs = [1.0] * 10 + [0.0] * 80 + [-1.0] * 2
    m, lo, hi = H.paired_bootstrap(diffs, resamples=2000)
    assert (m, lo, hi) == H.paired_bootstrap(diffs, resamples=2000)
    assert lo < m < hi
    assert H.paired_bootstrap([0.0] * 20, resamples=100) == (0.0, 0.0, 0.0)


def test_decide_v2_requires_all_four():
    assert H.decide_v2(6, 1, 0, 1)["verdict"] == "BUILD"
    assert H.decide_v2(4.9, 1, 0, 1)["verdict"] == "DO NOT BUILD"
    assert H.decide_v2(6, 0, 0, 1)["verdict"] == "DO NOT BUILD"
    assert H.decide_v2(6, 1, 2.1, 1)["verdict"] == "DO NOT BUILD"
    assert H.decide_v2(6, 1, 2, 0)["verdict"] == "DO NOT BUILD"

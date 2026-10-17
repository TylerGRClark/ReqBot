"""HyPE spike (eval/spike_results/hype): the grounding filter, the collapse to requirement_id and the decision rule."""
import importlib.util
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parents[2] / "eval" / "spike_results" / "hype"
_spec = importlib.util.spec_from_file_location("hype_lib", _DIR / "hype_lib.py")
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

TEXT = "The DoD Component heads shall designate a CNDSP certification authority within 30 days."


def test_grounded_question_is_kept():
    kept, rejected = H.ground_questions(["Who designates the CNDSP certification authority?"], TEXT)
    assert kept == ["Who designates the CNDSP certification authority?"]
    assert rejected == []


def test_invented_number_acronym_or_name_is_rejected():
    questions = [
        "Within how many days must the CNDSP authority be designated, 60?",  # 60 is not in the text
        "Who designates the FedRAMP certification authority?",  # FedRAMP is not in the text
        "Who designates the certification authority at Fort Meade?",  # capitalised names not in the text
    ]
    kept, rejected = H.ground_questions(questions, TEXT)
    assert kept == []
    assert [r["reason"] for r in rejected] == ["ungrounded"] * 3
    assert "60" in rejected[0]["terms"] and "FedRAMP" in rejected[1]["terms"]


def test_sentence_initial_question_word_is_not_a_capitalised_term():
    kept, _ = H.ground_questions(["Which authority does the CNDSP certification need?", "Where is the CNDSP authority designated?"], TEXT)
    assert len(kept) == 2
    # a leading acronym still has to be in the text
    kept, rejected = H.ground_questions(["NIST guidance on the CNDSP authority?"], TEXT)
    assert kept == [] and rejected[0]["terms"] == ["NIST"]
    # and a capitalised name that is not first is still checked
    assert H.ground_questions(["Who in Washington designates the CNDSP authority?"], TEXT)[0] == []


def test_grounding_uses_the_records_own_text_not_a_neighbours():
    assert H.ground_questions(["Who designates the CNDSP authority?"], "Heads shall designate an authority.")[0] == []


def test_duplicates_length_and_cap():
    qs = ["Who designates the CNDSP certification authority?", "who designates the cndsp certification authority", "Too short?",
          "Within how many days must it be designated?", "What must the Component heads do?", "How is the CNDSP involved here at all?"]
    kept, rejected = H.ground_questions(qs, TEXT)
    assert len(kept) == 3
    reasons = [r["reason"] for r in rejected]
    assert "duplicate" in reasons and "length" in reasons and "over_limit" in reasons


def test_parse_questions_tolerates_bad_output():
    assert H.parse_questions('{"questions": ["a b c d e f g", "  ", 5]}') == ["a b c d e f g"]
    assert H.parse_questions("not json") == []
    assert H.parse_questions('{"questions": "oops"}') == []
    assert H.parse_questions(None) == []


def test_record_text_never_includes_reference_or_duplicates():
    p = {"parent_stem": "Heads shall:", "explained_text": "Heads shall: do X.", "source_quote": "do X.", "source_ref": "3.9.", "document_id": "abc"}
    assert H.record_text(p) == "Heads shall: do X."


def test_collapse_keeps_best_ranked_point_and_order():
    ranked = [
        {"requirement_id": "R2", "hype_question": "q about r2"},
        {"requirement_id": "R1"},
        {"requirement_id": "R2"},  # the requirement's own point, ranked below its question
        {"requirement_id": "R3"},
        {"requirement_id": "R1", "hype_question": "q about r1"},
    ]
    out = H.collapse_to_requirement_id(ranked)
    assert [r["requirement_id"] for r in out] == ["R2", "R1", "R3"]
    assert out[0].get("hype_question") == "q about r2"  # the first (best) point's entry is the one kept


def test_collapse_cuts_after_collapsing_and_drops_idless():
    ranked = [{"requirement_id": "R1"}] * 4 + [{"requirement_id": "R2"}, {"x": 1}, {"requirement_id": ""}, {"requirement_id": "R3"}]
    assert [r["requirement_id"] for r in H.collapse_to_requirement_id(ranked, limit=2)] == ["R1", "R2"]
    assert [r["requirement_id"] for r in H.collapse_to_requirement_id(ranked)] == ["R1", "R2", "R3"]


def test_question_point_ids_are_stable_distinct_and_not_requirement_point_ids():
    from pipeline.embed_and_index import requirement_point_id
    a, b = H.question_point_id("REQ-1", 0), H.question_point_id("REQ-1", 1)
    assert a == H.question_point_id("REQ-1", 0) and a != b
    assert a != requirement_point_id({"requirement_id": "REQ-1"})


def test_decision_rule_boundaries():
    rule = json.loads((_DIR / "decision_rule.json").read_text())
    assert H.decide(0.20, 0.35, 0.50, 0.48, rule)["verdict"] == "BUILD"  # +15 points, -2 points: both limits inclusive
    assert H.decide(0.20, 0.34, 0.50, 0.50, rule)["verdict"] == "DO NOT BUILD"  # +14
    assert H.decide(0.20, 0.50, 0.50, 0.47, rule)["verdict"] == "DO NOT BUILD"  # precision fell 3
    d = H.decide(0.2, 0.2, 0.5, 0.5, rule)
    assert not d["rise_requirement_met"] and d["fall_limit_met"]


def test_scratch_guard_names():
    import importlib.util as u
    spec = u.spec_from_file_location("run_hype", _DIR / "run_hype.py")
    mod = u.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.guard_scratch("grc_hype_spike_20261013_220000")
    for bad in ("grc_requirements", "grc_context", "grc_requirements_1791895764", "other"):
        try:
            mod.guard_scratch(bad)
        except RuntimeError:
            continue
        raise AssertionError(bad)

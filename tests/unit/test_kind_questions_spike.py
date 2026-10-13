"""Pure functions of the kind-aware question spike (eval/spike_results/kind_questions/kind_questions.py). No model, no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval" / "spike_results" / "kind_questions"))
import kind_questions as kq  # noqa: E402, I001
from services import requirement_kind as rk  # noqa: E402


def item(quote, **kw):
    return {"source_quote": quote, "item_flags": kw.get("flags", []), "citation": kw.get("citation", "2.1"), "applies_to": "", "parent_text": "", "passage": quote}


def test_authorize_leading_imperative_is_duty_under_rules7_only():
    row = item("Authorize release of certification data to DoD (T-0). Personnel can access and submit release authorization at this link.")
    assert rk.classify(row)["kind"] == "permission"
    assert kq.classify_rules7(row)["kind"] == "duty_imperative"
    assert "authorize" not in rk._COMMAND_VERBS  # the services module is left as it was


def test_noun_authorizing_is_not_an_imperative():
    row = item("Authorizing Officials may extend time limits for a dated period.")
    assert kq.classify_rules7(row)["kind"] == "permission"


def test_pure_pointer_is_suppressed_and_pointer_with_duty_is_kept():
    assert kq.pointer_decision(item("A list of programs can be found in Section 1.4.1."))["action"] == "suppress"
    both = item("Lead support efforts with Centers/Wings in execution of assessments. Assessment types are described in section 3.3.")
    assert kq.pointer_decision(both)["action"] == "keep"
    aside = item("Assess the event against the incident criteria (See Table 1.1, Incident Categories).")
    assert kq.pointer_decision(aside)["action"] == "keep"


def test_recommendation_flag_marks_strength():
    flag = kq.recommendation_flag(item("Personnel should reference Attachment 3 for a template."))
    assert flag["strength"] == "recommended" and flag["matched"].lower() == "should"


def test_check_question_catches_placeholder_duty_and_ungrounded():
    row = item("This may be waived to a SECRET level with a justification memorandum sent through the HAF CARM Program office.")
    good = "When this is waived to a SECRET level, was a justification memorandum sent through the HAF CARM Program office?"
    assert kq.check_question(good, row, "with a justification memorandum sent through the HAF CARM Program office") == []
    assert "C2_placeholder" in kq.check_question("Where the unit does X, is it done within what the document allows?", row)
    assert "C4_turns_may_into_duty" in kq.check_question("Does the unit waive the requirement to a SECRET level?", row)
    assert "C1_not_grounded" in kq.check_question("When this is waived to a TOP SECRET level, is a memorandum sent?", row)
    assert "C3_not_yes_no" in kq.check_question("The memorandum is sent through the HAF CARM Program office.", row)
    assert "C5_limit_not_verbatim" in kq.check_question(good, row, "with a signed memorandum")

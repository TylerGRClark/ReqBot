import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("draft_questions", ROOT / "eval/spike_results/wp_46_4/draft_questions.py")
DQ = importlib.util.module_from_spec(spec)
sys.modules["draft_questions"] = DQ
for p in (ROOT, ROOT / "eval/spike_results/wp_45_7"):
    sys.path.insert(0, str(p))
spec.loader.exec_module(DQ)


def test_unverified_terms_flags_numbers_acronyms_and_names_not_in_the_row():
    material = "The CFP shall notify the servicing MCCC within 24 hours. Applies to: AF/A3"
    assert DQ.unverified_terms("Does the CFP notify the servicing MCCC within 24 hours?", material) == []
    assert DQ.unverified_terms("Does the CFP notify the servicing MCCC within 48 hours?", material) == ["48"]
    assert "NOS" in DQ.unverified_terms("Does the CFP notify the NOS?", material)
    assert DQ.unverified_terms("Does the unit notify the Commander?", material) == ["Commander"]  # a capitalized word the row never uses
    assert DQ.unverified_terms("", material) == []


def test_prohibition_rule_is_only_added_when_the_quote_forbids_something():
    assert DQ.PROHIBITION.search("Preliminary response actions should not result in a self-imposed denial of service;")
    assert DQ.PROHIBITION.search("Personnel shall not exceed the limit.")
    assert not DQ.PROHIBITION.search("The CFP shall notify the MCCC.")


def test_token_level_check_accepts_a_title_without_its_parenthetical_acronym():
    material = "designated Computer Network Defense Service Provider (CNDSP) Certification Authority (CA) for Special Access Program (SAP) networks"
    assert DQ.unverified_terms("Is it designated Computer Network Defense Service Provider Certification Authority for Special Access Program networks?", material) == []
    assert DQ.unverified_terms("Is it designated the Certification Authority for Special Access Program Zebra networks?", material) == ["Zebra"]


def test_prohibition_forms_are_recognized_and_descriptions_are_not():
    for text in ("Do not release the report.", "The unit does not share keys.", "Users cannot reuse passwords.", "Disclosure is prohibited.", "Personnel must not leave the area."):
        assert DQ.PROHIBITION.search(text), text
    assert not DQ.PROHIBITION.search("Examples include, but are not limited to, logs.")

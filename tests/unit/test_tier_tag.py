from pipeline.checklist_export import to_csv
from services.tier_tag import tier_of


def test_a_tag_inside_the_quote_is_the_tier():
    assert tier_of({"source_quote": "The commander will appoint a monitor. (T-2)", "passage": ""}) == "T-2"


def test_a_tag_right_after_the_marked_sentence_is_the_tier():
    passage = "- 4.2.2.1.  >> DoD PKI certificates are at the medium assurance level. << (T-0) .  This is a portable certificate."
    assert tier_of({"source_quote": "DoD PKI certificates are at the medium assurance level.", "passage": passage}) == "T-0"


def test_spacing_inside_the_tag_does_not_matter():
    assert tier_of({"source_quote": "Enter and validate BEI.", "passage": "2.20.10.  >> Enter and validate BEI. << ( T-1 )"}) == "T-1"


def test_a_tag_on_an_earlier_sentence_is_not_the_marked_sentences_tier():
    passage = "A2.2.1.1.1.  The DAFECO must review all requests.  (T-0).  Access is by the SharePoint site. (T-1).  >> This site will provide an access request module. <<"
    assert tier_of({"source_quote": "This site will provide an access request module.", "passage": passage}) == ""


def test_a_tag_on_the_parent_paragraph_is_not_inherited():
    assert tier_of({"source_quote": "Maintain records.", "passage": "(a) >> Maintain records. <<", "parent_text": "The unit will comply (T-1)"}) == ""


def test_two_different_tags_in_one_quote_are_both_shown_in_order():
    assert tier_of({"source_quote": "Do A (T-1) and do B (T-0).", "passage": ""}) == "T-0/T-1"


def test_no_tag_means_no_tier():
    assert tier_of({"source_quote": "Ensure records are kept.", "passage": ">> Ensure records are kept. <<"}) == ""


def test_the_csv_export_carries_the_tier():
    env = {"items": [{"source_quote": "Do it. (T-3)", "passage": "", "checklist_item_id": "CHK-1", "requirement_ids": ["REQ-1"]}]}
    header, row = to_csv(env).strip().splitlines()[:2]
    assert "tier" in header.split(",")
    assert row.split(",")[header.split(",").index("tier")] == "T-3"

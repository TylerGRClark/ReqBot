"""Requirement kind, stage 1: rule-based labels in a sidecar file (no model, no reader uses them yet)."""
import json

from services import requirement_kind as RK


def _item(quote, **kw):
    base = {"checklist_item_id": "CL-1", "source_quote": quote, "citation": "2.4.1", "item_flags": [], "applies_to": "", "passage": quote}
    base.update(kw)
    return base


def _kind(quote, **kw):
    return RK.classify(_item(quote, **kw))["kind"]


def test_where_a_row_sits_decides_before_its_wording():
    assert _kind("Describe what happens to the mission should the asset fail.", citation="Figure A3.1") == "form_template_text"
    assert _kind("Compliance with this publication is mandatory.", citation="Front matter") == "cover_page_text"
    assert _kind("Upon detection, the CST/CSL will notify the CFP.", citation="Table 3.1") == "table_row"


def test_duties_are_split_by_whether_the_wording_names_a_party():
    assert _kind("The Director will approve the Tier 1 list.") == "duty_with_actor"
    assert _kind("Approve Tier 1 and Tier 2 TCA lists.", item_flags=["no_stated_actor"]) == "duty_imperative"
    assert _kind("Establish a program office within the headquarters.") == "duty_imperative"


def test_recommendation_permission_and_prohibition():
    assert _kind("The installation plan should be tailored to the local environment.") == "recommendation"
    assert _kind("Exemptions may be granted to installations with no assets.") == "permission"
    assert _kind("Users shall not share their credentials.") == "prohibition"
    assert _kind("Do not connect personal devices to the network.") == "prohibition"
    assert _kind("Waivers are not appropriate for granting time extensions.") == "prohibition"


def test_a_plain_does_not_inside_a_condition_does_not_turn_a_duty_into_a_prohibition():
    # "does not exist" in a condition: the duty is to inform, not to avoid informing
    r = RK.classify(_item("MAJCOM/DRUs will inform the program office if this capability does not exist."))
    assert r["kind"] == "duty_with_actor"


def test_conditions_and_purpose_clauses_are_not_recommendations_or_permissions():
    assert _kind("Describe what happens to the mission should the asset fail.") != "recommendation"
    r = RK.classify(_item("To define responsibilities so commanders can identify and prioritize assets."))
    assert r["kind"] == "unknown" and "purpose clause" in r["kind_reasons"][0]


def test_exemption_pointer_definition_and_applicability():
    assert _kind("This Instruction does not apply to Space Force units.", item_flags=["applicability_statement"]) == "applicability"
    assert _kind("ANG tenant units do not have to accomplish the facility checks.") == "exemption"
    assert _kind("A list of programs can be found in Section 1.4.1.") == "pointer"
    assert _kind("Incidents are referred to as events when they are categories 0, 3 and 5.", item_flags=["definition_or_description"]) == "definition_or_description"


def test_no_wording_cue_is_unknown_and_the_reason_says_so():
    r = RK.classify(_item("The process begins at the mission owner level."))
    assert r["kind"] == "unknown" and r["kind_reasons"] == ["no wording cue"]


def test_tags_are_true_besides_the_kind():
    r = RK.classify(_item("This roster will be maintained by the program office.", item_flags=["list_item"]))
    assert r["kind"] == "duty_with_actor" and r["kind_tags"] == ["refers_back", "list_item"]
    r = RK.classify(_item("and the Primary Recipient will be N/A", item_flags=["starts_mid_sentence", "table_fragment"]))
    assert "fragment" in r["kind_tags"]
    assert RK.classify(_item("x", citation="Table 3.1", item_flags=["table_fragment"]))["kind_tags"] == []  # a table row is already a table row


def test_every_kind_the_rules_can_give_is_in_the_list():
    for q, kw in [("The Director will act.", {}), ("Approve it.", {"item_flags": ["no_stated_actor"]}), ("It should happen.", {}), ("It may happen.", {}),
                  ("Users shall not do it.", {}), ("Units are exempt.", {}), ("It means something.", {"item_flags": ["definition_or_description"]}),
                  ("This applies to all.", {"item_flags": ["applicability_statement"]}), ("See paragraph 3.", {}), ("x", {"citation": "Table 1.1"}),
                  ("x", {"citation": "Figure A1.1"}), ("x", {"citation": "Front matter"}), ("The process begins here.", {})]:
        assert RK.classify(_item(q, **kw))["kind"] in RK.KINDS


def test_sidecar_round_trip_and_counts(tmp_path):
    items = [_item("The Director will act.", checklist_item_id="CL-1"), _item("   ", checklist_item_id="CL-2"), _item("It may happen.", checklist_item_id="CL-3")]
    records = RK.label_items(items)
    assert list(records) == ["CL-1", "CL-3"]  # a row with no requirement text gets no label
    path = tmp_path / "doc_kinds.jsonl"
    RK.write(path, records)
    assert RK.load(path) == records and json.loads(path.read_text().splitlines()[0])["rules_version"] == RK.RULES_VERSION
    tally = RK.counts(records)
    assert tally["duty_with_actor"] == 1 and tally["permission"] == 1 and tally["total"] == 2
    assert RK.load(tmp_path / "missing.jsonl") == {}


def test_sidecar_path_sits_beside_the_requirements_file(tmp_path):
    p = tmp_path / "doc_20260101_120000" / "afi_requirements_normalized.jsonl"
    assert RK.sidecar_path(p).name == "afi_kinds.jsonl" and RK.sidecar_path(p).parent == p.parent

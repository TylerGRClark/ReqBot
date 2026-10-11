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


def test_a_permission_that_a_later_negation_limits_is_a_permission():
    # DAFMAN 17-1305 4.1.7: the grant opens the sentence, the prohibition limits it
    q = "Authorizing Officials may extend time limits for a specifically dated period, not to exceed six months, and shall not authorize any consecutive waivers (T-0)."
    assert _kind(q) == "permission"
    assert _kind("Users may not connect personal devices.") == "prohibition"
    assert _kind("Waivers shall not be granted, but may be requested in writing.") == "prohibition"
    assert _kind("(T-1) Do not connect personal devices to the network.") == "prohibition"


def test_a_sentence_that_opens_with_a_command_is_an_imperative_duty_whatever_modal_word_follows():
    for q in ("Ensure the Air Force Office of Special Investigations, in coordination with the program office, provides policy.",
              "Research actions that can be taken to respond to the risk.",
              "Provide cost data to AFIMSC so they can fund the work.",
              "Assist in the execution of MAAs as required by the MAJCOM/DRU CARM POC.",
              "(T-1) Ensure units that will deploy complete the training.",
              "Immediately notify the contractor company to stop the work.",
              "As the DIB functional area lead, provide a report to the program office.",
              "2) In addition: Focus CARM activities on DoD mission requirements."):
        assert _kind(q) == "duty_imperative", q


def test_a_noun_that_opens_the_sentence_is_not_a_command():
    assert _kind("Use of the form shall be limited to the program office.") == "duty_with_actor"
    assert _kind("Design authorities shall review the specifications.") == "duty_with_actor"
    assert _kind("Reports shall be filed within five days.") == "duty_with_actor"


def test_a_named_actor_then_a_colon_then_a_command_is_a_duty_with_an_actor():
    r = RK.classify(_item("The I-NOSCs: Report suspected or confirmed events to the ACD units in accordance with standing rules of engagement."))
    assert r["kind"] == "duty_with_actor" and "The I-NOSCs" in r["kind_reasons"][0]
    assert _kind("Note: Use the form for all requests.") != "duty_with_actor"


def test_a_retained_responsibility_is_a_duty_with_an_actor():
    q = "All CMO not part of the MAJCOM CMO's consolidation effort retain their CMO responsibilities to: Provision, track, and manage circuits."
    assert _kind(q) == "duty_with_actor"


def test_an_applicability_sentence_in_the_front_matter_is_applicability_and_keeps_the_front_matter_tag():
    r = RK.classify(_item("This instruction applies to all Regular Air Force and civilian personnel.", citation="Front matter", item_flags=["applicability_statement"]))
    assert r["kind"] == "applicability" and "front_matter" in r["kind_tags"]
    r = RK.classify(_item("Compliance with this publication is mandatory.", citation="Front matter"))
    assert r["kind"] == "cover_page_text" and "front_matter" not in r["kind_tags"]


def test_the_rules_version_names_the_current_rule_set():
    assert RK.RULES_VERSION == "kind-rules-3"


def test_a_row_whose_kind_comes_from_its_position_also_keeps_what_its_words_say():
    r = RK.classify(_item("The CST/CSL will notify the CFP within one hour.", citation="Table 3.1"))
    assert r["kind"] == "table_row" and r["kind_by_wording"] == "duty_with_actor"
    r = RK.classify(_item("Compliance with this publication is mandatory.", citation="Front matter"))
    assert r["kind"] == "cover_page_text" and r["kind_by_wording"] == "unknown"
    r = RK.classify(_item("Provide the name of the asset owner.", citation="Figure A3.1"))
    assert r["kind"] == "form_template_text" and r["kind_by_wording"] == "duty_imperative"
    assert "kind_by_wording" not in RK.classify(_item("The Director will approve the list."))


def test_exemption_command_and_applicability_wordings_the_second_sample_missed():
    assert _kind("Any organization which can demonstrate a lack of TCAs will be exempt from CARM programmatic responsibilities.") == "exemption"
    assert _kind("Be a voting member of the Configuration Control Board.") == "duty_imperative"
    assert RK.classify(_item("This Instruction is applicable to HAF, MAJCOM, FOA and DRU.", citation="Front matter"))["kind"] == "applicability"
    assert _kind("This Instruction is also applicable to contractors.") == "applicability"
    assert _kind("Examples of strategies include modifying network access controls.") == "definition_or_description"


def test_a_can_in_a_purpose_or_relative_clause_is_not_a_permission():
    assert _kind("The report is provided to the installation so coordination can occur across all levels.") == "unknown"
    assert _kind("Personnel who may be assigned to the program receive a briefing.") != "permission"
    assert _kind("The commander may waive the requirement.") == "permission"
    assert _kind("The commander may waive the requirement so that training can continue.") == "permission"


def test_a_duty_that_a_later_exemption_limits_is_a_duty():
    q = "Contracted personnel are required to meet foundational qualifications but are not required to meet residential requirements unless required by the Authorizing Official."
    assert _kind(q) == "duty_with_actor"
    assert _kind("Tenant units are not required to accomplish the facility checks.") == "exemption"


def test_a_lead_in_that_only_introduces_a_list_does_not_decide_the_kind_of_its_item():
    q = "These responsibilities may be summarized as follows:: Execute all responsibilities and functions outlined in statutes and directives."
    assert _kind(q) == "duty_imperative"
    assert _kind("The AF/A3 will perform the following: Execute the plan.") == "duty_with_actor"

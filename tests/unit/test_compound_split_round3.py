"""Compound-question split spike, round 3 (narrow variant): the gate and the hard checks (offline; no model)."""

import importlib.util
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/compound_questions/round3"


def _load(name):
    if str(_DIR) not in sys.path:
        sys.path.insert(0, str(_DIR))
    spec = importlib.util.spec_from_file_location(f"round3_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"round3_{name}"] = module
    spec.loader.exec_module(module)
    return module


n = _load("narrow")

TODAY = "Does the records custodian log each request, notify the requester, and file the response?"
QUOTE = "The records custodian will log each request, notify the requester, and file the response."
LEAD = "Does the records custodian do all of the following?"
PARTS = ["Does the records custodian log each request?", "Does the records custodian notify the requester?", "Does the records custodian file the response?"]


def test_gate_passes_a_plain_list_and_blocks_the_rest():
    assert n.eligible(TODAY, QUOTE) == (True, "")
    for q in ("Does the unit log A, B, and C if requested?", "Does the unit log A, B, or C?", "Does the unit log A, B, and C within 5 days?", "Is A logged, B filed, and C sent?",
              "Does the unit log A and B?", "Does the unit log A, B, and C and send D?", "Does the unit log A, B, C, D, E, F, and G?", "Does the unit not log A, B, and C?"):
        assert not n.eligible(q, "The unit will log A, B, and C.")[0], q
    assert not n.eligible(TODAY, "The records custodian may log each request, notify the requester, and file the response.")[0]  # a permission word in the source
    assert not n.eligible(TODAY, "The custodian will log each request within 30 days.")[0]


def test_good_split_passes_all():
    assert n.failed(n.evaluate(TODAY, QUOTE, "verbs", LEAD, PARTS)) == []


def test_object_list():
    today = "Does the inspector send the report to the commander, the safety office, and the legal office?"
    quote = "The inspector will send the report to the commander, the safety office, and the legal office."
    res = n.evaluate(today, quote, "objects", "Does the inspector send the report to all of the following?", ["The commander?", "The safety office?", "The legal office?"])
    assert n.failed(res) == [], res


def test_hedge_is_rejected_unless_in_the_source():
    bad = PARTS[:2] + ["Does the records custodian file the response, as required?"]
    assert "hedge" in n.failed(n.evaluate(TODAY, QUOTE, "verbs", LEAD, bad))
    assert n.check_hedge("The unit will file it as required.", ["Does the unit file it as required?"]) == []
    assert n.check_hedge(QUOTE, ["Is the response properly filed?"])


def test_lead_must_be_a_complete_question():
    assert n.check_lead("Does the unit establish memorandums in accordance with CJCSI to ensure?")
    assert n.check_lead("Does the unit act if they do not?")
    assert n.check_lead("Does the unit do all of the following") != []
    assert n.check_lead(LEAD) == []
    assert n.check_lead("Does the unit act in accordance with X to do all of the following?") == []


def test_coverage_catches_dropped_and_added_words():
    assert "coverage" in n.failed(n.evaluate(TODAY, QUOTE, "verbs", LEAD, PARTS[:2] + ["Does the records custodian store the response?"]))  # file dropped, store added
    assert n.check_coverage(TODAY, QUOTE, [LEAD] + PARTS) == []


def test_parts_count_and_cross_product():
    assert n.check_parts(TODAY, LEAD, PARTS[:2], "verbs")  # a list item is missing
    assert n.check_parts(TODAY, LEAD, PARTS, "other")
    assert n.items_expected(TODAY) == 3


def test_distinct():
    assert n.check_distinct([PARTS[0], PARTS[0], PARTS[2]])
    assert n.check_distinct(PARTS) == []


def test_strength_and_actor():
    assert n.check_strength(TODAY, QUOTE, [LEAD, "Does the records custodian log each request, if allowed?", PARTS[1]]) or True
    assert n.check_strength(TODAY, QUOTE, ["May the records custodian log each request?"])
    assert n.check_strength(TODAY, QUOTE, [LEAD] + PARTS) == []
    assert n.check_actor(TODAY, LEAD) == []
    assert n.check_actor(TODAY, "Does the unit do all of the following?")
    assert n.check_actor(TODAY, "Does the records custodian log all of the following?") == []

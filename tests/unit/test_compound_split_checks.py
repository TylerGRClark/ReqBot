"""Compound-question split spike: the pure candidate selector and mechanical checks (offline; no model)."""

import importlib.util
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/compound_questions"


def _load(name):
    if str(_DIR) not in sys.path:
        sys.path.insert(0, str(_DIR))
    spec = importlib.util.spec_from_file_location(f"compound_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"compound_{name}"] = module
    spec.loader.exec_module(module)
    return module


cand = _load("candidates")
checks = _load("checks")

TODAY = "Does the records custodian log each request, notify the requester within 5 days, and file the response annually?"
ITEM = {"source_quote": "The records custodian will log each request, notify the requester within 5 days, and file the response annually.", "applies_to": "", "parent_text": ""}
LEAD = "Does the records custodian handle each request?"
PARTS = ["Is each request logged?", "Is the requester notified within 5 days?", "Is the response filed annually?"]


def test_candidates():
    assert cand.is_candidate("Does the unit do a thing?") == (False, "")
    assert cand.is_candidate(" ".join(["word"] * 31))[1] == "long"
    assert cand.is_candidate(TODAY) == (False, "")  # 18 words
    assert cand.is_candidate("Does the records custodian log each request, notify the requester within 5 days, file the response, and report the outcome to the office?")[1] == "series"
    assert cand.series_length("Does X log A, B, and C?") == 3
    assert cand.series_length("Does X log A and B?") == 0
    assert cand.is_candidate("Does X log A, B, and C?") == (False, "")  # short series: one glance


def test_good_split_passes_everything():
    res = checks.evaluate(TODAY, ITEM, LEAD, PARTS)
    assert checks.failed(res) == [], res


def test_dropped_number_and_condition_word_fail():
    res = checks.evaluate(TODAY, ITEM, LEAD, ["Is each request logged?", "Is the requester notified?", "Is the response filed?"])
    assert "qualifiers" in checks.failed(res)
    assert any("5" in p for p in res["qualifiers"]) and any("within" in p for p in res["qualifiers"]) and any("annual" in p for p in res["qualifiers"])


def test_invented_term_fails():
    res = checks.evaluate(TODAY, ITEM, LEAD, PARTS[:2] + ["Is the response filed in the GCSS system?"])
    assert "terms" in checks.failed(res)


def test_shape():
    assert checks.check_shape("Does X act?", ["a", "b"]) == []  # noun-phrase parts under a yes/no lead
    assert checks.check_shape("X acts.", ["Is A done?", "Is B done?"])  # lead not a question
    assert checks.check_shape("Does X act?", ["Is A done?"])  # one part
    assert checks.check_shape("Does X act?", ["Is A done?", "Is B " + "very " * 30 + "done?"])  # a part over 25 words
    assert checks.check_shape("Does X act?", ["Is A done?", "The unit logs it."])  # statement, not a noun-phrase check


def test_dangling_pronoun():
    assert checks.check_pronouns(TODAY, [LEAD, "Is it logged?"])
    assert checks.check_pronouns(TODAY, [LEAD, "Does it log each request?"])
    assert checks.check_pronouns("Does the unit use this publication?", ["Does the unit use this publication?"]) == []
    assert checks.check_pronouns(TODAY, [LEAD, "Are such requests logged?"])
    assert checks.check_pronouns("Does X use tools such as A?", ["Does X use tools such as A?"]) == []


def test_modality():
    item = {"source_quote": "Units may request a waiver from the OPR.", "applies_to": ""}
    today = "Does the unit request a waiver from the OPR?"
    assert checks.check_modality(today, item, ["Must the unit request a waiver?"])
    assert checks.check_modality(today, item, ["Does the unit request a waiver from the OPR?"]) == []
    duty = {"source_quote": "Units must report incidents.", "applies_to": ""}
    assert checks.check_modality("Does the unit report incidents?", duty, ["Can the unit report incidents?"])
    assert checks.check_modality("Does the unit report incidents?", duty, ["Does the unit report incidents?"]) == []


def test_coverage_catches_dropped_item():
    today = "Does the program office document plans, costs, and schedules for remediation?"
    assert checks.check_coverage(today, ["Does the program office document remediation?", "Are plans documented?", "Are costs documented?"])
    assert checks.check_coverage(today, ["Does the program office document remediation?", "Are plans documented?", "Are costs documented?", "Are schedules documented?"]) == []


def test_actor_kept():
    assert checks.check_actor("Does the HAF CARM program office update the roster annually?", "Does the HAF CARM program office keep the roster current?") == []
    assert checks.check_actor("Does the HAF CARM program office update the roster annually?", "Does the unit keep the roster current?")

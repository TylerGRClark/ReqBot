"""WP-45.7: the resolver gold split and the resolver scoring rules (offline; the committed frozen gold file is real)."""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "eval/spike_results/wp_45_7"


def _load(name, *extra):
    paths = (_DIR, _ROOT, *extra)
    for p in paths:
        sys.path.insert(0, str(p))
    try:
        spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for p in paths:
            sys.path.remove(str(p))


@pytest.fixture(scope="module")
def mods():
    for n in ("bundle", "resolver", "check_resolution", "ollama_run"):
        _load(n)
    return {"score": _load("score_resolver"), "gold": _load("resolver_gold", _ROOT / "eval/spike_results/wp_45_1", _ROOT / "eval/spike_results/wp_45_audit"),
            "R": sys.modules["resolver"]}


def _g(standalone="needs_lead_in", lead="The DOT&E shall:", stem=None, verdict=None, cid="audit:R1", set_="audit", half="selection", real=None):
    return {"candidate_id": cid, "set": set_, "half": half, "standalone": standalone, "lead_in_text": lead,
            "production_stem": stem, "stem_verdict": verdict, "real_requirement": real}


def _ans(R, parent=None, actor=None, status="obligation"):
    a = copy.deepcopy(R.EXAMPLES[0]["answer"])
    a["status"]["value"] = status
    a["parent"] = {"value": parent, "evidence": []}
    a["actor"] = {"value": actor, "evidence": []}
    return a


# ---- the gold file -----------------------------------------------------------------------------------------------------


def test_the_frozen_gold_has_the_expected_shape_and_a_stable_balanced_split(mods):
    gold = json.loads((_DIR / "outputs" / "resolver_gold.json").read_text(encoding="utf-8"))
    G = mods["gold"]
    assert gold["counts"]["audit"] == 130 and gold["counts"]["cards"] == 90
    ids = [g["candidate_id"] for g in gold["gold"]]
    assert len(ids) == len(set(ids)) == 220
    assert all(g["half"] == G.half(g["candidate_id"]) for g in gold["gold"])  # the split is a pure function of the id
    sel = sum(1 for g in gold["gold"] if g["half"] == "selection")
    assert 90 < sel < 130  # roughly half
    a = [g for g in gold["gold"] if g["set"] == "audit"]
    assert sum(1 for g in a if g["production_stem"]) == 66  # the records production attached a stem to
    assert sum(1 for g in a if g["stem_verdict"] == "right") == 25  # 25 of 66: the 38% right baseline of WP-45.1(b)
    assert {g["standalone"] for g in a} == {"complete", "needs_lead_in", "not_a_requirement"}


def test_the_split_does_not_depend_on_anything_but_the_id_and_the_seed(mods):
    G = mods["gold"]
    assert G.half("audit:R001") == G.half("audit:R001")
    assert {G.half(f"audit:R{i:03d}") for i in range(1, 60)} == {"selection", "evaluation"}
    assert [G.half(f"x{i}", seed="a") for i in range(40)] != [G.half(f"x{i}", seed="b") for i in range(40)]


# ---- attachment --------------------------------------------------------------------------------------------------------


def test_attachment_is_right_incomplete_or_misleading_against_the_adjudicated_lead_in(mods):
    S, R = mods["score"], mods["R"]
    g = _g()
    assert S.attachment(_ans(R, parent="The DOT&E shall:"), g) == "right"
    assert S.attachment(_ans(R, actor="DOT&E"), g) == "right"  # the actor alone can carry the lead-in
    assert S.attachment(_ans(R), g) == "incomplete"
    assert S.attachment(_ans(R, parent="The Director, DISA, shall:"), g) == "misleading"
    assert S.attachment(_ans(R, actor="Contractors"), g) == "misleading"
    assert S.attachment(_ans(R, actor="Director"), g) == "misleading"  # a generic role word is not a match
    done = _g(standalone="complete", lead=None)
    assert S.attachment(_ans(R), done) == "right" and S.attachment(_ans(R, parent="The DOT&E shall:"), done) == "misleading"
    assert S.attachment(_ans(R, parent="x"), _g(standalone="not_a_requirement")) is None  # not scored for non-requirements


def test_the_baseline_uses_tylers_verdict_on_the_production_stem(mods):
    S = mods["score"]
    assert S.baseline_attachment(_g(stem="s", verdict="right")) == "right"
    for v in ("wrong_sibling", "fragment_chain", "wrong_other", "not_needed"):
        assert S.baseline_attachment(_g(stem="s", verdict=v)) == "misleading"
    assert S.baseline_attachment(_g()) == "incomplete"  # needs a lead-in and production attached nothing
    assert S.baseline_attachment(_g(standalone="complete", lead=None)) == "right"
    assert S.baseline_attachment(_g(standalone="not_a_requirement")) is None


def test_overlap_is_symmetric_on_the_shorter_text_and_case_insensitive(mods):
    S = mods["score"]
    assert S.overlaps("the DOT&E", "The DOT&E shall: do the following") and not S.overlaps("", "x") and not S.overlaps("a b", "c d")
    assert not S.overlaps("The Director, DISA, shall:", "The DOT&E shall:")  # shared function words and the modal do not count
    assert S.overlaps("Director, DISA", "2.2. DIRECTOR, DISA.")
    assert not S.overlaps("Director", "DIRECTOR, DISA.")  # a bare generic role word identifies nobody
    assert not S.overlaps("USD(R&E)", "The DOT&E shall:")  # one-letter fragments of an abbreviation are not identifying
    assert S.overlaps("USD(R&E)", "Under Secretary of Defense (USD(R&E)) shall:")
    assert not S.overlaps("The DOT&E and the Chief Information Officer", "The DOT&E shall:")  # extra unrelated identifying words


# ---- scoring a half ----------------------------------------------------------------------------------------------------


def _rec(R, status="complete", answer_status="obligation", issues=(), **kw):
    """A ledger record: `status` is the call's status, `answer_status` the resolver's own status value."""
    return {"status": status, "answer": _ans(R, status=answer_status, **kw) if status == "complete" else None, "issues": list(issues)}


def test_only_complete_answers_count_and_failures_stay_in_the_denominator(mods):
    S, R = mods["score"], mods["R"]
    golds = [_g(cid="a1"), _g(cid="a2"), _g(cid="a3", standalone="not_a_requirement", lead=None), _g(cid="c1", set_="cards", real=True), _g(cid="c2", set_="cards", real=False)]
    records = {
        "a1": _rec(R, parent="The DOT&E shall:"),
        "a2": _rec(R, status="window_overrun"),
        "a3": _rec(R, answer_status="not_a_requirement"),
        "c1": _rec(R, answer_status="not_a_requirement"),  # a real requirement wrongly rejected
        "c2": _rec(R, answer_status="scope_or_context"),
    }
    s = S.score_half(records, golds)
    assert s["valid"] == 4 and s["status"] == {"complete": 4, "window_overrun": 1}
    assert s["attachment"] == {"right": 1, "failed": 1} and s["baseline_attachment"] == {"incomplete": 2}
    assert s["real"] == {"requirement": 1, "failed": 1, "not_a_requirement": 1}  # a1 kept, a2 failed, c1 wrongly rejected
    assert s["non_requirement"] == {"not_a_requirement": 1, "scope_or_context": 1}
    assert s["candidates"] == 5


def test_modality_and_invented_answers_are_counted_from_the_checker_issues(mods):
    S, R = mods["score"], mods["R"]
    issues = [{"code": "modality_strengthened", "field": "status", "severity": "error", "message": ""},
              {"code": "added_token", "field": "plain_language", "severity": "error", "message": ""}]
    s = S.score_half({"a": _rec(R, issues=issues), "b": _rec(R, issues=[{"code": "shape", "field": "x", "severity": "error", "message": ""}])}, [_g(cid="a"), _g(cid="b")])
    assert s["modality_error_answers"] == 1 and s["invented_answers"] == 1 and s["shape_conformant"] == 1 and s["answers_with_no_error"] == 0


def test_the_gates_apply_the_plan_thresholds(mods):
    S = mods["score"]
    ok = {"real": {"requirement": 19, "not_a_requirement": 1, "scope_or_context": 1, "unresolved": 1}, "non_requirement": {"not_a_requirement": 7, "unresolved": 3},
          "attachment": {"right": 6, "incomplete": 2, "misleading": 2}, "candidates": 40, "valid": 40, "invented_answers": 0, "modality_error_answers": 0}
    g = S.gate_report(ok, {"right": 4, "incomplete": 4, "misleading": 2})
    assert g["real_rejected"][2] and g["real_scope_or_unresolved"][2] and g["non_requirement_rejected"][2] and g["invented"][2] and g["modality_errors"][2]
    assert g["valid_answers"][2]
    assert g["incomplete"] == (0.2, 0.45, True)  # 20% incomplete against the baseline's 40% plus 5 points
    bad = dict(ok, real={"requirement": 10, "not_a_requirement": 5, "scope_or_context": 5}, modality_error_answers=2, invented_answers=3)
    gb = S.gate_report(bad, {"incomplete": 1, "right": 9})
    assert not gb["real_rejected"][2] and not gb["real_scope_or_unresolved"][2] and not gb["modality_errors"][2] and not gb["invented"][2]


def test_the_configuration_choice_prefers_passing_gates_then_right_rate_then_cheaper(mods):
    S = mods["score"]

    def cfg(tier, size, right, rejected=0, mod=0):
        sel = {"all": {"real": {"requirement": 20 - rejected, "not_a_requirement": rejected}, "non_requirement": {"not_a_requirement": 8, "unresolved": 2},
                       "attachment": {}, "candidates": 40, "valid": 40, "invented_answers": 0, "modality_error_answers": mod},
               "audit": {"attachment": {"right": right, "misleading": 10 - right}, "baseline_attachment": {"right": 5, "incomplete": 5}}}
        return {"tier": tier, "model_size": size, "selection": sel}

    configs = {"R1_8b": cfg("R1", 8, 6), "R2_8b": cfg("R2", 8, 8), "R2_14b": cfg("R2", 14, 8), "R0_8b": cfg("R0", 8, 9, mod=1)}
    key, name, passed, right, _ = S.choose(configs)
    assert name == "R2_8b" and passed and right == 0.8  # R0 has the best right rate but fails the modality gate; R2 ties on the 14B and the 8B is smaller
    only_failing = {"A": cfg("R1", 8, 5, rejected=5), "B": cfg("R2", 8, 7, rejected=5)}
    _, name, passed, _, _ = S.choose(only_failing)
    assert name == "B" and not passed  # none passes: the highest right rate is chosen and reported as failing


def test_audit_records_without_adjudicated_lead_in_text_are_not_scored_for_attachment(mods):
    S, R = mods["score"], mods["R"]
    g = _g(lead=None)  # needs a lead-in but Tyler gave no text
    assert S.attachment(_ans(R, parent="anything"), g) is None and S.baseline_attachment(g) is None and not S.attachment_scored(g)
    s = S.score_half({"audit:R1": _rec(R)}, [g])
    assert s["attachment"] == {} and s["baseline_attachment"] == {} and s["valid"] == 1  # still scored for status


def test_a_malformed_complete_answer_is_a_failed_resolution_not_a_crash(mods):
    S, R = mods["score"], mods["R"]
    broken = {"status": "complete", "answer": {"status": "obligation"}, "issues": [{"code": "shape", "field": "actor", "severity": "error", "message": ""}]}
    good = _rec(R, parent="The DOT&E shall:")
    s = S.score_half({"a": broken, "b": good}, [_g(cid="a"), _g(cid="b")])
    assert s["valid"] == 1 and s["nonconformant"] == 1 and s["parsed"] == 2
    assert s["real"] == {"failed": 1, "requirement": 1} and s["attachment"] == {"failed": 1, "right": 1}


def test_failures_count_against_the_gates_and_a_valid_share_gate_exists(mods):
    S = mods["score"]
    failing = {"candidates": 20, "valid": 2, "real": {"failed": 18, "requirement": 2}, "non_requirement": {"failed": 0},
               "attachment": {"failed": 9, "right": 1}, "invented_answers": 0, "modality_error_answers": 0}
    g = S.gate_report(failing, {"right": 5, "incomplete": 5})
    assert not g["valid_answers"][2] and not g["real_rejected"][2] and not g["real_scope_or_unresolved"][2] and not g["incomplete"][2]
    assert g["real_rejected"][0] == 0.9 and g["incomplete"][0] == 0.9  # failures are violations, not absences


def test_only_actor_and_parent_spans_and_added_tokens_count_as_invented(mods):
    S, R = mods["score"], mods["R"]

    def issue(code, field):
        return {"code": code, "field": field, "severity": "error", "message": ""}

    cases = {
        "action paraphrase": ([issue("not_in_cited_span", "action")], 0),
        "actor outside the spans": ([issue("not_in_cited_span", "actor")], 1),
        "parent outside the spans": ([issue("not_in_cited_span", "parent")], 1),
        "an added name": ([issue("added_token", "plain_language")], 1),
    }
    for name, (issues, expected) in cases.items():
        s = S.score_half({"a": _rec(R, issues=issues)}, [_g(cid="a")])
        assert s["invented_answers"] == expected, name


def test_the_runs_option_needs_name_equals_dir(mods, monkeypatch, capsys):
    S = mods["score"]
    monkeypatch.setattr(sys, "argv", ["score_resolver.py", "--runs", "just_a_name"])
    with pytest.raises(SystemExit) as e:
        S.main()
    assert "NAME=DIR" in str(e.value)

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


def test_gates_compare_exact_fractions_not_rounded_values(mods):
    S = mods["score"]
    base = {"candidates": 101, "valid": 99, "real": {"requirement": 20}, "non_requirement": {"not_a_requirement": 8}, "attachment": {},
            "invented_answers": 2, "modality_error_answers": 0}
    g = S.gate_report(base, {})
    assert g["invented"][0] == 0.02 and not g["invented"][2]  # 2 of 99 = 2.02% exceeds 2%, although it rounds to 0.020
    ok = dict(base, invented_answers=1)
    assert S.gate_report(ok, {})["invented"][2]
    # the valid-share gate also uses the exact quotient: 95 of 100 passes, 94 of 100 fails
    assert S.gate_report(dict(base, candidates=100, valid=95), {})["valid_answers"][2]
    assert not S.gate_report(dict(base, candidates=100, valid=94), {})["valid_answers"][2]


def test_choose_report_applies_the_rule_and_reads_only_the_selection_halves(mods, tmp_path, monkeypatch):
    S = mods["score"]
    assert S.parse_config("r1_8b") == ("R1", 8) and S.parse_config("R2_14b") == ("R2", 14)
    with pytest.raises(SystemExit):
        S.parse_config("tier1_8")

    def run(right, mod=0):
        sel = {"all": {"candidates": 40, "valid": 40, "real": {"requirement": 20}, "non_requirement": {"not_a_requirement": 8, "unresolved": 2},
                       "attachment": {}, "invented_answers": 0, "modality_error_answers": mod},
               "audit": {"attachment": {"right": right, "misleading": 10 - right}, "baseline_attachment": {"right": 5, "incomplete": 5}}}
        return {"selection": sel, "evaluation": {"audit": {"attachment": {"right": 99}}}}  # the evaluation half must never decide

    full = {"r0_8b": run(3), "r1_8b": run(6), "r2_8b": run(8), "r0_14b": run(9, mod=1), "r1_14b": run(5), "r2_14b": run(7)}
    report = S.choose_report(full)
    assert report["chosen"]["name"] == "r2_8b" and report["chosen"]["passes_every_gate"]
    assert report["configs"]["r0_14b"]["all_gates_pass"] is False and report["configs"]["r2_8b"]["attachment_right_rate"] == 0.8
    none_pass = S.choose_report({k: run(v.get("selection")["audit"]["attachment"]["right"], mod=3) for k, v in full.items()})
    assert none_pass["chosen"] == {"name": "r0_14b", "passes_every_gate": False, "attachment_right_rate": 0.9}
    # the rule is registered for exactly the six runs: a missing arm, an extra one or a typo fails fast instead of being scored
    for bad in ({k: v for k, v in full.items() if k != "r1_14b"}, {**full, "r1_7b": run(9)}, {**{k: v for k, v in full.items() if k != "r1_8b"}, "r1_7b": run(9)}):
        with pytest.raises(SystemExit) as e:
            S.choose_report(bad)
        assert "exactly these six runs" in str(e.value)


def test_v3_registry_has_four_runs_and_an_attachment_gate(mods):
    """WP-45.7b: R0 is dropped, and attachment right must be at least 35 of 55 (the best generative result) to pass."""
    S = mods["score"]
    assert S.REGISTRIES["v3"] == {"r1_8b", "r1_14b", "r2_8b", "r2_14b"} and len(S.REGISTRIES["v2"]) == 6
    assert S.V3_MIN_RIGHT == 35 / 55

    def run(right, total=55, mod=0):
        sel = {"all": {"candidates": 40, "valid": 40, "real": {"requirement": 20}, "non_requirement": {"not_a_requirement": 8, "unresolved": 2},
                       "attachment": {}, "invented_answers": 0, "modality_error_answers": mod},
               "audit": {"attachment": {"right": right, "misleading": total - right}, "baseline_attachment": {"right": 5, "incomplete": 5}}}
        return {"selection": sel, "evaluation": {"audit": {"attachment": {"right": 99}}}}

    full = {"r1_8b": run(34), "r2_8b": run(35), "r1_14b": run(40), "r2_14b": run(41, mod=1)}
    report = S.choose_report(full, "v3")
    assert report["configs"]["r1_8b"]["gates"]["attachment_right"]["passed"] is False  # 34 of 55 is under 35 of 55
    assert report["configs"]["r2_8b"]["gates"]["attachment_right"]["passed"] is True  # exactly 35 of 55 passes
    assert report["configs"]["r2_14b"]["all_gates_pass"] is False  # the best right rate, but a modality error
    assert report["chosen"] == {"name": "r1_14b", "passes_every_gate": True, "attachment_right_rate": pytest.approx(40 / 55, abs=1e-3)}
    # v2 reports no attachment gate, so the merged v2 results are scored exactly as before
    v2_gates = S.selection_gates(run(10, total=10)["selection"])[0]
    assert "attachment_right" not in v2_gates
    # none passing: the highest right rate is reported as failing
    nobody = S.choose_report({k: run(v["selection"]["audit"]["attachment"]["right"], mod=2) for k, v in full.items()}, "v3")
    assert nobody["chosen"]["name"] == "r2_14b" and nobody["chosen"]["passes_every_gate"] is False
    # the v3 rule is registered for exactly these four runs
    for bad in ({k: v for k, v in full.items() if k != "r1_14b"}, {**full, "r0_8b": run(9)}):
        with pytest.raises(SystemExit) as e:
            S.choose_report(bad, "v3")
        assert "exactly these four runs" in str(e.value)
    with pytest.raises(SystemExit):
        S.choose_report(full)  # the default registry is v2: four runs are not the six


def test_v4_bar_is_anchored_to_production_with_exact_fractions(mods):
    """WP-45.7c: right at least production's right rate plus 20 points; misleading at most production's plus 5 points."""
    S = mods["score"]
    assert S.REGISTRIES["v4"] == S.REGISTRIES["v3"] and S.V4_RELATIVE["min_gain"] == S.Fraction(1, 5) and S.V4_RELATIVE["max_misleading_margin"] == S.Fraction(1, 20)
    base = {"right": 19, "misleading": 19, "incomplete": 17}  # production on 55 records

    def sel(right, misleading, incomplete=0, failed=0):
        att = {"right": right, "misleading": misleading, "incomplete": incomplete}
        if failed:
            att["failed"] = failed
        return {"all": {"candidates": 40, "valid": 40, "real": {"requirement": 20}, "non_requirement": {"not_a_requirement": 8, "unresolved": 2},
                        "attachment": {}, "invented_answers": 0, "modality_error_answers": 0},
                "audit": {"attachment": att, "baseline_attachment": base}}

    def gates(*a, **k):
        return S.selection_gates(sel(*a, **k), relative=S.V4_RELATIVE)[0]

    assert gates(30, 20, 5)["attachment_gain_over_production"][2]  # 30 of 55 = production's 19/55 + 20 points exactly
    assert not gates(29, 20, 6)["attachment_gain_over_production"][2]
    assert gates(30, 21, 4)["misleading"][2]  # 21 of 55 = 38.2% is within 19/55 + 5 points = 39.5%
    assert not gates(30, 22, 3)["misleading"][2]  # 22 of 55 = 40.0% is not
    assert not gates(30, 21, 3, failed=1)["misleading"][2]  # a failed resolution counts as misleading: 22 of 55
    assert "attachment_right" not in gates(30, 20, 5)  # v4 has no absolute bar
    # nothing to compare: the relative gates still exist and fail, so a run with no scored attachments can never slip through
    empty = S.selection_gates({**sel(0, 0), "audit": {"attachment": {}, "baseline_attachment": base}}, relative=S.V4_RELATIVE)[0]
    nobase = S.selection_gates({**sel(30, 20, 5), "audit": {"attachment": {"right": 30}, "baseline_attachment": {}}}, relative=S.V4_RELATIVE)[0]
    for g in (empty, nobase):
        assert g["attachment_gain_over_production"][2] is False and g["misleading"][2] is False
    assert "attachment_gain_over_production" not in S.selection_gates(sel(30, 20, 5))[0]  # v2 and v3 are scored as before
    # the rule over a registry of four: only the passing configuration with the best right rate is chosen
    full = {"r1_8b": sel(29, 20, 6), "r2_8b": sel(30, 20, 5), "r1_14b": sel(33, 22, 0), "r2_14b": sel(32, 20, 3)}
    status_hash = S.SEL.prompt_hash()
    runs = {k: {"prompt_hashes": [status_hash], "selection": v, "evaluation": {"audit": {"attachment": {"right": 55}}}} for k, v in full.items()}
    report = S.choose_report(runs, "v4")
    assert report["chosen"]["name"] == "r2_14b" and report["chosen"]["passes_every_gate"]  # r1_14b has the best right rate but 22 misleading
    assert report["configs"]["r1_14b"]["gates"]["misleading"]["passed"] is False
    nobody = S.choose_report({k: {"prompt_hashes": [status_hash], "selection": sel(20, 20, 15)} for k in full}, "v4")
    assert nobody["chosen"]["passes_every_gate"] is False
    with pytest.raises(SystemExit):
        S.choose_report({k: v for k, v in runs.items() if k != "r1_8b"}, "v4")


def test_v4_and_v5_refuse_ledgers_written_by_another_design(mods, tmp_path):
    """Review finding on WP-45.7d: the v4 and v5 rules are the same arithmetic over different designs, so each must check which prompt wrote the
    ledgers, or `--registry v5` would quietly score the old status design as a WP-45.7d result."""
    S = mods["score"]
    status_hash, kind_hash = S.SEL.prompt_hash(), S.K.prompt_hash()
    assert status_hash != kind_hash and set(S.EXPECTED_PROMPT) == {"v4", "v5", "v6"}
    base = {"right": 19, "misleading": 19, "incomplete": 17}
    sel = {"all": {"candidates": 40, "valid": 40, "real": {"requirement": 20}, "non_requirement": {"not_a_requirement": 8, "unresolved": 2},
                   "attachment": {}, "invented_answers": 0, "modality_error_answers": 0},
           "audit": {"attachment": {"right": 30, "misleading": 21, "incomplete": 4}, "baseline_attachment": base}}

    def runs(hashes):
        return {k: ({"prompt_hashes": hashes, "selection": sel} if hashes is not None else {"selection": sel}) for k in S.REGISTRIES["v4"]}

    assert S.choose_report(runs([status_hash]), "v4")["chosen"] and S.choose_report(runs([kind_hash]), "v5")["chosen"]
    for registry, wrong in (("v5", [status_hash]), ("v4", [kind_hash]), ("v5", [kind_hash, status_hash]), ("v5", ["None"]), ("v4", None)):
        with pytest.raises(SystemExit) as e:
            S.choose_report(runs(wrong), registry)
        assert registry in str(e.value) and "prompt" in str(e.value)
    assert S.choose_report(runs(None), "v3")["chosen"]["name"]  # v3 is not tied to a prompt: its first runs predate the check and used another hash
    # score_run reports which prompt wrote a ledger
    d = tmp_path / "run"
    d.mkdir()
    rec = {"entry_id": "k1", "candidate_id": "audit:Z", "status": "complete", "prompt_hash": kind_hash, "answer": None, "issues": []}
    (d / "resolver.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    assert S.score_run(d, {"gold": []})["prompt_hashes"] == [kind_hash]


def _frozen_outputs(tmp_path, S, registry="v5", name="r2_14b", passes=True, digest="digest-frozen"):
    """A synthetic outputs directory holding a Stage B choice report and the run summary of the chosen run."""
    out = tmp_path / "outputs"
    run = out / f"selection_{registry}_runs" / f"{registry}_sel_{name}"
    run.mkdir(parents=True, exist_ok=True)
    (out / S.CHOICE_REPORTS[registry]).write_text(json.dumps({"chosen": {"name": name, "passes_every_gate": passes, "attachment_right_rate": 0.64}}))
    tier, size = S.parse_config(name)
    (run / "run_summary.json").write_text(json.dumps({"tier": tier, "model": S.MODELS[size], "digest": digest}))
    (run / "resolver.jsonl").write_text(json.dumps({"candidate_id": "x", "temperature": 0.1, "num_ctx": 8192, "num_predict": 200}) + "\n")
    root = tmp_path / "code"  # the code files the frozen runs used, and the manifest of their hashes
    root.mkdir(exist_ok=True)
    manifest = {}
    for rel, text in (("menu.py", "menu v1"), ("check_resolution.py", "checker v1"), ("outputs/resolver_gold.json", "{}")):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
        manifest[rel] = S.hashlib.sha256(text.encode()).hexdigest()
    (out / S.FROZEN_CODE.get(registry, f"frozen_{registry}.json")).write_text(json.dumps({"files": manifest}))
    return out


def _eval_half(right, misleading, incomplete, real_rej=0, mod=0, invented=0):
    base = {"right": 20, "misleading": 20, "incomplete": 20}  # production on 60 records of the evaluation half
    return {"all": {"candidates": 100, "valid": 100, "real": {"requirement": 80 - real_rej, "not_a_requirement": real_rej},
                    "non_requirement": {"not_a_requirement": 18, "scope_or_context": 2}, "attachment": {}, "status": {"complete": 100},
                    "invented_answers": invented, "modality_error_answers": mod},
            "audit": {"attachment": {"right": right, "misleading": misleading, "incomplete": incomplete}, "baseline_attachment": base}}


def _eval_result(S, half, hashes=None, tier="R2", model=None, digest="digest-frozen", temperature="0.1", num_ctx="8192", num_predict="200"):
    return {"prompt_hashes": [S.K.prompt_hash()] if hashes is None else hashes, "evaluation": half,
            "run_meta": {"tiers": [tier], "models": [model or S.MODELS[14]], "digests": [digest], "temperatures": [temperature],
                         "num_ctxs": [num_ctx], "num_predicts": [num_predict]},
            "selection": _eval_half(0, 60, 0, mod=9)}  # a failing selection half that must not matter


def test_the_verdict_scores_the_evaluation_half_once_with_the_registered_gates(mods, tmp_path):
    """WP-45.7d Stage C: one frozen run, the evaluation half only, exact fractions against that half's own production baseline."""
    S = mods["score"]
    out = _frozen_outputs(tmp_path, S)

    def verdict(*a, **k):
        return S.verdict_report(_eval_result(S, _eval_half(*a, **k)), "v5", "r2_14b", out, tmp_path / "code")

    ok = verdict(32, 20, 8)  # 32 of 60 = 20/60 + 1/5 exactly; misleading 20 of 60, within +5 points
    assert ok["all_gates_pass"] and ok["half"] == "evaluation" and ok["candidates"] == 100 and ok["prompt_hash"] == S.K.prompt_hash()
    assert ok["configuration"] == {"name": "r2_14b", "tier": "R2", "model": S.MODELS[14], "digest": "digest-frozen",
                                   "temperatures": ["0.1"], "num_ctxs": ["8192"], "num_predicts": ["200"]}
    assert ok["gates"]["attachment_gain_over_production"]["passed"] and ok["gates"]["misleading"]["passed"]
    assert not verdict(31, 20, 9)["gates"]["attachment_gain_over_production"]["passed"]
    assert verdict(32, 23, 5)["gates"]["misleading"]["passed"]  # 23 of 60 = 38.3% <= 33.3% + 5 points
    assert not verdict(32, 24, 4)["gates"]["misleading"]["passed"]  # 24 of 60 = 40%
    assert not verdict(32, 20, 8, real_rej=5)["gates"]["real_rejected"]["passed"]  # 5 of 80 = 6.25% > 5%
    assert verdict(32, 20, 8, real_rej=4)["gates"]["real_rejected"]["passed"]  # 4 of 80 = 5% exactly
    assert not verdict(32, 20, 8, mod=1)["all_gates_pass"]
    assert not verdict(32, 20, 8, invented=3)["all_gates_pass"]  # 3 of 100 > 2%
    with pytest.raises(SystemExit) as e:  # a ledger that never ran the evaluation half has nothing to score
        S.verdict_report({**_eval_result(S, None), "evaluation": None}, "v5", "r2_14b", out, tmp_path / "code")
    assert "no evaluation-half results" in str(e.value)


def test_the_verdict_refuses_anything_but_the_frozen_configuration(mods, tmp_path):
    """Review findings on #235: the wrong run (same prompt, other tier, model, model file or runner parameters), changed frozen code, and a
    stopped protocol (v4: no configuration passed) must not get or consume the one-shot verdict."""
    S = mods["score"]
    out = _frozen_outputs(tmp_path, S)
    root = tmp_path / "code"
    half = _eval_half(32, 20, 8)
    S.verdict_report(_eval_result(S, half), "v5", "r2_14b", out, root)  # the accepted case
    S.verdict_report(_eval_result(S, half), "v5", "R2_14B", out, root)  # the name is not case-sensitive
    bad = {
        "another configuration's name": dict(name="r1_8b"),
        "another tier": dict(result=_eval_result(S, half, tier="R1")),
        "another model": dict(result=_eval_result(S, half, model=S.MODELS[8])),
        "another model file": dict(result=_eval_result(S, half, digest="digest-other")),
        "another temperature": dict(result=_eval_result(S, half, temperature="0.7")),
        "another context size": dict(result=_eval_result(S, half, num_ctx="4096")),
        "another answer limit": dict(result=_eval_result(S, half, num_predict="900")),
        "the status design's prompt": dict(result=_eval_result(S, half, hashes=[S.SEL.prompt_hash()])),
        "mixed prompts": dict(result=_eval_result(S, half, hashes=[S.K.prompt_hash(), S.SEL.prompt_hash()])),
    }
    for label, k in bad.items():
        with pytest.raises(SystemExit):
            S.verdict_report(k.get("result") or _eval_result(S, half), "v5", k.get("name", "r2_14b"), out, root)
    mixed = _eval_result(S, half)
    mixed["run_meta"]["models"] = [S.MODELS[14], S.MODELS[8]]  # two models in one ledger
    with pytest.raises(SystemExit):
        S.verdict_report(mixed, "v5", "r2_14b", out, root)
    # frozen code: a changed or missing file is refused, with its name; restoring it makes the verdict possible again
    (root / "menu.py").write_text("menu v2")
    with pytest.raises(SystemExit) as e:
        S.verdict_report(_eval_result(S, half), "v5", "r2_14b", out, root)
    assert "menu.py" in str(e.value) and "check_resolution.py" not in str(e.value)
    (root / "menu.py").write_text("menu v1")
    (root / "check_resolution.py").unlink()
    with pytest.raises(SystemExit) as e:
        S.verdict_report(_eval_result(S, half), "v5", "r2_14b", out, root)
    assert "check_resolution.py" in str(e.value)
    (root / "check_resolution.py").write_text("checker v1")
    S.verdict_report(_eval_result(S, half), "v5", "r2_14b", out, root)
    # a stopped protocol, a missing report, and the registries that have no verdict at all
    stopped = _frozen_outputs(tmp_path / "stopped", S, registry="v4", passes=False)
    with pytest.raises(SystemExit) as e:
        S.verdict_report(_eval_result(S, half, hashes=[S.SEL.prompt_hash()]), "v4", "r2_14b", stopped, root)
    assert "stopped at Stage B" in str(e.value)
    with pytest.raises(SystemExit) as e:
        S.verdict_report(_eval_result(S, half), "v5", "r2_14b", tmp_path / "nowhere", root)
    assert "no committed choice report" in str(e.value)
    for registry in ("v2", "v3"):
        with pytest.raises(SystemExit) as e:
            S.verdict_report(_eval_result(S, half), registry, "r2_14b", out, root)
        assert "only for the registries tied to a prompt" in str(e.value)


def test_the_committed_stage_b_files_agree_with_the_verdict_guard(mods):
    """The real repository: v5 froze r2_14b with the kind prompt on the 14B model, and v4 stopped (its evaluation half stays reserved)."""
    S = mods["score"]
    frozen = S.frozen_choice("v5")
    assert frozen["name"] == "r2_14b" and frozen["tier"] == "R2" and frozen["model"] == S.MODELS[14] and frozen["digest"]
    assert frozen["temperatures"] == ["0.1"] and frozen["num_ctxs"] == ["8192"] and frozen["num_predicts"] == ["200"]
    summary = json.loads((S.OUTPUTS / "selection_v5_runs" / "v5_sel_r2_14b" / "run_summary.json").read_text())
    assert summary["prompt_hash"] == S.K.prompt_hash() and summary["half"] == "selection" and summary["design"] == "kind"
    with pytest.raises(SystemExit) as e:
        S.frozen_choice("v4")
    assert "stopped at Stage B" in str(e.value)


def test_the_committed_frozen_code_manifest_matches_the_files_in_the_repository(mods):
    """Editing any frozen file (menu generator, checker, assembler, runner, gold) fails this test and blocks the verdict until someone
    re-freezes on purpose. The manifest was made from the commit the Stage B runs used."""
    S = mods["score"]
    manifest = json.loads((S.OUTPUTS / S.FROZEN_CODE["v5"]).read_text())
    w = "eval/spike_results/wp_45_7/"
    assert set(manifest["files"]) >= {w + f for f in ("menu.py", "check_resolution.py", "kind_selection.py", "selection.py", "bundle.py", "run_selection.py",
                                                       "outputs/resolver_gold.json", "outputs/heldout_frozen.json")}
    # the transitive imports and the input pins, not only the files named in the experiment (review finding)
    assert {"pipeline/enrich_requirements.py", "eval/spike_results/wp_45_audit/_inputs.py", "eval/spike_results/wp_44/manifest.json",
            w + "chunk_sets.py", w + "draw_heldout.py"} <= set(manifest["files"])
    # the artifacts that name the choice are pinned too, or editing the choice report would change what the verdict scores
    base = "eval/spike_results/wp_45_7/outputs/"
    assert base + "resolver_selection_v5_choice.json" in manifest["files"]
    for run in ("r1_8b", "r1_14b", "r2_8b", "r2_14b"):
        for f in ("run_summary.json", "resolver.jsonl"):
            assert f"{base}selection_v5_runs/v5_sel_{run}/{f}" in manifest["files"], (run, f)
    S.check_frozen_code("v5")  # raises SystemExit naming any file that differs
    # and the manifest itself: a tampered manifest could pin anything, so its own hash is fixed here (regenerate it only on purpose)
    own = S.hashlib.sha256((S.OUTPUTS / S.FROZEN_CODE["v5"]).read_bytes()).hexdigest()
    assert own == "b121e9988eab84d6f73cda8882050b13fdf3aad113fb0d49e26e2cf8a297cf3f", own


def test_the_verdict_command_line_paths(mods, tmp_path, monkeypatch):
    S = mods["score"]
    d = tmp_path / "run"
    d.mkdir()
    rec = {"entry_id": "k1", "candidate_id": "audit:Z", "status": "complete", "prompt_hash": S.K.prompt_hash(), "tier": "R2",
           "model": S.MODELS[14], "digest": "digest-x", "answer": None, "issues": []}
    (d / "resolver.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    assert S.score_run(d, {"gold": []})["prompt_hashes"] == [S.K.prompt_hash()]
    meta = S.score_run(d, {"gold": []})["run_meta"]
    assert meta["tiers"] == ["R2"] and meta["models"] == [S.MODELS[14]] and meta["digests"] == ["digest-x"]
    assert meta["temperatures"] == ["None"] and meta["num_ctxs"] == ["None"] and meta["num_predicts"] == ["None"]  # absent fields are visible, not dropped
    monkeypatch.setattr(S, "OUTPUTS", _frozen_outputs(tmp_path, S))
    monkeypatch.setattr(sys, "argv", ["score_resolver.py", "--verdict", f"r2_14b={d}", "--registry", "v5"])
    with pytest.raises(SystemExit):  # the digest differs from the frozen run's, and the ledger holds no evaluation-half records
        S.main()
    monkeypatch.setattr(sys, "argv", ["score_resolver.py", "--verdict", "no-equals", "--registry", "v5"])
    with pytest.raises(SystemExit) as e:
        S.main()
    assert "NAME=DIR" in str(e.value)
    monkeypatch.setattr(sys, "argv", ["score_resolver.py", "--registry", "v5"])
    with pytest.raises(SystemExit) as e:
        S.main()
    assert "--runs" in str(e.value)

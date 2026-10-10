"""Workflow failure-path regressions; no network, provider SDK or paid calls."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / ".github" / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def reviewer(monkeypatch):
    module = load_script("gemini_review")
    monkeypatch.setattr(module, "generate_review", lambda *args: pytest.fail(
        "Unit tests must not call a live provider; inject a fake generate function.",
    ))
    return module


@pytest.fixture
def gate():
    return load_script("codeql_gate")


def valid_review():
    return {
        "summary": "The patch changes retry handling.",
        "checked": ["Traced retry exhaustion and failure propagation."],
        "findings": [], "limitations": ["No live provider calls."],
    }


def provider_response(raw=None, finish_reason="STOP"):
    return {
        "text": json.dumps(valid_review()) if raw is None else raw,
        "finish_reason": finish_reason,
        "prompt_tokens": 100, "output_tokens": 200, "thinking_tokens": 300,
    }


@pytest.fixture
def original_get_review(reviewer):
    return reviewer.get_review


@pytest.fixture
def review_run(reviewer, original_get_review, monkeypatch, tmp_path):
    for key, value in {
        "GITHUB_REPOSITORY": "owner/repo", "PR_NUMBER": "12", "GITHUB_RUN_ID": "99",
        "BASE_SHA": "a" * 40, "HEAD_SHA": "b" * 40,
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(reviewer, "EVIDENCE_PATH", tmp_path / "evidence.json")
    brief = tmp_path / "brief.md"
    brief.write_text("Trusted architecture brief.")
    monkeypatch.setattr(reviewer, "CONTEXT_PATH", brief)
    monkeypatch.setattr(reviewer, "current_candidate", lambda *args: True)
    monkeypatch.setattr(reviewer, "prepare_input", lambda *args: (
        "diff", "d" * 64, ["file.py"], [{"path": "file.py", "text": "pass"}], [],
    ))
    monkeypatch.setattr(reviewer, "get_review", lambda *args, **kwargs: (
        "fallback-model", json.dumps(valid_review()), 3,
    ))
    posted = []

    def post(args, **kwargs):
        posted.append((args, json.loads(kwargs["input"])))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(reviewer.subprocess, "run", post)
    return reviewer, posted


def test_success_records_actual_model_and_revision(review_run):
    reviewer, posted = review_run
    assert reviewer.main() == 0
    evidence = json.loads(reviewer.EVIDENCE_PATH.read_text())
    assert evidence["status"] == "complete"
    assert evidence["model"] == "fallback-model"
    assert evidence["attempts"] == 3
    assert evidence["head_sha"] == "b" * 40
    assert evidence["context_sha256"]
    assert evidence["publication"] == "published"
    assert "not merge approval" in posted[0][1]["body"]


def test_provider_outage_is_incomplete_and_fails(review_run, monkeypatch):
    reviewer, posted = review_run

    def outage(*args, **kwargs):
        raise reviewer.ReviewUnavailable("Provider unavailable.", 8)

    monkeypatch.setattr(reviewer, "get_review", outage)
    assert reviewer.main() == 1
    evidence = json.loads(reviewer.EVIDENCE_PATH.read_text())
    assert evidence["status"] == "unavailable"
    assert evidence["review"] is None and evidence["model"] is None
    assert evidence["attempts"] == 8
    assert "unavailable" in posted[0][1]["body"]
    assert "No findings reported" not in posted[0][1]["body"]


@pytest.mark.parametrize("raw", ["not JSON", "null", "{}", '{"summary":"clean"}', None])
def test_malformed_output_never_becomes_complete(review_run, monkeypatch, raw):
    reviewer, posted = review_run
    monkeypatch.setattr(reviewer, "get_review", lambda *args, **kwargs: ("model", raw, 1))
    assert reviewer.main() == 1
    evidence = json.loads(reviewer.EVIDENCE_PATH.read_text())
    assert evidence["status"] == "invalid"
    assert evidence["review"] is None
    assert "invalid" in posted[0][1]["body"]


def test_no_checks_is_not_a_clean_review(reviewer):
    review = valid_review()
    review["checked"] = []
    with pytest.raises(reviewer.InvalidReview, match="what was checked"):
        reviewer.validate_review(json.dumps(review), ["file.py"])


def test_substantive_findings_are_not_automatic_merge_verdicts(review_run, monkeypatch):
    reviewer, posted = review_run
    review = valid_review()
    review["findings"] = [{
        "severity": "High", "path": "file.py", "line": 10, "title": "Failure swallowed",
        "explanation": "The exception branch returns success.", "evidence": "except: return 0",
    }]
    monkeypatch.setattr(reviewer, "get_review", lambda *args, **kwargs: ("model", json.dumps(review), 1))
    assert reviewer.main() == 0  # Completed advisory review, not acceptance.
    assert "[High]" in posted[0][1]["body"]


@pytest.mark.parametrize("change", [{"path": "not-in-diff.py"}, {"line": True}, {"evidence": ""}])
def test_finding_requires_a_changed_file_and_evidence(reviewer, change):
    finding = {
        "severity": "High", "path": "file.py", "line": 10, "title": "Bug",
        "explanation": "A failure returns success.", "evidence": "return 0",
    }
    finding.update(change)
    review = valid_review()
    review["findings"] = [finding]
    with pytest.raises(reviewer.InvalidReview):
        reviewer.validate_review(json.dumps(review), ["file.py"])


def test_new_push_during_review_cannot_publish_old_evidence(review_run, monkeypatch):
    reviewer, posted = review_run
    states = iter([True, False])
    monkeypatch.setattr(reviewer, "current_candidate", lambda *args: next(states))
    assert reviewer.main() == 1
    assert not posted
    evidence = json.loads(reviewer.EVIDENCE_PATH.read_text())
    assert evidence["status"] == "complete" and evidence["publication"] == "stale"


def test_stale_event_makes_no_provider_call(review_run, monkeypatch):
    reviewer, posted = review_run
    monkeypatch.setattr(reviewer, "current_candidate", lambda *args: False)
    monkeypatch.setattr(reviewer, "get_review", lambda *args, **kwargs: pytest.fail("Provider called"))
    assert reviewer.main() == 1
    assert not posted
    assert json.loads(reviewer.EVIDENCE_PATH.read_text())["publication"] == "stale"


def test_comments_never_update_another_run(review_run, monkeypatch):
    reviewer, posted = review_run
    assert reviewer.main() == 0
    monkeypatch.setenv("HEAD_SHA", "c" * 40)
    assert reviewer.main() == 0
    assert len(posted) == 2
    assert all(args[args.index("--method") + 1] == "POST" for args, _ in posted)
    assert "b" * 40 in posted[0][1]["body"]
    assert "c" * 40 in posted[1][1]["body"]


def test_publication_failure_is_not_success(review_run, monkeypatch):
    reviewer, _ = review_run

    def failure(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "gh")

    monkeypatch.setattr(reviewer.subprocess, "run", failure)
    assert reviewer.main() == 1
    assert json.loads(reviewer.EVIDENCE_PATH.read_text())["publication"] == "failed"


def test_provider_fallback_budget_and_model_are_recorded(reviewer, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    calls = []

    def generate(model, key, contents, timeout):
        calls.append(model)
        assert timeout <= 60
        if len(calls) == 1:
            raise TimeoutError
        return provider_response()

    model, _, attempts = reviewer.get_review("input", [], generate=generate)
    assert model == reviewer.MODEL_CHAIN[1] and attempts == 2
    monkeypatch.setattr(reviewer, "MAX_CALLS", 1)
    with pytest.raises(reviewer.ReviewUnavailable) as caught:
        reviewer.get_review("input", [], generate=lambda *args: (_ for _ in ()).throw(TimeoutError()))
    assert caught.value.attempts == 1


def test_provider_time_budget_stops_new_calls(reviewer, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    clock = iter([0, reviewer.PROVIDER_BUDGET_SECONDS + 1])
    monkeypatch.setattr(reviewer.time, "monotonic", lambda: next(clock))
    with pytest.raises(reviewer.ReviewUnavailable, match="budget exhausted"):
        reviewer.get_review("input", [], generate=lambda *args: pytest.fail("Provider called"))


def test_all_provider_failures_exhaust_exactly_the_call_budget(reviewer, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "first-test-key")
    monkeypatch.setenv("GEMINI_API_KEY_2", "second-test-key")
    calls = []

    def outage(model, key, contents, timeout):
        calls.append((model, key))
        raise TimeoutError

    with pytest.raises(reviewer.ReviewUnavailable) as caught:
        reviewer.get_review("input", [], generate=outage)
    assert len(calls) == reviewer.MAX_CALLS == caught.value.attempts
    assert len(set(calls)) == len(calls)


@pytest.mark.parametrize("first", [
    provider_response('{"summary": "cut off', "MAX_TOKENS"),
    provider_response("not JSON"), provider_response("{}"),
    provider_response("null"), provider_response(""),
    provider_response(finish_reason="SAFETY"), provider_response(finish_reason=None),
])
def test_incomplete_or_invalid_output_falls_back_to_complete_review(reviewer, monkeypatch, first):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    responses = iter([first, provider_response()])
    diagnostics = []
    model, raw, attempts = reviewer.get_review(
        "input", ["file.py"], generate=lambda *args: next(responses), attempt_log=diagnostics,
    )
    assert model == reviewer.MODEL_CHAIN[1] and attempts == 2
    assert reviewer.validate_review(raw, ["file.py"]) == valid_review()
    assert [item["status"] for item in diagnostics] == ["invalid", "complete"]
    assert diagnostics[0]["finish_reason"] == (first["finish_reason"] or "UNKNOWN")
    assert diagnostics[1]["output_tokens"] == 200
    assert diagnostics[1]["thinking_tokens"] == 300


def test_valid_json_with_max_tokens_is_not_complete(reviewer, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    monkeypatch.setattr(reviewer, "MAX_CALLS", 1)
    diagnostics = []
    with pytest.raises(reviewer.InvalidReview, match="No complete valid review"):
        reviewer.get_review(
            "input", [], generate=lambda *args: provider_response(finish_reason="MAX_TOKENS"),
            attempt_log=diagnostics,
        )
    assert diagnostics[0]["status"] == "invalid"
    assert diagnostics[0]["unvalidated_review"] == valid_review()


def test_invalid_attempts_stop_at_the_same_call_budget(reviewer, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "first-test-key")
    monkeypatch.setenv("GEMINI_API_KEY_2", "second-test-key")
    diagnostics = []
    with pytest.raises(reviewer.InvalidReview, match="No complete valid review"):
        reviewer.get_review(
            "input", [], generate=lambda *args: provider_response("not JSON"),
            attempt_log=diagnostics,
        )
    assert len(diagnostics) == reviewer.MAX_CALLS
    assert all(item["status"] == "invalid" for item in diagnostics)


def test_no_fallback_call_after_candidate_changes(reviewer, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    states = iter([True, False])
    calls = []

    def generate(*args):
        calls.append(args)
        return provider_response("not JSON")

    with pytest.raises(reviewer.InvalidReview, match="Candidate changed"):
        reviewer.get_review("input", [], generate=generate, is_current=lambda: next(states))
    assert len(calls) == 1


def test_freshness_check_cannot_extend_provider_start_budget(reviewer, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    clock = iter([0, 1, reviewer.PROVIDER_BUDGET_SECONDS + 1])
    monkeypatch.setattr(reviewer.time, "monotonic", lambda: next(clock))
    diagnostics = []
    with pytest.raises(reviewer.ReviewUnavailable, match="budget exhausted") as caught:
        reviewer.get_review(
            "input", [], generate=lambda *args: pytest.fail("Provider called"),
            is_current=lambda: True, attempt_log=diagnostics,
        )
    assert caught.value.attempts == 0 and not diagnostics


def test_invalid_retry_consumes_time_budget(reviewer, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    clock = iter([0, 1, 2, reviewer.PROVIDER_BUDGET_SECONDS + 1])
    monkeypatch.setattr(reviewer.time, "monotonic", lambda: next(clock))
    diagnostics = []
    with pytest.raises(reviewer.InvalidReview, match="budget exhausted"):
        reviewer.get_review(
            "input", [], generate=lambda *args: provider_response("not JSON"),
            attempt_log=diagnostics,
        )
    assert len(diagnostics) == 1


@pytest.mark.parametrize("shape", ["wrapper", "array", "string", "number", "null"])
def test_rejected_findings_survive_clean_fallback(review_run, original_get_review, monkeypatch, shape):
    reviewer, posted = review_run
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    rejected = valid_review()
    rejected["findings"] = [{
        "severity": "High", "path": "other.py", "line": 10, "title": "Bug",
        "explanation": "A failure returns success.", "evidence": "return 0",
    }]
    rejected = {
        "wrapper": rejected, "array": rejected["findings"],
        "string": "A finding without the required wrapper", "number": 42, "null": None,
    }[shape]
    responses = iter([provider_response(json.dumps(rejected)), provider_response()])
    def get(contents, paths, **kwargs):
        return original_get_review(contents, paths, generate=lambda *args: next(responses), **kwargs)

    monkeypatch.setattr(reviewer, "get_review", get)
    assert reviewer.main() == 0
    evidence = json.loads(reviewer.EVIDENCE_PATH.read_text())
    assert evidence["status"] == "complete" and evidence["attempts"] == 2
    assert evidence["review"]["findings"] == []
    assert evidence["provider_attempts"][0]["unvalidated_review"] == rejected
    assert "Inspect them for findings and record dispositions" in posted[0][1]["body"]


def test_all_invalid_reviews_persist_failure_evidence(review_run, original_get_review, monkeypatch):
    reviewer, posted = review_run
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    def get(contents, paths, **kwargs):
        return original_get_review(contents, paths, generate=lambda *args: provider_response("bad"), **kwargs)

    monkeypatch.setattr(reviewer, "get_review", get)
    assert reviewer.main() == 1
    evidence = json.loads(reviewer.EVIDENCE_PATH.read_text())
    assert evidence["status"] == "invalid" and evidence["review"] is None
    assert evidence["attempts"] == len(reviewer.MODEL_CHAIN)
    assert len(evidence["provider_attempts"]) == evidence["attempts"]
    assert "No findings reported" not in posted[0][1]["body"]


def test_diagnostics_do_not_log_keys_or_raw_provider_text(reviewer, monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    responses = iter([provider_response("private candidate text"), provider_response()])
    diagnostics = []
    reviewer.get_review("input", [], generate=lambda *args: next(responses), attempt_log=diagnostics)
    output = capsys.readouterr()
    assert "secret-test-key" not in output.err + json.dumps(diagnostics)
    assert "private candidate text" not in output.err + json.dumps(diagnostics)
    assert diagnostics[0]["response_sha256"]


def test_reruns_have_distinct_comment_identities(review_run, monkeypatch):
    reviewer, posted = review_run
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    assert reviewer.main() == 0
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    assert reviewer.main() == 0
    assert posted[0][1]["body"].splitlines()[0] != posted[1][1]["body"].splitlines()[0]
    assert "Run attempt: 2" in posted[1][1]["body"]


def test_complete_review_with_findings_stops_fallback(reviewer, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    review = valid_review()
    review["findings"] = [{
        "severity": "High", "path": "file.py", "line": 10, "title": "Bug",
        "explanation": "Failure returns success.", "evidence": "return 0",
    }]
    calls = []

    def generate(*args):
        calls.append(args)
        return provider_response(json.dumps(review))

    _, raw, attempts = reviewer.get_review("input", ["file.py"], generate=generate)
    assert attempts == len(calls) == 1
    assert reviewer.validate_review(raw, ["file.py"])["findings"] == review["findings"]


@pytest.mark.parametrize("change", [
    {"head": {"sha": "c" * 40}}, {"base": {"sha": "c" * 40}},
    {"state": "closed"}, {"draft": True},
])
def test_github_candidate_checks_both_revisions_and_reviewable_state(reviewer, monkeypatch, change):
    snapshot = {
        "state": "open", "draft": False,
        "base": {"sha": "a" * 40}, "head": {"sha": "b" * 40},
    }
    monkeypatch.setattr(reviewer, "run_command", lambda *args: json.dumps(snapshot).encode())
    assert reviewer.current_candidate("owner/repo", "12", "a" * 40, "b" * 40)
    snapshot.update(change)
    assert not reviewer.current_candidate("owner/repo", "12", "a" * 40, "b" * 40)


def test_pinned_diff_and_surroundings_without_candidate_checkout(reviewer, tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path).decode().strip()

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    git("remote", "add", "origin", str(tmp_path))
    (tmp_path / "file.py").write_text("old = 1\n")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (tmp_path / "file.py").write_text("new = 2\n")
    git("commit", "-qam", "candidate")
    head = git("rev-parse", "HEAD")
    git("checkout", "-q", base)
    monkeypatch.chdir(tmp_path)
    diff, digest, paths, context, omitted = reviewer.prepare_input(base, head)
    assert "new = 2" in diff and len(digest) == 64
    assert paths == ["file.py"] and context[0]["text"] == "new = 2\n"
    assert git("rev-parse", "HEAD") == base and not omitted
    monkeypatch.setattr(reviewer, "MAX_DIFF_BYTES", 1)
    with pytest.raises(reviewer.InvalidReview, match="oversized"):
        reviewer.prepare_input(base, head)


def sarif(rule=None, result=None):
    rule = rule or {"id": "test/rule"}
    result = result or {"ruleId": "test/rule", "level": "warning"}
    return {"version": "2.1.0", "runs": [{
        "tool": {"driver": {"name": "CodeQL", "rules": [rule]}}, "results": [result],
    }]}


def write_sarif(tmp_path, data):
    (tmp_path / "results.sarif").write_text(json.dumps(data))


def test_missing_scan_output_fails(gate, tmp_path):
    assert gate.main([str(tmp_path / "absent")]) == 1
    assert gate.main([str(tmp_path)]) == 1


def test_valid_empty_scan_passes(gate, tmp_path):
    data = sarif()
    data["runs"][0]["results"] = []
    write_sarif(tmp_path, data)
    assert gate.main([str(tmp_path)]) == 0


@pytest.mark.parametrize("name", ["CodeQL", "CodeQL command-line toolchain"])
@pytest.mark.parametrize("blocking", [False, True])
def test_action_and_cli_driver_names_preserve_severity_policy(gate, tmp_path, name, blocking):
    data = sarif({
        "id": "test/rule", "properties": {"security-severity": "7.0" if blocking else "3.0"},
    })
    data["runs"][0]["tool"]["driver"]["name"] = name
    write_sarif(tmp_path, data)
    assert gate.evaluate(tmp_path) == (["test/rule"] if blocking else [])
    assert gate.main([str(tmp_path)]) == (1 if blocking else 0)


def test_unrelated_tool_cannot_substitute_for_codeql(gate, tmp_path):
    data = sarif()
    data["runs"][0]["results"] = []
    data["runs"][0]["tool"]["driver"]["name"] = "Other scanner"
    write_sarif(tmp_path, data)
    assert gate.main([str(tmp_path)]) == 1


def test_inherited_error_level_blocks(gate, tmp_path):
    write_sarif(tmp_path, sarif(
        {"id": "test/rule", "defaultConfiguration": {"level": "error"}},
        {"ruleId": "test/rule"},
    ))
    assert gate.evaluate(tmp_path) == ["test/rule"]
    assert gate.main([str(tmp_path)]) == 1


def test_warning_with_critical_security_severity_blocks(gate, tmp_path):
    write_sarif(tmp_path, sarif({
        "id": "test/rule", "properties": {"security-severity": "9.8", "precision": "medium"},
    }))
    assert gate.evaluate(tmp_path) == ["test/rule"]


def test_warning_with_low_security_severity_passes(gate, tmp_path):
    write_sarif(tmp_path, sarif({"id": "test/rule", "properties": {"security-severity": "3.0"}}))
    assert gate.main([str(tmp_path)]) == 0


def test_explicit_level_overrides_rule_default(gate, tmp_path):
    write_sarif(tmp_path, sarif({"id": "test/rule", "defaultConfiguration": {"level": "error"}}))
    assert gate.main([str(tmp_path)]) == 0


@pytest.mark.parametrize("data", [{}, {"version": "2.1.0", "runs": []},
                                   {"version": "2.1.0", "runs": [{}]}])
def test_malformed_scan_fails(gate, tmp_path, data):
    write_sarif(tmp_path, data)
    assert gate.main([str(tmp_path)]) == 1


def test_unreadable_sarif_fails(gate, tmp_path):
    (tmp_path / "results.sarif").write_text("not json")
    assert gate.main([str(tmp_path)]) == 1


@pytest.mark.parametrize("severity", ["NaN", "inf", "not-a-number", -1, 11, True])
def test_invalid_security_severity_cannot_pass(gate, tmp_path, severity):
    write_sarif(tmp_path, sarif({"id": "test/rule", "properties": {"security-severity": severity}}))
    assert gate.main([str(tmp_path)]) == 1


def test_failed_scan_invocation_cannot_pass(gate, tmp_path):
    data = sarif()
    data["runs"][0]["results"] = []
    data["runs"][0]["invocations"] = [{"executionSuccessful": False}]
    write_sarif(tmp_path, data)
    assert gate.main([str(tmp_path)]) == 1


def test_unresolved_or_conflicting_rule_cannot_pass(gate, tmp_path):
    write_sarif(tmp_path, sarif(result={"ruleId": "unknown", "ruleIndex": 0}))
    assert gate.main([str(tmp_path)]) == 1

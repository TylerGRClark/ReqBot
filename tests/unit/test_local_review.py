"""Behaviour of the advisory local pre-push reviewer (.github/scripts/local_review.py).

No Ollama server or network is used: the chat call is replaced in every test.
"""

import importlib.util
import json
import subprocess
import urllib.error
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "local_review.py"


@pytest.fixture
def review(monkeypatch):
    spec = importlib.util.spec_from_file_location("local_review", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "base_ref", lambda requested: requested or "origin/main")
    monkeypatch.setattr(module, "reqbot_defaults", lambda: ("http://ollama.test:11434", "m:14b"))
    return module


def with_diff(module, monkeypatch, diff="diff --git a/x.py b/x.py\n+x = 1\n", changed=("x.py",)):
    monkeypatch.setattr(module, "collect_diff", lambda base, paths: (diff, set(changed)))


def answer(summary="Looks fine.", findings=(), **extra):
    reply = {
        "message": {"content": json.dumps({"summary": summary, "findings": list(findings)})},
        "done_reason": "stop", "prompt_eval_count": 3000,
    }
    reply.update(extra)
    return reply


def finding(path="x.py", severity="High", line=1):
    return {"severity": severity, "path": path, "line": line, "title": "t", "explanation": "e"}


def test_finding_must_cite_a_changed_file(review):
    content = json.dumps({"summary": "s", "findings": [finding("x.py"), finding("other.py")]})
    summary, kept, dropped = review.parse_review(content, {"x.py"})
    assert [f["path"] for f in kept] == ["x.py"] and dropped == 1


def test_malformed_review_is_rejected(review):
    assert review.parse_review("not json", {"x.py"}) is None
    assert review.parse_review(json.dumps({"summary": 1, "findings": []}), {"x.py"}) is None
    assert review.parse_review(json.dumps({"summary": "s"}), {"x.py"}) is None


def test_findings_are_sorted_by_severity(review):
    content = json.dumps({"summary": "s", "findings": [finding(severity="Low"), finding(severity="Critical")]})
    _, kept, _ = review.parse_review(content, {"x.py"})
    assert [f["severity"] for f in kept] == ["Critical", "Low"]


def test_empty_diff_makes_no_model_call(review, monkeypatch, capsys):
    with_diff(review, monkeypatch, diff="  \n", changed=())
    monkeypatch.setattr(review, "chat", lambda *a: pytest.fail("model must not be called"))
    assert review.main([]) == 0
    assert "Nothing to review" in capsys.readouterr().out


def test_oversized_diff_is_refused_not_truncated(review, monkeypatch, capsys):
    with_diff(review, monkeypatch, diff="+" + "x" * (review.MAX_DIFF_BYTES + 1))
    monkeypatch.setattr(review, "chat", lambda *a: pytest.fail("model must not be called"))
    assert review.main([]) == 0
    out = capsys.readouterr().out
    assert "incomplete" in out and "over the" in out


def test_unreachable_ollama_is_unavailable_and_never_blocks(review, monkeypatch, capsys):
    with_diff(review, monkeypatch)

    def refuse(*args):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(review, "chat", refuse)
    assert review.main([]) == 0
    assert "unavailable" in capsys.readouterr().out


def test_missing_model_hints_it_is_not_pulled(review, monkeypatch, capsys):
    with_diff(review, monkeypatch)

    def missing(*args):
        raise urllib.error.HTTPError("http://x", 404, "not found", {}, None)

    monkeypatch.setattr(review, "chat", missing)
    assert review.main([]) == 0
    assert "pulled" in capsys.readouterr().out


def test_clean_review_is_complete_but_not_approval(review, monkeypatch, capsys):
    with_diff(review, monkeypatch)
    monkeypatch.setattr(review, "chat", lambda *a: answer())
    assert review.main([]) == 0
    out = capsys.readouterr().out
    assert "complete" in out and "not approval" in out


def test_full_context_window_is_reported_incomplete(review, monkeypatch, capsys):
    with_diff(review, monkeypatch)
    monkeypatch.setattr(review, "chat", lambda *a: answer(prompt_eval_count=review.NUM_CTX))
    assert review.main([]) == 0
    out = capsys.readouterr().out
    assert "incomplete" in out and "context window" in out


def test_cut_off_answer_is_incomplete(review, monkeypatch, capsys):
    with_diff(review, monkeypatch)
    monkeypatch.setattr(review, "chat", lambda *a: answer(done_reason="length"))
    assert review.main([]) == 0
    assert "incomplete" in capsys.readouterr().out


def test_high_severity_finding_is_shown_and_still_exits_zero(review, monkeypatch, capsys):
    with_diff(review, monkeypatch)
    monkeypatch.setattr(review, "chat", lambda *a: answer(findings=[finding(severity="Critical", line=7)]))
    assert review.main([]) == 0
    assert "[Critical] x.py:7" in capsys.readouterr().out


def test_url_and_model_flags_override_reqbot_config(review, monkeypatch):
    with_diff(review, monkeypatch)
    seen = {}

    def capture(url, model, messages):
        seen.update(url=url, model=model)
        return answer()

    monkeypatch.setattr(review, "chat", capture)
    review.main([])
    assert seen == {"url": "http://ollama.test:11434", "model": "m:14b"}
    review.main(["--ollama-url", "http://other:1/", "--model", "q:7b"])
    assert seen == {"url": "http://other:1", "model": "q:7b"}


def test_diff_skips_data_files_and_never_reads_untracked_files(review, monkeypatch, tmp_path):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": __import__("os").environ["PATH"]}

    def run(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, env=env)

    run("init", "-q", "-b", "main")
    (tmp_path / "a.py").write_text("a = 1\n")
    (tmp_path / "data.jsonl").write_text('{"k": 1}\n')
    run("add", "a.py", "data.jsonl")
    run("commit", "-q", "-m", "base")
    (tmp_path / "a.py").write_text("a = 2\n")  # unstaged change to a tracked file
    (tmp_path / "data.jsonl").write_text('{"k": 2}\n')
    (tmp_path / "draft.md").write_text("private draft\n")  # untracked
    monkeypatch.setattr(review, "_ROOT", tmp_path)

    diff, changed = review.collect_diff("main", [])
    assert changed == {"a.py"}
    assert "a = 2" in diff and "k" not in diff and "private draft" not in diff

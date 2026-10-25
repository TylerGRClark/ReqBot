"""The parts around the job engine (stage 3): progress lines, the admin access code, the read-only job routes, and the `jobs` and `token` commands."""
import json
import os
import stat
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core import access
from pipeline import progress
from services import job_service as js
from services.job_service import JobStore


@pytest.fixture(autouse=True)
def _progress_off():
    progress.disable()
    yield
    progress.disable()


@pytest.fixture
def code_file(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.delenv(access.ENV_ADMIN_TOKEN, raising=False)
    monkeypatch.setattr(access, "FAILED_ATTEMPT_DELAY_SECONDS", 0)
    return tmp_path / "access.json"


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = JobStore(tmp_path / "processed" / ".jobs")
    monkeypatch.setattr(js, "default_store", lambda *a, **k: s)
    return s


# -- progress --------------------------------------------------------------------

def test_progress_prints_nothing_unless_enabled(capsys):
    progress.emit("finding", 1, 2)
    assert capsys.readouterr().out == ""


def test_progress_prints_one_compact_json_line_per_call(capsys):
    progress.enable()
    progress.emit("reading")
    progress.emit("finding", 120, 427)
    lines = capsys.readouterr().out.splitlines()
    assert [json.loads(line) for line in lines] == [{"step": "reading"}, {"step": "finding", "done": 120, "total": 427}]
    assert lines[1] == '{"step":"finding","done":120,"total":427}'


def test_the_labeler_and_indexers_say_nothing_when_progress_is_off(capsys):
    from pipeline import embed_and_index, embed_context_index

    progress.emit("finding", 1, 2)  # the clause labeler reports through pipeline.progress directly
    embed_and_index._emit_progress("indexing", 1, 2)
    embed_context_index._emit_progress("indexing-context", 1, 2)
    assert capsys.readouterr().out == ""
    progress.enable()
    embed_and_index._emit_progress("indexing", 1, 2)
    assert json.loads(capsys.readouterr().out) == {"step": "indexing", "done": 1, "total": 2}


def test_ingest_with_the_flag_prints_progress_and_without_it_prints_nothing_on_stdout(tmp_path, capsys):
    from cli.reqbot import cmd_ingest

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    index_path = out_dir / "DOC_requirements_normalized.jsonl"
    index_path.write_text(json.dumps({"document_id": "d", "requirement_id": "REQ-1"}) + "\n")
    (out_dir / "DOC_chunks.jsonl").write_text(json.dumps({"chunk_id": 0, "text": "x"}) + "\n")

    def args(flag):
        return SimpleNamespace(pdf=str(pdf), output_dir=str(out_dir), extraction_model=None, model=None, max_chunks=None, no_index=False,
                               profile="cybersecurity", ollama_url="http://o", qdrant_url="http://q",
                               progress_json=flag)

    for flag, expect in ((False, ""), (True, "indexing")):
        progress.disable()
        with patch("pipeline.run_pipeline.run", return_value=str(index_path)), patch("pipeline.embed_and_index.run"), patch("pipeline.embed_context_index.run"):
            assert cmd_ingest(args(flag)) == 0
        out = capsys.readouterr().out
        if not flag:
            assert out == ""
        else:
            steps = [json.loads(line)["step"] for line in out.splitlines()]
            assert steps == ["indexing", "indexing-context", "done"] and expect in steps


# -- the admin access code ------------------------------------------------------

def test_no_code_configured_means_nobody_is_admin(code_file):
    assert access.admin_token() is None and access.source() == "none"
    assert access.check_admin("anything") == "not-configured" and access.check_admin(None) == "not-configured"


def test_a_created_code_is_random_private_and_kept_until_rotated(code_file):
    token, created = access.create_admin_token()
    assert created and len(token) >= 32
    assert stat.S_IMODE(os.stat(code_file).st_mode) == 0o600
    assert access.create_admin_token() == (token, False)
    new, created = access.create_admin_token(rotate=True)
    assert created and new != token and access.admin_token() == new


def test_the_environment_variable_wins_over_the_file(code_file, monkeypatch):
    access.create_admin_token()
    monkeypatch.setenv(access.ENV_ADMIN_TOKEN, "from-the-environment")
    assert access.admin_token() == "from-the-environment" and access.source() == "environment"
    assert access.check_admin("from-the-environment") == "ok"


def test_check_admin_answers_ok_missing_or_wrong(code_file):
    token, _ = access.create_admin_token()
    assert access.check_admin(token) == "ok"
    assert access.check_admin(None) == "missing" and access.check_admin("") == "missing"
    assert access.check_admin(token + "x") == "wrong" and access.check_admin("x") == "wrong"


def test_the_code_is_not_in_the_config_route(code_file):
    from api.app import app

    token, _ = access.create_admin_token()
    body = TestClient(app).get("/api/config").text
    assert token not in body and "admin" not in json.loads(body).get("effective", json.loads(body)).keys()


# -- the job routes --------------------------------------------------------------

def _client():
    from api.app import app
    return TestClient(app)


def test_job_routes_answer_403_until_a_code_is_configured(code_file, store):
    for path in ("/api/jobs", "/api/jobs/JOB-1"):
        r = _client().get(path)
        assert r.status_code == 403 and "reqbot token" in r.json()["detail"]


def test_job_routes_need_the_code_and_take_either_header(code_file, store):
    token, _ = access.create_admin_token()
    c = _client()
    assert c.get("/api/jobs").status_code == 401
    assert c.get("/api/jobs", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert c.get("/api/jobs", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert c.get("/api/jobs", headers={"X-ReqBot-Token": token}).status_code == 200


def test_job_list_and_detail_show_state_progress_and_the_log_tail(code_file, store, tmp_path):
    token, _ = access.create_admin_token()
    done = store.enqueue("ingest", [sys.executable, "/x/cli/reqbot.py", "ingest", "a.pdf"], title="Ingest a.pdf")
    time.sleep(0.01)
    waiting = store.enqueue("ingest", [sys.executable, "/x/cli/reqbot.py", "ingest", "b.pdf"], title="Ingest b.pdf")
    runner = {"id": "r", "host": "h", "pid": os.getpid(), "stamp": None}
    claimed = store.claim_next(runner)
    store.record_progress(claimed["id"], 1, "r", {"step": "finding", "done": 3, "total": 9})
    store.log_path(claimed["id"]).write_text("line one\nline two\n")
    h = {"Authorization": f"Bearer {token}"}
    listing = _client().get("/api/jobs", headers=h).json()
    assert [j["id"] for j in listing["jobs"]] == [waiting["id"], done["id"]]
    assert listing["running"] == done["id"] and listing["queued"] == 1
    assert listing["jobs"][1]["progress"]["done"] == 3 and listing["jobs"][1]["command"] == "reqbot ingest a.pdf"
    assert "argv" not in listing["jobs"][1] and "lease" not in listing["jobs"][1]
    detail = _client().get(f"/api/jobs/{done['id']}", headers=h).json()
    assert detail["state"] == "running" and "line two" in detail["log_tail"]
    assert _client().get("/api/jobs/JOB-nope", headers=h).status_code == 404
    assert _client().get("/api/jobs/.lock", headers=h).status_code == 404


def test_the_routes_cannot_start_or_change_a_job(code_file, store):
    token, _ = access.create_admin_token()
    h = {"Authorization": f"Bearer {token}"}
    for method in ("post", "put", "delete"):
        assert getattr(_client(), method)("/api/jobs", headers=h).status_code in (404, 405)


# -- the commands -----------------------------------------------------------------

def test_the_token_command_creates_shows_and_rotates(code_file, capsys):
    from cli.reqbot import cmd_token

    assert cmd_token(SimpleNamespace(rotate=False)) == 0
    first = capsys.readouterr().out
    token = access.admin_token()
    assert token in first and "(new)" in first
    cmd_token(SimpleNamespace(rotate=False))
    assert "(new)" not in capsys.readouterr().out and access.admin_token() == token
    cmd_token(SimpleNamespace(rotate=True))
    assert access.admin_token() != token


def test_the_token_command_says_when_the_environment_supplies_the_code(code_file, monkeypatch, capsys):
    from cli.reqbot import cmd_token

    monkeypatch.setenv(access.ENV_ADMIN_TOKEN, "secret-from-env")
    cmd_token(SimpleNamespace(rotate=False))
    out = capsys.readouterr().out
    assert "secret-from-env" not in out and access.ENV_ADMIN_TOKEN in out


def _jobs_args(**kw):
    return SimpleNamespace(**{"jobs_command": "list", "limit": 20, "json_output": False, "job_id": None, **kw})


def test_jobs_commands_list_show_cancel_retry(tmp_path, capsys):
    from cli import reqbot

    s = JobStore(tmp_path / ".jobs")
    queued = s.enqueue("ingest", [sys.executable, "/x/cli/reqbot.py", "ingest", "a.pdf"], title="Ingest a.pdf", run_dir="/r/a_1")
    with patch.object(reqbot, "_job_store", return_value=s):
        assert reqbot.cmd_jobs(_jobs_args()) == 0
        assert queued["id"] in capsys.readouterr().out
        assert reqbot.cmd_jobs(_jobs_args(jobs_command="list", json_output=True)) == 0
        assert json.loads(capsys.readouterr().out)[0]["command"] == "reqbot ingest a.pdf"
        assert reqbot.cmd_jobs(_jobs_args(jobs_command="show", job_id=queued["id"])) == 0
        assert "Ingest a.pdf" in capsys.readouterr().out
        assert reqbot.cmd_jobs(_jobs_args(jobs_command="retry", job_id=queued["id"])) == 1  # still queued
        assert reqbot.cmd_jobs(_jobs_args(jobs_command="cancel", job_id=queued["id"])) == 0
        assert s.get(queued["id"])["state"] == "cancelled"
        assert reqbot.cmd_jobs(_jobs_args(jobs_command="retry", job_id=queued["id"])) == 0
        assert len([j for j in s.list_jobs() if j["state"] == "queued"]) == 1
        assert reqbot.cmd_jobs(_jobs_args(jobs_command="show", job_id="JOB-none")) == 1


def test_jobs_add_ingest_queues_the_command_without_running_it(tmp_path, capsys):
    from cli import reqbot

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    s = JobStore(tmp_path / ".jobs")
    cfg = SimpleNamespace(ollama_url="http://o", qdrant_url="http://q", extraction_model="m", enrichment_model="m", embedding_model="e",
                          processed_dir_path=lambda: tmp_path / "p")
    with patch.object(reqbot, "_job_store", return_value=s), patch.object(reqbot, "_cfg", cfg):
        rc = reqbot.cmd_jobs(SimpleNamespace(jobs_command="add", add_kind="ingest", pdf=str(pdf), no_index=True, max_chunks=2))
    assert rc == 0
    (job,) = s.list_jobs()
    assert job["state"] == "queued" and "--no-index" in job["argv"] and job["requested_by"] == "cli"
    assert reqbot.cmd_jobs(SimpleNamespace(jobs_command="add", add_kind="ingest", pdf=str(tmp_path / "nope.pdf"), no_index=False, max_chunks=None)) == 1
    assert job["params"]["then_questions"] is False
    other = tmp_path / "other.pdf"
    other.write_bytes(b"%PDF-1.4")
    with patch.object(reqbot, "_job_store", return_value=s), patch.object(reqbot, "_cfg", cfg):
        rc = reqbot.cmd_jobs(SimpleNamespace(jobs_command="add", add_kind="ingest", pdf=str(other), no_index=False, max_chunks=None, then_questions=True))
    assert rc == 0 and s.list_jobs()[0]["params"]["then_questions"] is True


# -- trusted-network mode ---------------------------------------------------------

def test_open_mode_is_off_by_default_and_asks_for_no_code_when_on(code_file, monkeypatch):
    monkeypatch.delenv(access.ENV_ADMIN_OPEN, raising=False)
    assert access.admin_mode() == "unconfigured" and not access.is_open()
    access.create_admin_token()
    assert access.admin_mode() == "code" and access.check_admin(None) == "missing"
    access.set_open(True)
    assert access.admin_mode() == "open" and access.check_admin(None) == "ok" and access.check_admin("anything") == "ok"
    access.set_open(False)
    assert access.admin_mode() == "code" and access.check_admin(None) == "missing"


def test_open_mode_keeps_the_code_and_the_file_stays_private(code_file):
    token, _ = access.create_admin_token()
    access.set_open(True)
    assert access.admin_token() == token
    assert stat.S_IMODE(os.stat(code_file).st_mode) == 0o600
    new, created = access.create_admin_token(rotate=True)
    assert created and new != token and access.is_open()  # rotating the code does not change the mode


def test_the_environment_variable_turns_open_mode_on_without_the_file(code_file, monkeypatch):
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv(access.ENV_ADMIN_OPEN, value)
        assert access.admin_mode() == "open"
    for value in ("0", "false", "", "maybe"):
        monkeypatch.setenv(access.ENV_ADMIN_OPEN, value)
        assert access.admin_mode() == "unconfigured"


def test_admin_routes_need_no_code_in_open_mode_and_a_screen_can_ask_which_mode(code_file, store):
    c = _client()
    assert c.get("/api/access").json() == {"admin": "unconfigured"}
    assert c.get("/api/jobs").status_code == 403
    token, _ = access.create_admin_token()
    assert c.get("/api/access").json() == {"admin": "code"}
    assert c.get("/api/jobs").status_code == 401
    access.set_open(True)
    assert c.get("/api/access").json() == {"admin": "open"}
    assert c.get("/api/jobs").status_code == 200
    assert token not in c.get("/api/access").text


def test_nothing_in_the_api_can_turn_open_mode_on(code_file):
    c = _client()
    for method, path in (("post", "/api/access"), ("put", "/api/access"), ("post", "/api/config")):
        r = getattr(c, method)(path, json={"admin": "open", "open": True})
        assert r.status_code in (403, 404, 405, 422), (method, path, r.status_code)
    assert not access.is_open()


def test_the_token_command_switches_open_mode_on_and_off(code_file, capsys):
    from cli.reqbot import cmd_token

    assert cmd_token(SimpleNamespace(rotate=False, open=True, require=False)) == 0
    assert access.admin_mode() == "open" and "ON" in capsys.readouterr().out
    assert cmd_token(SimpleNamespace(rotate=False, open=False, require=False)) == 0
    shown = capsys.readouterr().out
    assert "ON" in shown and "--require" in shown  # asking for the code while open says so, and how to turn it off
    assert cmd_token(SimpleNamespace(rotate=False, open=False, require=True)) == 0
    assert not access.is_open() and "OFF" in capsys.readouterr().out

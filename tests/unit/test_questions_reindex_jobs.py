"""Stage 6a of docs/WEB_UI_PARITY_PLAN.md, backend: draft questions and the library rebuild as jobs (job kinds, routes, progress)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core import access
from services import audit_questions
from services import job_service as js
from services.job_service import JobStore


def _cfg(tmp_path: Path):
    return SimpleNamespace(ollama_url="http://ollama.test:11434", qdrant_url="http://qdrant.test:6333", extraction_model="m", enrichment_model="m",
                           embedding_model="nomic-embed-text", processed_dir_path=lambda: tmp_path / "processed")


def _library(tmp_path: Path, *keys: str) -> None:
    for key in keys:
        run = tmp_path / "processed" / f"{key}_20261001_120000"
        run.mkdir(parents=True)
        (run / f"{key}_requirements_normalized.jsonl").write_text(json.dumps({"requirement_id": "REQ-1", "source_quote": "Units will report."}) + "\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    (tmp_path / "processed").mkdir()
    monkeypatch.setenv("REQBOT_PROCESSED_DIR", str(tmp_path / "processed"))
    monkeypatch.setattr(access, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.setattr(access, "FAILED_ATTEMPT_DELAY_SECONDS", 0)
    token, _ = access.create_admin_token()
    return SimpleNamespace(tmp=tmp_path, headers={"Authorization": f"Bearer {token}"})


def _client() -> TestClient:
    from api.app import app
    return TestClient(app)


# -- the job kinds -----------------------------------------------------------------------

def test_a_questions_job_builds_its_whole_command_and_fixes_the_model(tmp_path):
    _library(tmp_path, "afi99-1")
    store = JobStore(tmp_path / "processed" / ".jobs")
    job = js.enqueue_questions("afi99-1", store=store, cfg=_cfg(tmp_path), requested_by="cli")
    argv = job["argv"]
    assert argv[0] == sys.executable and argv[2:4] == ["questions", "--doc"] and argv[4] == "afi99-1"
    assert argv[argv.index("--model") + 1] == js.QUESTIONS_MODEL and "--progress-json" in argv
    assert argv[argv.index("--ollama-url") + 1] == "http://ollama.test:11434"
    assert job["kind"] == "questions" and job["title"] == "Draft questions for afi99-1" and job["params"]["doc_key"] == "afi99-1"
    assert job["requires"] == {"ollama_url": "http://ollama.test:11434", "ollama_models": [js.QUESTIONS_MODEL], "qdrant_url": ""}


def test_the_questions_model_is_the_one_the_command_and_the_question_writer_use():
    assert js.QUESTIONS_MODEL == audit_questions.MODEL


def test_only_a_document_in_the_library_can_be_named_and_only_once_at_a_time(tmp_path):
    _library(tmp_path, "afi99-1", "DODI 5200.01")
    store, cfg = JobStore(tmp_path / "processed" / ".jobs"), _cfg(tmp_path)
    with pytest.raises(LookupError):
        js.enqueue_questions("no-such-doc", store=store, cfg=cfg)
    for bad in ("", "../etc", "a/b", "x*", ".hidden", "a\\b"):
        with pytest.raises(ValueError):
            js.enqueue_questions(bad, store=store, cfg=cfg)
    first = js.enqueue_questions("DODI 5200.01", store=store, cfg=cfg)
    with pytest.raises(js.JobAlreadyQueued) as e:
        js.enqueue_questions("DODI 5200.01", store=store, cfg=cfg)
    assert e.value.job_id == first["id"]
    assert js.enqueue_questions("afi99-1", store=store, cfg=cfg)["state"] == "queued"  # another document is independent


def test_a_reindex_job_needs_the_model_machine_and_qdrant_and_runs_one_at_a_time(tmp_path):
    store, cfg = JobStore(tmp_path / "processed" / ".jobs"), _cfg(tmp_path)
    job = js.enqueue_reindex(store=store, cfg=cfg, requested_by="cli")
    argv = job["argv"]
    assert argv[2] == "reindex" and "--progress-json" in argv and "--requirements-only" not in argv
    assert argv[argv.index("--qdrant-url") + 1] == "http://qdrant.test:6333"
    assert job["requires"]["qdrant_url"] == "http://qdrant.test:6333" and job["requires"]["ollama_models"] == ["nomic-embed-text"]
    assert job["env"] == {"REQBOT_EMBEDDING_MODEL": "nomic-embed-text"}
    with pytest.raises(js.JobAlreadyQueued):
        js.enqueue_reindex(store=store, cfg=cfg)
    store.cancel(job["id"])
    partial = js.enqueue_reindex(store=store, cfg=cfg, requirements_only=True)
    assert "--requirements-only" in partial["argv"] and "requirements only" in partial["title"]


def test_the_summary_carries_what_a_screen_matches_a_job_to_its_document_by(tmp_path):
    _library(tmp_path, "afi99-1")
    store = JobStore(tmp_path / "processed" / ".jobs")
    job = js.enqueue_questions("afi99-1", store=store, cfg=_cfg(tmp_path))
    s = js.summarize(job)
    assert s["params"] == {"doc_key": "afi99-1", "profile": "cybersecurity"} and "model" not in s["params"] and "argv" not in s


# -- the routes -----------------------------------------------------------------------------

def test_the_new_routes_need_the_admin_code(env):
    c = _client()
    assert c.post("/api/jobs/questions", json={"doc_key": "x"}).status_code == 401
    assert c.post("/api/jobs/reindex", json={}).status_code == 401


def test_start_questions_queues_then_skips_a_duplicate_and_refuses_an_unknown_document(env):
    _library(env.tmp, "afi99-1")
    c, h = _client(), env.headers
    r = c.post("/api/jobs/questions", json={"doc_key": "afi99-1"}, headers=h)
    assert r.status_code == 202 and r.json()["result"] == "queued" and r.json()["job"]["kind"] == "questions"
    again = c.post("/api/jobs/questions", json={"doc_key": "afi99-1"}, headers=h)
    assert again.status_code == 200 and again.json()["result"] == "skipped" and again.json()["job_id"] == r.json()["job"]["id"]  # nothing was accepted: 200, not 202
    missing = c.post("/api/jobs/questions", json={"doc_key": "nope"}, headers=h)
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "no_such_document"
    bad = c.post("/api/jobs/questions", json={"doc_key": "../x"}, headers=h)
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "bad_request"
    assert len(js.default_store().list_jobs()) == 1


def test_start_reindex_queues_one_rebuild(env):
    c, h = _client(), env.headers
    r = c.post("/api/jobs/reindex", json={"requirements_only": True}, headers=h)
    assert r.status_code == 202 and r.json()["job"]["kind"] == "reindex" and r.json()["job"]["params"]["requirements_only"] is True
    again = c.post("/api/jobs/reindex", json={}, headers=h)
    assert again.status_code == 200 and again.json()["result"] == "skipped"


# -- progress -------------------------------------------------------------------------------

def test_draft_questions_reports_each_row_with_the_total():
    items = [{"checklist_item_id": f"CHK-{i}", "source_quote": f"Units will report item {i}.", "passage": "p", "applies_to": "", "item_flags": []} for i in range(3)]
    items.append({"checklist_item_id": "CHK-blank", "source_quote": "", "passage": "", "applies_to": "", "item_flags": []})  # not a row: no text
    seen = []
    with patch.object(audit_questions, "write"), patch.object(audit_questions, "load", return_value={}):
        audit_questions.draft_questions(items, Path("unused.jsonl"), model="m", call=lambda p: '{"question": "Does the unit report?"}', on_row=lambda d, t: seen.append((d, t)))
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_questions_with_the_flag_prints_one_progress_line_per_row_and_done(capsys):
    from cli.reqbot import cmd_questions
    from pipeline import progress

    def fake(items, path, *, on_row=None, **kw):
        for i in (1, 2):
            on_row(i, 2)
        return {"errors": 0}

    progress.disable()
    try:
        with patch("services.checklist_service.generate", return_value={"items": []}), patch("services.checklist_service.requirements_path", return_value=Path("x")), \
             patch.object(audit_questions, "draft_questions", fake):
            rc = cmd_questions(SimpleNamespace(doc="afi99-1", profile="cybersecurity", model="m", ollama_url="http://o", progress_json=True))
    finally:
        progress.disable()
    assert rc == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert lines == [{"step": "questions", "done": 1, "total": 2}, {"step": "questions", "done": 2, "total": 2}, {"step": "done"}]


def test_reindex_says_which_half_is_done_when_the_context_half_fails(caplog):
    import logging

    from cli.reqbot import cmd_reindex

    args = SimpleNamespace(requirements_only=False, qdrant_url="http://q", ollama_url="http://o", progress_json=False)
    files = {"doc": Path("/x/doc_requirements_normalized.jsonl")}
    with patch("core.artifact_resolver.resolve_latest_requirement_files", return_value=files), patch("cli.reqbot._reindex_requirements", return_value=True), \
         patch("cli.reqbot._reindex_context", return_value=False), patch("cli.reqbot._cfg") as cfg:
        cfg.processed_dir_path.return_value = Path("/tmp")
        cfg.embedding_model = "nomic-embed-text"
        with caplog.at_level(logging.INFO):
            assert cmd_reindex(args) == 1
    text = caplog.text
    assert "requirements index is rebuilt and live" in text and "context index was NOT rebuilt" in text and "already live beside the old context" in text


def test_a_retry_is_held_to_the_same_one_at_a_time_rule_as_the_original(tmp_path):
    _library(tmp_path, "afi99-1")
    store, cfg = JobStore(tmp_path / "processed" / ".jobs"), _cfg(tmp_path)
    first = js.enqueue_questions("afi99-1", store=store, cfg=cfg)
    store.cancel(first["id"])
    second = js.enqueue_questions("afi99-1", store=store, cfg=cfg)  # a new one was queued after the first was cancelled
    with pytest.raises(js.JobAlreadyQueued) as e:
        store.retry(first["id"])
    assert e.value.job_id == second["id"]
    store.cancel(second["id"])
    assert store.retry(first["id"])["state"] == "queued"  # nothing in the way now
    # a rebuild too
    r1 = js.enqueue_reindex(store=store, cfg=cfg)
    store.cancel(r1["id"])
    r2 = js.enqueue_reindex(store=store, cfg=cfg)
    with pytest.raises(js.JobAlreadyQueued):
        store.retry(r1["id"])
    assert r2["state"] == "queued"


def test_retrying_over_the_api_answers_409_when_the_same_thing_is_already_queued(env):
    _library(env.tmp, "afi99-1")
    c, h = _client(), env.headers
    first = c.post("/api/jobs/questions", json={"doc_key": "afi99-1"}, headers=h).json()["job"]
    c.post(f"/api/jobs/{first['id']}/cancel", headers=h)
    c.post("/api/jobs/questions", json={"doc_key": "afi99-1"}, headers=h)
    r = c.post(f"/api/jobs/{first['id']}/retry", headers=h)
    assert r.status_code == 409 and "already queued or running" in r.json()["detail"]


def test_the_profile_the_checklist_was_built_with_goes_to_the_questions_job(tmp_path):
    _library(tmp_path, "afi99-1")
    store, cfg = JobStore(tmp_path / "processed" / ".jobs"), _cfg(tmp_path)
    job = js.enqueue_questions("afi99-1", store=store, cfg=cfg)
    assert job["argv"][job["argv"].index("--profile") + 1] == "cybersecurity" and job["params"]["profile"] == "cybersecurity"
    for bad in ("../x", "a b", "", "x" * 80):
        if bad:
            with pytest.raises(ValueError):
                js.enqueue_questions("afi99-1", store=store, cfg=cfg, profile=bad)
    with pytest.raises(ValueError, match="unknown profile"):
        js.enqueue_questions("afi99-1", store=store, cfg=cfg, profile="no-such-profile")


def test_one_questions_job_per_document_and_profile(tmp_path):
    _library(tmp_path, "afi99-1")
    store, cfg = JobStore(tmp_path / "processed" / ".jobs"), _cfg(tmp_path)
    from core import (
        profiles as _profiles,  # only one profile ships; a second one is stood in for here
    )
    with patch.object(_profiles, "load_profile", lambda name: {"name": name}):
        js.enqueue_questions("afi99-1", store=store, cfg=cfg, profile="cybersecurity")
        with pytest.raises(js.JobAlreadyQueued):
            js.enqueue_questions("afi99-1", store=store, cfg=cfg, profile="cybersecurity")
        second = js.enqueue_questions("afi99-1", store=store, cfg=cfg, profile="another")  # a different profile is a different checklist
    assert second["params"]["profile"] == "another"


def test_the_route_passes_the_profile_and_refuses_an_unknown_one(env):
    _library(env.tmp, "afi99-1")
    c, h = _client(), env.headers
    ok = c.post("/api/jobs/questions", json={"doc_key": "afi99-1", "profile": "cybersecurity"}, headers=h)
    assert ok.status_code == 202 and ok.json()["job"]["params"]["profile"] == "cybersecurity"
    bad = c.post("/api/jobs/questions", json={"doc_key": "afi99-1", "profile": "no-such-profile"}, headers=h)
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "bad_request"

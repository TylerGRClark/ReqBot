"""Remove a document (docs/WEB_UI_PARITY_PLAN.md, section 9): run folders to the trash, points out of both collections, never without a confirmation.

Uses the in-memory Qdrant stand-in from the replace tests; nothing here touches a real index."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core import access
from services import library_service as lib
from tests.unit.test_index_replace import FakeQdrant  # the same stand-in the replace tests use


def _doc(processed: Path, key: str, runs: tuple[str, ...] = ("20261001_120000",)) -> list[Path]:
    out = []
    for stamp in runs:
        d = processed / f"{key}_{stamp}"
        d.mkdir(parents=True)
        (d / f"{key}_requirements_normalized.jsonl").write_text(json.dumps({"requirement_id": "REQ-1", "source_quote": "x", "source_pdf": f"{key}.pdf"}) + "\n")
        (d / f"{key}_audit_questions.jsonl").write_text("{}\n")
        out.append(d)
    return out


def _points(q: FakeQdrant, key: str, n: int = 3, chunks: bool = False) -> None:
    q.exists = True
    for i in range(n):
        q.points[f"{key}-{'c' if chunks else 'r'}{i}"] = {"source_pdf": f"{key}_chunks.jsonl" if chunks else f"{key}.pdf"}


@pytest.fixture
def library(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    return processed


def test_a_removal_moves_every_run_folder_to_the_trash_and_takes_only_this_documents_points(library):
    folders = _doc(library, "afi99-1", ("20261001_120000", "20261009_213629"))
    other = _doc(library, "afi10-2402")
    (library / ".uploads").mkdir()
    q = FakeQdrant()
    _points(q, "afi99-1", 3)
    _points(q, "afi99-1", 2, chunks=True)
    _points(q, "afi10-2402", 4)
    _points(q, "afi10-2402", 1, chunks=True)
    out = lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[], client=q, now=1_791_000_000)
    assert out["document"] == "afi99-1" and out["points_removed"] == {"requirements": 3, "context": 2}
    assert sorted(out["run_folders_moved"]) == sorted(f.name for f in folders)
    assert not any(f.exists() for f in folders)
    trash = Path(out["trash"])
    assert trash.parent == library / ".trash" and all((trash / f.name / "afi99-1_requirements_normalized.jsonl").is_file() for f in folders)  # moved whole, sidecars included
    assert other[0].is_dir() and (library / ".uploads").is_dir()
    assert {i for i in q.points} == {f"afi10-2402-r{i}" for i in range(4)} | {"afi10-2402-c0"}


def test_nothing_is_removed_without_the_confirmation_and_the_exact_key(library):
    folders = _doc(library, "afi99-1")
    q = FakeQdrant()
    _points(q, "afi99-1")
    for kwargs in (dict(confirm=False, confirm_name="afi99-1"), dict(confirm=True, confirm_name=""), dict(confirm=True, confirm_name="afi99"), dict(confirm=True, confirm_name="AFI99-1")):
        with pytest.raises(lib.ConfirmationRequired):
            lib.remove_document(library, "afi99-1", active_jobs=[], client=q, **kwargs)
    assert folders[0].is_dir() and len(q.points) == 3 and q.deletes == 0


def test_a_document_with_a_job_queued_or_running_is_not_removed(library):
    _doc(library, "afi99-1")
    q = FakeQdrant()
    _points(q, "afi99-1")
    for job in ({"id": "J1", "state": "queued", "params": {"stem": "afi99-1"}}, {"id": "J2", "state": "running", "params": {"doc_key": "afi99-1"}}):
        with pytest.raises(lib.RemoveBlocked) as e:
            lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[job], client=q)
        assert e.value.job_ids == [job["id"]]
    done = {"id": "J3", "state": "succeeded", "params": {"stem": "afi99-1"}}
    unrelated = {"id": "J4", "state": "running", "params": {"stem": "afi10-2402"}}
    assert lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[done, unrelated], client=q)["document"] == "afi99-1"


def test_unknown_documents_and_unsafe_keys_are_refused_before_anything_moves(library):
    _doc(library, "afi99-1")
    with pytest.raises(LookupError):
        lib.remove_document(library, "nope", confirm=True, confirm_name="nope", active_jobs=[])
    for bad in ("", ".hidden", "../x", "a/b", "x*"):
        with pytest.raises(ValueError):
            lib.remove_document(library, bad, confirm=True, confirm_name=bad, active_jobs=[])
    assert (library / "afi99-1_20261001_120000").is_dir()


def test_a_failure_cleaning_the_index_moves_nothing_and_a_retry_finishes_the_job(library):
    folders = _doc(library, "afi99-1")
    q = FakeQdrant()
    _points(q, "afi99-1", 3)
    real_delete = q.delete

    def broken(*a, **kw):
        raise RuntimeError("Qdrant went away")

    q.delete = broken
    with pytest.raises(RuntimeError, match="Nothing was moved"):
        lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[], client=q)
    assert folders[0].is_dir() and not (library / ".trash").exists()
    q.delete = real_delete
    assert lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[], client=q)["points_removed"]["requirements"] == 3
    assert not folders[0].exists()


def test_an_extension_in_capitals_is_the_same_document(library):
    _doc(library, "policy")
    q = FakeQdrant()
    q.points["a"] = {"source_pdf": "policy.PDF"}
    q.points["b"] = {"source_pdf": "other.pdf"}
    lib.remove_document(library, "policy", confirm=True, confirm_name="policy", active_jobs=[], client=q)
    assert set(q.points) == {"b"}


# -- the route and the command ---------------------------------------------------------------

@pytest.fixture
def api(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    monkeypatch.setenv("REQBOT_PROCESSED_DIR", str(processed))
    monkeypatch.setattr(access, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.setattr(access, "FAILED_ATTEMPT_DELAY_SECONDS", 0)
    token, _ = access.create_admin_token()
    q = FakeQdrant()
    monkeypatch.setattr("api.routes.library._qdrant", lambda url: q)
    from api.app import app
    return SimpleNamespace(processed=processed, headers={"Authorization": f"Bearer {token}"}, client=TestClient(app), q=q)


def test_the_route_needs_the_admin_code(api):
    assert api.client.post("/api/documents/remove", json={"doc_key": "x"}).status_code == 401


def test_the_route_answers_for_each_case(api):
    _doc(api.processed, "afi99-1")
    _points(api.q, "afi99-1", 2)
    post = lambda body: api.client.post("/api/documents/remove", json=body, headers=api.headers)  # noqa: E731
    r = post({"doc_key": "afi99-1"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "confirmation_required"
    assert post({"doc_key": "nope", "confirm": True, "confirm_name": "nope"}).status_code == 404
    assert post({"doc_key": "../x", "confirm": True, "confirm_name": "../x"}).status_code == 422
    from services import job_service as js
    js.default_store().enqueue("ingest", ["x"], title="t", params={"stem": "afi99-1"})
    busy = post({"doc_key": "afi99-1", "confirm": True, "confirm_name": "afi99-1"})
    assert busy.status_code == 409 and busy.json()["detail"]["code"] == "jobs_active" and len(api.q.points) == 2
    js.default_store().cancel(js.default_store().list_jobs()[0]["id"])
    ok = post({"doc_key": "afi99-1", "confirm": True, "confirm_name": "afi99-1"})
    assert ok.status_code == 200 and ok.json()["points_removed"]["requirements"] == 2 and not api.q.points
    assert not list(api.processed.glob("afi99-1_*"))


def test_the_route_says_when_the_index_cannot_be_reached(api):
    _doc(api.processed, "afi99-1")
    _points(api.q, "afi99-1", 2)
    api.q.scroll = lambda **kw: (_ for _ in ()).throw(OSError("connection refused"))
    r = api.client.post("/api/documents/remove", json={"doc_key": "afi99-1", "confirm": True, "confirm_name": "afi99-1"}, headers=api.headers)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "index_unreachable"
    assert (api.processed / "afi99-1_20261001_120000").is_dir()


def test_the_command_only_describes_without_yes_and_does_it_with_yes(library, capsys):
    from cli import reqbot

    folders = _doc(library, "afi99-1")
    q = FakeQdrant()
    _points(q, "afi99-1", 2)
    cfg = SimpleNamespace(processed_dir_path=lambda: library)
    with patch.object(reqbot, "_cfg", cfg), patch("qdrant_client.QdrantClient", return_value=q):
        assert reqbot.cmd_remove(SimpleNamespace(doc="afi99-1", yes=False, qdrant_url="http://q")) == 1
        assert "Nothing was changed" in capsys.readouterr().out and folders[0].is_dir() and len(q.points) == 2
        assert reqbot.cmd_remove(SimpleNamespace(doc="afi99-1", yes=True, qdrant_url="http://q")) == 0
        assert "Removed afi99-1" in capsys.readouterr().out and not folders[0].exists() and not q.points
        assert reqbot.cmd_remove(SimpleNamespace(doc="afi99-1", yes=True, qdrant_url="http://q")) == 1  # already gone


# -- the reviewer's findings on this change ----------------------------------------------------

class NotFound(Exception):
    status_code = 404


class SomeMissing(FakeQdrant):
    """An index where some collections were never created."""

    def __init__(self, missing=()):
        super().__init__()
        self.missing = set(missing)

    def get_collection(self, name):
        if name in self.missing:
            raise NotFound(f"Collection `{name}` doesn't exist!")
        return super().get_collection(name)


def test_a_rebuild_in_progress_blocks_a_removal(library):
    _doc(library, "afi99-1")
    q = FakeQdrant()
    _points(q, "afi99-1")
    for state in ("queued", "running"):
        with pytest.raises(lib.RemoveBlocked):
            lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", client=q,
                                active_jobs=[{"id": "R1", "kind": "reindex", "state": state, "params": {"requirements_only": False}}])
    assert len(q.points) == 3
    finished = [{"id": "R0", "kind": "reindex", "state": "succeeded", "params": {}}]
    assert lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", client=q, active_jobs=finished)["document"] == "afi99-1"


def test_a_document_is_found_from_its_artifacts_wherever_its_folder_is_called(library):
    custom = library / "my-own-folder"
    custom.mkdir()
    (custom / "afi99-1_requirements_normalized.jsonl").write_text(json.dumps({"requirement_id": "R", "source_quote": "x"}) + "\n")
    (custom / "afi99-1_chunks.jsonl").write_text("{}\n")
    out = lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[])
    assert out["run_folders_moved"] == ["my-own-folder"] and not custom.exists()
    assert (Path(out["trash"]) / "my-own-folder" / "afi99-1_chunks.jsonl").is_file()


def test_a_folder_shared_with_another_document_gives_up_only_this_documents_files(library):
    shared = library / "batch_run"
    shared.mkdir()
    for key in ("afi99-1", "afi99-1_2", "afi10-2402"):
        (shared / f"{key}_requirements_normalized.jsonl").write_text(json.dumps({"requirement_id": "R", "source_quote": "x"}) + "\n")
        (shared / f"{key}_chunks.jsonl").write_text("{}\n")
    (shared / "notes.txt").write_text("someone's notes")
    out = lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[])
    assert out["files_moved"] == 2
    left = sorted(p.name for p in shared.iterdir())
    assert left == ["afi10-2402_chunks.jsonl", "afi10-2402_requirements_normalized.jsonl", "afi99-1_2_chunks.jsonl", "afi99-1_2_requirements_normalized.jsonl", "notes.txt"]
    assert sorted(p.name for p in (Path(out["trash"]) / "batch_run").iterdir()) == ["afi99-1_chunks.jsonl", "afi99-1_requirements_normalized.jsonl"]


def test_artifacts_lying_directly_in_the_processed_folder_are_moved_file_by_file(library):
    (library / "afi99-1_requirements_normalized.jsonl").write_text(json.dumps({"requirement_id": "R", "source_quote": "x"}) + "\n")
    (library / "afi99-1_audit_questions.jsonl").write_text("{}\n")
    (library / "other.pdf").write_bytes(b"%PDF-1.4")
    out = lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[])
    assert library.is_dir() and (library / "other.pdf").is_file() and not list(library.glob("afi99-1_*"))
    assert out["files_moved"] == 2


def test_a_removed_document_in_the_trash_is_not_found_again(library):
    _doc(library, "afi99-1")
    lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[])
    assert list((library / ".trash").rglob("afi99-1_requirements_normalized.jsonl"))
    with pytest.raises(LookupError):
        lib.describe(library, "afi99-1")
    with pytest.raises(LookupError):
        lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[])


def test_collections_that_do_not_exist_are_already_clean(library):
    folders = _doc(library, "afi99-1")
    q = SomeMissing(missing={lib.DOCS_COLLECTION, lib.CONTEXT_COLLECTION})  # a document ingested without indexing, or a fresh install
    out = lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[], client=q)
    assert out["points_removed"] == {"requirements": 0, "context": 0} and not folders[0].exists()
    _doc(library, "afi10-2402")
    half = SomeMissing(missing={lib.CONTEXT_COLLECTION})
    _points(half, "afi10-2402", 2)
    assert lib.remove_document(library, "afi10-2402", confirm=True, confirm_name="afi10-2402", active_jobs=[], client=half)["points_removed"] == {"requirements": 2, "context": 0}


def test_an_index_that_cannot_be_reached_is_not_mistaken_for_clean(library):
    folders = _doc(library, "afi99-1")

    class Down(FakeQdrant):
        def get_collection(self, name):
            raise OSError("connection refused")

    with pytest.raises(RuntimeError, match="Nothing was moved"):
        lib.remove_document(library, "afi99-1", confirm=True, confirm_name="afi99-1", active_jobs=[], client=Down())
    assert folders[0].is_dir()

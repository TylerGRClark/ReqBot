"""A removed document is out of the library everywhere (docs/WEB_UI_PARITY_PLAN.md, section 9, stage 6c).

Removing moves a document's run folders into `<processed>/.trash/`. Everything that lists, searches or rebuilds the library scans the processed folder, so each of those has to
leave hidden folders alone, or the document comes straight back: listed in the corpus, offered in the search filter, and put back into search by the next rebuild. These tests
remove a document through the real service and then ask each of those places, so a new place that scans the folder its own way fails here.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from core import artifact_resolver
from services import docs_service, intake_service, library_service, status_service
from tests.unit.test_index_replace import FakeQdrant

REQ = {"requirement_id": "REQ-1", "source_quote": "Passwords shall be long."}


def _run(processed: Path, key: str, stamp: str = "20261001_120000") -> Path:
    d = processed / f"{key}_{stamp}"
    d.mkdir(parents=True)
    (d / f"{key}_requirements_normalized.jsonl").write_text(json.dumps({**REQ, "source_pdf": f"{key}.pdf", "document_hash_full": f"hash-{key}"}) + "\n")
    (d / f"{key}_normalization_failures.jsonl").write_text("{}\n")
    (d / f"{key}_chunks.jsonl").write_text("{}\n")
    return d


@pytest.fixture
def library(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    _run(processed, "keep-me")
    _run(processed, "remove-me", "20261001_120000")
    _run(processed, "remove-me", "20261009_213629")  # a document with two runs: both have to leave
    q = FakeQdrant()
    q.exists = True
    q.points["r1"] = {"source_pdf": "remove-me.pdf"}
    library_service.remove_document(processed, "remove-me", confirm=True, confirm_name="remove-me", active_jobs=[], client=q, now=1_791_000_000)
    return processed


def _keys(result: dict) -> list[str]:
    return [d["doc_key"] for d in result["docs"]]


def test_the_trash_holds_the_removed_document_and_nothing_else_does(library):
    trashed = sorted(p.name for p in (library / ".trash").rglob("*_requirements_normalized.jsonl"))
    assert trashed == ["remove-me_requirements_normalized.jsonl"] * 2


def test_the_document_list_does_not_show_a_removed_document(library):
    result = docs_service.list_docs(library)
    assert _keys(result) == ["keep-me"] and result["total_docs"] == 1 and result["total_reqs"] == 1


def test_the_source_pdf_lookup_does_not_find_a_removed_document(library):
    assert docs_service.resolve_source_pdfs(library, ["keep-me", "remove-me"]) == {"keep-me": "keep-me.pdf", "remove-me": ""}


def test_the_rebuild_does_not_see_a_removed_document(library):
    """`reqbot reindex` takes its documents from this resolver, so a removed one is not put back into search."""
    assert set(artifact_resolver.resolve_latest_requirement_files(library)) == {"keep-me"}
    with pytest.raises(ValueError):
        artifact_resolver.resolve_requirement_file(library, "remove-me")  # a checklist, a question run or a trace for it is "no such document"


def test_the_library_scan_for_uploads_does_not_see_a_removed_document(library):
    assert set(intake_service.library_documents(library)) == {"keep-me"}
    # putting the same file in again is a new document, not "already in the library, nothing to do"
    assert intake_service.classify(library, "remove-me", "hash-remove-me", [])["status"] == "new"


def test_the_status_listing_does_not_show_a_removed_document(library):
    with patch("requests.get", side_effect=requests.ConnectionError("down")):
        result = status_service.check("http://ollama:11434", "http://qdrant:6333", library)
    assert [Path(d["path"]).name for d in result["processed_documents"]] == ["keep-me_requirements_normalized.jsonl"]


def test_a_removal_can_be_put_back_by_moving_the_folders_out_of_the_trash(library):
    stamp = next((library / ".trash").iterdir())
    for folder in stamp.iterdir():
        folder.rename(library / folder.name)
    assert set(artifact_resolver.resolve_latest_requirement_files(library)) == {"keep-me", "remove-me"}
    assert _keys(docs_service.list_docs(library)) == ["keep-me", "remove-me"]


def test_hidden_folders_are_skipped_below_the_library_but_not_when_the_library_itself_is_hidden(tmp_path):
    hidden_library = tmp_path / ".reqbot" / "processed"
    hidden_library.mkdir(parents=True)
    _run(hidden_library, "doc")
    (hidden_library / ".inbox").mkdir()
    shared = hidden_library / ".trash" / "20261012_150000"
    shared.mkdir(parents=True)
    _run(shared, "gone")
    found = artifact_resolver.find_run_files(hidden_library, "_requirements_normalized.jsonl")
    assert [p.name for p in found] == ["doc_requirements_normalized.jsonl"]
    assert artifact_resolver.find_run_files(tmp_path / "nowhere", "_requirements_normalized.jsonl") == []


def test_a_hidden_folder_nested_in_a_run_folder_is_skipped_too(tmp_path):
    processed = tmp_path / "processed"
    _run(processed, "doc")
    nested = processed / "doc_20261001_120000" / ".old"
    nested.mkdir()
    (nested / "doc_requirements_normalized.jsonl").write_text("{}\n")
    found = artifact_resolver.find_run_files(processed, "_requirements_normalized.jsonl")
    assert [p.parent.name for p in found] == ["doc_20261001_120000"]

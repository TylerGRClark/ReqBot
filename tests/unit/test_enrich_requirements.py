"""Regression test for enrich_requirements.py's enriched-filename derivation
(Codex PR #92 review, WP-24.3 follow-up).

A broad `.replace("_requirements_normalized", "")` on the normalized JSONL's
stem would collapse every occurrence of that substring, not just the trailing
one — so a PDF whose own stem happens to contain "_requirements_normalized"
(e.g. "policy_requirements_normalized_v1.pdf") produced a mangled enriched
filename whose doc_key no longer matched the real *_chunks.jsonl file,
silently breaking context indexing for that document (ask --context / trace
--context). The fix reuses core.artifact_resolver.doc_key_from_requirements_path()
(anchored suffix strip) instead.
"""
import json
from pathlib import Path
from unittest.mock import patch

import requests

import pipeline.enrich_requirements as enrich_mod

_BASE_REQ = {
    "requirement_id": "REQ-abc123",
    "source_quote": "Systems shall restrict access.",
    "source_ref": "T-1",
    "description": "",
    "domain_tags": [],
    "requirement_type": "",
    "chunk_id": 1,
    "page_start": 1,
    "page_end": 1,
    "confidence": 0.9,
    "document_id": "abcd1234",
    "document_hash_full": "abcd1234abcd1234",
    "source_pdf": "policy_requirements_normalized_v1.pdf",
    "schema_version": "2.0",
    "pipeline_version": "1.0",
    "extraction_model": "test-model",
    "run_timestamp": "2026-01-01T00:00:00Z",
    "section_ref_path": [],
    "section_title_path": [],
    "parent_section_ref": None,
    "parent_context": None,
    "child_section_refs": [],
}


def test_enriched_filename_preserves_pdf_stem_containing_normalized_substring(tmp_path):
    # Simulates a PDF literally named "policy_requirements_normalized_v1.pdf" —
    # the resulting normalized JSONL's stem contains "_requirements_normalized"
    # twice: once as part of the original filename, once as the real suffix.
    stem = "policy_requirements_normalized_v1"
    norm_file = tmp_path / f"{stem}_requirements_normalized.jsonl"
    norm_file.write_text(json.dumps(_BASE_REQ) + "\n", encoding="utf-8")

    fake_resp = type("R", (), {"raise_for_status": lambda self: None})()

    with (
        patch.object(enrich_mod, "_enrich_batch", return_value=[
            {"description": "d", "domain_tags": ["access-control"], "requirement_type": "policy"}
        ]),
        patch.object(requests, "get", return_value=fake_resp),
    ):
        enriched_path = enrich_mod.run(
            str(norm_file), str(tmp_path),
            model="test-model",
            ollama_url="http://localhost:11434",
        )

    # Must preserve the full original stem, not collapse the embedded
    # "_requirements_normalized" substring found earlier in the filename.
    assert Path(enriched_path).name == f"{stem}_requirements_enriched.jsonl"


def test_cached_enrichment_keeps_only_its_own_fields_and_the_fresh_record_wins_the_rest(tmp_path):
    """Codex review, PR #185 (first written for parent stems, deleted with the list-writing extraction step): a record already in the
    enrichment resume-cache keeps the cache's LLM fields, and every other field comes from this run's normalized record, so a stale cache
    cannot bring back fields the pipeline no longer writes or wrote differently."""
    doc_key = "cachetest"
    norm_file = tmp_path / f"{doc_key}_requirements_normalized.jsonl"
    fresh = {**_BASE_REQ, "requirement_id": "REQ-cached", "source_quote": "(3) Restrain competition.", "chunk_id": 2, "source_pdf": f"{doc_key}.pdf",
             "explained_text": "Classification shall not be used to: Restrain competition.", "clause_label": "PROHIBITION"}
    norm_file.write_text(json.dumps(fresh) + "\n", encoding="utf-8")
    enriched_file = tmp_path / f"{doc_key}_requirements_enriched.jsonl"
    cached_record = {**fresh, "explained_text": "stale", "clause_label": "UNSURE", "parent_stem": "stale stem", "embedding_text": "stale",
                     "description": "Cached description", "domain_tags": ["access-control"], "requirement_type": "policy", "enrichment_model": "test-model"}
    enriched_file.write_text(json.dumps(cached_record) + "\n", encoding="utf-8")

    fake_resp = type("R", (), {"raise_for_status": lambda self: None})()
    with patch.object(requests, "get", return_value=fake_resp):
        enriched_path = enrich_mod.run(str(norm_file), str(tmp_path), model="test-model", ollama_url="http://localhost:11434")

    result = json.loads(Path(enriched_path).read_text(encoding="utf-8").splitlines()[0])
    assert result["description"] == "Cached description" and result["domain_tags"] == ["access-control"]  # the cache was used, no model call
    assert result["explained_text"] == "Classification shall not be used to: Restrain competition."
    assert result["clause_label"] == "PROHIBITION"
    assert "parent_stem" not in result and "embedding_text" not in result

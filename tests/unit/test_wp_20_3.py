"""WP-20.3 unit tests — profile-aware pipeline integration.

Verifies that profile vocabulary (domain_tags, requirement_types, obligation_verbs)
flows correctly through normalizing (parse_and_normalize), Step D.5 (enrich_requirements),
and run_pipeline. The Step C tests (validate_requirement, the list-writing prompt) were deleted with
that step: requirement finding is clause labeling now, which uses no profile vocabulary. These tests do NOT call Ollama or the filesystem pipeline — they
test the plumbing in isolation.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pipeline.enrich_requirements as enrich_mod
import pipeline.parse_and_normalize as normalize_mod
from core.profiles import load_profile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CYBER_PROFILE = load_profile("cybersecurity")

_TEST_DOMAIN_PROFILE = load_profile("test-domain")


# ---------------------------------------------------------------------------
# Test profile: test-domain.json loads cleanly (plumbing validation)
# ---------------------------------------------------------------------------

def test_test_domain_profile_loads():
    p = load_profile("test-domain")
    assert p["name"] == "test-domain"
    assert p["domain_tags"] == ["test-tag-alpha", "test-tag-beta"]
    assert p["requirement_types"] == ["policy", "guidance"]


def test_test_domain_profile_has_required_fields():
    from core.profiles import REQUIRED_FIELDS
    p = load_profile("test-domain")
    for field in REQUIRED_FIELDS:
        assert field in p, f"Missing: {field}"


# ---------------------------------------------------------------------------
# Step D.5: _validate_enrichment uses profile domain tags and requirement types
# ---------------------------------------------------------------------------

def test_validate_enrichment_accepts_profile_tag():
    raw = {
        "description": "Test requirement.",
        "domain_tags": ["test-tag-beta"],
        "requirement_type": "guidance",
    }
    result = enrich_mod._validate_enrichment(
        raw,
        valid_domain_tags=_TEST_DOMAIN_PROFILE["domain_tags"],
        valid_requirement_types=_TEST_DOMAIN_PROFILE["requirement_types"],
    )
    assert result["domain_tags"] == ["test-tag-beta"]
    assert result["requirement_type"] == "guidance"


def test_validate_enrichment_rejects_cybersecurity_tag_under_test_profile():
    raw = {
        "description": "Test requirement.",
        "domain_tags": ["audit-and-logging"],  # valid cybersecurity tag
        "requirement_type": "technical-control",  # valid cybersecurity type
    }
    result = enrich_mod._validate_enrichment(
        raw,
        valid_domain_tags=_TEST_DOMAIN_PROFILE["domain_tags"],
        valid_requirement_types=_TEST_DOMAIN_PROFILE["requirement_types"],
    )
    assert result["domain_tags"] == []
    assert result["requirement_type"] == ""


def test_validate_enrichment_cybersecurity_profile_unchanged():
    raw = {
        "description": "MFA must be enforced.",
        "domain_tags": ["authentication-and-identity"],
        "requirement_type": "technical-control",
    }
    result = enrich_mod._validate_enrichment(
        raw,
        valid_domain_tags=_CYBER_PROFILE["domain_tags"],
        valid_requirement_types=_CYBER_PROFILE["requirement_types"],
    )
    assert result["domain_tags"] == ["authentication-and-identity"]
    assert result["requirement_type"] == "technical-control"


# ---------------------------------------------------------------------------
# run_pipeline: profile_name flows through to step C and D.5
# ---------------------------------------------------------------------------

def test_run_pipeline_passes_profile_to_normalizing(tmp_path):
    """run_pipeline.run() loads the named profile and passes it to normalizing (parse_and_normalize.run()); the clause labeler takes none."""
    from pipeline import run_pipeline

    captured = {}

    def fake_step_c(chunks_jsonl, output_dir, **kwargs):
        captured["labeler_kwargs"] = kwargs
        # Write minimal output file so pipeline can continue
        out = Path(output_dir) / "doc_extracted_requirements.jsonl"
        out.write_text("", encoding="utf-8")
        return str(out)

    def fake_step_d(reqs_jsonl, chunks_jsonl, pdf_path, output_dir, **kwargs):
        captured["profile"] = kwargs.get("profile")
        norm = Path(output_dir) / "doc_requirements_normalized.jsonl"
        norm.write_text("", encoding="utf-8")
        return str(norm)

    def fake_step_e(jsonl, output_dir, source_pdf, **kwargs):
        pass

    # Provide a minimal chunks.jsonl so Step C is called
    chunks = tmp_path / "doc_chunks.jsonl"
    chunks.write_text('{"chunk_id": 1, "text": "test"}\n', encoding="utf-8")

    with (
        patch.object(run_pipeline, "run", wraps=run_pipeline.run),
        # WP-34.1: docling is the only ingestion path now, so this test mocks it
        # at its two entry points rather than routing around it via a legacy
        # layout_mode -- this test is about profile passing, not docling itself.
        # ancestry_result is never inspected since run_structure_aware is also
        # mocked, so a bare object() placeholder is enough.
        patch("pipeline.run_pipeline._docling_available", return_value=True),
        patch("pipeline.section_parser.run", return_value=object()),
        patch("pipeline.chunk_text.run_structure_aware", return_value=str(chunks)),
        patch("pipeline.clause_labeling.run", side_effect=fake_step_c),
        patch("pipeline.parse_and_normalize.run", side_effect=fake_step_d),
        patch("pipeline.aggregate_and_export.run", side_effect=fake_step_e),
    ):
        # We need a fake PDF to exist
        fake_pdf = tmp_path / "doc.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        run_pipeline.run(
            str(fake_pdf),
            str(tmp_path),
            skip_enrichment=True,
            profile_name="test-domain",
        )

    assert "profile" not in captured["labeler_kwargs"]
    assert captured.get("profile") is not None
    assert captured["profile"]["name"] == "test-domain"
    assert captured["profile"]["domain_tags"] == ["test-tag-alpha", "test-tag-beta"]


# ---------------------------------------------------------------------------
# Review-round fixes — Gemini: empty list validation in core/profiles.py
# ---------------------------------------------------------------------------

def test_empty_obligation_verbs_raises(tmp_path):
    import json as _json

    import pytest

    import core.profiles as _profiles_mod
    from core.profiles import load_profile as _load

    bad = {
        "name": "bad-profile",
        "obligation_verbs": [],
        "skip_sections": [],
        "domain_tags": ["test-tag-alpha"],
        "requirement_types": ["policy"],
    }
    (tmp_path / "bad-profile.json").write_text(_json.dumps(bad), encoding="utf-8")

    with patch.object(_profiles_mod, "_PROFILES_DIR", tmp_path):
        with pytest.raises(ValueError, match="obligation_verbs"):
            _load("bad-profile")


# ---------------------------------------------------------------------------
# Review-round fixes — Codex P2 #1: parse_and_normalize uses profile tags
# ---------------------------------------------------------------------------

def _clause_files(tmp_path, rows: list[dict]):
    """The extraction and chunk files for clause rows: each row's quote is its own chunk's text, with the offsets clause labeling would write."""
    chunks, reqs = [], []
    for i, row in enumerate(rows):
        text = row["source_quote"]
        chunks.append({"chunk_id": i, "page_start": 1, "page_end": 1, "text": text, "raw_text": text})
        reqs.append({**row, "chunk_id": i, "clause_index": 0, "clause_label": "DUTY", "anchor_status": "exact", "anchor_start": 0, "anchor_end": len(text)})
    reqs_file = tmp_path / "doc_extracted_requirements.jsonl"
    reqs_file.write_text("".join(json.dumps(r) + "\n" for r in reqs), encoding="utf-8")
    chunks_file = tmp_path / "doc_chunks.jsonl"
    chunks_file.write_text("".join(json.dumps(c) + "\n" for c in chunks), encoding="utf-8")
    return reqs_file, chunks_file


def test_parse_normalize_uses_profile_domain_tags(tmp_path):
    """Step D must filter against the active profile's tags, not the hardcoded cybersecurity set."""
    req = {
        "source_quote": "Systems shall implement test-tag-alpha controls.",
        "source_ref": "T-1",
        "domain_tags": ["test-tag-alpha", "access-control"],
        "requirement_type": "policy",
        "description": "",
    }
    reqs_file, chunks_file = _clause_files(tmp_path, [req])

    out = normalize_mod.run(str(reqs_file), str(chunks_file), "", str(tmp_path), profile=_TEST_DOMAIN_PROFILE)

    records = [json.loads(line) for line in Path(out).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 1
    assert "test-tag-alpha" in records[0]["domain_tags"], "test-domain tag should pass through Step D"
    assert "access-control" not in records[0]["domain_tags"], "cybersecurity tag should be filtered in test-domain run"


def test_parse_normalize_uses_profile_requirement_types(tmp_path):
    """Step D must accept only requirement_types listed in the active profile."""
    req_valid = {
        "source_quote": "Systems shall implement policy controls.",
        "source_ref": "T-1",
        "domain_tags": ["test-tag-alpha"],
        "requirement_type": "guidance",  # valid in test-domain
        "description": "",
    }
    req_invalid_type = {
        "source_quote": "Systems must enforce technical controls.",
        "source_ref": "T-2",
        "domain_tags": ["test-tag-beta"],
        "requirement_type": "technical-control",  # valid for cybersecurity, NOT test-domain
        "description": "",
    }
    reqs_file, chunks_file = _clause_files(tmp_path, [req_valid, req_invalid_type])

    out = normalize_mod.run(str(reqs_file), str(chunks_file), "", str(tmp_path), profile=_TEST_DOMAIN_PROFILE)

    records = [json.loads(line) for line in Path(out).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 2
    by_ref = {r["source_ref"]: r for r in records}
    assert by_ref["T-1"]["requirement_type"] == "guidance"
    assert by_ref["T-2"]["requirement_type"] == "", "technical-control must be cleared under test-domain profile"


# ---------------------------------------------------------------------------
# Review-round fixes — Codex P2 #2: enrichment cache invalidated on profile change
# ---------------------------------------------------------------------------

_BASE_NORM_REQ = {
    "requirement_id": "REQ-cachetest000001",
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
    "source_pdf": "test.pdf",
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


def test_enrichment_cache_bypassed_on_profile_change(tmp_path):
    """A cache record stamped with 'cybersecurity' must be re-enriched under 'test-domain'."""
    norm_file = tmp_path / "doc_requirements_normalized.jsonl"
    norm_file.write_text(json.dumps(_BASE_NORM_REQ) + "\n", encoding="utf-8")

    cached = {
        **_BASE_NORM_REQ,
        "description": "Old cached enrichment.",
        "domain_tags": ["access-control"],
        "requirement_type": "policy",
        "enrichment_model": "test-model",
        "enrichment_profile": "cybersecurity",
    }
    enriched_file = tmp_path / "doc_requirements_enriched.jsonl"
    enriched_file.write_text(json.dumps(cached) + "\n", encoding="utf-8")

    enrich_calls: list = []

    def fake_batch(batch, model, url, timeout, *, valid_tags_str, valid_types_str, valid_domain_tags, valid_requirement_types):
        enrich_calls.extend(batch)
        return [{"description": "new", "domain_tags": ["test-tag-alpha"], "requirement_type": "guidance"}]

    import requests as _requests
    fake_resp = type("R", (), {"raise_for_status": lambda self: None})()

    with (
        patch.object(enrich_mod, "_enrich_batch", side_effect=fake_batch),
        patch.object(_requests, "get", return_value=fake_resp),
    ):
        enrich_mod.run(
            str(norm_file), str(tmp_path),
            model="test-model",
            ollama_url="http://localhost:11434",
            profile=_TEST_DOMAIN_PROFILE,
        )

    assert len(enrich_calls) == 1, "Cache should be bypassed when profile changes"
    assert enrich_calls[0]["requirement_id"] == "REQ-cachetest000001"

    # enrichment_profile is NOT written to output records (WP-20.4 owns schema changes)
    out_records = [json.loads(line) for line in enriched_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert "enrichment_profile" not in out_records[0]


def test_enrichment_cache_honored_when_profile_matches(tmp_path):
    """A cybersecurity cache record (no enrichment_profile field) must not be re-enriched on a cybersecurity run.

    This is the production scenario: pre-WP-20.4 records have no enrichment_profile field;
    the cybersecurity run treats them as cybersecurity-valid and skips re-enrichment.
    """
    norm_file = tmp_path / "doc_requirements_normalized.jsonl"
    norm_file.write_text(json.dumps(_BASE_NORM_REQ) + "\n", encoding="utf-8")

    # Production-accurate: cybersecurity enrichment record has no enrichment_profile field
    cached = {
        **_BASE_NORM_REQ,
        "description": "Cached cybersecurity enrichment.",
        "domain_tags": ["access-control"],
        "requirement_type": "technical-control",
        "enrichment_model": "test-model",
        # No enrichment_profile field — all existing records are cybersecurity by assumption
    }
    enriched_file = tmp_path / "doc_requirements_enriched.jsonl"
    enriched_file.write_text(json.dumps(cached) + "\n", encoding="utf-8")

    enrich_calls: list = []

    def fake_batch(batch, *args, **kwargs):
        enrich_calls.extend(batch)
        return [{"description": "new", "domain_tags": [], "requirement_type": ""}]

    import requests as _requests
    fake_resp = type("R", (), {"raise_for_status": lambda self: None})()

    with (
        patch.object(enrich_mod, "_enrich_batch", side_effect=fake_batch),
        patch.object(_requests, "get", return_value=fake_resp),
    ):
        enrich_mod.run(
            str(norm_file), str(tmp_path),
            model="test-model",
            ollama_url="http://localhost:11434",
            profile=_CYBER_PROFILE,
        )

    assert len(enrich_calls) == 0, "Cybersecurity cache with matching model must be honored"

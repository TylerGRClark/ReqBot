"""The citation label in search: the checklist's reference for a row, stored beside `source_ref` in the index and shown by Ask, Evidence, Trace and the MCP tools.

`source_ref` is never replaced: Evidence groups by it and the index embeds it. A record, an index built before this change, or a document with no chunk file simply has no citation,
and every reader falls back to `source_ref`.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.display import requirement_citation
from pipeline.embed_and_index import build_embedding_text, build_payload
from pipeline.embed_and_index import run as embed_and_index_run
from services.checklist_service import generate, requirement_citations


def _jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


CHUNKS = [
    {"chunk_id": 0, "raw_text": "AIR FORCE INSTRUCTION 99-1\nCompliance with this publication is mandatory.", "section_title_path": ["BY ORDER"]},
    {"chunk_id": 1, "raw_text": "1.1. Purpose. This instruction sets the rules.\n1.2. Units will report incidents within 24 hours.", "section_title_path": ["1. Introduction"]},
    {"chunk_id": 2, "raw_text": "2.1. Commanders will:\n- Ensure plans exist.\n- Test plans annually.", "section_title_path": ["2. Responsibilities"]},
    {"chunk_id": 3, "raw_text": "Table 3.1. Incident Matrix.\n| Action | Owner |\n| --- | --- |\n| Report | The unit will report the incident |", "section_title_path": ["3. Actions"]},
]


def _req(rid, quote, ref, chunk_id, **extra):
    return {"requirement_id": rid, "source_quote": quote, "source_ref": ref, "chunk_id": chunk_id, "source_pdf": "doc.pdf", "document_id": "d1",
            "section_title_path": CHUNKS[chunk_id]["section_title_path"], "page_start": 1, "page_end": 1, **extra}


REQS = [
    _req("REQ-front", "Compliance with this publication is mandatory.", "", 0),                    # before the first numbered paragraph
    _req("REQ-numbered", "Units will report incidents within 24 hours.", "1.2", 1),                 # the recorded reference is already a paragraph number
    _req("REQ-inferred", "Test plans annually.", "", 2),                                            # no reference: the numbered paragraph above it
    _req("REQ-table", "The unit will report the incident", "(T-2)", 3),                            # a tier tag recorded as the reference; the row sits in a table
]


def _doc(tmp_path: Path, with_chunks: bool = True) -> Path:
    run = tmp_path / "doc_20260101_120000"
    run.mkdir()
    _jsonl(run / "doc_requirements_normalized.jsonl", REQS)
    if with_chunks:
        _jsonl(run / "doc_chunks.jsonl", CHUNKS)
    return run


def test_citation_is_read_from_the_document_for_each_kind_of_row(tmp_path):
    run = _doc(tmp_path)
    cites = requirement_citations(run / "doc_requirements_normalized.jsonl")
    assert cites == {
        "REQ-front": "Front matter",
        "REQ-numbered": "1.2",
        "REQ-inferred": "2.1 (inferred)",
        "REQ-table": "Table 3.1",
    }


def test_the_index_label_is_the_checklist_label_row_for_row(tmp_path):
    """One function builds both, so a sheet and a search result cannot disagree."""
    _doc(tmp_path)
    env = generate(tmp_path, "doc", "cybersecurity")
    on_sheet = {i["requirement_ids"][0]: i["citation"] for i in env["items"] if i["requirement_ids"]}
    in_index = requirement_citations(tmp_path / "doc_20260101_120000" / "doc_requirements_normalized.jsonl")
    assert on_sheet == in_index and len(in_index) == 4


def test_without_a_chunk_file_the_label_still_reads_what_the_record_carries(tmp_path):
    run = _doc(tmp_path, with_chunks=False)
    cites = requirement_citations(run / "doc_requirements_normalized.jsonl")
    assert cites["REQ-numbered"] == "1.2"
    assert cites["REQ-front"] == "" and cites["REQ-table"] == ""  # nothing to read them from: readers fall back to source_ref


def test_a_record_without_an_id_or_text_is_left_out(tmp_path):
    run = tmp_path / "doc_20260101_120000"
    run.mkdir()
    _jsonl(run / "doc_requirements_normalized.jsonl", [_req("", "Units will report.", "1.2", 1), _req("REQ-x", "", "1.2", 1), _req("REQ-ok", "Units will report.", "1.2", 1)])
    assert list(requirement_citations(run / "doc_requirements_normalized.jsonl")) == ["REQ-ok"]


def test_a_reader_shows_the_citation_and_falls_back_to_source_ref():
    assert requirement_citation({"citation": "Table 3.1", "source_ref": "(T-2)"}) == "Table 3.1"
    assert requirement_citation({"citation": "", "source_ref": "3.4.2"}) == "3.4.2"
    assert requirement_citation({"source_ref": " 3.4.2 "}) == "3.4.2"
    assert requirement_citation({"citation": None, "source_ref": None}) == "" and requirement_citation(None) == ""


def test_payload_carries_the_citation_and_the_embedded_text_does_not_change():
    req = {"requirement_id": "REQ-1", "source_quote": "Units will report.", "source_ref": "(T-2)"}
    plain = build_payload(req, "m", 8)
    assert plain["citation"] == "" and plain["source_ref"] == "(T-2)"
    labeled = build_payload(req, "m", 8, {"citation": "Table 3.1"})
    assert labeled["citation"] == "Table 3.1" and labeled["source_ref"] == "(T-2)"
    assert build_embedding_text(req) == "Units will report.\nRef: (T-2)"  # vectors stay valid: the label is payload only


def test_the_indexer_writes_the_extras_into_each_points_payload(tmp_path):
    path = tmp_path / "reqs.jsonl"
    _jsonl(path, [{"requirement_id": "REQ-1", "source_quote": "Units will report.", "source_ref": "(T-2)"},
                  {"requirement_id": "REQ-2", "source_quote": "Units will drill.", "source_ref": "1.1"}])
    qdrant = MagicMock()
    qdrant.collection_exists.return_value = True
    qdrant.get_collection.return_value = MagicMock(points_count=2)
    ollama_client = MagicMock()
    ollama_client.embed.return_value = MagicMock(embeddings=[[0.0] * 4, [0.0] * 4])
    sparse = MagicMock()
    sparse.embed.side_effect = lambda texts: [MagicMock(indices=MagicMock(tolist=lambda: [1]), values=MagicMock(tolist=lambda: [1.0])) for _ in texts]
    with patch("pipeline.embed_and_index.QdrantClient", return_value=qdrant), \
         patch("pipeline.embed_and_index.ollama.Client", return_value=ollama_client), \
         patch("pipeline.embed_and_index.SparseTextEmbedding", return_value=sparse):
        embed_and_index_run(str(path), payload_extras={"REQ-1": {"citation": "Table 3.1"}})
    points = qdrant.upsert.call_args.kwargs["points"]
    by_id = {p.payload["requirement_id"]: p.payload for p in points}
    assert by_id["REQ-1"]["citation"] == "Table 3.1" and by_id["REQ-1"]["source_ref"] == "(T-2)"
    assert by_id["REQ-2"]["citation"] == ""


def test_evidence_labels_a_record_with_no_reference_by_its_citation_but_still_groups_by_source_ref():
    from services.evidence_service import _group_key_and_label

    key, label = _group_key_and_label({"source_ref": "", "citation": "2.1 (inferred)", "requirement_id": "REQ-a"})
    assert key == "__no_ref__REQ-a" and label == "2.1 (inferred)"
    assert _group_key_and_label({"source_ref": "", "requirement_id": "REQ-b"})[1] == "(no ref)"
    assert _group_key_and_label({"source_ref": "IA-05", "citation": "Table 3.1", "requirement_id": "REQ-c"}) == ("IA-05", "IA-05")


def test_ask_evidence_text_cites_the_citation():
    from core.ask import format_evidence

    text = format_evidence([{"source_pdf": "a.pdf", "source_ref": "(T-2)", "citation": "Table 3.1", "page_start": 4, "page_end": 4, "source_quote": "Units will report."},
                            {"source_pdf": "a.pdf", "source_ref": "1.2", "page_start": 5, "page_end": 5, "source_quote": "Units will drill."}])
    assert "[1] (a.pdf, Table 3.1, p.4)" in text and "[2] (a.pdf, 1.2, p.5)" in text


def test_citation_extras_never_fail_an_indexing_run(tmp_path):
    from cli import reqbot

    run = _doc(tmp_path)
    path = run / "doc_requirements_normalized.jsonl"
    assert reqbot._citation_extras(path)["REQ-table"] == {"citation": "Table 3.1"}
    assert "REQ-table" in reqbot._citation_extras(path) and all(v["citation"] for v in reqbot._citation_extras(path).values())  # a blank label is not stored
    with patch("services.checklist_service.requirement_citations", side_effect=RuntimeError("boom")):
        assert reqbot._citation_extras(path) == {}


def test_reindex_passes_each_documents_labels_to_the_indexer(tmp_path):
    from cli import reqbot

    run = _doc(tmp_path)
    path = run / "doc_requirements_normalized.jsonl"
    with patch("pipeline.embed_and_index.run") as mock_embed, \
         patch("pipeline.embed_and_index.load_jsonl", return_value=[]), \
         patch("qdrant_client.QdrantClient"):
        try:
            reqbot._reindex_requirements({"doc": path}, "http://q", "http://o", "m")
        except Exception:
            pass  # only the call into the indexer matters here; the alias swap needs a live Qdrant
    _, kwargs = mock_embed.call_args
    assert kwargs["payload_extras"]["REQ-table"] == {"citation": "Table 3.1"}

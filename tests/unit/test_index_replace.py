"""Replace a document in the index without a gap (docs/WEB_UI_PARITY_PLAN.md, section 6): new points first, verified, and only then the stale ones.

The plan's acceptance rule: a failure injected after half the batches leaves the old document fully searchable, and the retry leaves no stale point."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pipeline import embed_and_index, embed_context_index, index_replace
from pipeline.embed_and_index import expected_point_ids, requirement_point_id


class FakeQdrant:
    """The few calls the indexers and the replace step make, over a dict."""

    def __init__(self):
        self.points: dict[str, dict] = {}
        self.upserts = 0
        self.deletes = 0
        self.fail_on_upsert: int | None = None
        self.exists = False

    def collection_exists(self, name):
        return self.exists

    def create_collection(self, **kw):
        self.exists = True

    def delete_collection(self, name):
        self.points.clear()
        self.exists = False

    def get_collection(self, name):
        return SimpleNamespace(points_count=len(self.points))

    def upsert(self, collection_name, points):
        self.upserts += 1
        if self.fail_on_upsert is not None and self.upserts == self.fail_on_upsert:
            raise RuntimeError("Qdrant went away")
        for p in points:
            self.points[str(p.id)] = dict(p.payload)

    def retrieve(self, collection_name, ids, with_payload=False, with_vectors=False):
        return [SimpleNamespace(id=i) for i in ids if str(i) in self.points]

    def scroll(self, collection_name, scroll_filter=None, limit=256, offset=None, with_payload=False, with_vectors=False):
        ids = list(self.points)
        start = offset or 0
        part = ids[start:start + limit]
        nxt = start + limit if start + limit < len(ids) else None
        return [SimpleNamespace(id=i, payload=({k: self.points[i].get(k) for k in with_payload} if isinstance(with_payload, list) else None)) for i in part], nxt

    def delete(self, collection_name, points_selector):
        self.deletes += 1
        for i in points_selector.points:
            self.points.pop(str(i), None)


def _sparse():
    m = SimpleNamespace()
    m.embed = lambda texts: [SimpleNamespace(indices=SimpleNamespace(tolist=lambda: [1]), values=SimpleNamespace(tolist=lambda: [1.0])) for _ in texts]
    return m


def _ollama(fail_on: str | None = None):
    def embed(model, input):
        texts = input if isinstance(input, list) else [input]
        if fail_on and any(fail_on in t for t in texts):
            raise RuntimeError("embedding failed")
        return SimpleNamespace(embeddings=[[0.0] * 4 for _ in texts])

    return SimpleNamespace(embed=embed)


def _reqs(path, ids, source_pdf="afi99-1.pdf"):
    path.write_text("".join(json.dumps({"requirement_id": rid, "source_quote": f"Units will {rid}.", "source_ref": "1.1", "source_pdf": source_pdf}) + "\n" for rid in ids))
    return str(path)


def _index(qdrant, path, **kw):
    with patch("pipeline.embed_and_index.QdrantClient", return_value=qdrant), patch("pipeline.embed_and_index.ollama.Client", return_value=_ollama(kw.pop("fail_on", None))), \
         patch("pipeline.embed_and_index.SparseTextEmbedding", return_value=_sparse()):
        return embed_and_index.run(path, batch_size=kw.pop("batch_size", 1), **kw)


def _ids(*rids):
    return {requirement_point_id({"requirement_id": r}) for r in rids}


def test_replace_removes_only_the_points_the_new_run_no_longer_has(tmp_path):
    q = FakeQdrant()
    _index(q, _reqs(tmp_path / "a.jsonl", ["REQ-1", "REQ-2", "REQ-3"]))
    other = _reqs(tmp_path / "o.jsonl", ["REQ-X"], source_pdf="afi10-2402.pdf")
    _index(q, other)
    assert set(q.points) == _ids("REQ-1", "REQ-2", "REQ-3", "REQ-X")
    _index(q, _reqs(tmp_path / "b.jsonl", ["REQ-1", "REQ-2", "REQ-4"]), prune_stale=True)
    assert set(q.points) == _ids("REQ-1", "REQ-2", "REQ-4", "REQ-X")  # REQ-3 gone, the other document untouched


def test_without_the_option_nothing_is_ever_removed(tmp_path):
    q = FakeQdrant()
    _index(q, _reqs(tmp_path / "a.jsonl", ["REQ-1", "REQ-2"]))
    _index(q, _reqs(tmp_path / "b.jsonl", ["REQ-1"]))
    assert set(q.points) == _ids("REQ-1", "REQ-2") and q.deletes == 0  # ordinary indexing only adds and overwrites, as before


def test_a_failure_halfway_leaves_the_old_document_fully_searchable_and_the_retry_leaves_no_stale_point(tmp_path):
    q = FakeQdrant()
    old = ["REQ-1", "REQ-2", "REQ-3", "REQ-4"]
    _index(q, _reqs(tmp_path / "a.jsonl", old))
    new = _reqs(tmp_path / "b.jsonl", ["REQ-1", "REQ-2", "REQ-5", "REQ-6"])
    q.upserts = 0
    q.fail_on_upsert = 3  # one point per batch: the failure lands after half of the four batches
    with pytest.raises(RuntimeError):
        _index(q, new, prune_stale=True)
    assert q.deletes == 0
    assert _ids(*old) <= set(q.points)  # every old point is still there, so the document is still fully searchable
    q.fail_on_upsert = None
    _index(q, new, prune_stale=True)  # the retry
    assert set(q.points) == _ids("REQ-1", "REQ-2", "REQ-5", "REQ-6")


def test_an_embedding_that_failed_keeps_the_old_points_until_a_clean_run(tmp_path):
    q = FakeQdrant()
    _index(q, _reqs(tmp_path / "a.jsonl", ["REQ-1", "REQ-2", "REQ-3"]))
    new = _reqs(tmp_path / "b.jsonl", ["REQ-1", "REQ-4"])
    _index(q, new, prune_stale=True, fail_on="REQ-4")  # REQ-4 could not be embedded and is skipped
    assert _ids("REQ-1", "REQ-2", "REQ-3") <= set(q.points) and q.deletes == 0
    _index(q, new, prune_stale=True)
    assert set(q.points) == _ids("REQ-1", "REQ-4")


def test_replace_does_nothing_when_a_document_has_no_source_name(tmp_path):
    q = FakeQdrant()
    _index(q, _reqs(tmp_path / "a.jsonl", ["REQ-1", "REQ-2"], source_pdf=""))
    _index(q, _reqs(tmp_path / "b.jsonl", ["REQ-1"], source_pdf=""), prune_stale=True)
    assert set(q.points) == _ids("REQ-1", "REQ-2")


def test_the_check_and_the_prune_work_on_their_own(tmp_path):
    q = FakeQdrant()
    for i, name in enumerate(["a", "b", "c"]):
        q.points[f"id-{name}"] = {"source_pdf": "x.pdf"}
    q.points["id-z"] = {"source_pdf": "y.pdf"}
    assert index_replace.all_present(q, "c", ["id-a", "id-b"]) is True
    assert index_replace.all_present(q, "c", ["id-a", "id-missing"]) is False
    assert index_replace.prune_if_complete(q, "c", "x.pdf", ["id-a", "id-missing"]) == 0 and "id-c" in q.points  # not complete: nothing removed
    assert index_replace.prune_if_complete(q, "c", "x.pdf", ["id-a", "id-b"], skipped=1) == 0
    assert index_replace.prune_if_complete(q, "c", "x.pdf", ["id-a", "id-b"]) == 1
    assert set(q.points) == {"id-a", "id-b", "id-z"}


def test_the_context_collection_is_replaced_the_same_way(tmp_path):
    q = FakeQdrant()

    def chunks(path, n):
        path.write_text("".join(json.dumps({"chunk_id": i, "text": f"chunk {i}", "page_start": 1, "page_end": 1}) + "\n" for i in range(n)))
        return str(path)

    def run(path, document_id, **kw):
        with patch("pipeline.embed_context_index.QdrantClient", return_value=q), patch("pipeline.embed_context_index.ollama.Client", return_value=_ollama()), \
             patch("pipeline.embed_context_index.SparseTextEmbedding", return_value=_sparse()):
            return embed_context_index.run(path, document_id=document_id, source_pdf="afi99-1_chunks.jsonl", batch_size=1, **kw)

    run(chunks(tmp_path / "c1.jsonl", 4), "edition-one")
    run(chunks(tmp_path / "c2.jsonl", 3), "edition-two", prune_stale=True)  # a new edition: new document id, fewer chunks
    assert len(q.points) == 3 and {p["document_id"] for p in q.points.values()} == {"edition-two"}


# -- the command and the job ----------------------------------------------------------

def _ingest_args(**kw):
    base = dict(pdf="x.pdf", output_dir=None, extraction_model=None, enrichment_model=None, model=None, max_chunks=None, no_index=False, skip_enrichment=False,
                skip_description_gate=False, profile="cybersecurity", ollama_url="http://o", qdrant_url="http://q", progress_json=False, replace=False)
    base.update(kw)
    return SimpleNamespace(**base)


def test_ingest_replace_is_refused_for_a_partial_run_and_a_run_without_indexing(tmp_path):
    from cli.reqbot import cmd_ingest

    assert cmd_ingest(_ingest_args(replace=True, max_chunks=3)) == 1
    assert cmd_ingest(_ingest_args(replace=True, no_index=True)) == 1


def test_ingest_replace_asks_both_indexers_to_prune(tmp_path):
    from cli.reqbot import cmd_ingest

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    out = tmp_path / "out"
    out.mkdir()
    idx = out / "DOC_requirements_normalized.jsonl"
    idx.write_text(json.dumps({"document_id": "d", "requirement_id": "REQ-1"}) + "\n")
    (out / "DOC_chunks.jsonl").write_text(json.dumps({"chunk_id": 0, "text": "x"}) + "\n")
    for flag in (True, False):
        with patch("pipeline.run_pipeline.run", return_value=str(idx)), patch("pipeline.embed_and_index.run") as req, patch("pipeline.embed_context_index.run") as ctx:
            assert cmd_ingest(_ingest_args(pdf=str(pdf), output_dir=str(out), replace=flag)) == 0
        assert req.call_args.kwargs["prune_stale"] is flag and ctx.call_args.kwargs["prune_stale"] is flag


def test_the_job_carries_replace_only_when_asked_and_only_for_a_whole_document(tmp_path):
    from services import job_service as js

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    cfg = SimpleNamespace(ollama_url="http://o", qdrant_url="http://q", extraction_model="m", enrichment_model="m", embedding_model="e",
                          processed_dir_path=lambda: tmp_path / "p")
    store = js.JobStore(tmp_path / "p" / ".jobs")
    plain = js.enqueue_ingest(pdf, store=store, cfg=cfg)
    assert "--replace" not in plain["argv"] and plain["params"]["replace"] is False
    store.cancel(plain["id"])
    rep = js.enqueue_ingest(pdf, store=store, cfg=cfg, replace=True)
    assert "--replace" in rep["argv"] and rep["params"]["replace"] is True
    store.cancel(rep["id"])
    with pytest.raises(ValueError):
        js.enqueue_ingest(pdf, store=store, cfg=cfg, replace=True, max_chunks=2)


def test_expected_ids_ignore_records_that_are_not_indexed():
    recs = [{"requirement_id": "REQ-1", "source_quote": "x"}, {"requirement_id": "REQ-2", "source_quote": ""}]
    assert set(expected_point_ids(recs)) == _ids("REQ-1")


# -- the reviewer's findings on this change -------------------------------------------------

def test_extraction_gaps_counts_failed_label_batches_and_nothing_else(tmp_path):
    p = tmp_path / "doc_raw_responses.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"batch_id": "b00000", "status": "complete"}, {"batch_id": "b00001", "status": "failed"}, {"batch_id": "b00002", "status": "unparsed"},
        {"batch_id": "b00003", "status": "failed"}, {"chunk_id": 4, "status": "truncated"},  # an unparsed batch keeps its clauses as UNSURE: not a gap; "truncated" is a run folder from the deleted list-extraction step, still a gap
        {"chunk_id": 5},  # an older record with no status
    ]) + "\nnot json\n")
    assert index_replace.extraction_gaps(p) == {"failed": 2, "truncated": 1}
    assert index_replace.extraction_gaps(tmp_path / "missing.jsonl") == {}
    p.write_text(json.dumps({"chunk_id": 0, "status": "complete"}) + "\n")
    assert index_replace.extraction_gaps(p) == {}


def test_ingest_replace_keeps_the_old_points_when_the_run_had_a_failed_chunk(tmp_path):
    from cli.reqbot import cmd_ingest

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    out = tmp_path / "out"
    out.mkdir()
    idx = out / "DOC_requirements_normalized.jsonl"
    idx.write_text(json.dumps({"document_id": "d", "requirement_id": "REQ-1"}) + "\n")
    (out / "DOC_chunks.jsonl").write_text(json.dumps({"chunk_id": 0, "text": "x"}) + "\n")
    raw = out / "DOC_raw_responses.jsonl"
    for statuses, expect in ((["complete", "failed"], False), (["complete", "complete"], True)):
        raw.write_text("".join(json.dumps({"chunk_id": i, "status": s}) + "\n" for i, s in enumerate(statuses)))
        with patch("pipeline.run_pipeline.run", return_value=str(idx)), patch("pipeline.embed_and_index.run") as req, patch("pipeline.embed_context_index.run") as ctx:
            assert cmd_ingest(_ingest_args(pdf=str(pdf), output_dir=str(out), replace=True)) == 0
        assert req.call_count == 1 and ctx.call_count == 1  # the new points are indexed either way
        assert req.call_args.kwargs["prune_stale"] is expect and ctx.call_args.kwargs["prune_stale"] is expect


def test_an_empty_replacement_removes_nothing(tmp_path):
    q = FakeQdrant()
    _index(q, _reqs(tmp_path / "a.jsonl", ["REQ-1", "REQ-2"]))
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    assert _index(q, str(empty), prune_stale=True) == 0
    assert set(q.points) == _ids("REQ-1", "REQ-2") and q.deletes == 0


def test_a_file_with_another_name_is_another_document(tmp_path):
    q = FakeQdrant()
    _index(q, _reqs(tmp_path / "a.jsonl", ["REQ-1", "REQ-2"], source_pdf="afi99-1.pdf"))
    _index(q, _reqs(tmp_path / "b.jsonl", ["REQ-3"], source_pdf="afi99-1-2026.pdf"), prune_stale=True)
    assert set(q.points) == _ids("REQ-1", "REQ-2", "REQ-3")  # the replacement of "afi99-1.pdf" is a file called afi99-1.pdf


def test_the_same_document_is_found_whatever_the_case_of_its_extension(tmp_path):
    q = FakeQdrant()
    _index(q, _reqs(tmp_path / "a.jsonl", ["REQ-1", "REQ-2"], source_pdf="policy.PDF"))  # ingested from an inbox as policy.PDF
    _index(q, _reqs(tmp_path / "o.jsonl", ["REQ-X"], source_pdf="other.pdf"))
    _index(q, _reqs(tmp_path / "b.jsonl", ["REQ-1", "REQ-3"], source_pdf="policy.pdf"), prune_stale=True)  # replaced by an upload, whose extension is lower case
    assert set(q.points) == _ids("REQ-1", "REQ-3", "REQ-X")
    assert index_replace.document_key("Policy.Pdf") == "Policy" and index_replace.document_key("afi99-1_chunks.jsonl") == "afi99-1_chunks.jsonl"

"""Unit tests for cmd_reindex (WP-24.2 -- unified requirements + context rebuild; WP-45.0.1 coverage guard).

Qdrant is an in-memory fake (_FakeQdrant) wrapped in a MagicMock so calls can still be counted. Most tests
mock pipeline.embed_and_index.run and pipeline.embed_context_index.run with "perfect" fake indexers that
write the point IDs a complete index would hold; the failure-injection tests at the bottom run the REAL
indexers against a fake Ollama/sparse model that fails on a marked text. Real tmp_path JSONL/chunk files
make core.artifact_resolver.resolve_latest_requirement_files() and cli.reqbot._read_document_id()
exercise real file I/O.
"""
import json
import logging
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import cli.reqbot as cli_reqbot
import core.config as core_config
from cli.reqbot import _collection_point_ids, cmd_reindex
from pipeline import embed_and_index, embed_context_index


class _FakeQdrant:
    """In-memory stand-in for the Qdrant calls the indexers and cmd_reindex make."""

    def __init__(self):
        self.points = {}   # collection name -> {point id: payload}
        self.aliases = {}  # alias -> collection name
        self.drop = set()  # point IDs the perfect fake indexers leave out (simulated embedding failure)

    def collection_exists(self, name):
        return name in self.points

    def delete_collection(self, name):
        self.points.pop(name, None)

    def create_collection(self, collection_name, **kwargs):
        self.points.setdefault(collection_name, {})

    def upsert(self, collection_name, points):
        for point in points:
            self.points[collection_name][str(point.id)] = point.payload

    def get_collection(self, name):
        return SimpleNamespace(points_count=len(self.points[name]))

    def scroll(self, collection_name, limit=10, offset=None, with_payload=True, with_vectors=False):
        if collection_name not in self.points:
            raise ValueError(f"Collection {collection_name} not found")
        ids = sorted(self.points[collection_name])
        start = offset or 0
        nxt = start + limit if start + limit < len(ids) else None
        return [SimpleNamespace(id=i) for i in ids[start:start + limit]], nxt

    def get_aliases(self):
        return SimpleNamespace(
            aliases=[SimpleNamespace(alias_name=a, collection_name=c) for a, c in self.aliases.items()]
        )

    def update_collection_aliases(self, change_aliases_operations):
        for op in change_aliases_operations:
            if hasattr(op, "delete_alias"):
                self.aliases.pop(op.delete_alias.alias_name, None)
            elif hasattr(op, "create_alias"):
                self.aliases[op.create_alias.alias_name] = op.create_alias.collection_name

    # -- perfect mocked indexers: write what a complete index would hold, minus self.drop --
    def index_requirements(self, path, *, collection_name, **kwargs):
        records = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        collection = self.points.setdefault(collection_name, {})
        for point_id in embed_and_index.expected_point_ids(records):
            if point_id not in self.drop:
                collection[point_id] = {}

    def index_context(self, path, *, document_id, collection_name, **kwargs):
        chunks = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        collection = self.points.setdefault(collection_name, {})
        for point_id in embed_context_index.expected_point_ids(document_id, chunks):
            if point_id not in self.drop:
                collection[point_id] = {}


@contextmanager
def _env(req_effect=None, ctx_effect=None):
    """Patch Qdrant with a fake and both indexers with perfect fakes (or the given side effects)."""
    fake = _FakeQdrant()
    client = MagicMock(wraps=fake)
    with patch("qdrant_client.QdrantClient", return_value=client), \
         patch("pipeline.embed_and_index.run", side_effect=req_effect or fake.index_requirements) as req, \
         patch("pipeline.embed_context_index.run", side_effect=ctx_effect or fake.index_context) as ctx:
        yield SimpleNamespace(client=client, fake=fake, req=req, ctx=ctx)


def _write_doc(processed_dir: Path, doc_key: str, document_id: str, with_chunks: bool = True, quotes=("hello",)):
    """Create a minimal run directory with a normalized requirements JSONL
    (and optionally a chunks JSONL) for doc_key."""
    run_dir = processed_dir / f"{doc_key}_20260101_000000"
    run_dir.mkdir(parents=True, exist_ok=True)
    req_path = run_dir / f"{doc_key}_requirements_normalized.jsonl"
    req_path.write_text("".join(
        json.dumps({
            "document_id": document_id, "requirement_id": f"REQ-{doc_key}-{i}", "source_quote": quote,
        }) + "\n"
        for i, quote in enumerate(quotes)
    ))
    if with_chunks:
        chunks_path = run_dir / f"{doc_key}_chunks.jsonl"
        chunks_path.write_text("".join(
            json.dumps({"chunk_id": f"c{i}", "text": quote}) + "\n" for i, quote in enumerate(quotes)
        ))
    return req_path


def _args(requirements_only=False):
    return SimpleNamespace(
        qdrant_url="http://qdrant:6333",
        ollama_url="http://ollama:11434",
        requirements_only=requirements_only,
    )


@pytest.fixture(autouse=True)
def _isolate_cfg(tmp_path, monkeypatch):
    mock_cfg = SimpleNamespace(processed_dir_path=lambda: tmp_path, embedding_model="nomic-embed-text")
    monkeypatch.setattr(cli_reqbot, "_cfg", mock_cfg)


def test_default_reindex_rebuilds_both_collections(tmp_path):
    _write_doc(tmp_path, "DOC-A", "hash-a")
    _write_doc(tmp_path, "DOC-B", "hash-b")

    with _env() as env:
        rc = cmd_reindex(_args())

    assert rc == 0
    assert env.req.call_count == 2
    assert env.ctx.call_count == 2
    # One alias swap for grc_requirements, one for grc_context.
    assert env.client.update_collection_aliases.call_count == 2


def test_reindex_threads_configured_embedding_model_through(tmp_path, monkeypatch):
    """WP-25.6c: reqbot reindex must re-embed with whatever embedding_model is
    currently configured, not a hardcoded default."""
    _write_doc(tmp_path, "DOC-A", "hash-a")
    monkeypatch.setattr(
        cli_reqbot, "_cfg",
        SimpleNamespace(processed_dir_path=lambda: tmp_path, embedding_model="custom-embed-model"),
    )

    with _env() as env:
        rc = cmd_reindex(_args())

    assert rc == 0
    assert env.req.call_args.kwargs["embedding_model"] == "custom-embed-model"
    assert env.ctx.call_args.kwargs["embedding_model"] == "custom-embed-model"


def test_requirements_only_skips_context_entirely(tmp_path):
    _write_doc(tmp_path, "DOC-A", "hash-a")

    with _env() as env:
        rc = cmd_reindex(_args(requirements_only=True))

    assert rc == 0
    assert env.req.call_count == 1
    env.ctx.assert_not_called()
    assert env.client.update_collection_aliases.call_count == 1


def test_context_temp_collection_uses_grc_context_prefix(tmp_path):
    _write_doc(tmp_path, "DOC-A", "hash-a")

    with _env() as env:
        cmd_reindex(_args())

    _, kwargs = env.ctx.call_args
    assert kwargs["collection_name"].startswith("grc_context_")

    # The alias-swap call for grc_context should target that same temp name.
    alias_names = set()
    for call in env.client.update_collection_aliases.call_args_list:
        for op in call.kwargs["change_aliases_operations"]:
            if hasattr(op, "create_alias"):
                alias_names.add((op.create_alias.alias_name, op.create_alias.collection_name))
    assert ("grc_context", kwargs["collection_name"]) in alias_names


def test_document_id_read_from_requirements_file_not_filename(tmp_path):
    _write_doc(tmp_path, "DOC-A", "pdf-hash-abc123")

    with _env() as env:
        cmd_reindex(_args())

    _, kwargs = env.ctx.call_args
    assert kwargs["document_id"] == "pdf-hash-abc123"


def test_two_documents_sharing_a_run_directory_get_matching_chunks(tmp_path):
    """A run directory holding artifacts for more than one document must not
    pair one document's chunks with another's document_id — chunk_files[0]
    from an unfiltered glob would do exactly that."""
    run_dir = tmp_path / "shared_run"
    run_dir.mkdir()

    req_a = run_dir / "DOC-A_requirements_normalized.jsonl"
    req_a.write_text(json.dumps({"document_id": "hash-a", "requirement_id": "REQ-1", "source_quote": "a"}) + "\n")
    chunks_a = run_dir / "DOC-A_chunks.jsonl"
    chunks_a.write_text(json.dumps({"chunk_id": "a1", "text": "doc a text"}) + "\n")

    req_b = run_dir / "DOC-B_requirements_normalized.jsonl"
    req_b.write_text(json.dumps({"document_id": "hash-b", "requirement_id": "REQ-2", "source_quote": "b"}) + "\n")
    chunks_b = run_dir / "DOC-B_chunks.jsonl"
    chunks_b.write_text(json.dumps({"chunk_id": "b1", "text": "doc b text"}) + "\n")

    with _env() as env:
        rc = cmd_reindex(_args())

    assert rc == 0
    assert env.ctx.call_count == 2
    calls_by_document_id = {c.kwargs["document_id"]: c.args[0] for c in env.ctx.call_args_list}
    assert calls_by_document_id["hash-a"] == str(chunks_a)
    assert calls_by_document_id["hash-b"] == str(chunks_b)


def test_missing_chunks_file_does_not_prevent_requirements_indexing(tmp_path):
    _write_doc(tmp_path, "DOC-A", "hash-a", with_chunks=True)
    _write_doc(tmp_path, "DOC-B", "hash-b", with_chunks=False)

    with _env() as env:
        rc = cmd_reindex(_args())

    assert rc == 0
    assert env.req.call_count == 2  # both requirements files indexed
    assert env.ctx.call_count == 1  # only DOC-A has chunks


def test_missing_chunks_file_is_named_in_a_warning(tmp_path, caplog):
    """WP-45.0.1: a document with no chunks file is a flagged skip, not a silent one -- the new
    grc_context will not hold its chunks, and the summary says which documents."""
    _write_doc(tmp_path, "DOC-A", "hash-a", with_chunks=True)
    _write_doc(tmp_path, "DOC-B", "hash-b", with_chunks=False)

    with caplog.at_level(logging.WARNING), _env():
        rc = cmd_reindex(_args())

    assert rc == 0
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("DOC-B" in m and "absent from the new grc_context" in m for m in warnings)


def test_context_failure_for_one_doc_does_not_swap_and_deletes_temp(tmp_path, caplog):
    """embed_context_index.run() upserts in batches, so a failed document may
    have already written partial chunks into the temp collection before
    raising. The temp collection must be discarded, not swapped live, even
    though another document succeeded — otherwise grc_context would end up
    with a partial/incomplete version of the failed document."""
    _write_doc(tmp_path, "DOC-A", "hash-a")
    _write_doc(tmp_path, "DOC-B", "hash-b")
    fake_for_effect = _FakeQdrant()

    def _ctx_side_effect(chunks_jsonl, **kwargs):
        if "DOC-B" in chunks_jsonl:
            raise RuntimeError("embedding failed")
        fake_for_effect.index_context(chunks_jsonl, **kwargs)

    with _env(ctx_effect=_ctx_side_effect) as env:
        rc = cmd_reindex(_args())

    assert rc == 1  # partial context failure must not report overall success
    # Only the requirements alias swap happened — context was never swapped,
    # and the temp context collection was deleted instead.
    assert env.client.update_collection_aliases.call_count == 1
    context_temp_names = {
        call.args[0] for call in env.client.delete_collection.call_args_list
        if call.args[0].startswith("grc_context_")
    }
    assert len(context_temp_names) == 1
    assert "REINDEX PARTIAL" in caplog.text
    assert "untouched" in caplog.text.lower()


def test_all_context_docs_fail_no_swap_and_nonzero(tmp_path):
    _write_doc(tmp_path, "DOC-A", "hash-a")

    with _env(ctx_effect=RuntimeError("boom")) as env:
        rc = cmd_reindex(_args())

    assert rc == 1
    # Only the requirements alias swap happened — context never swapped.
    assert env.client.update_collection_aliases.call_count == 1


def test_requirements_failure_aborts_before_context(tmp_path):
    _write_doc(tmp_path, "DOC-A", "hash-a")

    with _env(req_effect=RuntimeError("boom")) as env:
        rc = cmd_reindex(_args())

    assert rc == 1
    env.ctx.assert_not_called()
    env.client.update_collection_aliases.assert_not_called()


def test_no_requirements_jsonl_found_returns_1(tmp_path):
    rc = cmd_reindex(_args())
    assert rc == 1


def test_reindex_help_shows_requirements_only_flag(capsys, monkeypatch):
    # main() builds argparse defaults from every subcommand's config fields,
    # not just processed_dir_path — restore the real config for this test
    # rather than the file's simplified autouse mock.
    monkeypatch.setattr(cli_reqbot, "_cfg", core_config.load())
    monkeypatch.setattr(sys, "argv", ["reqbot", "reindex", "--help"])
    with pytest.raises(SystemExit):
        cli_reqbot.main()
    assert "--requirements-only" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# WP-45.0.1 -- coverage guard: never promote a rebuilt index that is missing expected points
# ---------------------------------------------------------------------------

def _live_index(fake, alias, backing, ids=("old-1", "old-2")):
    """Pre-existing live index: an alias pointing at a backing collection holding some points."""
    fake.points[backing] = {i: {} for i in ids}
    fake.aliases[alias] = backing


def test_missing_requirement_points_block_the_swap_and_keep_the_live_index(tmp_path, caplog):
    """The indexer skips (does not raise on) a record whose embedding fails. Simulate that with
    perfect fake indexers that leave one point out: reindex must refuse the swap, delete the temp
    collection, leave the live alias and its backing collection alone, name the missing record, and
    not start the context rebuild."""
    _write_doc(tmp_path, "DOC-A", "hash-a", quotes=("alpha", "beta", "gamma"))
    missing_id = embed_and_index.requirement_point_id({"requirement_id": "REQ-DOC-A-1"})

    with _env() as env:
        _live_index(env.fake, "grc_requirements", "grc_requirements_old")
        env.fake.drop = {missing_id}
        rc = cmd_reindex(_args())

    assert rc == 1
    assert env.fake.aliases == {"grc_requirements": "grc_requirements_old"}
    assert set(env.fake.points) == {"grc_requirements_old"}  # temp collection deleted, live backing intact
    env.client.update_collection_aliases.assert_not_called()
    env.ctx.assert_not_called()
    assert "1 of 3 expected point(s) are missing" in caplog.text
    assert "MISSING: REQ-DOC-A-1" in caplog.text


def test_missing_context_points_block_the_context_swap_only(tmp_path, caplog):
    _write_doc(tmp_path, "DOC-A", "hash-a", quotes=("alpha", "beta"))
    missing_id = embed_context_index.context_point_id("hash-a", "c1")

    with _env() as env:
        _live_index(env.fake, "grc_context", "grc_context_old")
        env.fake.drop = {missing_id}
        rc = cmd_reindex(_args())

    assert rc == 1
    assert env.fake.aliases["grc_context"] == "grc_context_old"
    assert "grc_context_old" in env.fake.points
    assert not [name for name in env.fake.points if name.startswith("grc_context_") and name != "grc_context_old"]
    # requirements were complete, so that alias did swap
    assert env.fake.aliases["grc_requirements"].startswith("grc_requirements_")
    assert "1 of 2 expected point(s) are missing" in caplog.text
    assert "MISSING: hash-a:c1" in caplog.text


def test_a_collection_that_cannot_be_read_is_refused_not_trusted(tmp_path, caplog):
    _write_doc(tmp_path, "DOC-A", "hash-a")

    with _env() as env:
        _live_index(env.fake, "grc_requirements", "grc_requirements_old")
        env.client.scroll.side_effect = RuntimeError("qdrant unreachable")
        rc = cmd_reindex(_args())

    assert rc == 1
    assert env.fake.aliases == {"grc_requirements": "grc_requirements_old"}
    assert "could not verify" in caplog.text


def test_repeated_requirement_ids_are_one_expected_point_not_two(tmp_path, caplog):
    """Point IDs are uuid5(requirement_id), so a repeated ID is one point. Coverage is measured
    against distinct IDs, otherwise a complete index would look incomplete (or an incomplete one
    complete) by row count."""
    run_dir = tmp_path / "DOC-A_20260101_000000"
    run_dir.mkdir()
    rows = [
        {"document_id": "hash-a", "requirement_id": "REQ-DUP", "source_quote": "first"},
        {"document_id": "hash-a", "requirement_id": "REQ-DUP", "source_quote": "second"},
        {"document_id": "hash-a", "requirement_id": "REQ-OTHER", "source_quote": "third"},
    ]
    (run_dir / "DOC-A_requirements_normalized.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    with caplog.at_level(logging.INFO), _env() as env:
        rc = cmd_reindex(_args(requirements_only=True))

    assert rc == 0
    assert "2 point(s) verified present" in caplog.text
    assert "1 record(s) share a requirement_id" in caplog.text
    swapped = env.fake.aliases["grc_requirements"]
    assert len(env.fake.points[swapped]) == 2


def test_records_without_a_source_quote_are_not_expected_and_are_reported(tmp_path, caplog):
    """The indexer skips a record with no source_quote by design; it is not a coverage failure,
    but the summary says how many were left out."""
    run_dir = tmp_path / "DOC-A_20260101_000000"
    run_dir.mkdir()
    rows = [
        {"document_id": "hash-a", "requirement_id": "REQ-1", "source_quote": "kept"},
        {"document_id": "hash-a", "requirement_id": "REQ-2", "source_quote": "  "},
    ]
    (run_dir / "DOC-A_requirements_normalized.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    with caplog.at_level(logging.INFO), _env():
        rc = cmd_reindex(_args(requirements_only=True))

    assert rc == 0
    assert "1 point(s) verified present" in caplog.text
    assert "1 record(s) without a source_quote were not indexed" in caplog.text


def test_collection_point_ids_reads_every_page():
    fake = _FakeQdrant()
    fake.points["big"] = {f"id-{i:05d}": {} for i in range(2500)}
    assert _collection_point_ids(fake, "big") == set(fake.points["big"])


def test_point_id_helpers_match_the_original_uuid5_formulas():
    """run() now builds IDs through these helpers; they must produce exactly what it always did, or a
    reindex would orphan every existing point."""
    assert embed_and_index.requirement_point_id({"requirement_id": "REQ-1"}) == str(
        uuid.uuid5(embed_and_index.QDRANT_UUID_NAMESPACE, "REQ-1")
    )
    assert embed_context_index.context_point_id("doc", "c7") == str(
        uuid.uuid5(embed_context_index.CONTEXT_UUID_NAMESPACE, "doc:c7")
    )


# ---------------------------------------------------------------------------
# Failure injection through the REAL indexers: a text the fake embedder fails on is skipped by run(),
# which is exactly how a flaky Ollama or sparse model loses a point in production.
# ---------------------------------------------------------------------------

def _fake_ollama(poison):
    class _Client:
        def __init__(self, host=None):
            pass

        def embed(self, model, input):
            texts = [input] if isinstance(input, str) else list(input)
            if any(mark in text for text in texts for mark in poison):
                raise RuntimeError("dense embedding failed")
            return SimpleNamespace(embeddings=[[0.1, 0.2, 0.3] for _ in texts])
    return _Client


def _fake_sparse(poison):
    class _Array:
        def __init__(self, values):
            self._values = values

        def tolist(self):
            return list(self._values)

    class _Model:
        def __init__(self, model_name=None):
            pass

        def embed(self, texts):
            if any(mark in text for text in texts for mark in poison):
                raise RuntimeError("sparse embedding failed")
            for _ in texts:
                yield SimpleNamespace(indices=_Array([1, 2]), values=_Array([0.5, 0.5]))
    return _Model


@contextmanager
def _real_indexers(*, dense_poison=(), sparse_poison=()):
    fake = _FakeQdrant()
    client = MagicMock(wraps=fake)
    with patch("qdrant_client.QdrantClient", return_value=client), \
         patch("pipeline.embed_and_index.QdrantClient", return_value=client), \
         patch("pipeline.embed_context_index.QdrantClient", return_value=client), \
         patch("ollama.Client", _fake_ollama(dense_poison)), \
         patch("pipeline.embed_and_index.SparseTextEmbedding", _fake_sparse(sparse_poison)), \
         patch("pipeline.embed_context_index.SparseTextEmbedding", _fake_sparse(sparse_poison)):
        yield SimpleNamespace(client=client, fake=fake)


def test_real_indexers_clean_run_is_verified_and_swapped(tmp_path):
    """Positive control: with nothing failing, the real indexers produce a complete index, the guard
    passes, and both aliases move."""
    _write_doc(tmp_path, "DOC-A", "hash-a", quotes=("alpha", "beta", "gamma"))

    with _real_indexers() as env:
        rc = cmd_reindex(_args())

    assert rc == 0
    assert len(env.fake.points[env.fake.aliases["grc_requirements"]]) == 3
    assert len(env.fake.points[env.fake.aliases["grc_context"]]) == 3


@pytest.mark.parametrize("kind", ["dense", "sparse"])
def test_real_requirements_indexer_embedding_failure_blocks_the_swap(tmp_path, caplog, kind):
    _write_doc(tmp_path, "DOC-A", "hash-a", quotes=("alpha", "POISON beta", "gamma"))
    poison = {"dense_poison": ("POISON",)} if kind == "dense" else {"sparse_poison": ("POISON",)}

    with _real_indexers(**poison) as env:
        _live_index(env.fake, "grc_requirements", "grc_requirements_old")
        rc = cmd_reindex(_args())

    assert rc == 1
    assert env.fake.aliases == {"grc_requirements": "grc_requirements_old"}
    assert set(env.fake.points) == {"grc_requirements_old"}
    assert "1 of 3 expected point(s) are missing" in caplog.text
    assert "MISSING: REQ-DOC-A-1" in caplog.text


@pytest.mark.parametrize("kind", ["dense", "sparse"])
def test_real_context_indexer_embedding_failure_blocks_the_context_swap(tmp_path, caplog, kind):
    _write_doc(tmp_path, "DOC-A", "hash-a", quotes=("alpha", "POISON beta", "gamma"))
    # Fail only the context text: requirements embed the quote + ref, context embeds the chunk text,
    # and both contain "POISON", so make the requirements side succeed by failing on a marker that
    # only the chunk file carries.
    chunks = tmp_path / "DOC-A_20260101_000000" / "DOC-A_chunks.jsonl"
    chunks.write_text("".join(
        json.dumps({"chunk_id": f"c{i}", "text": text}) + "\n"
        for i, text in enumerate(("alpha", "CHUNKFAIL beta", "gamma"))
    ))
    poison = {"dense_poison": ("CHUNKFAIL",)} if kind == "dense" else {"sparse_poison": ("CHUNKFAIL",)}

    with _real_indexers(**poison) as env:
        _live_index(env.fake, "grc_context", "grc_context_old")
        rc = cmd_reindex(_args())

    assert rc == 1
    assert env.fake.aliases["grc_context"] == "grc_context_old"
    assert env.fake.aliases["grc_requirements"].startswith("grc_requirements_")
    assert "grc_context_old" in env.fake.points
    assert "REINDEX PARTIAL" in caplog.text
    assert "1 of 3 expected point(s) are missing" in caplog.text
    assert "MISSING: hash-a:c1" in caplog.text


@pytest.mark.parametrize("legacy_first_line", ["missing-field", "blank-line"])
def test_real_context_indexer_with_a_legacy_requirements_file_is_not_falsely_refused(tmp_path, legacy_first_line):
    """_read_document_id() returns None for a requirements file with no document_id (or that starts with
    a blank line), and the indexer then derives the ID from the chunks filename. The guard must expect the
    IDs that were actually indexed, not "None:<chunk_id>" -- otherwise it rejects a complete rebuild."""
    run_dir = tmp_path / "DOC-A_20260101_000000"
    run_dir.mkdir()
    record = json.dumps({"requirement_id": "REQ-1", "source_quote": "alpha"}) + "\n"
    (run_dir / "DOC-A_requirements_normalized.jsonl").write_text(
        record if legacy_first_line == "missing-field" else "\n" + record
    )
    (run_dir / "DOC-A_chunks.jsonl").write_text(json.dumps({"chunk_id": "c0", "text": "alpha"}) + "\n")

    with _real_indexers() as env:
        rc = cmd_reindex(_args())

    assert rc == 0
    context_ids = env.fake.points[env.fake.aliases["grc_context"]]
    assert set(context_ids) == {embed_context_index.context_point_id("DOC-A", "c0")}


def test_resolve_document_id_prefers_the_given_id_and_falls_back_to_the_chunks_filename(tmp_path):
    chunks = tmp_path / "SOME-DOC_chunks.jsonl"
    assert embed_context_index.resolve_document_id("hash-a", chunks) == "hash-a"
    assert embed_context_index.resolve_document_id(None, chunks) == "SOME-DOC"
    assert embed_context_index.resolve_document_id("", chunks) == "SOME-DOC"
    assert embed_context_index.resolve_document_id(None, tmp_path / "plain.jsonl") == "plain"

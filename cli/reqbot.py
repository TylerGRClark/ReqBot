#!/usr/bin/env python3
"""ReqBot — Single CLI entrypoint for the requirements extraction pipeline.

Subcommands:
    reqbot ingest <pdf>     Run the full extraction pipeline on a PDF
    reqbot index <jsonl>    Embed and index requirements into Qdrant
    reqbot ask "question"   Query requirements via vector search
    reqbot status           Show system status (Qdrant, Ollama, docs)
"""

import sys
from pathlib import Path

# When running from cli/ subfolder, add the repo root (bundle: app/) to sys.path
# so that `from core import ...`, `from pipeline import ...`, and
# `from _build_info import ...` all resolve correctly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

__version__ = "0.1.0"
__build_date__ = "dev"
try:
    from _build_info import __version__, __build_date__  # type: ignore[import,assignment]
except ImportError:
    pass

import argparse
import json
import logging
import time
import uuid
from datetime import datetime as _dt

import requests

from core import config as _config
from core.display import requirement_citation as _requirement_citation
from core.display import requirement_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

_cfg = _config.load()


def _positive_int(value: str) -> int:
    """Argparse type validator that requires a positive integer."""
    try:
        i = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid integer")
    if i <= 0:
        raise argparse.ArgumentTypeError(f"{value} must be a positive integer")
    return i


def _read_document_id(jsonl_path: str) -> str | None:
    """Read the document_id field from the first record of a requirements JSONL.

    This is the PDF-content-hash document_id written by parse_and_normalize,
    used so context chunks can be cross-referenced by the same ID stored in
    requirements payloads (ask --context, trace). Returns None if the file is
    empty/unreadable or the field is missing — callers then fall back to
    embed_context_index.run()'s filename-derived default.
    """
    try:
        with open(jsonl_path) as f:
            first_line = f.readline()
        if first_line:
            return json.loads(first_line).get("document_id")
    except Exception as e:
        log.warning(
            "Could not read document_id from %s: %s — context chunks will use filename-derived ID",
            jsonl_path, e,
        )
    return None


def _citation_extras(jsonl_path) -> dict:
    """{requirement_id: {"citation": label}} for the index payload (see services.checklist_service.index_payload_extras; never raises)."""
    from services import checklist_service as _checklist
    return _checklist.index_payload_extras(jsonl_path)


def cmd_ingest(args: argparse.Namespace) -> int:
    """Run the full extraction pipeline on a PDF."""
    from core import artifact_resolver as _resolver
    from pipeline import run_pipeline as _run_pipeline
    from pipeline import embed_and_index as _embed
    from pipeline import embed_context_index as _embed_ctx

    from pipeline import progress as _progress

    if getattr(args, "progress_json", False):
        _progress.enable()

    replace = bool(getattr(args, "replace", False))
    if replace and (getattr(args, "max_chunks", None) or getattr(args, "no_index", False)):
        log.error("--replace needs the whole document indexed: it cannot be combined with --max-chunks or --no-index")
        return 1

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        log.error("PDF not found: %s", pdf_path)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir).resolve()
    else:
        timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
        out_dir = _cfg.processed_dir_path() / f"{pdf_path.stem}_{timestamp}"

    # --model is a convenience alias; individual flags take precedence when --model not given
    if args.model:
        extraction_model = args.model
        enrichment_model = args.model
    else:
        extraction_model = args.extraction_model or _cfg.extraction_model
        enrichment_model = args.enrichment_model or _cfg.enrichment_model

    try:
        index_path = _run_pipeline.run(
            str(pdf_path),
            str(out_dir),
            ollama_url=args.ollama_url,
            extraction_model=extraction_model,
            enrichment_model=enrichment_model,
            max_chunks=args.max_chunks,
            skip_enrichment=args.skip_enrichment,
            skip_description_gate=args.skip_description_gate,
            profile_name=args.profile,
        )
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    if getattr(args, "no_index", False):
        _progress.emit("done")
        return 0

    if replace:
        from pipeline import index_replace as _index_replace
        gaps = _index_replace.extraction_gaps(
            Path(index_path).parent / f"{_resolver.doc_key_from_requirements_path(Path(index_path))}_raw_responses.jsonl")
        if gaps:
            log.warning(
                "Replace skipped: %s. The new points are indexed but the old ones are kept, because this run may be missing requirements the old index has. "
                "Run it again to retry those chunks.",
                " and ".join(f"{n} chunk(s) {k}" for k, n in gaps.items()),
            )
            replace = False

    # Index by default (uses enriched JSONL if enrichment ran, else normalized)
    _progress.emit("indexing")
    try:
        _embed.run(
            index_path, qdrant_url=args.qdrant_url, ollama_url=args.ollama_url,
            embedding_model=_cfg.embedding_model,
            payload_extras=_citation_extras(index_path),
            prune_stale=replace,
        )
    except Exception as e:
        log.error("Index into Qdrant failed: %s", e)
        return 1

    # Also index raw chunks into grc_context for dual-retrieval.
    # Pass the PDF-hash document_id from the indexed JSONL so that
    # ask.py can resolve context chunks by the same ID used in requirements payloads.
    # Exact doc_key match, not glob()[0] — same correctness fix as WP-24.2's
    # reindex context-matching (see core/artifact_resolver.py).
    out_dir_path = Path(index_path).parent
    doc_key = _resolver.doc_key_from_requirements_path(Path(index_path))
    chunk_path = out_dir_path / f"{doc_key}_chunks.jsonl"
    if chunk_path.exists():
        _progress.emit("indexing-context")
        try:
            _embed_ctx.run(
                str(chunk_path),
                document_id=_read_document_id(index_path),
                qdrant_url=args.qdrant_url,
                ollama_url=args.ollama_url,
                embedding_model=_cfg.embedding_model,
                prune_stale=replace,
            )
        except Exception as e:
            log.error("Index context into Qdrant failed: %s", e)
            return 1
    else:
        log.warning("No chunks.jsonl found in %s — skipping context index", out_dir_path)

    _progress.emit("done")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    """Embed and index requirements into Qdrant."""
    from pipeline import embed_and_index as _embed
    try:
        _embed.run(
            args.jsonl,
            qdrant_url=args.qdrant_url,
            ollama_url=args.ollama_url,
            recreate=args.recreate,
            batch_size=args.batch_size or 32,
            embedding_model=_cfg.embedding_model,
            payload_extras=_citation_extras(args.jsonl),
        )
        return 0
    except Exception as e:
        log.error("Embed and index failed: %s", e)
        return 1


def cmd_ask(args: argparse.Namespace) -> int:
    """Query requirements via vector search."""
    from core import ask as _ask
    try:
        _ask.run(
            args.question,
            top_k=args.top_k,
            min_score=args.min_score,
            synthesize=args.synthesize,
            model=args.model or "",
            domain_tags=args.domain_tags,
            requirement_types=args.requirement_types,
            document_ids=args.document_ids,
            no_rewrite=args.no_rewrite,
            rewrite_model=args.rewrite_model or _cfg.rewrite_model,
            embedding_model=_cfg.embedding_model,
            qdrant_url=args.qdrant_url,
            ollama_url=args.ollama_url,
            json_output=args.json_output,
            context=args.context,
            context_collection=args.context_collection,
            hyde=not getattr(args, "no_hyde", False),
        )
        return 0
    except Exception as e:
        log.error("Query failed: %s", e)
        return 1


def cmd_index_context(args: argparse.Namespace) -> int:
    """Embed and index raw chunks into the grc_context collection."""
    from pipeline import embed_context_index as _embed_ctx
    try:
        _embed_ctx.run(
            args.chunks_jsonl,
            document_id=args.document_id or None,
            source_pdf=args.source_pdf or "",
            qdrant_url=args.qdrant_url,
            ollama_url=args.ollama_url,
            recreate=args.recreate,
            batch_size=args.batch_size or 32,
            embedding_model=_cfg.embedding_model,
        )
        return 0
    except Exception as e:
        log.error("Embed and index context failed: %s", e)
        return 1


def cmd_batch(args: argparse.Namespace) -> int:
    """Run the full pipeline on every PDF in a directory."""
    from core import artifact_resolver as _resolver
    from pipeline import run_pipeline as _run_pipeline
    from pipeline import embed_and_index as _embed
    from pipeline import embed_context_index as _embed_ctx
    pdf_dir = Path(args.pdf_dir).resolve()
    if not pdf_dir.is_dir():
        log.error("Not a directory: %s", pdf_dir)
        return 1

    pdfs = sorted(pdf_dir.glob("*.pdf")) + sorted(pdf_dir.glob("*.PDF"))
    if not pdfs:
        log.error("No PDF files found in: %s", pdf_dir)
        return 1

    log.info("Found %d PDF(s) to process in %s", len(pdfs), pdf_dir)

    # Resolve models once for the whole batch (same alias logic as cmd_ingest)
    if args.model:
        batch_extraction_model = args.model
        batch_enrichment_model = args.model
    else:
        batch_extraction_model = args.extraction_model or _cfg.extraction_model
        batch_enrichment_model = args.enrichment_model or _cfg.enrichment_model

    succeeded = []
    failed = []

    for i, pdf_path in enumerate(pdfs, 1):
        log.info("=" * 60)
        log.info("[%d/%d] Processing: %s", i, len(pdfs), pdf_path.name)
        log.info("=" * 60)

        timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
        out_dir = _cfg.processed_dir_path() / f"{pdf_path.stem}_{timestamp}"

        try:
            index_path = _run_pipeline.run(
                str(pdf_path),
                str(out_dir),
                ollama_url=args.ollama_url,
                extraction_model=batch_extraction_model,
                enrichment_model=batch_enrichment_model,
                skip_enrichment=args.skip_enrichment,
                skip_description_gate=args.skip_description_gate,
            )
        except RuntimeError as e:
            log.error("Pipeline FAILED for %s: %s", pdf_path.name, e)
            failed.append(pdf_path.name)
            continue

        try:
            _embed.run(
                index_path, qdrant_url=args.qdrant_url, ollama_url=args.ollama_url,
                embedding_model=_cfg.embedding_model,
                payload_extras=_citation_extras(index_path),
            )
        except Exception as e:
            log.warning("Indexing failed for %s: %s — pipeline artifacts still saved", pdf_path.name, e)
            failed.append(pdf_path.name)
            continue

        # Also index raw chunks into grc_context for dual-retrieval.
        # Pass the PDF-hash document_id so ask.py can resolve context chunks
        # by the same ID stored in requirements payloads.
        # Exact doc_key match, not glob()[0] — same correctness fix as
        # WP-24.2's reindex context-matching.
        doc_key = _resolver.doc_key_from_requirements_path(Path(index_path))
        chunk_path = out_dir / f"{doc_key}_chunks.jsonl"
        if chunk_path.exists():
            try:
                _embed_ctx.run(
                    str(chunk_path),
                    document_id=_read_document_id(index_path),
                    qdrant_url=args.qdrant_url,
                    ollama_url=args.ollama_url,
                    embedding_model=_cfg.embedding_model,
                )
            except Exception as e:
                log.warning("Context indexing failed for %s: %s — requirements still indexed", pdf_path.name, e)
        else:
            log.warning("No chunks.jsonl found for %s — skipping context index", pdf_path.name)

        succeeded.append(pdf_path.name)

    # Summary
    log.info("=" * 60)
    log.info("BATCH COMPLETE: %d succeeded, %d failed", len(succeeded), len(failed))
    for name in succeeded:
        log.info("  OK:   %s", name)
    for name in failed:
        log.error("  FAIL: %s", name)
    log.info("=" * 60)

    return 0 if not failed else 1


def _alias_swap(qdrant, live_name: str, temp_name: str) -> None:
    """Atomically point live_name at temp_name, replacing whatever backs it today.

    Handles both cases: live_name is currently an alias (pure atomic swap), or
    live_name is currently a real collection — a one-time migration with a
    brief delete-then-alias-create window, the same cost any first move to
    aliasing pays. Shared by both the grc_requirements and grc_context rebuild
    paths in cmd_reindex.
    """
    from qdrant_client.models import (
        CreateAliasOperation, CreateAlias,
        DeleteAliasOperation, DeleteAlias,
    )

    old_backing = None
    try:
        for a in qdrant.get_aliases().aliases:
            if a.alias_name == live_name:
                old_backing = a.collection_name
                break
    except Exception:
        pass

    alias_ops = []
    if old_backing:
        alias_ops.append(DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=live_name)))
    else:
        try:
            qdrant.delete_collection(live_name)
            log.info("Deleted old real collection '%s'", live_name)
        except Exception as e:
            log.warning("Could not delete old collection '%s': %s", live_name, e)

    alias_ops.append(CreateAliasOperation(
        create_alias=CreateAlias(collection_name=temp_name, alias_name=live_name),
    ))
    qdrant.update_collection_aliases(change_aliases_operations=alias_ops)
    log.info("Alias '%s' now points to '%s'", live_name, temp_name)

    if old_backing and old_backing != temp_name:
        try:
            qdrant.delete_collection(old_backing)
            log.info("Deleted old backing collection: %s", old_backing)
        except Exception as e:
            log.warning("Could not delete old backing collection %s: %s", old_backing, e)


def _collection_point_ids(qdrant, collection: str) -> set[str]:
    """Every point ID in a collection (IDs only; no payloads or vectors)."""
    ids: set[str] = set()
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=collection, limit=1000, offset=offset,
            with_payload=False, with_vectors=False,
        )
        ids.update(str(p.id) for p in points)
        # An empty page ends the walk even if an offset comes back: stopping early only means the
        # guard sees fewer IDs (a refusal), never a hang or a false pass.
        if offset is None or not points:
            return ids


def _coverage_gap(qdrant, collection: str, expected: dict[str, str]) -> list[str] | None:
    """Labels of the expected points that are missing from `collection`.

    `expected` maps point ID -> a human-readable label. Returns None when the collection
    could not be read at all -- an unverifiable index is treated like an incomplete one.
    """
    try:
        present = _collection_point_ids(qdrant, collection)
    except Exception as e:
        log.error("Could not read point IDs from %s to verify coverage: %s", collection, e)
        return None
    return sorted(label for point_id, label in expected.items() if point_id not in present)


def _refuse_incomplete_swap(qdrant, live_alias: str, temp_name: str, expected_count: int,
                            missing: list[str] | None, header: str) -> None:
    """Log why a rebuilt collection is not promoted, and delete it. The live alias is untouched."""
    log.error("=" * 60)
    if missing is None:
        log.error("%s -- could not verify that %s holds every expected point. Live %s untouched.",
                  header, temp_name, live_alias)
    else:
        log.error("%s -- %d of %d expected point(s) are missing from the rebuilt %s. Live %s untouched.",
                  header, len(missing), expected_count, temp_name, live_alias)
        for label in missing[:10]:
            log.error("  MISSING: %s", label)
        if len(missing) > 10:
            log.error("  ... and %d more", len(missing) - 10)
    log.error("=" * 60)
    try:
        qdrant.delete_collection(temp_name)
        log.info("Deleted incomplete temp collection: %s", temp_name)
    except Exception as e:
        log.warning("Could not delete temp collection %s: %s", temp_name, e)


def _reindex_requirements(req_files: dict, qdrant_url: str, ollama_url: str, embedding_model: str) -> bool:
    """Rebuild grc_requirements from the resolved requirements JSONL per document.

    All-or-nothing: any file failure aborts the temp collection and leaves the
    live alias untouched (unchanged from pre-WP-24.2 behavior). WP-45.0.1: the
    indexer skips (and does not raise on) a record whose embedding fails, so before
    the swap the temp collection must also contain every distinct point ID the
    source files should produce; otherwise it is deleted and the live alias stays.
    """
    from pipeline import embed_and_index as _embed
    from qdrant_client import QdrantClient as _QC

    live_alias = "grc_requirements"
    temp_name = f"{live_alias}_{int(time.time())}"
    log.info("Building requirements into temp collection: %s", temp_name)

    items = sorted(req_files.items())
    failed = []
    from pipeline import progress as _progress

    for i, (doc_key, jsonl_path) in enumerate(items):
        _progress.emit("reindex", i, len(items))
        log.info("[%d/%d] Indexing: %s", i + 1, len(items), jsonl_path.name)
        try:
            _embed.run(
                str(jsonl_path),
                qdrant_url=qdrant_url,
                ollama_url=ollama_url,
                collection_name=temp_name,
                recreate=(i == 0),
                embedding_model=embedding_model,
                payload_extras=_citation_extras(jsonl_path),
            )
        except Exception as e:
            log.error("Indexing failed for %s: %s", jsonl_path.name, e)
            failed.append(jsonl_path.name)

    qdrant = _QC(url=qdrant_url)

    if failed:
        log.error("=" * 60)
        log.error("REINDEX FAILED — %d file(s) failed. Live requirements index untouched.", len(failed))
        for name in failed:
            log.error("  FAIL: %s", name)
        log.error("=" * 60)
        try:
            qdrant.delete_collection(temp_name)
            log.info("Deleted incomplete temp collection: %s", temp_name)
        except Exception as e:
            log.warning("Could not delete temp collection %s: %s", temp_name, e)
        return False

    expected: dict[str, str] = {}
    unindexable = collapsed = 0
    for _, jsonl_path in items:
        records = _embed.load_jsonl(jsonl_path)
        before = len(expected)
        expected.update(_embed.expected_point_ids(records))
        eligible = sum(1 for r in records if _embed.build_embedding_text(r) is not None)
        unindexable += len(records) - eligible
        collapsed += eligible - (len(expected) - before)
    missing = _coverage_gap(qdrant, temp_name, expected)
    if missing is None or missing:
        _refuse_incomplete_swap(qdrant, live_alias, temp_name, len(expected), missing, "REINDEX FAILED")
        return False

    _alias_swap(qdrant, live_alias, temp_name)
    log.info("=" * 60)
    log.info(
        "Requirements reindex complete: %d document(s), %d point(s) verified present, live alias swapped",
        len(items), len(expected),
    )
    if unindexable:
        log.warning("%d record(s) without a source_quote were not indexed", unindexable)
    if collapsed:
        log.warning("%d record(s) share a requirement_id with another and collapsed into one point", collapsed)
    log.info("=" * 60)
    return True


def _reindex_context(req_files: dict, qdrant_url: str, ollama_url: str, embedding_model: str) -> bool:
    """Rebuild grc_context from *_chunks.jsonl alongside each resolved requirements file.

    A missing chunks file is a warning-and-skip, not a failure — indexing
    continues for the remaining documents either way. But a real indexing
    exception for any document means the shared temp collection is NOT
    alias-swapped: embed_context_index.run() upserts in batches, so a failed
    document may have already written some of its chunks into the temp
    collection before raising, and swapping it live would pollute grc_context
    with a partial/incomplete version of that document. On any failure the
    temp collection is deleted and the live grc_context alias is left
    completely untouched; only a fully clean temp collection (every attempted
    document succeeded) is ever swapped in.
    """
    from pipeline import embed_context_index as _embed_ctx
    from qdrant_client import QdrantClient as _QC

    live_alias = "grc_context"
    temp_name = f"{live_alias}_{int(time.time())}"
    log.info("Building context into temp collection: %s", temp_name)

    items = sorted(req_files.items())
    indexed = []
    indexed_sources = []
    failed = []
    skipped = []

    from pipeline import progress as _progress

    for n, (doc_key, req_path) in enumerate(items):
        _progress.emit("reindex-context", n, len(items))
        # Exact match on doc_key, not an unfiltered glob()[0] — a run directory
        # could in principle hold artifacts for more than one document, and
        # grabbing an arbitrary chunks file would pair the wrong document_id
        # with the wrong chunks (corrupting ask --context / trace lookups).
        chunk_path = req_path.parent / f"{doc_key}_chunks.jsonl"
        if not chunk_path.exists():
            log.warning("No chunks.jsonl found for %s — skipping context index", doc_key)
            skipped.append(doc_key)
            continue

        try:
            # Resolve the filename fallback here so indexing and the coverage check agree on the ID.
            document_id = _embed_ctx.resolve_document_id(_read_document_id(str(req_path)), chunk_path)
            _embed_ctx.run(
                str(chunk_path),
                document_id=document_id,
                qdrant_url=qdrant_url,
                ollama_url=ollama_url,
                collection_name=temp_name,
                recreate=(not indexed),
                embedding_model=embedding_model,
            )
            indexed.append(doc_key)
            indexed_sources.append((document_id, chunk_path))
        except Exception as e:
            log.error("Context indexing failed for %s: %s", doc_key, e)
            failed.append(doc_key)

    qdrant = _QC(url=qdrant_url)

    if failed:
        log.error("=" * 60)
        log.error(
            "REINDEX PARTIAL: requirements rebuilt; context rebuild failed for %d document(s). "
            "Live context index untouched.",
            len(failed),
        )
        for name in failed:
            log.error("  FAIL: %s", name)
        log.error("=" * 60)
        try:
            qdrant.delete_collection(temp_name)
        except Exception as e:
            log.warning("Could not delete temp collection %s: %s", temp_name, e)
        return False

    if not indexed:
        log.error("REINDEX: no documents indexed into grc_context — live context index untouched")
        try:
            qdrant.delete_collection(temp_name)
        except Exception as e:
            log.warning("Could not delete temp collection %s: %s", temp_name, e)
        return False

    expected: dict[str, str] = {}
    for document_id, chunk_path in indexed_sources:
        expected.update(_embed_ctx.expected_point_ids(document_id, _embed_ctx.load_jsonl(chunk_path)))
    missing = _coverage_gap(qdrant, temp_name, expected)
    if missing is None or missing:
        _refuse_incomplete_swap(
            qdrant, live_alias, temp_name, len(expected), missing,
            "REINDEX PARTIAL: requirements rebuilt; context rebuild failed",
        )
        return False

    _alias_swap(qdrant, live_alias, temp_name)
    log.info("=" * 60)
    log.info(
        "Context reindex complete: %d document(s), %d point(s) verified present, live alias swapped",
        len(indexed), len(expected),
    )
    if skipped:
        log.warning(
            "No chunks.jsonl for %d document(s); their context is absent from the new grc_context: %s",
            len(skipped), ", ".join(skipped),
        )
    log.info("=" * 60)
    return True


def cmd_reindex(args: argparse.Namespace) -> int:
    """Rebuild grc_requirements and (by default) grc_context from existing artifacts.

    No LLM re-extraction — JSONL/chunks are the system of record. Uses an
    atomic temp-collection + alias-swap for both collections so the live
    index is never touched until indexing succeeds. Prefers
    *_requirements_gated.jsonl over *_requirements_enriched.jsonl over
    *_requirements_normalized.jsonl per document, "latest run wins" when
    multiple runs exist.
    --requirements-only skips the slower, CPU-bound grc_context rebuild.
    """
    from core.artifact_resolver import resolve_latest_requirement_files
    from pipeline import progress as _progress

    if getattr(args, "progress_json", False):
        _progress.enable()

    processed_dir = _cfg.processed_dir_path()
    if not processed_dir.exists():
        log.error("Processed documents directory not found: %s", processed_dir)
        return 1

    req_files = resolve_latest_requirement_files(processed_dir)
    if not req_files:
        log.error("No requirements JSONL files found in: %s", processed_dir)
        return 1

    log.info("Found %d document(s) to reindex", len(req_files))

    if not _reindex_requirements(req_files, args.qdrant_url, args.ollama_url, _cfg.embedding_model):
        log.error("The requirements index was NOT rebuilt and the live index is untouched. Run the rebuild again.")
        return 1
    log.info("The requirements index is rebuilt and live.")

    if getattr(args, "requirements_only", False):
        log.info("Skipped grc_context rebuild (--requirements-only)")
        _progress.emit("done")
        return 0

    if not _reindex_context(req_files, args.qdrant_url, args.ollama_url, _cfg.embedding_model):
        # the two collections are swapped one after the other, not together (docs/OPERATIONS.md): say plainly which half is done
        log.error("The context index was NOT rebuilt: the new requirements index is already live beside the old context index. Run the rebuild again to bring the context up to date.")
        return 1
    _progress.emit("done")
    return 0


def cmd_docs(args: argparse.Namespace) -> int:
    """List all indexed documents with requirement counts and extraction mode."""
    from services import docs_service

    processed_dir = _cfg.processed_dir_path()
    if not processed_dir.exists():
        log.error("Processed documents directory not found: %s", processed_dir)
        return 1

    result = docs_service.list_docs(processed_dir)

    # WP-33.2: skip_sections_applied is None (nothing configured to surface),
    # True, or False ("configured but silently didn't apply" -- the exact gap
    # this column exists to make visible without reading pipeline logs).
    def _skip_sections_display(applied: bool | None) -> str:
        if applied is None:
            return "-"
        return "yes" if applied else "no (!)"

    print(f"\n{'Document':<30} {'Reqs':>6}  {'Extraction':<12}  {'Skip-Sect':<10}  {'Run Date'}")
    print("-" * 82)
    for doc in result["docs"]:
        skip_sect = _skip_sections_display(doc.get("skip_sections_applied"))
        print(
            f"{doc['doc_key']:<30} {doc['count']:>6}  {doc['mode']:<12}  "
            f"{skip_sect:<10}  {doc['run_date']}"
        )
    print("-" * 82)
    print(f"{'TOTAL':<30} {result['total_reqs']:>6}  ({result['total_docs']} documents)")
    print()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show system status."""
    from services import status_service

    ollama_url = getattr(args, "ollama_url", _cfg.ollama_url)
    qdrant_url = getattr(args, "qdrant_url", _cfg.qdrant_url)
    processed_dir = getattr(args, "processed_dir", None) or _cfg.processed_dir_path()
    configured_models = {
        "embedding": _cfg.embedding_model,
        "extraction": _cfg.extraction_model,
        "enrichment": _cfg.enrichment_model,
        "rewrite": _cfg.rewrite_model,
        "synthesis": _cfg.synthesis_model,
    }
    result = status_service.check(ollama_url, qdrant_url, processed_dir, configured_models)

    print("=" * 60)
    print("ReqBot System Status")
    print("=" * 60)

    ollama = result["ollama"]
    print(f"\n--- Ollama ({ollama_url}) ---")
    if ollama["reachable"]:
        print(f"  Status: Running ({len(ollama['models'])} models)")
        for m in ollama["models"]:
            print(f"  - {m['name']} ({m['size_gb']:.1f} GB)")
    else:
        print("  Status: NOT REACHABLE")

    configured = result["configured_models"]
    print("\n--- Configured Models ---")
    print(f"  Embedding:   {configured['embedding']}")
    print(f"  Extraction:  {configured['extraction']}")
    print(f"  Enrichment:  {configured['enrichment']}")
    print(f"  Rewrite:     {configured['rewrite']}")
    print(f"  Synthesis:   {configured['synthesis']}")

    qdrant = result["qdrant"]
    print(f"\n--- Qdrant ({qdrant_url}) ---")
    if qdrant["reachable"]:
        print(f"  Status: Running ({len(qdrant['collections'])} collections)")
        for c in qdrant["collections"]:
            print(f"  - {c['name']}: {c['points']} points")
    else:
        print("  Status: NOT REACHABLE")

    print("\n--- Processed Documents ---")
    docs = result["processed_documents"]
    if docs:
        for d in docs:
            print(f"  - {d['path']}: {d['count']} requirements")
    else:
        print("  No processed documents found")

    print()
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    """Trace the full provenance of a specific requirement by ID."""
    from services import trace_service
    import textwrap as _tw

    qdrant_url = getattr(args, "qdrant_url", _cfg.qdrant_url)
    req_id = args.requirement_id
    json_output = getattr(args, "json_output", False)
    show_context = getattr(args, "context", False)

    try:
        result = trace_service.trace(req_id, qdrant_url, show_context=show_context)
    except ValueError as e:
        log.error("%s", e)
        return 1
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    payload = result["requirement"]
    cross_matches = result["cross_matches"]
    context_text = result["context_text"]
    source_ref = payload.get("source_ref", "")  # as extracted: what trace matched other documents on
    shown_ref = _requirement_citation(payload)  # what is shown for the requirement itself

    if json_output:
        out: dict = {
            "requirement": payload,
            "cross_framework_matches": cross_matches,
        }
        if show_context:
            out["context_text"] = context_text
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    # --- Terminal display ---
    LABEL_W = 16

    def _labeled(label: str, text: str) -> None:
        lines = _tw.wrap(str(text), width=80 - LABEL_W) if text else [""]
        print(f"{label:<{LABEL_W}}{lines[0] if lines else ''}")
        for line in lines[1:]:
            print(f"{' ' * LABEL_W}{line}")

    page_start = payload.get("page_start", "")
    page_end = payload.get("page_end", "")
    page_str = str(page_start) if page_start else "—"
    if page_end and page_end != page_start:
        page_str += f"–{page_end}"

    print("\nRequirement Trace")
    print("=================")
    _labeled("ID:", req_id)
    if payload.get("description"):
        _labeled("Description:", payload.get("description", ""))

    print("\nProvenance")
    print("----------")
    print(f"  {'Document:':<14} {payload.get('source_pdf', '—')}")
    print(f"  {'Source ref:':<14} {shown_ref or '—'}")
    if source_ref and source_ref.strip() != shown_ref:
        print(f"  {'As extracted:':<14} {source_ref.strip()}")
    print(f"  {'Page:':<14} {page_str}")
    print(f"  {'Domain profile:':<14} {payload.get('domain_profile', 'cybersecurity')}")
    print(f"  {'Extracted by:':<14} {payload.get('extraction_model', 'unknown')}")
    print(f"  {'Run date:':<14} {payload.get('run_timestamp', 'unknown')}")
    _auth_weight = _cfg.authority_weight(payload.get("source_pdf", ""))
    if _auth_weight is not None:
        _auth_fw = _cfg.authority_framework(payload.get("source_pdf", ""))
        _auth_label = f"{_auth_weight}/5" + (f"  ({_auth_fw})" if _auth_fw else "")
        print(f"  {'Authority:':<14} {_auth_label}")

    explained = payload.get("explained_text", "")
    if explained and explained != payload.get("source_quote", ""):
        print("\nRequirement")
        print("-----------")
        for line in _tw.wrap(explained, width=76):
            print(f"  {line}")

    source_quote = payload.get("source_quote", "")
    if source_quote:
        print("\nSource Quote")
        print("------------")
        quote_lines = _tw.wrap(source_quote, width=76)
        for i, line in enumerate(quote_lines):
            prefix = '  "' if i == 0 else '   '
            suffix = '"' if i == len(quote_lines) - 1 else ""
            print(f"{prefix}{line}{suffix}")

    if context_text:
        print("\nSurrounding Context")
        print("-------------------")
        for line in _tw.wrap(context_text, width=78):
            print(f"  {line}")

    if cross_matches:
        print(f"\nCross-Framework Matches (same source_ref: {source_ref})")
        print("-" * 50)
        for m in cross_matches:
            m_pdf = (m.get("source_pdf") or "")[:30]
            m_ref = m.get("source_ref", "")
            m_page = m.get("page_start", "")
            m_weight = _cfg.authority_weight(m.get("source_pdf", ""))
            weight_str = f"  [auth:{m_weight}/5]" if m_weight is not None else ""
            print(f"  {m_pdf:<30} {m_ref:<14} Page {m_page}{weight_str}")
    elif source_ref:
        print(f"\n  No other documents found with source_ref: {source_ref}")

    print()
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare a control ID or free-text query across all indexed documents."""
    import textwrap as _tw
    from services import compare_service

    query = args.query.strip()
    qdrant_url = getattr(args, "qdrant_url", _cfg.qdrant_url)
    ollama_url = getattr(args, "ollama_url", _cfg.ollama_url)
    top_k = getattr(args, "top_k", _cfg.top_k)
    json_output = getattr(args, "json_output", False)
    markdown_output = getattr(args, "markdown_output", False)
    document_ids = getattr(args, "document_ids", None) or []

    try:
        result = compare_service.compare(
            query, qdrant_url, ollama_url, top_k, document_ids,
            embedding_model=_cfg.embedding_model,
        )
    except ValueError as e:
        log.error("%s", e)
        return 1
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    # -----------------------------------------------------------------------
    # Exact match display
    # -----------------------------------------------------------------------
    if result["mode"] == "exact":
        query = result["query"]
        doc_groups = result["groups"]

        if json_output:
            print(json.dumps({
                "query": query,
                "mode": "exact",
                "source_ref": result["source_ref"],
                "groups": list(doc_groups.values()),
                "warnings": result.get("warnings", []),
            }, indent=2, ensure_ascii=False))
            return 0

        title = f"Cross-Framework Comparison: {query}"
        if markdown_output:
            print(f"# {title}\n")
            print(f"*{len(doc_groups)} document(s) — 1 control ID*\n")
            for doc_key, p in sorted(doc_groups.items()):
                page = p.get("page_start", "")
                header = f"{doc_key} (Page {page})" if page else doc_key
                print(f"## {header}\n")
                primary = requirement_text(p)
                print(f"{primary}\n")
                if p.get("source_quote") and primary != p.get("source_quote"):
                    print(f"> {p['source_quote']}\n")
                print("---\n")
        else:
            print(f"\n{title}")
            print("=" * len(title))
            for doc_key, p in sorted(doc_groups.items()):
                page = p.get("page_start", "")
                aw = _cfg.authority_weight(doc_key)
                auth_tag = f"  [auth:{aw}/5]" if aw is not None else ""
                subheader = (f"{doc_key} (Page {page})" if page else doc_key) + auth_tag
                print(f"\n{subheader}")
                print("-" * len(subheader))
                primary = requirement_text(p)
                for line in _tw.wrap(primary, width=76):
                    print(f"  {line}")
            print(f"\n{len(doc_groups)} document(s) — 1 control ID")
            print()

    # -----------------------------------------------------------------------
    # Semantic display
    # -----------------------------------------------------------------------
    else:
        query = result["query"]
        ref_order = result["ref_order"]
        ref_groups = result["ref_groups"]

        if json_output:
            print(json.dumps({
                "query": query,
                "mode": "semantic",
                "groups": [
                    {"source_ref": ref, "documents": list(ref_groups[ref].values())}
                    for ref in ref_order
                ],
                "warnings": result.get("warnings", []),
            }, indent=2, ensure_ascii=False))
            return 0

        total_docs = sum(len(v) for v in ref_groups.values())
        title = f"Cross-Framework Comparison: {query}"
        if markdown_output:
            print(f"# {title}\n")
            print(f"*{len(ref_groups)} control group(s), {total_docs} source(s)*\n")
            for ref in ref_order:
                print(f"## {ref}\n")
                for doc_key, p in ref_groups[ref].items():
                    page = p.get("page_start", "")
                    sub = f"**{doc_key}**" + (f" (Page {page})" if page else "")
                    print(f"### {sub}\n")
                    primary = requirement_text(p)
                    print(f"{primary}\n")
                print("---\n")
        else:
            print(f"\n{title}")
            print("=" * len(title))
            for ref in ref_order:
                docs = ref_groups[ref]
                ref_line = f"\n  [{ref}]  {len(docs)} document(s)"
                print(ref_line)
                print("  " + "-" * (len(ref) + 18))
                for doc_key, p in docs.items():
                    page = p.get("page_start", "")
                    aw = _cfg.authority_weight(doc_key)
                    auth_tag = f"  [auth:{aw}/5]" if aw is not None else ""
                    print(f"\n  {doc_key}" + (f" (Page {page})" if page else "") + auth_tag)
                    primary = requirement_text(p)
                    for line in _tw.wrap(primary, width=72):
                        print(f"    {line}")
            print(f"\n{len(ref_groups)} control group(s) — {total_docs} source(s)")
            print()

    for warning in result.get("warnings", []):
        print(f"[!] {warning}")

    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    """Export a defensible evidence pack grouped by control ID."""
    import os
    import textwrap as _tw
    from services import evidence_service

    query = args.query.strip()
    qdrant_url = getattr(args, "qdrant_url", _cfg.qdrant_url)
    ollama_url = getattr(args, "ollama_url", _cfg.ollama_url)
    top_k = getattr(args, "top_k", _cfg.top_k)
    fmt = getattr(args, "output_format", "markdown")
    output_file = getattr(args, "output_file", None)
    show_context = getattr(args, "context", False)
    document_ids = getattr(args, "document_ids", None) or []
    domain_tags = getattr(args, "domain_tags", None) or []
    requirement_types = getattr(args, "requirement_types", None) or []
    api_key = os.environ.get(_cfg.api_key_env, "") if _cfg.synthesis_backend == "remote" else ""

    try:
        result = evidence_service.build(
            query=query,
            qdrant_url=qdrant_url,
            ollama_url=ollama_url,
            top_k=top_k,
            show_context=show_context,
            document_ids=document_ids,
            domain_tags=domain_tags,
            requirement_types=requirement_types,
            synthesis_backend=_cfg.synthesis_backend,
            synthesis_model=_cfg.synthesis_model,
            remote_model=_cfg.remote_model,
            provider=_cfg.remote_provider,
            api_key=api_key,
            embedding_model=_cfg.embedding_model,
        )
    except ValueError as e:
        log.error("%s", e)
        return 1
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    groups = result["groups"]
    group_order = result["group_order"]
    total_sources = result["total_sources"]
    synthesis_text = result["synthesis_text"]
    timestamp = result["timestamp"]

    # -----------------------------------------------------------------------
    # Build output (JSON or Markdown) — rendering stays in the CLI layer
    # -----------------------------------------------------------------------
    if fmt == "json":
        out_groups = []
        for ref in group_order:
            g = groups[ref]
            rep = g["representative"]
            entry: dict = {
                "source_ref": g["source_ref"],
                "description": rep.get("description", ""),
                "source_quote": rep.get("source_quote", ""),
                "primary_text": requirement_text(rep),
                "confidence": rep.get("confidence"),
                "sources": [
                    {
                        "source_pdf": s.get("source_pdf", ""),
                        "source_ref": s.get("source_ref", ""),
                        "page_start": s.get("page_start"),
                        "page_end": s.get("page_end"),
                        "document_id": s.get("document_id", ""),
                    }
                    for s in g["sources"]
                ],
            }
            if show_context:
                entry["context_text"] = g.get("context_text")
            out_groups.append(entry)
        output_text = json.dumps({
            "query": query,
            "generated": timestamp,
            "group_count": len(groups),
            "source_count": total_sources,
            "executive_summary": synthesis_text or None,
            "groups": out_groups,
        }, indent=2, ensure_ascii=False)

    else:  # markdown (default)
        lines: list[str] = []
        title = f"Evidence Pack: {query}"
        lines += [
            title,
            "=" * len(title),
            f"Generated: {timestamp}",
            f"Query:     {query}",
            f"Results:   {len(groups)} requirement group(s), {total_sources} source(s)",
            "",
        ]
        if synthesis_text:
            lines.append("## Executive Summary")
            lines.append("")
            for line in _tw.wrap(synthesis_text.strip(), width=80):
                lines.append(line)
            lines.append("")

        for i, ref in enumerate(group_order, 1):
            g = groups[ref]
            rep = g["representative"]

            lines.append("---")
            lines.append("")
            lines.append(f"## Requirement Group {i} — {g['source_ref']}")
            lines.append("")
            lines.append("**Requirement:**")
            lines.append(requirement_text(rep))
            lines.append("")
            lines.append("**Sources:**")
            lines.append("")
            _has_auth = any(
                _cfg.authority_weight(s.get("source_pdf", "")) is not None
                for s in g["sources"]
            )
            if _has_auth:
                lines.append("| Framework | Reference | Page | Authority |")
                lines.append("|-----------|-----------|------|-----------|")
                for s in g["sources"]:
                    framework = s.get("source_pdf") or "—"
                    ref_str = s.get("source_ref") or "—"
                    page = s.get("page_start") or "—"
                    aw = _cfg.authority_weight(framework)
                    auth_cell = f"{aw}/5" if aw is not None else "—"
                    lines.append(f"| {framework} | {ref_str} | {page} | {auth_cell} |")
            else:
                lines.append("| Framework | Reference | Page |")
                lines.append("|-----------|-----------|------|")
                for s in g["sources"]:
                    framework = s.get("source_pdf") or "—"
                    ref_str = s.get("source_ref") or "—"
                    page = s.get("page_start") or "—"
                    lines.append(f"| {framework} | {ref_str} | {page} |")
            lines.append("")

            if show_context and g.get("context_text"):
                lines.append("**Context:**")
                lines.append("")
                for line in _tw.wrap(g["context_text"], width=78):
                    lines.append(f"> {line}")
                lines.append("")

            n = len(g["sources"])
            if n > 1:
                lines.append(f"**Notes:** Found in {n} sources across the corpus.")
            lines.append("")

        output_text = "\n".join(lines)

    # -----------------------------------------------------------------------
    # Write to file or stdout
    # -----------------------------------------------------------------------
    if output_file:
        try:
            Path(output_file).expanduser().write_text(output_text + "\n", encoding="utf-8")
            print(f"Evidence pack written to: {output_file}")
        except OSError as e:
            log.error("Could not write to file: %s", e)
            return 1
    else:
        print(output_text)

    for warning in result.get("warnings", []):
        log.warning("%s", warning)

    return 0


def cmd_questions(args: argparse.Namespace) -> int:
    """Write draft audit questions for a document's checklist rows to a sidecar file (WP-46.6); `reqbot checklist` shows them."""
    from pipeline import progress as _progress
    from services import audit_questions, checklist_service

    if getattr(args, "progress_json", False):
        _progress.enable()
    processed_dir = _cfg.processed_dir_path()
    try:
        checklist = checklist_service.generate(processed_dir, args.doc, args.profile)
        path = audit_questions.sidecar_path(checklist_service.requirements_path(processed_dir, args.doc))
    except (ValueError, FileNotFoundError) as e:
        log.error("%s", e)
        return 1
    counts = audit_questions.draft_questions(
        checklist["items"], path, model=args.model, ollama_url=args.ollama_url,
        progress=lambda c: log.info("questions so far: %s", c),
        on_row=lambda done, total: _progress.emit("questions", done, total),
    )
    print(f"Draft audit questions for {args.doc}: {counts}\nWritten to: {path}", file=sys.stderr if _progress.enabled() else sys.stdout)
    if counts.get("aborted"):
        log.error("Stopped: the model could not be reached %d times in a row (%s). Rows already written were kept.", audit_questions.MAX_CONSECUTIVE_FAILURES, args.ollama_url)
    if not counts["errors"]:
        _progress.emit("done")
    return 1 if counts["errors"] else 0


def cmd_kinds(args: argparse.Namespace) -> int:
    """Label each checklist row with the kind of statement it is, in a sidecar file (requirement kind, stage 1; docs/PIPELINE_REDESIGN_PLAN.md section 10). No model call."""
    from services import checklist_service, requirement_kind

    processed_dir = _cfg.processed_dir_path()
    try:
        checklist = checklist_service.generate(processed_dir, args.doc, args.profile)
        path = requirement_kind.sidecar_path(checklist_service.requirements_path(processed_dir, args.doc))
    except (ValueError, FileNotFoundError) as e:
        log.error("%s", e)
        return 1
    records = requirement_kind.label_items(checklist["items"])
    requirement_kind.write(path, records)
    print(f"Requirement kinds for {args.doc}: {requirement_kind.counts(records)}\nWritten to: {path}")
    return 0


def cmd_checklist(args: argparse.Namespace) -> int:
    """Generate an audit checklist from validated requirements for a document."""
    from services import checklist_service
    from pipeline import checklist_export

    processed_dir = _cfg.processed_dir_path()
    if not processed_dir.exists():
        log.error("Processed documents directory not found: %s", processed_dir)
        return 1

    try:
        checklist = checklist_service.generate(processed_dir, args.doc, args.profile)
    except (ValueError, FileNotFoundError) as e:
        log.error("%s", e)
        return 1

    fmt = args.format
    if fmt == "xlsx":
        if not args.output:
            log.error("--output FILE is required for --format xlsx (binary format cannot be written to stdout)")
            return 1
        xlsx_bytes = checklist_export.to_xlsx(checklist)
        try:
            Path(args.output).expanduser().write_bytes(xlsx_bytes)
            print(f"Checklist written to: {args.output}")
        except OSError as e:
            log.error("Could not write to file: %s", e)
            return 1
        return 0

    if fmt == "json":
        output_text = checklist_export.to_json(checklist)
    elif fmt == "md":
        output_text = checklist_export.to_markdown(checklist)
    else:
        output_text = checklist_export.to_csv(checklist)

    if args.output:
        try:
            Path(args.output).expanduser().write_text(output_text, encoding="utf-8")
            print(f"Checklist written to: {args.output}")
        except OSError as e:
            log.error("Could not write to file: %s", e)
            return 1
    else:
        print(output_text, end="")

    return 0


def _test_ollama(url: str) -> tuple[bool, str, list[str]]:
    """Test Ollama connectivity. Returns (ok, message, model_names_list). The check itself is shared with the setup wizard (services/setup_service.py)."""
    from services import setup_service

    return setup_service.test_ollama(url)


def _test_qdrant(url: str) -> tuple[bool, str]:
    """Test Qdrant connectivity. Returns (ok, message). Shared with the setup wizard."""
    from services import setup_service

    return setup_service.test_qdrant(url)


def _print_setup_check(result: dict) -> None:
    """The setup check as plain lines: what answers, which models are there, and whether ReqBot is ready."""
    def mark(ok):
        return "OK  " if ok else "FAIL" if ok is False else "??  "

    print(f"{mark(result['ollama']['ok'])} Ollama  {result['ollama']['url']}  {result['ollama']['message']}")
    print(f"{mark(result['qdrant']['ok'])} Qdrant  {result['qdrant']['url']}  {result['qdrant']['message']}")
    for m in result["models"]:
        state = "installed" if m["installed"] else "NOT INSTALLED" if m["installed"] is False else "unknown (Ollama did not answer)"
        need = "needed" if m["required"] else "optional"
        print(f"{mark(m['installed'])} Model  {m['name'] or '(not set)'}  {state}  [{need}: {m['needed_for']}]")
        if m["installed"] is False and m["name"]:  # an unset model has no name to pull
            print(f"       to install it, on the machine that runs Ollama: ollama pull {m['name']}")
    folder = result["folder"]
    print(f"{mark(folder['writable'])} Folder {folder['path']}  {folder['message']}")
    print("\nReady to use." if result["ready"] else "\nNot ready yet: fix the lines marked FAIL above (optional models only cost their own feature).")


def _cmd_init_check() -> int:
    """`reqbot init --check`: the checks the setup wizard shows, against the saved configuration. Changes nothing. Exit code 0 when ready, 1 otherwise."""
    from services import setup_service
    from services.job_service import QUESTIONS_MODEL

    values = {k: getattr(_cfg, k, None) for k in ("ollama_url", "qdrant_url", "embedding_model", "default_model", "extraction_model", "rewrite_model", "synthesis_model",
                                                    "synthesis_backend")}
    result = setup_service.run_check(values, _cfg.processed_dir_path(), QUESTIONS_MODEL)
    _print_setup_check(result)
    return 0 if result["ready"] else 1


def cmd_init(args: argparse.Namespace) -> int:
    """Guided first-run setup.

    Configures Qdrant/Ollama service URLs and model/synthesis preferences, then
    writes ~/.config/reqbot/config.json. ReqBot does not install, start, or
    manage the Qdrant or Ollama services themselves — both are expected to
    already be running somewhere reachable by URL.
    """
    if getattr(args, "check", False):
        return _cmd_init_check()

    print("\nReqBot Setup")
    print("============")

    def _prompt(label: str, default: str) -> str:
        """Prompt with default in brackets; empty input returns default."""
        val = input(f"{label} [{default}]: ").strip()
        return val if val else default

    def _prompt_role_model(label: str, resolved_default: str) -> str | None:
        """Prompt for a role model that falls back to default_model (R-2.1).

        Shows the just-entered default_model as the bracketed suggestion, not
        whatever this role happened to resolve to before this init run — a
        blank answer means "follow default_model", so it returns None rather
        than freezing a literal, letting core.config.load()'s existing
        fallback keep tracking default_model afterward (Codex review, PR #107:
        entering a new default_model then blanking through extraction/
        enrichment/rewrite must actually adopt the new value, not silently
        re-write the stale one loaded before init started).
        """
        val = input(f"{label} [{resolved_default}]: ").strip()
        return val if val else None

    def _prompt_choice(label: str, options: list[str], default: int = 1) -> int:
        """Print a numbered menu; return the 1-based choice (default on empty input)."""
        print(f"\n{label}")
        for i, opt in enumerate(options, 1):
            print(f"  [{i}] {opt}")
        while True:
            raw = input(f"Choice [{default}]: ").strip()
            if not raw:
                return default
            try:
                choice = int(raw)
                if 1 <= choice <= len(options):
                    return choice
            except ValueError:
                pass
            print(f"  Enter a number from 1 to {len(options)}.")

    try:
        # --- Qdrant ------------------------------------------------------ #
        print("\nQdrant (vector database) — must already be running; ReqBot connects")
        print("to it by URL and does not install or manage the service itself.")
        while True:
            qdrant_url = _prompt("Qdrant URL", _cfg.qdrant_url).rstrip("/")
            connected, msg = _test_qdrant(qdrant_url)
            print(f"  Testing connection... {msg}")
            if connected:
                break
            keep = input("  Connection failed. Keep this URL anyway? (y/N): ").strip().lower()
            if keep == "y":
                break

        # --- Ollama -------------------------------------------------------- #
        print()
        print("Ollama runs the local pipeline: embeddings, requirement extraction,")
        print("query rewriting, and HyDE. This is separate from where answer")
        print("synthesis happens, configured below. Must already be running; ReqBot")
        print("connects to it by URL and does not install or manage the service itself.")
        while True:
            ollama_url = _prompt("Ollama URL", _cfg.ollama_url).rstrip("/")
            connected, msg, _ = _test_ollama(ollama_url)
            print(f"  Testing connection... {msg}")
            if connected:
                break
            keep = input("  Connection failed. Keep this URL anyway? (y/N): ").strip().lower()
            if keep == "y":
                break

        # Single source of truth for available model names regardless of
        # which branch above was taken (Codex review: don't trust raw
        # `ollama pull`/`ollama list` output as a second source of truth).
        _, _, available_models = _test_ollama(ollama_url)
        from services import setup_service as _setup_service

        _installed = _setup_service.installed_names(available_models)

        def _model_installed(name: str) -> bool:
            """The same rule the wizard and a queued job's pre-flight use: a configured `nomic-embed-text` is the installed `nomic-embed-text:latest`."""
            return _setup_service.has_model(name, _installed)

        # Embedding model — independent of default_model; it defines the vector shape
        # already stored in Qdrant. Changing it requires a full 'reqbot reindex'
        # afterward, not just a config edit (WP-25.6c) — ReqBot still works and warns
        # on mismatches in the meantime rather than blocking queries.
        embedding_model = _prompt("Embedding model", _cfg.embedding_model)
        if available_models and not _model_installed(embedding_model):
            print(f"  [!] Warning: '{embedding_model}' not found on Ollama server.")
            print(f"      Available: {', '.join(available_models)}")
        if embedding_model != _cfg.embedding_model:
            print(
                f"  [!] Embedding model changed from '{_cfg.embedding_model}' to "
                f"'{embedding_model}' — existing indexed data was embedded with the old "
                "model. Run 'reqbot reindex' after saving to refresh it."
            )

        # Models — warn if not present on the server
        default_model = _prompt("Default model (fallback for all pipeline stages)", _cfg.default_model)
        if available_models and not _model_installed(default_model):
            print(f"  [!] Warning: '{default_model}' not found on Ollama server.")
            print(f"      Available: {', '.join(available_models)}")

        extraction_model = _prompt_role_model("Step C extraction model (default: same as above)", default_model)
        if extraction_model and available_models and not _model_installed(extraction_model):
            print(f"  [!] Warning: '{extraction_model}' not found on Ollama server.")
            print(f"      Available: {', '.join(available_models)}")

        enrichment_model = _prompt_role_model("Step D.5 enrichment model (default: same as above)", default_model)
        if enrichment_model and available_models and not _model_installed(enrichment_model):
            print(f"  [!] Warning: '{enrichment_model}' not found on Ollama server.")
            print(f"      Available: {', '.join(available_models)}")

        rewrite_model = _prompt_role_model("Query-rewrite/HyDE model (default: same as above)", default_model)
        if rewrite_model and available_models and not _model_installed(rewrite_model):
            print(f"  [!] Warning: '{rewrite_model}' not found on Ollama server.")
            print(f"      Available: {', '.join(available_models)}")

        synthesis_model = _prompt("Synthesis model", _cfg.synthesis_model)
        if available_models and not _model_installed(synthesis_model):
            print(f"  [!] Warning: '{synthesis_model}' not found on Ollama server.")
            print(f"      Available: {', '.join(available_models)}")

        # top_k — must be a positive int
        while True:
            raw = _prompt("Default top-k", str(_cfg.top_k))
            try:
                top_k = int(raw)
                if top_k > 0:
                    break
                print("  top-k must be a positive integer.")
            except ValueError:
                print("  Invalid value — enter a positive integer.")

        # min_score — must be a non-negative float
        while True:
            raw = _prompt("Minimum relevance score (0 = disabled)", str(_cfg.min_score))
            try:
                min_score = float(raw)
                if min_score >= 0:
                    break
                print("  min-score must be 0 or greater.")
            except ValueError:
                print("  Invalid value — enter a number (e.g. 0.02).")

        # processed_dir — validate and attempt to create
        processed_dir = _prompt("Processed documents dir", _cfg.processed_dir)
        processed_dir_path = Path(processed_dir).expanduser().resolve()
        try:
            processed_dir_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            print(f"  [!] Warning: Cannot create directory — check permissions: {processed_dir_path}")

        # --- Synthesis ----------------------------------------------------- #
        print()
        print("  Synthesis generates a written answer for '--synthesize' queries.")
        print("  Retrieval (search, --context, evidence, trace) always works either way.")
        print("  Remote sends only retrieved evidence snippets and your query — never")
        print("  full documents.")
        synth_choice = _prompt_choice(
            "Synthesis:",
            [
                "Local Ollama",
                "Remote (Claude / GPT-4o)",
                "None — retrieval only; synthesis requests return no generated answer",
            ],
        )

        synthesis_backend = "local"
        remote_provider = _cfg.remote_provider
        remote_model = _cfg.remote_model
        api_key_env = _cfg.api_key_env

        if synth_choice == 2:
            provider_raw = input(
                f"  Provider [anthropic/openai] (default: {_cfg.remote_provider}): "
            ).strip().lower()
            remote_provider = provider_raw if provider_raw in ("anthropic", "openai") else _cfg.remote_provider

            _default_model = "claude-sonnet-4-6" if remote_provider == "anthropic" else "gpt-4o"
            model_raw = input(
                f"  Remote model (default: {_default_model}): "
            ).strip()
            remote_model = model_raw if model_raw else _default_model

            _default_env = "ANTHROPIC_API_KEY" if remote_provider == "anthropic" else "OPENAI_API_KEY"
            env_raw = input(
                f"  API key environment variable (default: {_default_env}): "
            ).strip()
            api_key_env = env_raw if env_raw else _default_env

            synthesis_backend = "remote"
            print(f"  Remote synthesis configured: {remote_provider} / {remote_model}")
            print(f"  API key read from: ${api_key_env}")
        elif synth_choice == 3:
            synthesis_backend = "none"

    except (KeyboardInterrupt, EOFError):
        print("\n\n[!] Setup cancelled — config not saved.")
        return 1

    # Write config — same service-layer write path the settings API uses
    # (WP-29.3), so cmd_init() and POST /config never maintain two copies
    # of "how config.json gets written."
    from services import config_service as _config_service

    cfg_data = {
        "ollama_url": ollama_url,
        "qdrant_url": qdrant_url,
        "default_model": default_model,
        "extraction_model": extraction_model,
        "enrichment_model": enrichment_model,
        "rewrite_model": rewrite_model,
        "synthesis_model": synthesis_model,
        "embedding_model": embedding_model,
        "top_k": top_k,
        "min_score": min_score,
        "processed_dir": processed_dir,
        "synthesis_backend": synthesis_backend,
        "remote_provider": remote_provider,
        "remote_model": remote_model,
        "api_key_env": api_key_env,
    }
    _config_service.update_config(cfg_data)
    print(f"\nConfig saved to {_config.CONFIG_PATH} (permissions: 600)")

    # Gate the success banner on actual service health, regardless of which
    # URLs were entered above.
    resolved_processed_dir = Path(processed_dir).expanduser().resolve()
    status_args = argparse.Namespace(
        ollama_url=ollama_url, qdrant_url=qdrant_url, processed_dir=resolved_processed_dir
    )
    cmd_status(status_args)

    from services import status_service as _status_service
    health = _status_service.check(ollama_url, qdrant_url, resolved_processed_dir)
    if not health["ollama"]["reachable"] or not health["qdrant"]["reachable"]:
        print("[-] Config saved, but the environment is not healthy yet.")
        print("    Fix the status issues above, then run 'reqbot status' to re-check.")
        return 1

    print("\n=== ReqBot is ready ===")
    print()
    print('  reqbot ask "what are the password requirements?"')
    print("  reqbot docs")
    print("  reqbot serve   # starts the read-only API on http://127.0.0.1:8000")
    if synthesis_backend == "local":
        print()
        print(f"Note: ReqBot does not download models for you. If '{synthesis_model}' isn't")
        print(f"already on your Ollama server, pull it before using --synthesize:")
        print(f"  OLLAMA_HOST={ollama_url} ollama pull {synthesis_model}")

    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    """Deprecated alias for 'init' — runs the same guided first-run flow.

    Kept for backward compatibility with existing scripts/docs. --advanced is
    accepted but is a no-op now that 'setup' and 'init' run the same flow.
    """
    print("[!] 'reqbot setup' is deprecated and now runs 'reqbot init'. "
          "Use 'reqbot init' going forward.")
    return cmd_init(args)


def cmd_token(args: argparse.Namespace) -> int:
    """Create (or show, or rotate) the admin access code that lets a request start jobs."""
    from core import access as _access

    want_open, want_require = getattr(args, "open", False), getattr(args, "require", False)
    if want_open or want_require:
        _access.set_open(bool(want_open))
        if want_open:
            print("Trusted-network mode is ON: anyone who can reach this server can add documents and start jobs, and no code is asked for.")
            print("Turn it off again with: reqbot token --require")
        else:
            print("Trusted-network mode is OFF: starting jobs needs the access code (reqbot token shows how to create one).")
        return 0
    if _access.is_open():
        print("Trusted-network mode is ON (no code is asked for). To require a code again: reqbot token --require")
        return 0
    if _access.source() == "environment":
        print(f"The admin access code comes from the environment variable {_access.ENV_ADMIN_TOKEN}, which takes precedence over the saved one.")
        return 0
    token, created = _access.create_admin_token(rotate=args.rotate)
    print(f"Admin access code{' (new)' if created else ''}:\n  {token}")
    print(f"Saved in {_access.ACCESS_PATH}, readable by you only. A request that starts or manages jobs sends it as 'Authorization: Bearer <code>'.")
    print("To replace it: reqbot token --rotate")
    return 0


def _job_store():
    from services import job_service as _jobs
    return _jobs.default_store(_cfg.processed_dir_path())


def _job_progress_text(job: dict) -> str:
    p = job.get("progress") or {}
    if not p:
        return ""
    return f"{p.get('step', '')} {p.get('done')}/{p.get('total')}" if p.get("total") else str(p.get("step", ""))


def cmd_jobs(args: argparse.Namespace) -> int:
    """List, show, cancel, retry and add jobs, or run the queue in the foreground (worker)."""
    from services import job_service as _jobs

    store = _job_store()
    action = args.jobs_command

    if action == "list":
        jobs = store.list_jobs(args.limit)
        if args.json_output:
            print(json.dumps([_jobs.summarize(j) for j in jobs], indent=2, ensure_ascii=False))
            return 0
        if not jobs:
            print("No jobs.")
            return 0
        print(f"{'ID':<28} {'STATE':<12} {'PROGRESS':<22} TITLE")
        for j in jobs:
            print(f"{j['id']:<28} {j['state']:<12} {_job_progress_text(j):<22} {j['title']}")
        return 0

    if action in ("show", "cancel", "retry"):
        try:
            job = store.get(args.job_id)
        except ValueError:
            job = None
        if job is None:
            log.error("No such job: %s", args.job_id)
            return 1
        if action == "cancel":
            job = store.cancel(args.job_id)
            print(f"{job['id']}: {'cancelled' if job['state'] == 'cancelled' else 'cancel requested (' + job['state'] + ')'}")
            return 0
        if action == "retry":
            try:
                new = store.retry(args.job_id)
            except ValueError as e:
                log.error("%s", e)
                return 1
            print(f"Queued {new['id']} (retry of {job['id']}). Run the queue with: reqbot jobs worker (or reqbot serve).")
            return 0
        if args.json_output:
            print(json.dumps({**_jobs.summarize(job), "log_tail": store.log_tail(job["id"])}, indent=2, ensure_ascii=False))
            return 0
        s = _jobs.summarize(job)
        for key in ("id", "title", "state", "attempt", "command", "run_dir", "created_at", "started_at", "finished_at", "exit_code", "error"):
            if s.get(key) not in (None, ""):
                print(f"{key + ':':<12} {s[key]}")
        if _job_progress_text(job):
            print(f"{'progress:':<12} {_job_progress_text(job)}")
        tail = store.log_tail(job["id"], 2000)
        if tail.strip():
            print("\n--- end of log ---\n" + tail.rstrip())
        return 0

    if action == "add":
        try:
            if args.add_kind == "questions":
                job = _jobs.enqueue_questions(args.doc, store=store, cfg=_cfg, requested_by="cli", profile=args.profile)
            elif args.add_kind == "reindex":
                job = _jobs.enqueue_reindex(store=store, cfg=_cfg, requirements_only=args.requirements_only, requested_by="cli")
            else:
                job = _jobs.enqueue_ingest(args.pdf, store=store, cfg=_cfg, no_index=args.no_index, max_chunks=args.max_chunks, requested_by="cli",
                                           then_questions=bool(getattr(args, "then_questions", False)))
        except (ValueError, LookupError) as e:
            log.error("%s", e)
            return 1
        print(f"Queued {job['id']}: {job['title']}")
        print("It runs when a runner is up: reqbot serve (the server runs the queue), or reqbot jobs worker.")
        return 0

    if action == "worker":
        import threading
        runner = _jobs.JobRunner(store)
        stop = threading.Event()
        log.info("Job runner %s started; queue in %s. Ctrl+C to stop (a running job is ended and marked interrupted).", runner.identity["id"], store.dir)
        try:
            runner.run_forever(stop)
        except KeyboardInterrupt:
            stop.set()
            print("Stopped. A job that was running was ended and marked 'interrupted'; retry it with: reqbot jobs retry <id>")
        return 0

    log.error("Unknown jobs command: %s", action)
    return 1


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove a document from the library: run folders to the trash, points out of search. Needs --yes; without it only says what would happen."""
    from services import job_service as _jobs
    from services import library_service as _library

    processed_dir = _cfg.processed_dir_path()
    try:
        plan = _library.describe(processed_dir, args.doc)
    except (ValueError, LookupError) as e:
        log.error("%s", e)
        return 1
    if not args.yes:
        print(f"Removing {plan['document']} would move {len(plan['run_folders'])} run folder(s) to {processed_dir / _library.TRASH}/ and take its rows out of search:")
        for name in plan["run_folders"]:
            print(f"  {name}")
        print("Nothing was changed. Run it again with --yes to do it (it can be undone: move the folders back and run 'reqbot reindex').")
        return 1
    from qdrant_client import QdrantClient

    try:
        out = _library.remove_document(processed_dir, args.doc, confirm=True, confirm_name=args.doc, client=QdrantClient(url=args.qdrant_url),
                                       active_jobs=_jobs.default_store(processed_dir).list_jobs())
    except _library.RemoveBlocked as e:
        log.error("A job for %s is queued or running (%s); cancel it or wait for it first.", args.doc, ", ".join(e.job_ids))
        return 1
    except (ValueError, LookupError, RuntimeError) as e:
        log.error("%s", e)
        return 1
    print(f"Removed {out['document']}: {len(out['run_folders_moved'])} run folder(s) moved to {out['trash']}; "
          f"{out['points_removed']['requirements']} requirement row(s) and {out['points_removed']['context']} context chunk(s) taken out of search.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the ReqBot API server (the page reads; queued jobs run in the background)."""
    try:
        import uvicorn
    except ImportError:
        log.error(
            "uvicorn is not installed — run: "
            "pip3 install --break-system-packages uvicorn fastapi"
        )
        return 1
    try:
        from api.app import app
    except ImportError as e:
        log.error("API module could not be loaded: %s", e)
        return 1

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    if not getattr(args, "no_runner", False):
        from services import job_service as _jobs
        _jobs.start_background_runner(_job_store())
        log.info("Job runner started (queued jobs run here, one at a time; --no-runner to turn this off)")
    from core import access as _access
    if _access.is_open() and host not in ("127.0.0.1", "localhost", "::1"):
        log.warning("Admin actions are OPEN: anyone who can reach http://%s:%s can add documents and start jobs (trusted-network mode; reqbot token --require turns it off)", host, port)
    log.info("Starting ReqBot API on http://%s:%s", host, port)
    log.info("Swagger UI available at http://%s:%s/api-docs", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    """Start the ReqBot MCP server: stdio (an AI tool on this machine starts it), or with --http the network door that serves other machines."""
    if getattr(args, "http", False):
        try:
            from mcp_server.network import run as run_network
        except ImportError:
            log.error(
                "mcp is not installed — run: pip3 install --break-system-packages 'reqbot[mcp]'"
            )
            return 1
        return run_network(
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8765),
            allowed_hosts=getattr(args, "allow_hosts", None),
        )
    try:
        from mcp_server.server import run as run_mcp
    except ImportError:
        log.error(
            "mcp is not installed — run: pip3 install --break-system-packages 'reqbot[mcp]'"
        )
        return 1
    run_mcp()
    return 0


def cmd_mcp_code(args: argparse.Namespace) -> int:
    """Create, list or revoke the access codes of the network MCP door (one per connected tool)."""
    from core import mcp_codes as _codes

    action = args.mcp_code_command
    if action == "add":
        try:
            code = _codes.add(args.name)
        except ValueError as e:
            log.error("%s", e)
            return 1
        print(f"Access code for '{args.name}' (shown once, it cannot be looked up again):\n  {code}")
        print("The connected tool sends it on every request as 'Authorization: Bearer <code>'.")
        print("Start the door with: reqbot mcp --http   Cut this tool off again with: reqbot mcp-code revoke " + args.name)
        return 0
    if action == "revoke":
        try:
            removed = _codes.revoke(args.name)
        except ValueError as e:
            log.error("%s", e)
            return 1
        if not removed:
            log.error("No code named '%s'. See them with: reqbot mcp-code list", args.name)
            return 1
        print(f"Revoked '{args.name}'. It stops working on the next request; a running door needs no restart.")
        return 0
    rows = _codes.listing()
    if not rows:
        print("No access codes. Create one with: reqbot mcp-code add NAME")
        return 0
    print(f"{'NAME':<42} {'CREATED':<22} SOURCE")
    for r in rows:
        print(f"{r['name']:<42} {r['created'] or '-':<22} {r['source']}")
    for name in _codes.rejected_from_environment():
        print(f"(ignored: '{name}' in {_codes.ENV_CODES} has a bad name or a code under {_codes.MIN_ENV_CODE_LENGTH} characters)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="reqbot",
        description="ReqBot — Cybersecurity requirements extraction and search",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ReqBot {__version__} (built {__build_date__})",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Run extraction pipeline on a PDF")
    p_ingest.add_argument("pdf", type=str, help="Path to the PDF file")
    p_ingest.add_argument("--output-dir", type=str, help="Output directory")
    p_ingest.add_argument(
        "--extraction-model", type=str, default=None, dest="extraction_model",
        help="Ollama model for Step C extraction (default: from config)",
    )
    p_ingest.add_argument(
        "--enrichment-model", type=str, default=None, dest="enrichment_model",
        help="Ollama model for Step D.5 enrichment (default: from config)",
    )
    p_ingest.add_argument(
        "--model", type=str, default=None,
        help="Convenience alias: sets both --extraction-model and --enrichment-model",
    )
    p_ingest.add_argument("--max-chunks", type=int, help="Limit chunks for testing")
    p_ingest.add_argument(
        "--no-index", action="store_true", dest="no_index",
        help="Skip indexing — write pipeline artifacts only (debug/inspection)",
    )
    # Deprecated: indexing is now the default, so --index is an inert no-op.
    # Kept accepted (not removed) so old scripts/shell history/README snippets
    # that still type --index don't suddenly fail to parse.
    p_ingest.add_argument("--index", action="store_true", help=argparse.SUPPRESS)
    p_ingest.add_argument(
        "--skip-enrichment",
        action="store_true",
        dest="skip_enrichment",
        help="Skip Pass 2 enrichment (description/tags/type). Index source_quote-only output directly.",
    )
    p_ingest.add_argument(
        "--skip-description-gate",
        action="store_true",
        dest="skip_description_gate",
        help="Skip Step D.6 description-grounding gate (WP-35.4). Index enriched output without checking descriptions for fabrication.",
    )
    p_ingest.add_argument(
        "--profile",
        type=str,
        default="cybersecurity",
        help="Domain profile name (default: cybersecurity). Profile must exist in profiles/<name>.json.",
    )
    p_ingest.add_argument(
        "--replace", action="store_true",
        help="Replace this document in the search index: once the new run is fully indexed and verified, remove the document's earlier points that it no longer has "
             "(never before; needs the whole document, so not with --max-chunks or --no-index)",
    )
    p_ingest.add_argument(
        "--progress-json", action="store_true", dest="progress_json",
        help="Print one JSON progress line per step on stdout (used by the job runner; the log stays on stderr)",
    )
    p_ingest.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")
    p_ingest.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")

    # index
    p_index = subparsers.add_parser("index", help="Embed and index requirements into Qdrant")
    p_index.add_argument("jsonl", type=str, help="Path to requirements_normalized.jsonl")
    p_index.add_argument("--recreate", action="store_true", help="Recreate Qdrant collection")
    p_index.add_argument("--batch-size", type=int, help="Embedding batch size")
    p_index.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")
    p_index.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")

    # ask
    p_ask = subparsers.add_parser("ask", help="Query requirements via vector search")
    p_ask.add_argument("question", type=str, help="Natural language question")
    p_ask.add_argument("--top-k", type=int, default=_cfg.top_k, help=f"Number of results (default: {_cfg.top_k})")
    p_ask.add_argument("--min-score", type=float, default=_cfg.min_score, dest="min_score", help=f"Minimum RRF score threshold (default: {_cfg.min_score}; 0 disables)")
    p_ask.add_argument("--synthesize", action="store_true", help="Generate LLM answer")
    p_ask.add_argument("--model", type=str, help="LLM model for synthesis")
    p_ask.add_argument("--domain-tag", action="append", dest="domain_tags", help="Filter by domain tag")
    p_ask.add_argument("--requirement-type", action="append", dest="requirement_types", help="Filter by type")
    p_ask.add_argument("--document-id", action="append", dest="document_ids", help="Filter by document")
    p_ask.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    p_ask.add_argument(
        "--context", action="store_true",
        help="Include surrounding raw chunk text from grc_context (retrieval-time only; does not affect indexing)",
    )
    p_ask.add_argument("--no-rewrite", action="store_true", dest="no_rewrite", help="Skip query rewriting")
    p_ask.add_argument("--no-hyde", action="store_true", dest="no_hyde", help="Disable HyDE hypothesis leg — baseline dense + BM25 RRF only")
    p_ask.add_argument("--rewrite-model", type=str, default=None, dest="rewrite_model", help=f"LLM model for query rewriting (default: configured rewrite_model, currently {_cfg.rewrite_model})")
    p_ask.add_argument("--context-collection", type=str, default="grc_context", dest="context_collection", help="Qdrant context collection name")
    p_ask.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")
    p_ask.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")

    # batch
    p_batch = subparsers.add_parser("batch", help="Run pipeline on all PDFs in a directory")
    p_batch.add_argument("pdf_dir", type=str, help="Directory containing PDF files")
    p_batch.add_argument(
        "--extraction-model", type=str, default=None, dest="extraction_model",
        help="Ollama model for Step C extraction (default: from config)",
    )
    p_batch.add_argument(
        "--enrichment-model", type=str, default=None, dest="enrichment_model",
        help="Ollama model for Step D.5 enrichment (default: from config)",
    )
    p_batch.add_argument(
        "--model", type=str, default=None,
        help="Convenience alias: sets both --extraction-model and --enrichment-model",
    )
    p_batch.add_argument(
        "--skip-enrichment",
        action="store_true",
        dest="skip_enrichment",
        help="Skip Pass 2 enrichment (description/tags/type). Index source_quote-only output directly.",
    )
    p_batch.add_argument(
        "--skip-description-gate",
        action="store_true",
        dest="skip_description_gate",
        help="Skip Step D.6 description-grounding gate (WP-35.4). Index enriched output without checking descriptions for fabrication.",
    )
    p_batch.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")
    p_batch.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")

    # index-context
    p_ictx = subparsers.add_parser(
        "index-context",
        help="Embed and index raw chunks into grc_context collection",
    )
    p_ictx.add_argument("chunks_jsonl", type=str, help="Path to <stem>_chunks.jsonl from Step B")
    p_ictx.add_argument("--document-id", type=str, default=None, dest="document_id",
                        help="Document identifier (default: derived from filename)")
    p_ictx.add_argument("--source-pdf", type=str, default="", dest="source_pdf",
                        help="Source PDF filename for display")
    p_ictx.add_argument("--recreate", action="store_true", help="Recreate grc_context collection")
    p_ictx.add_argument("--batch-size", type=int, dest="batch_size", help="Embedding batch size")
    p_ictx.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")
    p_ictx.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")

    # docs
    p_docs = subparsers.add_parser(
        "docs",
        help="List all indexed documents with requirement counts",
    )
    p_docs.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")
    p_docs.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")

    # reindex
    p_reindex = subparsers.add_parser(
        "reindex",
        help="Rebuild grc_requirements and grc_context from existing JSONL/chunks (no re-extraction)",
    )
    p_reindex.add_argument(
        "--requirements-only",
        action="store_true",
        dest="requirements_only",
        help="Skip the grc_context rebuild (fast path — requirements-only, same speed as before WP-24.2)",
    )
    p_reindex.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")
    p_reindex.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")
    p_reindex.add_argument("--progress-json", action="store_true", dest="progress_json", help="Print one JSON progress line per document on stdout (used by the job runner)")

    # compare
    p_compare = subparsers.add_parser(
        "compare",
        help="Compare a control ID or query across all indexed documents",
    )
    p_compare.add_argument("query", type=str,
                           help="Control ID (e.g. AC-2) or free-text query")
    p_compare.add_argument("--top-k", type=int, default=_cfg.top_k, dest="top_k",
                           help=f"Results for semantic search (default: {_cfg.top_k})")
    p_compare.add_argument("--json", action="store_true", dest="json_output",
                           help="Output as JSON")
    p_compare.add_argument("--markdown", action="store_true", dest="markdown_output",
                           help="Output as Markdown")
    p_compare.add_argument("--document-id", action="append", dest="document_ids", default=[],
                           help="Filter by document ID (repeatable)")
    p_compare.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")
    p_compare.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")

    # evidence
    p_evidence = subparsers.add_parser(
        "evidence",
        help="Export a defensible evidence pack grouped by control ID",
    )
    p_evidence.add_argument("query", type=str, help="Query to retrieve requirements for")
    p_evidence.add_argument("--format", type=str, choices=["markdown", "json"],
                            default="markdown", dest="output_format",
                            help="Output format: markdown (default) or json")
    p_evidence.add_argument("--output", type=str, default=None, dest="output_file",
                            help="Write output to FILE instead of printing")
    p_evidence.add_argument(
        "--context", action="store_true",
        help="Include surrounding raw chunk text from grc_context (retrieval-time only; does not affect indexing)",
    )
    p_evidence.add_argument("--top-k", type=int, default=20, dest="top_k",
                            help="Number of results to retrieve (default: 20)")
    p_evidence.add_argument("--document-id", action="append", dest="document_ids", default=[],
                            help="Filter by doc_key or source_pdf, e.g. afi17-101 (repeatable)")
    p_evidence.add_argument("--domain-tag", action="append", dest="domain_tags", default=[],
                            help="Filter by domain tag (repeatable)")
    p_evidence.add_argument("--requirement-type", action="append", dest="requirement_types",
                            default=[],
                            help="Filter by requirement type (repeatable)")
    p_evidence.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")
    p_evidence.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")

    # checklist
    p_checklist = subparsers.add_parser(
        "checklist",
        help="Generate an audit checklist from validated requirements for a document",
    )
    p_checklist.add_argument(
        "--doc", type=str, required=True,
        help="Document key (PDF stem, e.g. afi17-101) — same identifier shown by reqbot docs",
    )
    p_checklist.add_argument(
        "--format", type=str, choices=["csv", "json", "md", "xlsx"], default="csv",
        help="Output format: csv (default), json, md, or xlsx (requires --output)",
    )
    p_checklist.add_argument(
        "--output", type=str, default=None,
        help="Write output to FILE instead of printing to stdout",
    )
    p_checklist.add_argument(
        "--profile", type=str, default="cybersecurity",
        help="Domain profile name (default: cybersecurity)",
    )

    # kinds
    p_kinds = subparsers.add_parser(
        "kinds",
        help="Label each checklist row with the kind of statement it is (rule-based, no model; written to a sidecar file, nothing else reads it yet)",
    )
    p_kinds.add_argument("--doc", type=str, required=True, help="Document key (PDF stem), as shown by reqbot docs")
    p_kinds.add_argument("--profile", type=str, default="cybersecurity", help="Domain profile name (default: cybersecurity)")

    # questions
    p_questions = subparsers.add_parser(
        "questions",
        help="Write draft audit questions for a document's checklist rows (uses the local Ollama model; shown by 'reqbot checklist')",
    )
    p_questions.add_argument("--doc", type=str, required=True, help="Document key (PDF stem), as shown by reqbot docs")
    p_questions.add_argument("--profile", type=str, default="cybersecurity", help="Domain profile name (default: cybersecurity)")
    p_questions.add_argument("--model", type=str, default="qwen2.5:14b", help="Ollama model that writes the questions (default: qwen2.5:14b)")
    p_questions.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")
    p_questions.add_argument("--progress-json", action="store_true", dest="progress_json", help="Print one JSON progress line per row on stdout (used by the job runner)")

    # trace
    p_trace = subparsers.add_parser("trace", help="Trace full provenance of a requirement by ID")
    p_trace.add_argument("requirement_id", type=str, help="Requirement ID (e.g. REQ-a3f2c1d4e5b6)")
    p_trace.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    p_trace.add_argument(
        "--context", action="store_true",
        help="Include surrounding raw chunk text from grc_context (retrieval-time only; does not affect indexing)",
    )
    p_trace.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")

    # setup (deprecated alias for init)
    p_setup = subparsers.add_parser(
        "setup",
        help="Deprecated alias for 'init' — use 'reqbot init' instead",
    )
    p_setup.add_argument(
        "--advanced",
        action="store_true",
        help="No-op, kept for backward compatibility ('setup' and 'init' are now the same flow)",
    )

    # init
    p_init = subparsers.add_parser(
        "init",
        help="Guided first-run setup — configure Qdrant/Ollama URLs and synthesis "
             "preferences (does not install or manage either service)",
    )
    p_init.add_argument("--check", action="store_true", help="Only test the saved configuration (services reachable, models installed, folder writable); change nothing")

    # status
    p_status = subparsers.add_parser("status", help="Show system status")
    p_status.add_argument("--ollama-url", type=str, default=_cfg.ollama_url, dest="ollama_url")
    p_status.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start the ReqBot API server (also runs queued jobs in the background)")
    p_serve.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="Bind host (default: 127.0.0.1; use 0.0.0.0 to expose on all interfaces)",
    )
    p_serve.add_argument(
        "--port", type=_positive_int, default=8000,
        help="Port to listen on (default: 8000)",
    )
    p_serve.add_argument(
        "--no-runner", action="store_true", dest="no_runner",
        help="Do not run queued jobs in this process (a separate 'reqbot jobs worker' does)",
    )

    # remove
    p_remove = subparsers.add_parser("remove", help="Remove a document from the library (run folders to the trash, rows out of search); needs --yes")
    p_remove.add_argument("--doc", type=str, required=True, help="Document key, as shown by reqbot docs")
    p_remove.add_argument("--yes", action="store_true", help="Do it (without this, only says what would happen)")
    p_remove.add_argument("--qdrant-url", type=str, default=_cfg.qdrant_url, dest="qdrant_url")

    # token
    p_token = subparsers.add_parser("token", help="Create, show or replace the admin access code (lets a request start jobs)")
    p_token.add_argument("--rotate", action="store_true", help="Replace the saved code with a new one")
    p_token.add_argument("--open", action="store_true", help="Trusted network: stop asking for a code (anyone who can reach the server can add documents)")
    p_token.add_argument("--require", action="store_true", help="Ask for the code again (undo --open)")

    # jobs
    p_jobs = subparsers.add_parser("jobs", help="Long-running jobs: list, show, cancel, retry, add, or run the queue (worker)")
    jobs_sub = p_jobs.add_subparsers(dest="jobs_command", required=True)
    p_jobs_list = jobs_sub.add_parser("list", help="List jobs, newest first")
    p_jobs_list.add_argument("--limit", type=_positive_int, default=20)
    p_jobs_list.add_argument("--json", action="store_true", dest="json_output")
    p_jobs_show = jobs_sub.add_parser("show", help="Show one job and the end of its log")
    p_jobs_show.add_argument("job_id")
    p_jobs_show.add_argument("--json", action="store_true", dest="json_output")
    jobs_sub.add_parser("cancel", help="Cancel a queued job, or ask a running one to stop").add_argument("job_id")
    jobs_sub.add_parser("retry", help="Queue a failed, cancelled or interrupted job again (same run folder)").add_argument("job_id")
    p_jobs_add = jobs_sub.add_parser("add", help="Queue a job")
    add_sub = p_jobs_add.add_subparsers(dest="add_kind", required=True)
    p_add_ingest = add_sub.add_parser("ingest", help="Queue the full pipeline for one PDF")
    p_add_ingest.add_argument("pdf", type=str)
    p_add_ingest.add_argument("--no-index", action="store_true", dest="no_index")
    p_add_ingest.add_argument("--max-chunks", type=int, default=None, dest="max_chunks", help="Limit chunks (testing)")
    p_add_ingest.add_argument("--questions", action="store_true", dest="then_questions", help="Also queue the draft audit questions for the document when the ingest has succeeded")
    p_add_questions = add_sub.add_parser("questions", help="Queue draft audit questions for one document")
    p_add_questions.add_argument("--doc", required=True, help="Document key, as shown by reqbot docs")
    p_add_questions.add_argument("--profile", default="cybersecurity", help="Domain profile the checklist is built with (default: cybersecurity)")
    p_add_reindex = add_sub.add_parser("reindex", help="Queue a rebuild of the search library from the saved documents")
    p_add_reindex.add_argument("--requirements-only", action="store_true", dest="requirements_only")
    jobs_sub.add_parser("worker", help="Run the queue in the foreground (what 'reqbot serve' does in a background thread)")

    # mcp
    p_mcp = subparsers.add_parser(
        "mcp",
        help="Start the ReqBot MCP server for external LLM/agent clients: stdio by default, or --http to serve other machines",
    )
    p_mcp.add_argument("--http", action="store_true", help="Serve the read-only tools over HTTP to AI tools on other machines (needs an access code: reqbot mcp-code add NAME)")
    p_mcp.add_argument("--host", default="127.0.0.1", help="With --http: address to listen on (default: this machine only)")
    p_mcp.add_argument("--port", type=int, default=8765, help="With --http: port (default: 8765)")
    p_mcp.add_argument("--allow-host", action="append", dest="allow_hosts", default=None, help="With --http: a host name callers use to reach the door (repeatable); other Host headers are refused")

    # mcp-code
    p_mcp_code = subparsers.add_parser("mcp-code", help="Create, list or revoke the access codes of the network MCP door (one code per connected tool)")
    mcp_code_sub = p_mcp_code.add_subparsers(dest="mcp_code_command", required=True)
    p_mcp_code_add = mcp_code_sub.add_parser("add", help="Create a code for a connected tool and show it once")
    p_mcp_code_add.add_argument("name", help="A short name for the tool or person, e.g. claude-desktop-anna")
    mcp_code_sub.add_parser("list", help="List the codes by name (never the codes themselves)")
    p_mcp_code_revoke = mcp_code_sub.add_parser("revoke", help="Cut one connected tool off")
    p_mcp_code_revoke.add_argument("name")

    args = parser.parse_args()

    if not args.command:
        from cli import console as _console
        _console.launch()
        sys.exit(0)

    commands = {
        "ingest": cmd_ingest,
        "index": cmd_index,
        "index-context": cmd_index_context,
        "ask": cmd_ask,
        "batch": cmd_batch,
        "checklist": cmd_checklist,
        "kinds": cmd_kinds,
        "questions": cmd_questions,
        "docs": cmd_docs,
        "reindex": cmd_reindex,
        "status": cmd_status,
        "setup": cmd_setup,
        "init": cmd_init,
        "trace": cmd_trace,
        "compare": cmd_compare,
        "evidence": cmd_evidence,
        "serve": cmd_serve,
        "remove": cmd_remove,
        "token": cmd_token,
        "jobs": cmd_jobs,
        "mcp": cmd_mcp,
        "mcp-code": cmd_mcp_code,
    }

    rc = commands[args.command](args)
    sys.exit(rc)


if __name__ == "__main__":
    main()

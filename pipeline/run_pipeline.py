#!/usr/bin/env python3
"""Orchestrator: run the full GRC requirements extraction pipeline.

The steps are named by job; the older letters are kept beside them (docs/PIPELINE_REDESIGN_PLAN.md):
PDF reading (A), chunking (B), requirement finding (C), normalizing and checking (D),
totals and final file (E). Search indexing (F) is run by the caller.

Requirement finding is clause labeling (pipeline/clause_labeling.py): the chunk text is cut into clauses by rule and
the model gives each clause one label; every clause not labeled NOT_REQUIREMENT becomes a row, in the document's own
words. It replaced the step that asked the model to write a list of requirements (deleted, no switch back).

Usage:
    python run_pipeline.py <pdf_path> [options]

This script calls each step in sequence, passing artifacts between them.
All intermediate artifacts are stored in a timestamped output directory.
Individual steps can also be run standalone for debugging or reruns.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure repo root is on sys.path when run as a standalone script from pipeline/.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent

from core.config import RECOMMENDED_EXTRACTION_MODEL  # noqa: E402  (the clause labeler's model when none is given)

# Step names by job. The letters still work everywhere (options, older docs); a name is an alias for its letter.
STEP_NAMES = {
    "pdf-reading": "A",
    "chunking": "B",
    "requirement-finding": "C",
    "normalizing": "D",   # normalizing and checking
    "totals": "E",        # totals and final file
}
STEP_CHOICES = sorted(STEP_NAMES) + list("ABCDE")



def resolve_step(value: str) -> str:
    """The step letter for a letter or a step name; ValueError for anything else."""
    v = (value or "").strip()
    if v.upper() in tuple("ABCDE"):
        return v.upper()
    if v.lower() in STEP_NAMES:
        return STEP_NAMES[v.lower()]
    raise ValueError(f"unknown step {value!r}; use one of {', '.join(STEP_CHOICES)}")


def _docling_available() -> bool:
    """Cheap check that docling is importable.

    Uses find_spec instead of a real import -- docling pulls in torch, and actually
    importing it just to check availability would cost real time on every ingest.
    Docling is a base-install dependency (WP-34.1) -- this exists to turn a missing/
    broken install into a clear, actionable error instead of a raw ImportError
    surfacing deep inside section_parser.py.
    """
    import importlib.util
    return importlib.util.find_spec("docling") is not None


def _detect_layout_mode_from_chunks(chunks_path: Path) -> str:
    """Determine which backend actually produced an existing chunks.jsonl file,
    by inspecting its content rather than assuming the current invocation's
    backend (WP-33.2 fix, Codex review PR #155).

    Needed when resuming past Step B (--skip-to C/D/E): since WP-34.1, fresh
    Step A/B runs are always docling, but a resumed chunks.jsonl may predate
    that migration (e.g. a legacy pymupdf/pdfplumber run from before it
    shipped). Recording the wrong value would make layout_mode_used/
    skip_sections_applied describe a backend that never touched these chunks.

    Same signature docs_service.py uses: section_ref_path key presence is
    docling's own signature (legacy chunking never writes that key at all,
    confirmed during Phase 32); a TABLE_START sentinel is pdfplumber's.
    """
    import json

    if not chunks_path.exists():
        return ""
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            if "<<<TABLE_START>>>" in line:
                return "pdfplumber"
            try:
                data = json.loads(line)
                if isinstance(data, dict) and "section_ref_path" in data:
                    return "docling"
            except json.JSONDecodeError:
                pass
    return "pymupdf"


def _valid_style_record(rec) -> dict | None:
    return rec if isinstance(rec, dict) and rec.get("name") else None


def _saved_style_record(out_dir: Path, stem: str) -> dict | None:
    """The document style the chunks in this folder were made under, or None.

    Chunking saves the record in the PDF-reading artifact (`<doc>_ancestry.json`, rewritten with the chunks, so it always describes them). Only a folder without that record (made before the
    style was saved there) falls back to the stats of an earlier finished run."""
    out_dir = Path(out_dir)
    try:
        data = json.loads((out_dir / f"{stem}_ancestry.json").read_text(encoding="utf-8"))
        if isinstance(data, dict) and "doc_style" in data:
            return _valid_style_record(data["doc_style"])
    except (OSError, ValueError):
        pass
    try:
        return _valid_style_record(json.loads((out_dir / f"{stem}_stats.json").read_text(encoding="utf-8"))["pipeline"]["doc_style"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _persist_style_record(ancestry_path, record: dict) -> bool:
    """Save the chosen style in the PDF-reading artifact as soon as chunking is done, so a run that fails later (requirement finding takes hours) and is resumed still knows it.
    False, with a warning, if the file cannot be updated: that never stops a run."""
    try:
        path = Path(ancestry_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["doc_style"] = record
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except (OSError, ValueError, TypeError) as e:
        log.warning("Could not save the document style beside the chunks (%s); a resumed run will record it from its stats", e)
        return False


def _style_record_for_run(doc_style: dict, requested: str, detection, saved: dict | None, chunked_now: bool) -> dict:
    """What the run's stats record about its document style.

    When chunking ran in this invocation, the style used. When the run resumed past chunking, the style only matters for what chunking did, so keep what the earlier run recorded; an
    explicit --style that names a different style than the one the folder was chunked under is refused (start again from PDF reading to change it). With nothing saved and `auto`,
    say plainly that no style could be chosen because the PDF was not read."""
    from core import style_detection
    from core.doc_styles import style_record
    if chunked_now:
        return style_record(doc_style, requested=requested, detection=detection)
    if saved and (requested == style_detection.AUTO or saved.get("name") == requested):
        return saved
    if saved:
        raise RuntimeError(
            f"This run was chunked under the document style '{saved.get('name')}', so --style {requested} cannot be applied by resuming; "
            "start again from PDF reading (without --skip-to) to change the style.")
    if requested == style_detection.AUTO:
        return style_record(doc_style, requested=requested, detection=style_detection.Detection(
            "general", None, "none", "the PDF was not read in this run, so no style could be chosen"))
    return style_record(doc_style, requested=requested)


def run(
    pdf_path: str,
    output_dir: str,
    *,
    extraction_model: str = RECOMMENDED_EXTRACTION_MODEL,
    ollama_url: str = "http://localhost:11434",
    max_chunks: int | None = None,
    timeout: int = 120,
    skip_to: str = "A",
    profile_name: str = "cybersecurity",
    doc_style_name: str = "auto",
) -> str:
    """Run the full extraction pipeline in-process (PDF reading to totals).

    Callable interface for in-process use by reqbot.py.
    Standalone CLI usage is unchanged via main() / __main__.

    Args:
        pdf_path:          Path to the input PDF file.
        output_dir:        Directory to write all artifacts into.
        extraction_model:  Ollama model that labels the clauses in requirement finding (the clause labeler).
        ollama_url:        Ollama API base URL.
        max_chunks:        Label only the first N chunks (testing).
        timeout:           Per-request LLM timeout in seconds.
        skip_to:           Skip to a step: a letter ('A'-'E') or a name (pdf-reading, chunking, requirement-finding,
                           normalizing, totals). Requires prior artifacts.
        profile_name:      Domain profile name to load from profiles/<name>.json.
                           Default 'cybersecurity'. Loaded once and used by chunking (skip
                           sections) and normalizing.
        doc_style_name:    Document style name from doc_styles/<name>.json (how this kind of
                           document is laid out and numbered), or 'auto' (the default): the style
                           is chosen from the first page and the file name once the PDF has been
                           read (core/style_detection.py), and falls back to 'general' when the
                           type is not recognized. A name given here always wins over detection.
                           A bad name fails before any work starts. What was asked for, what was
                           chosen and why are recorded in the run's stats.

    Returns:
        Path to requirements_normalized.jsonl (str).

    Raises:
        RuntimeError: If any pipeline step fails, including docling itself being
            unavailable or failing on this document -- there is no fallback
            (WP-34.1: legacy pymupdf/pdfplumber chunking was removed; docling is
            the only ingestion path).
    """
    from core.profiles import load_profile as _load_profile
    try:
        profile = _load_profile(profile_name)
    except (FileNotFoundError, ValueError) as e:
        raise RuntimeError(f"Failed to load profile '{profile_name}': {e}") from e

    from core import style_detection as _style_detection
    from core.doc_styles import load_style as _load_style
    auto_style = doc_style_name == _style_detection.AUTO
    detection = None
    try:
        doc_style = _load_style("general" if auto_style else doc_style_name)
    except (FileNotFoundError, ValueError) as e:
        raise RuntimeError(f"Failed to load document style '{doc_style_name}': {e}") from e

    if not _docling_available():
        raise RuntimeError(
            "docling is required but not installed or not importable. "
            "Run: pip install ."
        )

    from pipeline import chunk_text as chunk_text_mod
    from pipeline import clause_labeling
    from pipeline import progress
    from pipeline import parse_and_normalize
    from pipeline import aggregate_and_export

    pdf = Path(pdf_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("Output directory: %s", out_dir)

    stem = pdf.stem
    steps_to_run = "ABCDE"
    skip_to = resolve_step(skip_to)
    if skip_to != "A":
        skip_idx = steps_to_run.index(skip_to)
        steps_to_run = steps_to_run[skip_idx:]
        log.info("Skipping to Step %s", skip_to)

    chunks_path = out_dir / f"{stem}_chunks.jsonl"
    reqs_path = out_dir / f"{stem}_extracted_requirements.jsonl"
    norm_path = out_dir / f"{stem}_requirements_normalized.jsonl"

    pipeline_start = time.time()
    saved_style = _saved_style_record(out_dir, pdf.stem)   # a resumed run has already been chunked under some style; the style only matters while chunking

    # Steps A and B: PDF → chunks, via Docling.
    #   Step A = section_parser.run() → DoclingDocument + *_ancestry.json
    #   Step B = chunk_text.run_structure_aware() → enriched *_chunks.jsonl
    #   The ancestry_result is passed in-process so HybridChunker reuses the
    #   already-parsed DoclingDocument without a second PDF conversion.
    # Failure here is a hard error -- no legacy fallback (WP-34.1).

    ancestry_result = None  # populated by Step A; used in Step B
    item_references = None  # {item self_ref: paragraph reference}, only under a document style with a reference grammar
    docling_step = None
    try:
        if "A" in steps_to_run:
            docling_step = "A"
            log.info("=" * 60)
            log.info("Starting PDF reading (Step A: PDF → Docling ancestry map)")
            log.info("=" * 60)
            progress.emit("reading")
            from pipeline import section_parser as _section_parser
            ancestry_result = _section_parser.run(str(pdf), str(out_dir))

        if "B" in steps_to_run:
            docling_step = "B"
            log.info("=" * 60)
            log.info("Starting chunking (Step B: Docling HybridChunker + breadcrumb injection)")
            log.info("=" * 60)
            progress.emit("chunking")
            # If --skip-to B, Step A was skipped so we need the ancestry
            if ancestry_result is None:
                log.info("Step A was skipped — running section_parser to obtain DoclingDocument")
                from pipeline import section_parser as _section_parser
                ancestry_result = _section_parser.run(str(pdf), str(out_dir))
            if auto_style:
                # no style was named: choose one from the first page and the file name (core/style_detection.py); a style the user names is never overridden
                try:
                    first_page_items = [item for item, _level in ancestry_result.doc.iterate_items()]
                except Exception as e:   # choosing a style must never stop an ingest: fall back to the file name alone
                    log.warning("Could not read the first page to choose a document style (%s); using the file name only", e)
                    first_page_items = []
                doc_style, detection = _style_detection.resolve(doc_style_name, first_page_items, pdf.name)
                log.info("Document style (auto): %s (%s; confidence %s)", doc_style["name"], detection.reason, detection.confidence)
            if doc_style.get("reference_grammar"):
                # label the reader's items now, while they still carry the document's own numbering; chunking records where each sits in the chunk text
                from pipeline import reference_labels as _reference_labels
                item_references = _reference_labels.label_document(ancestry_result.doc, doc_style)
            chunk_text_mod.run_structure_aware(
                str(chunks_path),
                ancestry_result=ancestry_result,
                skip_sections=profile.get("skip_sections", []),
                item_references=item_references,
            )
    except Exception as e:
        raise RuntimeError(f"Step {docling_step} (Docling) failed: {e}") from e

    style_record_for_stats = _style_record_for_run(doc_style, doc_style_name, detection, saved_style, chunked_now="B" in steps_to_run)
    if "B" in steps_to_run and ancestry_result is not None and getattr(ancestry_result, "ancestry_path", ""):
        _persist_style_record(ancestry_result.ancestry_path, style_record_for_stats)

    if "C" in steps_to_run:
        log.info("=" * 60)
        log.info("Starting requirement finding (Step C: clause labeling)")
        log.info("Requirement finding — labeling model: %s", extraction_model)
        log.info("=" * 60)
        progress.emit("finding")
        try:
            clause_labeling.run(
                str(chunks_path), str(out_dir),
                model=extraction_model, ollama_url=ollama_url,
                timeout=timeout, max_chunks=max_chunks,
            )
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Requirement finding (Step C) failed: {e}") from e

    if "D" in steps_to_run:
        log.info("=" * 60)
        log.info("Starting normalizing and checking (Step D)")
        log.info("=" * 60)
        progress.emit("checking")
        try:
            parse_and_normalize.run(
                str(reqs_path), str(chunks_path), str(pdf), str(out_dir),
                extraction_model=extraction_model, profile=profile,
            )
        except Exception as e:
            raise RuntimeError(f"Normalizing and checking (Step D) failed: {e}") from e

    index_path = norm_path

    if "E" in steps_to_run:
        log.info("=" * 60)
        log.info("Starting totals and final file (Step E)")
        log.info("=" * 60)
        progress.emit("totals")
        # Fresh Step A/B in this invocation is always docling (WP-34.1: the only
        # path left). Resuming past it (--skip-to C/D/E) means chunks_path is a
        # pre-existing artifact that may predate this migration -- detect the
        # real value from the file itself in that case, so an old legacy-chunked
        # resume doesn't get mislabeled "docling" (Codex review, PR #155).
        layout_mode_for_stats = (
            "docling" if "B" in steps_to_run
            else _detect_layout_mode_from_chunks(chunks_path)
        )
        try:
            aggregate_and_export.run(
                str(index_path), str(out_dir), source_pdf=pdf.name,
                layout_mode_used=layout_mode_for_stats,
                skip_sections_configured=profile.get("skip_sections", []),
                doc_style=style_record_for_stats,
            )
        except Exception as e:
            raise RuntimeError(f"Totals and final file (Step E) failed: {e}") from e

    total_elapsed = time.time() - pipeline_start
    log.info("=" * 60)
    log.info("Pipeline complete in %.1fs", total_elapsed)
    log.info("Artifacts in: %s", out_dir)
    log.info("=" * 60)

    return str(index_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full GRC requirements extraction pipeline"
    )
    parser.add_argument("pdf_path", type=str, help="Path to the input PDF file")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for all artifacts. Default: documents/processed/<pdf_stem>_<timestamp>/",
    )
    parser.add_argument(
        "--extraction-model",
        type=str,
        default=RECOMMENDED_EXTRACTION_MODEL,
        dest="extraction_model",
        help=f"Ollama model that labels the clauses in requirement finding (default: {RECOMMENDED_EXTRACTION_MODEL})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Convenience alias for --extraction-model",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="Ollama API base URL",
    )
    parser.add_argument(
        "--qdrant-url",
        type=str,
        default="http://localhost:6333",
        help="Qdrant API base URL (used with --index; default: http://localhost:6333)",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Label only the first N chunks (for testing)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-request LLM timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--skip-to",
        type=resolve_step,
        choices=list("ABCDE"),
        metavar="STEP",
        default="A",
        help="Skip to a specific step, by letter (A-E) or name: pdf-reading, chunking, requirement-finding, "
             "normalizing, totals (requires prior artifacts in output-dir)",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="After pipeline completes, embed and index requirements into Qdrant",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).resolve()
    if not pdf_path.exists():
        log.error("PDF file not found: %s", pdf_path)
        sys.exit(1)

    if args.output_dir:
        out_dir = Path(args.output_dir).resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = SCRIPTS_DIR.parent / "documents" / "processed" / f"{pdf_path.stem}_{timestamp}"

    # --model is a convenience alias; individual flags take precedence when --model not given
    if args.model:
        extraction_model = args.model
    else:
        extraction_model = args.extraction_model

    try:
        index_path = run(
            str(pdf_path),
            str(out_dir),
            extraction_model=extraction_model,
            ollama_url=args.ollama_url,
            max_chunks=args.max_chunks,
            timeout=args.timeout,
            skip_to=args.skip_to,
        )
    except RuntimeError as e:
        log.error("%s", e)
        sys.exit(1)

    # Step F: Embed and index into Qdrant (optional)
    if args.index:
        import json as _json
        from pipeline import embed_and_index as _embed
        from pipeline import embed_context_index as _embed_ctx

        try:
            _embed.run(index_path, ollama_url=args.ollama_url, qdrant_url=args.qdrant_url, payload_extras=_embed.derived_payload_fields(index_path))
        except Exception as e:
            log.warning("Qdrant indexing failed (%s) — pipeline artifacts are still available", e)

        # Also index raw chunks into grc_context.
        # Use the PDF-hash document_id from the indexed JSONL so that
        # ask --context can resolve chunks by the same ID as requirements payloads.
        out_dir_path = Path(index_path).parent
        chunk_files = list(out_dir_path.glob("*_chunks.jsonl"))
        if chunk_files:
            norm_doc_id: str | None = None
            try:
                with open(index_path) as _nf:
                    first_line = _nf.readline()
                if first_line:
                    norm_doc_id = _json.loads(first_line).get("document_id")
            except Exception as e:
                log.warning("Could not read document_id from %s: %s — context chunks will use filename-derived ID", index_path, e)

            try:
                _embed_ctx.run(
                    str(chunk_files[0]),
                    document_id=norm_doc_id,
                    ollama_url=args.ollama_url,
                    qdrant_url=args.qdrant_url,
                )
            except Exception as e:
                log.warning("Context indexing failed (%s) — requirements index is still available", e)
        else:
            log.warning("No chunks.jsonl found in %s — skipping context index", out_dir_path)


if __name__ == "__main__":
    main()

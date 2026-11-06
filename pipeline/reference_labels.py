#!/usr/bin/env python3
"""Paragraph references for a document, recorded at chunking time under a document style.

Under a style with a reference grammar (doc_styles/outline-dod.json) every item the PDF reader
produced is labeled, in reading order, with the paragraph reference it sits under ("Encl A, 5.k",
"2.10.b(3)"). This happens at PDF-reading time because the reader's items still carry the
document's own numbering (list markers, heading numbers, enclosure headings); the chunk text the
later steps see has dropped most of it.

The label travels with the data it describes:

  1. chunking (Step B) records, on each chunk, where each labeled item sits in the chunk's
     `raw_text`: `reference_spans` = [[start, end, reference], ...];
  2. normalizing (Step D) gives each requirement record a `reference` field, read from the span
     that holds the clause's own offset (`anchor_start`);
  3. the checklist and the search index read `reference` from the record. Nothing else is read.

No text is searched and no page is guessed: the clause offsets point into the same raw text the
spans point into, so the answer is exact (blank where the clause sits in no labeled item, such as a
table).

Standalone use, to add references to a document that is already ingested without a model run:

    python3 pipeline/reference_labels.py --pdf raw_pdfs/"DODI 8410.03.pdf" \
        --run-dir ~/documents/processed/"DODI 8410.03_20261024_033314" --style outline-dod

That re-reads the PDF, adds the spans to every stored chunk whose text is exactly what the PDF gives today (any other chunk is left as it is),
re-runs normalizing on the stored extraction, checks that every record is unchanged except for the
new `reference` field, and only then replaces the files (the old ones are kept as *.before-references).
"""

import argparse
import bisect
import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.doc_styles import load_style  # noqa: E402
from core.reference_grammar import Item, label_items, label_table_lines, parse_grammar  # noqa: E402

log = logging.getLogger(__name__)

_KINDS = {"section_header": "heading", "heading": "heading", "title": "heading",
          "list_item": "list_item", "text": "text", "paragraph": "text"}
_HEADING_LABELS = frozenset({"section_header", "title"})
BACKUP_SUFFIX = ".before-references"
_PLACE_FIELDS = ("page_start", "page_end", "section_ref_path", "section_title_path")   # what must agree, beside the text, before spans are copied to a stored chunk


def item_kind(docling_label) -> str:
    """The grammar's item kind for a Docling label such as "DocItemLabel.LIST_ITEM"; "other" is ignored."""
    return _KINDS.get(str(docling_label).split(".")[-1].lower(), "other")


def label_document(doc, style: dict) -> dict[str, "str | list"]:
    """{item self_ref: reference} for every item of a Docling document that sits under a numbered paragraph. A table of controls (a grammar with `table_id_pattern`) maps to a list
    with one reference (or None) per line of its markdown grid, the control id carried from table to table in reading order.

    Raises ValueError when the style has no reference grammar."""
    if not style.get("reference_grammar"):
        raise ValueError(f"Document style '{style.get('name')}' has no reference grammar")
    grammar = parse_grammar(style["reference_grammar"])
    refs_of, items = [], []
    for item, _level in doc.iterate_items():
        prov = getattr(item, "prov", None) or []
        items.append(Item(item_kind(getattr(item, "label", "")), getattr(item, "text", "") or "",
                          getattr(item, "marker", None) or "", prov[0].page_no if prov else None))
        refs_of.append((getattr(item, "self_ref", None), item))
    out: dict = {}
    carry = None
    for (self_ref, original), item, ref in zip(refs_of, items, label_items(items, grammar)):
        if item.kind == "other":   # tables, pictures and captions are not paragraphs: no reference of their own ...
            if grammar.table_id_pattern and self_ref and hasattr(original, "export_to_markdown"):   # ... except the rows of a table of controls
                lines, carry = label_table_lines(_table_text(original, doc), grammar, carry)
                if any(lines):
                    out[self_ref] = lines
            continue
        text = ref.text()
        if self_ref and text:
            out[self_ref] = text
    return out


def _table_text(item, doc) -> str:
    """A table's text as chunking wrote it into raw_text (its markdown grid), or ""."""
    for args in ((doc,), ()):
        try:
            return (item.export_to_markdown(*args) or "").strip()
        except Exception:
            continue
    return ""


def _item_text(item, doc) -> str:
    """The text of an item as it appears in a chunk's raw_text: its own text, or a table's markdown grid. "" when it has none."""
    text = getattr(item, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    if hasattr(item, "export_to_markdown"):   # a table: its grid, even if the item also carries an empty `text` attribute (Gemini, PR 394)
        return _table_text(item, doc)
    if isinstance(text, str):
        return ""
    try:  # a generic reference (a merged chunk's item): resolve it to the real item
        from docling_core.types.doc.document import RefItem
        real = RefItem(cref=item.self_ref).resolve(doc)
        text = getattr(real, "text", None)
        if isinstance(text, str):
            return text.strip()
        return _table_text(real, doc) if hasattr(real, "export_to_markdown") else ""
    except Exception:
        return ""


def spans_for_chunk(chunk, doc, raw_text: str, item_references: dict) -> list[list]:
    """[[start, end, reference], ...] for the labeled items of a chunk, as offsets into the chunk's `raw_text`.

    Each item's text is found in the raw text in reading order (so a sentence repeated in one chunk is matched to the right item; a table's grid is stepped over, so a paragraph that repeats
    a table cell's words is not matched inside the table). A span starts at the beginning of the item's line, so a
    clause that opens with the list marker ("- b.  Develop ...") falls inside it. Items that are headings (left out of raw_text), have no text, or are not found are skipped."""
    spans: list[list] = []
    cursor = 0
    for item in chunk.meta.doc_items:
        if str(getattr(item, "label", "")).split(".")[-1].lower() in _HEADING_LABELS:
            continue
        text = _item_text(item, doc)
        if not text:
            continue
        pos = raw_text.find(text, cursor)
        if pos < 0:
            continue
        end = pos + len(text)
        cursor = end
        ref = item_references.get(getattr(item, "self_ref", None))
        if not ref:
            continue
        if isinstance(ref, list):   # a table of controls: one span per row line, offset into the grid as it was written into raw_text
            offset = pos
            for line, line_ref in zip(text.split("\n"), ref):
                if line_ref:
                    spans.append([offset, offset + len(line), line_ref])
                offset += len(line) + 1
            continue
        start = max(raw_text.rfind("\n", 0, pos) + 1, spans[-1][1] if spans else 0)
        spans.append([start, end, ref])
    return spans


def reference_at(spans, offset) -> str:
    """The reference of the span that holds `offset`, or "". Malformed spans or offsets give ""."""
    if not isinstance(offset, int) or isinstance(offset, bool) or not isinstance(spans, list):
        return ""
    try:
        starts = [s[0] for s in spans]
        i = bisect.bisect_right(starts, offset) - 1
        if i >= 0 and spans[i][0] <= offset < spans[i][1] and isinstance(spans[i][2], str):
            return spans[i][2]
    except (TypeError, IndexError, KeyError):
        pass
    return ""


# --- adding references to a document that is already ingested -------------------------------------

def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


def merge_spans(old_chunks: list[dict], new_chunks: list[dict]) -> tuple[list[dict], dict]:
    """The stored chunks with `reference_spans` added from the freshly made chunks, wherever the text matches EXACTLY. Returns (chunks, report).

    The stored chunks and the fresh ones are lined up by their text (not their ids, which move when a section is skipped); a stored chunk whose text has no identical fresh chunk (the
    PDF is read slightly differently today, or the stored run kept a section that is skipped now) is left exactly as it is, and its rows keep the citation they have. Spans are only
    ever attached to identical text, so their offsets are exact. Identical text alone is not trusted: the same sentence can sit in two places (two enclosures), so a pair must also agree on its
    pages and its section path (they are part of the alignment key), otherwise that stored chunk is left unstamped. Raises ValueError when no chunk matches at all."""
    import difflib
    def key(c):   # text AND place: the same sentence under two enclosures is two different chunks
        return (c.get("raw_text"), *(repr(c.get(f)) for f in _PLACE_FIELDS))
    matcher = difflib.SequenceMatcher(None, [key(c) for c in old_chunks], [key(c) for c in new_chunks], autojunk=False)
    merged = [dict(c) for c in old_chunks]
    matched = 0
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            matched += 1
            spans = new_chunks[block.b + k].get("reference_spans")
            if spans:
                merged[block.a + k]["reference_spans"] = spans
    if old_chunks and not matched:
        raise ValueError("no stored chunk has identical text in today's reading of the PDF; the document would need a full re-run")
    return merged, {"stored_chunks": len(old_chunks), "fresh_chunks": len(new_chunks), "matched": matched, "unmatched_stored": len(old_chunks) - matched}


def assert_only_reference_added(old_rows: list[dict], new_rows: list[dict]) -> None:
    """Raises ValueError unless the new normalized rows are the old ones, in the same order with the same IDs, differing only in `reference` and `run_timestamp`."""
    if [r.get("requirement_id") for r in old_rows] != [r.get("requirement_id") for r in new_rows]:
        raise ValueError("re-normalizing changed the set or order of requirement IDs; not replacing anything")
    for old, new in zip(old_rows, new_rows):
        keys = (set(old) | set(new)) - {"reference", "run_timestamp"}
        changed = [k for k in sorted(keys) if old.get(k) != new.get(k)]
        if changed:
            raise ValueError(f"re-normalizing changed {changed} on {old.get('requirement_id')}; not replacing anything")


def add_references(pdf_path: Path, run_dir: Path, style_name: str, doc_key: str | None = None) -> dict:
    """Add paragraph references to an already-ingested document without a model run. Returns a small report.

    Re-reads the PDF with the stored run's own settings, adds spans to the stored chunks whose text matches exactly, re-runs normalizing on the stored extraction into a scratch folder, checks that nothing but
    `reference` (and the run timestamp) changed, and only then replaces the chunk file and the normalized file, keeping the old ones as *.before-references."""
    style = load_style(style_name)
    if not style.get("reference_grammar"):
        raise ValueError(f"Document style '{style_name}' has no reference grammar")
    pdf = Path(pdf_path).resolve()
    run_dir = Path(run_dir).resolve()
    stem = doc_key or pdf.stem
    chunks_path = run_dir / f"{stem}_chunks.jsonl"
    extracted_path = run_dir / f"{stem}_extracted_requirements.jsonl"
    norm_path = run_dir / f"{stem}_requirements_normalized.jsonl"
    for p in (chunks_path, extracted_path, norm_path):
        if not p.exists():
            raise FileNotFoundError(p)
    higher = [run_dir / f"{stem}_requirements_{tier}.jsonl" for tier in ("gated", "enriched")]
    if any(p.exists() for p in higher):
        # readers pick the freshest of gated > enriched > normalized (core/artifact_resolver.py); a rewritten normalized file would become the freshest and silently drop the enrichment
        raise ValueError(f"{run_dir.name} has an enriched or gated requirements file; adding references to it needs a normal re-run of normalizing and the later steps, not this shortcut")
    old_chunks, old_rows = _load(chunks_path), _load(norm_path)

    from core.profiles import load_profile
    from pipeline import chunk_text, parse_and_normalize, section_parser
    profile = load_profile((old_rows[0].get("domain_profile") if old_rows else None) or "cybersecurity")

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        ancestry = section_parser.run(str(pdf), str(tmp))
        item_references = label_document(ancestry.doc, style)
        new_chunks_path = tmp / f"{stem}_chunks.jsonl"
        chunk_text.run_structure_aware(str(new_chunks_path), ancestry_result=ancestry, skip_sections=profile.get("skip_sections", []), item_references=item_references)
        merged, merge_report = merge_spans(old_chunks, _load(new_chunks_path))
        log.info("Chunk alignment: %s", merge_report)
        merged_path = tmp / f"{stem}_chunks_merged.jsonl"
        _write(merged_path, merged)
        out_dir = tmp / "normalized"
        # the same extraction model the stored rows carry, so the rows come out identical
        parse_and_normalize.run(str(extracted_path), str(merged_path), str(pdf), str(out_dir), profile=profile)
        new_rows = _load(out_dir / f"{stem}_requirements_normalized.jsonl")
        assert_only_reference_added(old_rows, new_rows)
        for path in (chunks_path, norm_path):
            shutil.copy2(path, path.with_name(path.name + BACKUP_SUFFIX))
        _write(chunks_path, merged)
        _write(norm_path, new_rows)

    stamped = sum(1 for r in new_rows if r.get("reference"))
    log.info("References added (%s): %d of %d records now carry one; %d chunks have spans", style_name, stamped, len(new_rows),
             sum(1 for c in merged if c.get("reference_spans")))
    return {"records": len(new_rows), "with_reference": stamped, "chunks_with_spans": sum(1 for c in merged if c.get("reference_spans")), **merge_report}


def main() -> int:
    parser = argparse.ArgumentParser(description="Add paragraph references to an ingested document under a document style, without a model run.")
    parser.add_argument("--pdf", required=True, help="the document's PDF")
    parser.add_argument("--run-dir", required=True, help="the document's processed run folder")
    parser.add_argument("--style", required=True, help="document style name (doc_styles/<name>.json) with a reference grammar")
    parser.add_argument("--doc-key", default=None, help="artifact name prefix (default: the PDF's file name without .pdf)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        report = add_references(Path(args.pdf), Path(args.run_dir), args.style, args.doc_key)
    except (ValueError, FileNotFoundError) as e:
        log.error("%s", e)
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

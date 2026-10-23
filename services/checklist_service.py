"""Checklist service — generates audit checklist items from validated requirement records.

Prefers gated requirement output (*_requirements_gated.jsonl, Step D.6, WP-35.4) when
available, then enriched output (*_requirements_enriched.jsonl, Step D.5), so checklist
items reflect final domain_tags, description, and requirement_type -- with description
additionally having passed the description-grounding gate when a gated file exists.
Falls back to normalized output (*_requirements_normalized.jsonl, Step D) when neither
exists.

Returns structured data; all display and export logic stays in cli/reqbot.py and
pipeline/checklist_export.py (WP-21.4).
"""
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.artifact_resolver import doc_key_from_requirements_path, resolve_requirement_file
from core.profiles import load_profile
from services import audit_questions, checklist_audit, cleanup, criticality

log = logging.getLogger(__name__)

CONFIDENCE_REVIEW_THRESHOLD = 0.8


def _resolve_doc_path(processed_dir: Path, doc_key: str) -> Path:
    """Return the best requirements JSONL path for doc_key.

    Thin delegate to core.artifact_resolver.resolve_requirement_file(), which
    also backs cli/reqbot.py's cmd_reindex (WP-24.2) — enriched-preference and
    latest-run-wins are defined in exactly one place.

    Raises ValueError if no matching file is found.
    """
    return resolve_requirement_file(processed_dir, doc_key)


def _checklist_item_id(requirement_ids: list[str]) -> str:
    """Derive a stable deterministic CHK- ID from one or more requirement IDs."""
    key = "|".join(sorted(requirement_ids))
    return "CHK-" + hashlib.sha256(key.encode()).hexdigest()[:16]


def _page_refs(req: dict) -> list[int]:
    """Derive page reference list from page_start / page_end fields."""
    try:
        start = req.get("page_start")
        if start is None:
            return []
        start = int(start)
        end = req.get("page_end")
        if end is not None:
            end = int(end)
            if end > start:
                return list(range(start, end + 1))
        return [start]
    except (ValueError, TypeError):
        return []


def _load_chunks(jsonl_path: Path) -> dict:
    """{chunk_id: chunk record} from the *_chunks.jsonl beside the requirements file (same run directory), or {} if it is absent or unreadable."""
    path = jsonl_path.parent / f"{doc_key_from_requirements_path(jsonl_path)}_chunks.jsonl"
    out: dict = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                out[rec.get("chunk_id")] = rec
    except (OSError, ValueError):
        log.warning("No readable chunk file beside %s; checklist passages will be empty", jsonl_path.name)
        return {}
    return out


def _heading_map(chunks: dict) -> dict:
    """{paragraph number: title} over the document (numbered headings and run-in titles); see checklist_audit.heading_map."""
    headings, units = [], []
    for chunk_id in sorted(k for k in chunks if isinstance(k, int)):
        chunk = chunks[chunk_id]
        headings.extend(str(p) for p in (chunk.get("section_title_path") or []))
        units.extend(checklist_audit.paragraph_units(chunk.get("raw_text") or ""))
    return checklist_audit.heading_map(headings, units)


def _paragraph_map(chunks: dict) -> dict:
    """{paragraph number: text} over the document, from chunk text and from section headings (Docling keeps numbered headings out of a chunk's raw_text)."""
    units: list[str] = []
    for chunk_id in sorted(k for k in chunks if isinstance(k, int)):
        chunk = chunks[chunk_id]
        units.extend(str(p) for p in (chunk.get("section_title_path") or []))
        units.extend(checklist_audit.paragraph_units(chunk.get("raw_text") or ""))
    return checklist_audit.paragraph_map(units)


def requirements_path(processed_dir: Path, doc_key: str) -> Path:
    """The requirements file a checklist for `doc_key` is built from (the newest run's best tier)."""
    return _resolve_doc_path(processed_dir, doc_key)


def _quotes(req: dict) -> tuple[str, str, str]:
    """(root, shown text, locating text) of a record. The root is exactly what requirement finding returned; the shown text is the explained requirement when the record has one;
    the passage is located by the sentence itself, because a lead-in attached from the line above is not contiguous with it in the document (the root is contiguous text, and older
    records have only the root)."""
    root = req.get("source_quote", "")
    sentence_parts = [p.get("text") for p in (req.get("explained_parts") or []) if p.get("kind") == "sentence" and p.get("text")]
    return root, req.get("explained_text") or root, (sentence_parts[-1] if sentence_parts else root)


def _locate_row(req: dict, chunks: dict, hmap: dict, first_numbered, verbs) -> dict:
    """Where a record sits in its document, read from the document: how it is cited, who it applies to, its hint flags and the passage around its quote. No model.

    The checklist and the search index both call this, so the label an auditor sees on a sheet and the one a search result shows cannot drift apart. `table_ref` is the table's label
    ("Table 3.1") when the row sits in a table, else ""; `found` says whether the quote was located in its passage."""
    extracted_quote, source_quote, locate_text = _quotes(req)
    source_ref = req.get("source_ref") or ""
    section_title_path = req.get("section_title_path") or []
    # a row from a table is cited by the table's own caption ("Table 3.1"); the converter's heading for a table is a guess, so no party is read from it either
    table_ref, table_heading = checklist_audit.table_label(chunks, req.get("chunk_id"), locate_text)
    origin = req.get("source_ref_origin")  # how clause labeling found source_ref; None on records from before it
    cite0 = table_ref or checklist_audit.citation(source_ref, "", section_title_path, locate_text, origin)  # the paragraph number as extracted or as the quote opens; inferred ones need the passage
    numbered = None if table_ref else checklist_audit.applies_to_numbered(cite0, hmap, section_title_path)
    applies = "" if table_ref else (numbered if numbered is not None else checklist_audit.applies_to(section_title_path))
    flags = checklist_audit.item_flags(source_quote, source_ref, applies, verbs)
    chunk_id = req.get("chunk_id")
    chunk = chunks.get(chunk_id)
    prev_chunk = chunks.get(chunk_id - 1) if isinstance(chunk_id, int) else None
    # whether to put the end of the previous chunk in front of the passage depends on the item being a list item or starting mid-sentence: judge that from the root and the sentence,
    # not from the explained text (which starts with the lead-in), and always when a lead-in was attached by rule (it may sit in the previous chunk)
    has_rule_lead_in = any(p.get("kind") == "lead_in" and p.get("origin") == "rule" for p in (req.get("explained_parts") or []))
    passage_flags = set(flags) | set(checklist_audit.item_flags(extracted_quote, source_ref, applies, verbs)) | ({"list_item"} if has_rule_lead_in else set())
    passage, found = checklist_audit.build_passage(locate_text, chunk, prev_chunk, passage_flags)
    cite = table_ref or checklist_audit.citation(source_ref, passage, section_title_path, locate_text, origin)
    if cite != cite0:  # an inferred paragraph number: the numbering can now say who the row applies to
        numbered = checklist_audit.applies_to_numbered(cite, hmap, section_title_path)
        if numbered is not None:
            applies = numbered
            flags = checklist_audit.item_flags(source_quote, source_ref, applies, verbs)
    if req.get("clause_label") == "UNSURE":
        flags = [*flags, "labeled_unsure"]  # the labeler could not decide (or its answer could not be read): the row is kept for a reader to check
    if not cite:  # nothing numbered to cite: where the row sits, read from the document ("Front matter", "Figure A3.1")
        cite = checklist_audit.unnumbered_label(chunks, chunk_id, locate_text, first_numbered)
    return {"citation": cite, "table_ref": table_ref, "table_heading": table_heading, "applies": applies, "flags": flags, "passage": passage, "found": found}


def requirement_citations(jsonl_path) -> dict[str, str]:
    """{requirement_id: citation} for every record of a requirements file: the label the checklist gives the row (a paragraph number, "Table 3.1", "Front matter", marked
    "(inferred)" when it was worked out from the text before the quote), read from the document's chunk file beside it. The search index stores it next to `source_ref`, which it
    never replaces (Evidence groups by it and the embedded text carries it). A record with no `requirement_id` or no text is left out; a file with no chunk file beside it still
    gets the paragraph numbers the records themselves carry. No model."""
    jsonl_path = Path(jsonl_path)
    chunks = _load_chunks(jsonl_path)
    hmap = _heading_map(chunks)
    first_numbered = checklist_audit.first_numbered_chunk(chunks)
    out: dict[str, str] = {}
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue
            req_id = req.get("requirement_id", "")
            if not req_id or not _quotes(req)[1]:
                continue
            # the verbs only decide the "no stated actor" hint, which does not change where a row sits or how it is cited
            out[req_id] = _locate_row(req, chunks, hmap, first_numbered, ())["citation"]
    return out


def index_payload_extras(jsonl_path) -> dict:
    """{requirement_id: {"citation": label}} for the search index: `requirement_citations`, without the blanks, in the shape the indexer merges into each payload. A label is a display
    aid, so failing to work it out never fails an indexing run: the index then has none and readers show `source_ref`."""
    try:
        return {rid: {"citation": cite} for rid, cite in requirement_citations(jsonl_path).items() if cite}
    except Exception as e:
        log.warning("Citation labels not computed for %s: %s; the index will carry source_ref only", jsonl_path, e)
        return {}


def generate(processed_dir: Path, doc_key: str, profile_name: str) -> dict:
    """Generate a checklist envelope dict from normalized requirements for doc_key.

    Raises FileNotFoundError if processed_dir does not exist.
    Raises ValueError if doc_key is not found in processed_dir.
    Raises ValueError if profile_name is not a valid profile.
    """
    if not processed_dir.exists():
        raise FileNotFoundError(f"processed_dir not found: {processed_dir}")

    profile = load_profile(profile_name)  # validate profile exists and is well-formed
    jsonl_path = _resolve_doc_path(processed_dir, doc_key)
    chunks = _load_chunks(jsonl_path)
    hmap = _heading_map(chunks)
    para_map = _paragraph_map(chunks)  # WP-46.1: the document's own text, for the passage column; {} when the chunk file is not beside the requirements
    first_numbered = checklist_audit.first_numbered_chunk(chunks)  # for rows with no number to cite (front matter)

    items = []
    document_id = ""
    source_pdf = ""
    skipped = 0

    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                log.warning("Skipping malformed JSON line in %s", jsonl_path)
                continue

            if not document_id:
                document_id = req.get("document_id", "")
                source_pdf = req.get("source_pdf", "")

            req_id = req.get("requirement_id", "")
            extracted_quote, source_quote, locate_text = _quotes(req)  # the root; what the sheet shows (the explained requirement when the record has one); what the passage is located by

            # Hard provenance anchors — missing either means no checklist item
            if not req_id or not source_quote:
                skipped += 1
                log.debug("Skipping record — missing requirement_id or source_quote")
                continue

            page_refs = _page_refs(req)
            source_ref = req.get("source_ref") or ""
            section_title_path = req.get("section_title_path") or []
            domain_tags = req.get("domain_tags") or []
            confidence = req.get("confidence")  # None while confidence is switched off (records carry none)

            source_profile = req.get("domain_profile") or "cybersecurity"

            # WP-46.1 audit layout: who the row applies to, the document's own passage, and specific hints (nothing here is model-made)
            verbs = profile.get("obligation_verbs", [])
            where = _locate_row(req, chunks, hmap, first_numbered, verbs)
            table_ref, table_heading, cite = where["table_ref"], where["table_heading"], where["citation"]
            applies, flags, passage = where["applies"], where["flags"], where["passage"]
            parent_ref, parent_text = checklist_audit.parent_paragraph(source_ref, para_map)
            if not passage:
                flags.append("no_passage")
            elif not where["found"]:
                flags.append("quote_not_located_in_passage")

            review_reasons: list[str] = []
            if not source_ref:
                review_reasons.append("missing-source-ref")
            if not section_title_path:
                review_reasons.append("missing-section-title-path")
            if not page_refs:
                review_reasons.append("missing-page-refs")
            # Domain tags are no longer assigned (docs/PIPELINE_REDESIGN_PLAN.md), so a missing tag is not a reason to review; and confidence is only judged when the record carries one.
            if confidence is not None and confidence < CONFIDENCE_REVIEW_THRESHOLD:
                review_reasons.append("low-confidence")
            if source_profile != profile_name:
                review_reasons.append("profile-mismatch")

            items.append({
                "checklist_item_id": _checklist_item_id([req_id]),
                "requirement_ids": [req_id],
                "domain_tags": domain_tags,
                "source_ref": source_ref,
                "page_refs": page_refs,
                "section_title_path": section_title_path,
                "citation": cite,
                "section_heading": table_heading if table_ref else checklist_audit.section_heading(cite, hmap),
                "applies_to": applies,
                "parent_ref": parent_ref,
                "parent_text": parent_text,
                "source_quote": source_quote,
                "extracted_quote": extracted_quote,
                "explain_notes": req.get("explain_notes") or [],
                "passage": passage,
                "item_flags": flags,
                "audit_question": "",
                "evidence_to_request": [],
                "generation_notes": "",
                "assessor_notes": "",
                "status": "not-started",
                "confidence": confidence,
                "requires_human_review": bool(review_reasons),
                "review_reasons": review_reasons,
            })

    if skipped:
        log.info("Skipped %d record(s) missing requirement_id or source_quote", skipped)

    # WP-46.6: draft audit questions written earlier by `reqbot questions` (a sidecar file; building a checklist never calls a model)
    drafted = audit_questions.apply(items, audit_questions.sidecar_path(jsonl_path))
    criticality.apply(items, criticality.sidecar_path(jsonl_path), skip_ids=criticality.withheld_ids(audit_questions.sidecar_path(jsonl_path)))  # rough "look first" flag from the sidecar `reqbot questions` writes (no model call here)
    cleanup.apply(items, cleanup.sidecar_path(jsonl_path), cleanup.chunk_texts(jsonl_path, items))  # optional "probably not a requirement" flag, added to the same priority cell (docs/CLEANUP_FLAG_PLAN.md)

    return {
        "format": "reqbot-checklist",
        "format_version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": {
            "tool": "reqbot",
            "command": f"reqbot checklist --doc {doc_key} --profile {profile_name}",
        },
        "document": {
            "document_id": document_id,
            "source_pdf": source_pdf,
        },
        "profile": profile_name,
        "summary": {
            "total_items": len(items),
            "items_requiring_review": sum(1 for i in items if i["requires_human_review"]),
            "items_with_flags": sum(1 for i in items if i["item_flags"]),
            "items_with_draft_question": drafted,
        },
        "items": items,
    }

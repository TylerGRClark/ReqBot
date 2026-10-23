#!/usr/bin/env python3
"""Normalizing and checking: turn the clause labeler's rows into the final requirement records.

Input:  <doc>_extracted_requirements.jsonl (requirement finding: pipeline/clause_labeling.py, one row per clause not labeled NOT_REQUIREMENT)
        <doc>_chunks.jsonl (chunking: page references, section paths, and the chunk text the clause offsets index)
Output:
  - <doc>_requirements_normalized.jsonl: final schema per requirement
  - <doc>_normalization_failures.jsonl: rows rejected here, with the reason

Deterministic. Rejections: an empty clause, a clause that only repeats a heading of its own section, a clause that ends with a colon (a list's lead-in on its own; it is put in front
of its items instead), and a definitional pointer ("Term, as defined in DoDI 2000.26."). Invariant: the clause's offsets give back its text (clause_offset_mismatch otherwise, which
should never happen). Then page and section metadata, de-duplication and the stable requirement ID. An extraction file from the old list-writing step (rows without clause_index)
is refused: re-run requirement finding on that folder.
"""

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from rapidfuzz import fuzz

# Ensure repo root is on sys.path when run as a standalone script from pipeline/.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.chunk_text import _normalize_heading
from pipeline.sentence_expand import tidy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

SCHEMA_VERSION = "3.0"   # clause labeling (pipeline/clause_labeling.py writes the same)
PIPELINE_VERSION = "2.0"

COMPUTE_CONFIDENCE = False  # see the comment where confidence is computed


# WP-34.2: minimum fuzz.ratio (0-100, whole-string similarity) between a
# normalized source_quote and its chunk's own heading before treating it as a
# heading echo rather than real body content. ratio (not partial_ratio, which
# scores a short string against the best-aligned piece of a long one) is the right tool here: it scores
# the two full strings against each other, so a short generic heading (e.g.
# "Purpose") merely appearing as a substring inside an unrelated, much longer
# real quote scores low and passes through -- a literal substring-containment
# check does not have this property (confirmed against a real example: "Access
# badges shall be issued for the sole purpose of controlling entry to
# restricted areas." contains the heading "purpose" verbatim, but is a
# genuine, unrelated requirement). Both confirmed real fabrication fixtures are
# exact matches after normalization (ratio 100); 90 leaves headroom for
# incidental punctuation/whitespace differences without opening the substring
# false-positive risk above.
HEADING_ECHO_THRESHOLD = 90


def _is_heading_echo(source_quote: str, section_title_path: list[str]) -> bool:
    """True if source_quote is just a heading from its own ancestry, not body content.

    Step C occasionally extracts a heading (e.g. "COMPLIANCE WITH THIS
    PUBLICATION IS MANDATORY") as if it were a requirement in its own right.
    WP-34.2 originally checked only section_title_path[-1] (the chunk's
    immediate heading). WP-38.1's audit found a code-verified case
    (REQ-955ab005b394) where a quote echoes an *ancestor* heading two levels
    up instead -- section_title_path is ordered shallowest-first (root ...
    immediate parent, see section_parser.py's _ancestry_from_stack), so an
    echoed heading isn't always the last entry. WP-38.2 checks every entry in
    the path, not just the last one.

    Reuses chunk_text.py's _normalize_heading() for both sides so this matches
    on the same normalized form skip_sections filtering already uses -- not
    separate matching logic (WP-34.2).
    """
    if not section_title_path:
        return False
    normalized_quote = _normalize_heading(source_quote)
    if not normalized_quote:
        return False
    for heading in section_title_path:
        if not heading:
            continue
        normalized_heading = _normalize_heading(heading)
        if not normalized_heading:
            continue
        if fuzz.ratio(normalized_quote, normalized_heading) >= HEADING_ECHO_THRESHOLD:
            return True
    return False


# WP-38.2: an entire quote whose only content is a term followed by a
# "as defined in <citation>" cross-reference carries no independent
# obligation -- it's a definitional pointer, not a requirement (e.g.
# "Suspicious activity reporting, as defined in DoDI 2000.26, Suspicious
# Activity Reporting."). Only anchors the START of the quote (no `$`) because
# a real citation's own reference text legitimately contains internal commas
# and periods (document numbers, titles) -- anchoring to end-of-string would
# reject real citation-only quotes just as readily as it rejects the false
# positive below, so it isn't a safe fix on its own (see
# _has_obligation_after_citation_opener()).
_DEFINED_IN_CITATION_RE = re.compile(r"^[^,]{1,80},\s*as defined in\b", re.IGNORECASE)

# WP-38.2 (Gemini review round 2, PR #181): the first fix here checked
# whether the remainder after "as defined in" contained a word from a small
# obligation-verb whitelist -- but that check was backwards-fragile: ANY real
# obligation verb missing from the list (e.g. "requires", "applies",
# "protects" -- Gemini's own example, "...as defined in Executive Order
# 13556, requires safeguarding controls.") caused the search to find nothing,
# which made the function return True (citation-only) and silently discard a
# real requirement. A verb whitelist can never be exhaustive enough to make
# that failure direction safe, so this doesn't use one anymore.
#
# Instead: a real citation's own reference text in this corpus is
# consistently made of Title-Case document titles, ALL-CAPS/mixed-case
# acronyms, and numeric document IDs (e.g. "DoDI 2000.26, Suspicious Activity
# Reporting"), joined only by commas/"and". A real continuing obligation
# clause is ordinary lowercase prose ("shall be reported...", "requires
# safeguarding controls..."). So: does the remainder consist *only* of
# citation-shaped tokens and a small closed set of connector words, with no
# other lowercase word at all? If even one ordinary lowercase word shows up,
# treat it as real prose continuing past the citation, not citation-only
# content -- this doesn't need to recognize every possible obligation verb,
# only to recognize what an ordinary English sentence fragment looks like,
# which is a much smaller, more robust thing to get right.
_CITATION_CONNECTOR_WORDS = {
    "and", "or", "the", "of", "for", "in", "a", "an", "at", "to", "within", "per",
}

# WP-38.2 (Gemini review round 4, PR #181): stripping a fixed, enumerated set
# of punctuation characters (originally just ",.()")  keeps finding new gaps
# -- quotes, brackets, smart quotes, dashes, whatever the next real example
# happens to be wrapped in. Stripping every non-alphanumeric character from
# both ends, regardless of which specific characters they are, closes that
# whole class of gap at once instead of growing the enumerated set one
# reviewer finding at a time.
_NON_ALNUM_EDGE_RE = re.compile(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$")


def _looks_like_citation_reference(word: str) -> bool:
    stripped = _NON_ALNUM_EDGE_RE.sub("", word)
    if not stripped:
        return True
    if stripped.lower() in _CITATION_CONNECTOR_WORDS:
        return True
    # Title Case, ALL CAPS, or a mix with digits/periods (acronyms, document
    # IDs like "2000.26") -- never a lowercase-first ordinary word.
    return not stripped[0].islower()


# WP-38.2 (Gemini review round 6, PR #181; corrected round 8; replaced here
# after Codex's local review of PR #181 found a real false positive in both
# of those): _looks_like_citation_reference() tells a citation token from
# real prose by checking whether a word's first letter is lowercase --
# meaningless once the text it's looking at is ALL CAPS, since every word
# "looks like" a citation token regardless of what it actually is.
#
# Round 6 bailed (didn't reject) whenever `remainder.isupper()` -- but a
# short, genuine citation-only remainder made purely of acronym/document-ID
# tokens (e.g. "Term, as defined in CNSSI 4009.") is *also* all-uppercase on
# its own, so that wrongly let real citation-only fragments through
# uncaught. Round 8 widened the check to `source_quote.isupper()` (the whole
# quote) to fix that -- but a real quote whose citation opener is normal/
# title case while only its *governing clause* is rendered in caps (e.g.
# "Compliance data, as defined in DODI 2000.26, SHALL BE REPORTED
# IMMEDIATELY TO THE ISSO.") has neither the whole quote nor even the whole
# remainder all-uppercase (the citation portion, "DODI 2000.26,", isn't) --
# so neither round 6's nor round 8's version catches it, and a real
# obligation clause gets misclassified as citation-shaped word by word,
# silently discarding a real requirement. Codex's local review confirmed
# this via direct execution, including a case mixing a title-case citation
# with an all-caps clause in the very same remainder.
#
# What actually distinguishes the two is the *shape* of the all-caps run,
# not whether the whole string happens to be uppercase: a real citation's
# acronyms appear as isolated all-caps tokens breaking up otherwise mixed-
# case document titles and numbers, while a "shouted" clause is a run of
# consecutive all-caps words ("SHALL BE REPORTED IMMEDIATELY..." runs to 5).
# Flagging a run of 2+ consecutive all-caps multi-letter alphabetic words
# (skipping over, not resetting on, recognized connector words and any token
# containing a digit -- a real clause naturally contains "TO"/"THE" mid-run,
# or a number like "WITHIN 30 DAYS", without that breaking the clause) as
# unreliable-to-classify-by-case catches all three of Codex's examples plus
# every prior round's test case.
#
# Gemini's next automatic re-review (PR #181) found two more real gaps at
# the original threshold of 3: (1) a digit-only token (e.g. "30" in "SHALL
# REPORT WITHIN 30 DAYS") failed `.isalpha()` and *reset* the run instead of
# being skipped like a connector word, breaking runs that should have stayed
# intact; (2) threshold=3 still missed a short 2-word all-caps clause with no
# digits at all ("MUST COMPLY"). Fixing (1) alone doesn't fix (2) -- a clause
# with no digit token in it never benefits from skip-instead-of-reset.
# Lowering the threshold to 2 is the same "no text-level signal safely
# distinguishes two genuinely different real shapes" wall already hit and
# resolved once this session for _is_orphaned_list_item()'s marker+
# word-count branch: a 2-consecutive-all-caps-word run can be a real citation
# (an acronym pair like "NIST SP") or a real short clause ("MUST COMPLY"),
# and nothing about the words themselves tells them apart. Applying the same
# principle Tyler set there -- a missed catch (leaving a real citation-only
# fragment unrejected) is a strictly safer failure than a false rejection
# (silently discarding a real short obligation clause) -- threshold lowered
# to 2. Confirmed the one existing test this costs
# (`"Control, as defined in NIST SP 800-53."`) is itself a synthetic
# calibration example added during round 8, not a real fixture or live-corpus
# record; no real "as defined in"-citation record in this corpus is
# ALL-CAPS at all (checked directly), so this trade currently costs nothing
# against real data on either side.
_ALL_CAPS_CLAUSE_RUN_THRESHOLD = 2


def _has_all_caps_clause_run(remainder: str) -> bool:
    run = 0
    for word in remainder.split():
        stripped = _NON_ALNUM_EDGE_RE.sub("", word)
        if not stripped:
            continue
        if stripped.lower() in _CITATION_CONNECTOR_WORDS:
            continue
        if any(c.isdigit() for c in stripped):
            continue
        if stripped.isalpha() and stripped.isupper():
            run += 1
            if run >= _ALL_CAPS_CLAUSE_RUN_THRESHOLD:
                return True
        else:
            run = 0
    return False


def _is_definitional_citation_only(source_quote: str) -> bool:
    """True if source_quote opens with "<term>, as defined in <citation>" and
    everything after that opener still looks like citation reference text --
    not a real, independent governing clause (WP-38.2, see
    _looks_like_citation_reference()'s docstring above for the reasoning)."""
    match = _DEFINED_IN_CITATION_RE.match(source_quote)
    if not match:
        return False
    remainder = source_quote[match.end():]
    if _has_all_caps_clause_run(remainder):
        return False
    return all(_looks_like_citation_reference(w) for w in remainder.split())


def _is_orphaned_list_item(source_quote: str) -> bool:
    """True if source_quote is a definitional cross-reference with no
    independent content of its own -- "<term>, as defined in <citation>."
    is a definitional pointer, not an obligation (WP-38.2).

    Does NOT reject a short enumerated-list item by marker + word-count
    alone (e.g. "(1) Encrypt CUI." vs. "(3) Restrain competition.", which
    needs its "shall not be used to:" governing clause to be understood
    correctly) -- a marker+word-count branch here was tried and calibrated
    through four review rounds (Gemini rounds 1 and 6, Codex twice), narrowed
    each time, and ultimately removed (Codex local review, PR #181, second
    pass): no text-level signal distinguishes a short child item that's
    genuinely self-contained from one whose obligation is inherited from a
    parent stem, and rejecting the wrong one silently drops a valid
    requirement -- a worse failure than leaving a visible fragment in place.
    See archive/PHASE38_REQUIREMENTS.md's WP-38.2 Findings for the full history.

    Product direction (Tyler, PR #181): short enumerated child items are not
    safe to reject by text length alone. They may be valid requirements
    whose governing clause is inherited from a parent stem. Until
    hierarchy-aware parent-stem + child-item reconstruction exists (before
    embedding/search, not as a Step D rejection rule), preserve them --
    tracked as backlog, not part of WP-38.2's scope.

    Doesn't attempt to catch a bare noun-phrase list item with no marker and
    no citation (e.g. "Required NM data update rates.") either -- no safe,
    non-overfit text-level signal for that shape was found during
    calibration. Left as an honest gap, not silently claimed as covered --
    see archive/PHASE38_REQUIREMENTS.md's WP-38.2 Findings.
    """
    stripped = source_quote.strip()
    if not stripped:
        return False

    return _is_definitional_citation_only(stripped)


def compute_document_identity(pdf_path: Path) -> dict:
    """Compute document identity from PDF file bytes.

    Returns dict with document_id (short), document_hash_full, source_pdf.
    Hashes in 64 KB chunks to avoid loading large PDFs fully into memory.
    """
    hasher = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            hasher.update(block)
    full_hash = hasher.hexdigest()
    return {
        "document_id": full_hash[:16],
        "document_hash_full": full_hash,
        "source_pdf": pdf_path.name,
    }


def normalize_for_hash(text: str) -> str:
    """Normalize text deterministically for stable ID hashing.

    Lowercase, collapse whitespace, strip leading/trailing whitespace.
    """
    return re.sub(r"\s+", " ", text.strip().lower())


def compute_stable_id(
    document_id: str,
    source_ref: str,
    source_quote: str,
    chunk_id: int | None,
    requirement_type: str,
    description: str,
) -> str:
    """Compute a stable requirement ID based on document content.

    Uses a cascade of hash inputs ordered by stability:
    1. document_id + source_ref + normalized_source_quote (most stable)
    2. document_id + normalized_source_quote (if no source_ref)
    3. document_id + chunk_id + requirement_type + normalized_description (last resort)
    """
    norm_quote = normalize_for_hash(source_quote)
    norm_desc = normalize_for_hash(description)

    if norm_quote and source_ref:
        basis = f"{document_id}:{source_ref}:{norm_quote}"
    elif norm_quote:
        basis = f"{document_id}:{norm_quote}"
    else:
        basis = f"{document_id}:{chunk_id}:{requirement_type}:{norm_desc}"

    short_hash = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]
    return f"REQ-{short_hash}"


def load_jsonl(path: Path) -> list[dict]:
    """Load records from a JSONL file."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_chunk_page_map(chunks: list[dict]) -> dict[int, tuple[int, int]]:
    """Build a mapping from chunk_id to (page_start, page_end)."""
    return {
        c["chunk_id"]: (c["page_start"], c["page_end"])
        for c in chunks
    }


def build_chunk_hierarchy_map(chunks: list[dict]) -> dict[int, dict]:
    """Build a mapping from chunk_id to its hierarchy metadata fields.

    Returns empty-field dicts for chunks without WP-14.2 hierarchy output
    (legacy pymupdf/pdfplumber chunks) so callers get safe defaults.
    """
    result: dict[int, dict] = {}
    for c in chunks:
        result[c["chunk_id"]] = {
            "section_ref_path": c.get("section_ref_path") or [],
            "section_title_path": c.get("section_title_path") or [],
            "parent_header_text": c.get("parent_header_text"),
            "parent_context": c.get("parent_context"),
        }
    return result


def build_section_children_map(chunks: list[dict]) -> dict[str, list[str]]:
    """Build a mapping from each section ref to its direct child section refs.

    Walks every consecutive pair in each chunk's section_ref_path so that
    intermediate sections with no body chunk (heading-only, dropped by WP-14.2
    HybridChunker) are still represented.  For example, a chunk with path
    ["1", "1.1", "1.1.1"] contributes both "1" → "1.1" and "1.1" → "1.1.1",
    even if no chunk carries path ["1", "1.1"] directly.

    Only chunks with WP-14.2 numbered section_ref_path contribute; legacy
    chunks with empty paths are silently skipped.
    """
    parent_to_children: dict[str, set[str]] = {}
    for chunk in chunks:
        path = chunk.get("section_ref_path") or []
        for i in range(1, len(path)):
            parent_ref = path[i - 1]
            child_ref = path[i]
            parent_to_children.setdefault(parent_ref, set()).add(child_ref)
    return {k: sorted(v) for k, v in parent_to_children.items()}


def normalize_text(text: str) -> str:
    """Normalize whitespace and casing for comparison."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _dedup_score(req: dict) -> float:
    """Score a requirement for winner selection during deduplication.

    Higher score = preferred record. Formula:
      confidence * 1000 - len(source_quote)

    Confidence (0.0–1.0) dominates: a record with higher confidence always
    wins over one with lower confidence. For equal confidence, a shorter
    source_quote is preferred — it indicates a more precise verbatim capture
    rather than a padded or over-long quote.

    Tag count is intentionally excluded: the LLM can hallucinate tags, and
    more tags does not imply a better extraction.
    """
    confidence = req.get("confidence", 0.0)
    quote_len = len(req.get("source_quote", ""))
    return confidence * 1000 - quote_len


def deduplicate_requirements(requirements: list[dict]) -> list[dict]:
    """Remove duplicate requirements that share source_ref + normalized source_quote.

    When duplicates exist, keep the higher-confidence record; for equal
    confidence, prefer the shorter (more precise) source_quote.

    There is no description-based key: the first-pass extractor returns no
    description, so such a key could never fire (and would collapse distinct
    requirements that share a source_ref if it did).
    """
    seen: dict[str, dict] = {}
    for req in requirements:
        source_ref = req.get("source_ref", "")
        quote = normalize_text(req.get("source_quote", ""))
        if not quote:
            continue  # unchanged behavior: a record with no quote has no key and is not kept
        quote_key = f"{source_ref}::quote::{quote}"
        existing = seen.get(quote_key)
        if existing is None or _dedup_score(req) > _dedup_score(existing):
            seen[quote_key] = req
    return list(seen.values())


class OldExtractionFormatError(ValueError):
    """The extraction file was written by the old list-writing step (its rows have no clause_index)."""


# Fields the clause labeler writes that normalizing carries through unchanged (pipeline/clause_labeling.build_records).
CLAUSE_FIELDS = ("clause_index", "clause_label", "source_ref_origin", "label_prompt_sha", "anchor_status", "anchor_start", "anchor_end", "anchor_text")


def check_extraction_format(raw_reqs: list[dict], path) -> None:
    """Refuse rows from the old list-writing extraction step: they carry no clause_index, and their quotes were the model's own copy, which the checks that repaired them (grounding,
    anchoring, sentence stretching, parent stems) no longer exist to fix."""
    old = sum(1 for r in raw_reqs if r.get("clause_index") is None)
    if old:
        raise OldExtractionFormatError(
            f"{path}: {old} of {len(raw_reqs)} rows have no clause_index. This file was written by the old requirement-finding step, which no longer exists. "
            "Run requirement finding again on this folder (run_pipeline.py --skip-to requirement-finding); the chunk file is reused, the PDF is not read again.")


def clause_offset_mismatch(req: dict, raw_text: str | None) -> bool:
    """True when the clause's offsets do not give back its text: tidy(raw_text[anchor_start:anchor_end]) must equal source_quote. Clause labeling builds both from the same
    splitter offsets, so this should never fire; it guards against a chunk file that changed under the extraction file (a re-chunk without a re-label)."""
    start, end = req.get("anchor_start"), req.get("anchor_end")
    if raw_text is None or not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(raw_text):
        return True
    return tidy(raw_text[start:end]) != (req.get("source_quote") or "").strip()


def run(
    requirements_jsonl: str,
    chunks_jsonl: str,
    source_pdf_path: str,
    output_dir: str,
    *,
    extraction_model: str | None = None,
    profile: dict | None = None,
) -> str:
    """Normalize, check and de-duplicate the clause labeler's rows and write <doc>_requirements_normalized.jsonl (and the failures file).

    Args:
        requirements_jsonl: <doc>_extracted_requirements.jsonl from requirement finding (clause labeling).
        chunks_jsonl:       <doc>_chunks.jsonl from chunking: required (the clause offsets index its text; it gives pages and section paths).
        source_pdf_path:    Path to the original PDF (for the document identity hash).
        output_dir:         Directory to write into.
        extraction_model:   The labeler's model name; a row's own extraction_model wins (the labeler writes it on every row).
        profile:            Validated profile dict from core.profiles.load_profile(); the cybersecurity default when None.

    Raises OldExtractionFormatError for an extraction file from the old list-writing step, FileNotFoundError when the chunk file is missing.
    Returns the path of the normalized file (str).
    """
    if profile is None:
        from core.profiles import default_profile as _default_profile
        profile = _default_profile()

    _valid_domain_tags: frozenset[str] = frozenset(profile["domain_tags"])
    _valid_requirement_types: frozenset[str] = frozenset(profile["requirement_types"])

    reqs_path = Path(requirements_jsonl).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Loading requirements from: %s", reqs_path)
    raw_reqs = load_jsonl(reqs_path)
    log.info("Loaded %d raw requirements", len(raw_reqs))
    check_extraction_format(raw_reqs, reqs_path)

    chunks_path = Path(chunks_jsonl).resolve()
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_path} (normalizing checks each clause against its chunk's text)")

    doc_identity = {"document_id": "", "document_hash_full": "", "source_pdf": ""}
    if source_pdf_path:
        pdf_path = Path(source_pdf_path).resolve()
        if pdf_path.exists():
            doc_identity = compute_document_identity(pdf_path)
            log.info("Document identity: %s (%s)", doc_identity["document_id"], doc_identity["source_pdf"])
        else:
            log.warning("PDF file not found: %s — document_id will be empty", pdf_path)

    from core.artifact_resolver import doc_key_from_extracted_path
    stem = doc_key_from_extracted_path(reqs_path)
    norm_path = out_dir / f"{stem}_requirements_normalized.jsonl"
    fail_path = out_dir / f"{stem}_normalization_failures.jsonl"

    log.info("Loading chunk metadata from: %s", chunks_path)
    chunks = load_jsonl(chunks_path)
    chunk_page_map = build_chunk_page_map(chunks)
    chunk_hierarchy_map = build_chunk_hierarchy_map(chunks)
    section_children_map = build_section_children_map(chunks)
    chunk_raw_text_map = {c["chunk_id"]: c.get("raw_text") or c.get("text") or "" for c in chunks if "chunk_id" in c}
    log.info("Loaded page references for %d chunks", len(chunk_page_map))
    sections_with_children = sum(1 for v in section_children_map.values() if v)
    log.info("Hierarchy map: %d chunks, %d sections with children", len(chunk_hierarchy_map), sections_with_children)

    run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    start = time.time()

    valid_reqs = []
    failures = []

    for req in raw_reqs:
        description = req.get("description", "").strip()
        source_ref = req.get("source_ref", "").strip()
        source_quote = req.get("source_quote", "").strip()
        req_type = req.get("requirement_type", "").strip().lower()
        chunk_id = req.get("chunk_id")

        hierarchy = chunk_hierarchy_map.get(chunk_id) if chunk_id is not None else None
        if hierarchy:
            section_ref_path: list[str] = hierarchy["section_ref_path"]
            section_title_path: list[str] = hierarchy["section_title_path"]
            parent_context: str | None = hierarchy["parent_context"]
            # parent_section_ref: penultimate element of the ancestry path
            parent_section_ref: str | None = (
                section_ref_path[-2] if len(section_ref_path) >= 2 else None
            )
            # child_section_refs: direct children of this section across all chunks
            current_ref = section_ref_path[-1] if section_ref_path else None
            child_section_refs: list[str] = (
                section_children_map.get(current_ref, []) if current_ref else []
            )
        else:
            section_ref_path = []
            section_title_path = []
            parent_context = None
            parent_section_ref = None
            child_section_refs = []

        if not source_quote:
            failures.append({"requirement_id": req.get("requirement_id", "UNKNOWN"), "chunk_id": chunk_id, "error": "empty_source_quote", "raw": req})
            continue

        # The invariant: the clause is the document's own text at its offsets. Never expected to fire (both come from the splitter); a chunk file changed under the
        # extraction file would make it fire, and such a row must not be indexed under a position it does not have.
        if clause_offset_mismatch(req, chunk_raw_text_map.get(chunk_id)):
            failures.append({"requirement_id": req.get("requirement_id", "UNKNOWN"), "chunk_id": chunk_id, "error": "clause_offset_mismatch", "raw": req})
            continue

        # WP-34.2: a clause that only repeats a heading of its own section (e.g. "COMPLIANCE WITH THIS PUBLICATION IS MANDATORY").
        if _is_heading_echo(source_quote, section_title_path):
            failures.append({"requirement_id": req.get("requirement_id", "UNKNOWN"), "chunk_id": chunk_id, "error": "heading_echo_quote", "raw": req})
            continue

        # WP-38.2: a definitional cross-reference with no obligation of its own ("Term, as defined in CNSSI 4009."); see _is_orphaned_list_item().
        if _is_orphaned_list_item(source_quote):
            failures.append({"requirement_id": req.get("requirement_id", "UNKNOWN"), "chunk_id": chunk_id, "error": "orphaned_list_item_quote", "raw": req})
            continue

        raw_tags = req.get("domain_tags", [])
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        domain_tags = [t.strip().lower() for t in raw_tags if isinstance(t, str)]
        domain_tags = [t for t in domain_tags if t in _valid_domain_tags]

        if req_type not in _valid_requirement_types:
            req_type = ""

        page_start = None
        page_end = None
        if chunk_id is not None and chunk_id in chunk_page_map:
            page_start, page_end = chunk_page_map[chunk_id]

        # Switched off (docs/PIPELINE_REDESIGN_PLAN.md): confidence measured whether the record had tags, a description and a source reference, and the first-pass extractor supplies
        # neither of the first two, so every record scored 0.6 or 0.7 and the number said nothing. The record carries no confidence while COMPUTE_CONFIDENCE is False.
        confidence = None
        if COMPUTE_CONFIDENCE:
            confidence = 1.0
            if not domain_tags:
                confidence -= 0.2
            if not source_quote:
                confidence -= 0.2
            if len(description) < 20:
                confidence -= 0.1
            if not source_ref:
                confidence -= 0.1

        normalized = {
            "requirement_id": req.get("requirement_id", f"R-{chunk_id}-X"),
            "description": description,
            "source_ref": source_ref,
            "domain_tags": domain_tags,
            "requirement_type": req_type,
            "source_quote": source_quote,
            "chunk_id": chunk_id,
            "page_start": page_start,
            "page_end": page_end,
            **({"confidence": round(max(0.0, confidence), 2)} if confidence is not None else {}),
            # Hierarchy metadata (WP-14.3) — deterministic parser output from WP-14.2.
            "section_ref_path": section_ref_path,
            "section_title_path": section_title_path,
            "parent_section_ref": parent_section_ref,
            "parent_context": parent_context,
            "child_section_refs": child_section_refs,
            "domain_profile": profile["name"],
            "document_id": doc_identity["document_id"],
            "document_hash_full": doc_identity["document_hash_full"],
            "source_pdf": doc_identity["source_pdf"],
            "schema_version": SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "extraction_model": req.get("extraction_model") or extraction_model or "",
            "run_timestamp": run_timestamp,
        }
        normalized.update({k: req.get(k) for k in CLAUSE_FIELDS})
        valid_reqs.append(normalized)

    before_dedup = len(valid_reqs)
    valid_reqs = deduplicate_requirements(valid_reqs)
    dedup_removed = before_dedup - len(valid_reqs)

    # Explained layer (docs/PIPELINE_REDESIGN_PLAN.md): the clause without its list marker, with the lead-in of its list in front when it is a list item. A separate field beside the
    # root; source_quote is never changed.
    from pipeline import sentence_expand
    valid_reqs, explain_counts = sentence_expand.explain_records(
        valid_reqs, chunk_raw_text_map,
        {cid: (tuple(h.get("section_ref_path") or ()), tuple(h.get("section_title_path") or ())) for cid, h in chunk_hierarchy_map.items()},
    )
    log.info("Explained layer: %s", explain_counts)

    for req in valid_reqs:
        req["requirement_id"] = compute_stable_id(
            document_id=req["document_id"],
            source_ref=req["source_ref"],
            source_quote=req["source_quote"],  # the root: improving the explained layer never changes an ID
            chunk_id=req.get("chunk_id"),
            requirement_type=req["requirement_type"],
            description=req["description"],
        )
    ids = [r["requirement_id"] for r in valid_reqs]
    if len(set(ids)) != len(ids):  # de-duplication uses the same key as the ID, so this should not happen; the index keys each point by ID, so keep one of any pair
        seen_ids: set = set()
        unique = []
        for r in valid_reqs:
            if r["requirement_id"] in seen_ids:
                log.warning("Dropping a record with a repeated requirement_id %s", r["requirement_id"])
                continue
            seen_ids.add(r["requirement_id"])
            unique.append(r)
        valid_reqs = unique

    elapsed = time.time() - start
    mismatches = sum(1 for f in failures if f["error"] == "clause_offset_mismatch")
    if mismatches:
        log.error("%d clause(s) failed the offset invariant (clause_offset_mismatch): the chunk file no longer matches the extraction file; re-run requirement finding", mismatches)
    by_label: dict = {}
    for r in valid_reqs:
        by_label[r.get("clause_label")] = by_label.get(r.get("clause_label"), 0) + 1
    log.info(
        "Normalized %d requirements in %.2fs — %d failures, %d duplicates removed; labels %s",
        len(valid_reqs), elapsed, len(failures), dedup_removed, by_label,
    )

    with open(norm_path, "w", encoding="utf-8") as f:
        for req in valid_reqs:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")
    log.info("Wrote %s", norm_path)

    with open(fail_path, "w", encoding="utf-8") as f:
        for failure in failures:
            f.write(json.dumps(failure, ensure_ascii=False) + "\n")
    log.info("Wrote %s (%d failures)", fail_path, len(failures))
    if mismatches:  # an invariant violation is a bug or a stale chunk file, not a row to drop quietly; the files above are written for inspection
        raise RuntimeError(f"{mismatches} clause(s) failed the offset invariant (clause_offset_mismatch): the chunk file no longer matches the extraction file. Re-run requirement finding.")

    return str(norm_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize and deduplicate extracted requirements"
    )
    parser.add_argument(
        "requirements_jsonl",
        type=str,
        help="Path to <doc>_extracted_requirements.jsonl from requirement finding (clause labeling)",
    )
    parser.add_argument(
        "--chunks-jsonl",
        type=str,
        default=None,
        help="Path to <doc>_chunks.jsonl from chunking (required: clause offsets, pages, sections). "
             "Auto-detected if not provided.",
    )
    parser.add_argument(
        "--source-pdf-path",
        type=str,
        default=None,
        help="Path to original PDF file (for document identity hashing). "
             "If not provided, document_id fields will be empty.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: same directory as input)",
    )
    parser.add_argument(
        "--extraction-model",
        type=str,
        default=None,
        help="Name of the labeling model, for rows that do not carry one (the clause labeler writes it on every row).",
    )
    args = parser.parse_args()

    reqs_path = Path(args.requirements_jsonl).resolve()
    if not reqs_path.exists():
        log.error("Input file not found: %s", reqs_path)
        sys.exit(1)

    # Auto-detect chunks file if not provided
    if args.chunks_jsonl:
        chunks_path = str(Path(args.chunks_jsonl).resolve())
    else:
        from core.artifact_resolver import doc_key_from_extracted_path
        stem = doc_key_from_extracted_path(reqs_path)
        chunks_path = str(reqs_path.parent / f"{stem}_chunks.jsonl")

    out_dir = Path(args.output_dir).resolve() if args.output_dir else reqs_path.parent

    run(
        str(reqs_path),
        chunks_path,
        args.source_pdf_path or "",
        str(out_dir),
        extraction_model=args.extraction_model,
    )


if __name__ == "__main__":
    main()

"""WP-46.2: "possible missed requirements" — passages of the document that look like obligations but were not extracted, found by a rule-based scan of the chunk text.

No model call. The extractor finds roughly 6 in 10 known obligations (WP-45.11), so an audit sheet built only from extracted rows would silently omit the rest. This scan lists
candidates next to the extracted rows, clearly labeled, so a reader can see gaps. It is a net for a reader, not a classifier: some candidates are descriptions or examples, and
nothing found here is promoted to a requirement or sent to the index.

A candidate is a paragraph unit of a chunk (split at numbered or lettered paragraph markers, else at sentence ends) that
  - has a modal ("shall", "must", "will", "should", "required to", "is responsible", "are to"), or opens with an imperative verb, and
  - does not end with a colon (a lead-in such as "AF/A3 will:" is carried by the items under it), and
  - is not covered by any extracted quote (normalized text, containment either way, at least 25 characters).
"""
import hashlib
import re

from services import checklist_audit

# a paragraph starts at a line that opens with a bullet, or with a numbered/lettered marker (optionally after a bullet)
_MARKER = re.compile(r"(?m)^[ \t]*(?:[-•*][ \t]+(?=\S)|(?:[-•*][ \t]*)?(?=(?:\d+(?:\.\d+)+\.?|\([a-zA-Z0-9]{1,3}\)|[a-z]\.)[ \t]+\S))")
_BULLET = re.compile(r"^[ \t]*[-•*][ \t]*")
_SENTENCE = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")
_MODAL = re.compile(r"\b(shall|must|will|should|required to|is responsible|are responsible|is to|are to)\b", re.IGNORECASE)
_NUMBER_ONLY = re.compile(r"^\W*(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?$")
_REF = re.compile(r"^\W*((?:[A-Z]{1,2})?\d+(?:\.\d+)+)\.?\s")
MIN_UNIT_CHARS = 40
MIN_COVER_CHARS = 25
MAX_TEXT_CHARS = 700


def normalize(text: str) -> str:
    """Lower-case, whitespace collapsed, no space before closing punctuation or after an opening bracket (the pipeline tidies quotes this way; the document keeps the original)."""
    text = re.sub(r"\s+", " ", text or "").strip().lower()
    return re.sub(r"\s+([.,;:)\]])", r"\1", text).replace("( ", "(")


def paragraph_units(raw_text: str) -> list[str]:
    """The paragraphs of a chunk: split at numbered/lettered markers when there are at least two, otherwise at sentence ends."""
    starts = sorted({m.start() for m in _MARKER.finditer(raw_text)})
    if len(starts) >= 2:
        # text before the first marker (the end of a paragraph that began in the previous chunk) is a unit of its own
        bounds = ([0] if starts[0] > 0 and raw_text[: starts[0]].strip() else []) + starts + [len(raw_text)]
        return [raw_text[a:b].strip() for a, b in zip(bounds, bounds[1:]) if raw_text[a:b].strip()]
    pieces = [s.strip() for s in _SENTENCE.split(raw_text) if s.strip()]
    if len(pieces) > 1 and _NUMBER_ONLY.match(pieces[0]):  # "3.6. Incident Analysis. ..." must not be cut into "3.6." and "Incident Analysis. ..."
        pieces = [pieces[0] + " " + pieces[1]] + pieces[2:]
    return pieces


def _page_range(chunk: dict) -> list[int]:
    """Every page the chunk spans: the scan has no finer position, so a candidate is cited to the whole range rather than to the first page only."""
    try:
        start = chunk.get("page_start")
        if start is None:
            return []
        start = int(start)
        end = chunk.get("page_end")
        return list(range(start, int(end) + 1)) if end is not None and int(end) > start else [start]
    except (TypeError, ValueError):
        return []


def _covered(unit_norm: str, quotes: list[str]) -> bool:
    return any(len(q) >= MIN_COVER_CHARS and (q in unit_norm or unit_norm in q) for q in quotes)


def find_possible_missed(chunks: dict, quotes: list[str], extra_verbs=()) -> list[dict]:
    """Checklist-shaped candidate rows (`item_flags` carries `possible_missed`), in document order, not extracted and not duplicated."""
    covered_by = [normalize(q) for q in quotes if q]
    verbs = checklist_audit.IMPERATIVE_VERBS | {v.lower() for v in extra_verbs if " " not in v}
    seen: set[str] = set()
    out = []
    for chunk_id in sorted(k for k in chunks if isinstance(k, int)):
        chunk = chunks[chunk_id]
        for unit in paragraph_units(chunk.get("raw_text") or ""):
            unit = _BULLET.sub("", unit, count=1).strip()
            norm = normalize(unit)
            if len(norm) < MIN_UNIT_CHARS or norm in seen or norm.endswith(":") or unit.count("|") >= 2:
                continue
            seen.add(norm)
            if _MODAL.search(unit):
                why = "modal"
            elif checklist_audit._first_word(unit) in verbs:  # the bare imperative only: a plural noun such as "Reports are filed ..." also looks like a third-person verb
                why = "imperative"
            else:
                continue
            if _covered(norm, covered_by):
                continue
            path = [str(p) for p in (chunk.get("section_title_path") or [])]
            ref = (_REF.match(unit) or [None, ""])[1]
            pages = _page_range(chunk)
            text = unit if len(unit) <= MAX_TEXT_CHARS else unit[:MAX_TEXT_CHARS].rsplit(" ", 1)[0] + " ..."
            out.append({
                "checklist_item_id": "MISS-" + hashlib.sha256(f"{chunk_id}|{norm}".encode()).hexdigest()[:16],
                "requirement_ids": [],
                "domain_tags": [],
                "source_ref": ref,
                "page_refs": pages,
                "section_title_path": path,
                "applies_to": checklist_audit.applies_to(path),
                "section_heading": "",
                "parent_ref": "",
                "parent_text": "",
                "source_quote": text,
                "passage": "",
                "item_flags": ["possible_missed", why],
                "audit_question": "",
                "evidence_to_request": [],
                "generation_notes": "found by a text scan, not extracted",
                "assessor_notes": "",
                "status": "not-started",
                "confidence": None,
                "requires_human_review": True,
                "review_reasons": ["not-extracted"],
            })
    return out

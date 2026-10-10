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

from pipeline import sentence_expand
from services import checklist_audit

# a paragraph starts at a line that opens with a bullet, or with a numbered/lettered marker (optionally after a bullet)
_MARKER = re.compile(r"(?m)^[ \t]*(?:[-•*][ \t]+(?=\S)|(?:[-•*][ \t]*)?(?=(?:\d+(?:\.\d+)+\.?|\([a-zA-Z0-9]{1,3}\)|[a-z]\.)[ \t]+\S))")
_BULLET = re.compile(r"^[ \t]*[-•*][ \t]*")
_SENTENCE = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")
_MODAL = re.compile(r"\b(shall|must|will|should|required to|is responsible|are responsible|is to|are to)\b", re.IGNORECASE)
_NUMBER_ONLY = re.compile(r"^\W*(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?$")
_REF = re.compile(r"^\W*((?:[A-Z]{1,2})?\d+(?:\.\d+)+)\.?\s")
_NUMBER_PREFIX = re.compile(r"^[\s\-•*]*(?:(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?\s+)*")
MIN_UNIT_CHARS = 40
MIN_COVER_CHARS = 25
MAX_TEXT_CHARS = 700


_TIER_TAG = re.compile(r"\(\s*t-\d\s*\)")  # an AFI tier tag such as "(T-2)" is not part of what an extracted row says


def normalize(text: str) -> str:
    """Lower-case, whitespace collapsed, no tier tag, no space before closing punctuation or after an opening bracket (the pipeline tidies quotes this way; the document keeps the original)."""
    text = _TIER_TAG.sub("", re.sub(r"\s+", " ", text or "").strip().lower())
    text = re.sub(r"\s+", " ", text).strip()
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


def _scan(chunks: dict, quotes: list[str], extra_verbs=(), check_coverage: bool = True, by_sentence: bool = False) -> list[dict]:
    """The candidate paragraphs in document order, not duplicated and, unless `check_coverage` is off, not extracted: chunk, offset in the chunk, text, why, paragraph number,
    section path, pages. (`split_candidates` turns the paragraph-level coverage check off and judges coverage sentence by sentence: an extracted sentence must not hide the
    paragraph's other duty sentences; it also lets a later sentence qualify a paragraph (`by_sentence`) and lets the sentences of a chunk with a single numbered paragraph keep its
    number.)"""
    covered_by = [normalize(q) for q in quotes if q]
    verbs = checklist_audit.IMPERATIVE_VERBS | {v.lower() for v in extra_verbs if " " not in v}
    seen: set[str] = set()
    out = []
    for chunk_id in sorted(k for k in chunks if isinstance(k, int)):
        chunk = chunks[chunk_id]
        raw = chunk.get("raw_text") or ""
        cursor = 0
        by_sentences = len({m.start() for m in _MARKER.finditer(raw)}) < 2  # `paragraph_units` cuts a chunk with fewer than two markers into sentences
        chunk_ref = ""
        for unit in paragraph_units(raw):
            at = raw.find(unit, cursor)
            offset = at if at >= 0 else cursor
            cursor = offset + len(unit) if at >= 0 else cursor
            unit = _BULLET.sub("", unit, count=1).strip()
            own_ref = (_REF.match(unit) or [None, ""])[1]
            if own_ref:
                chunk_ref = own_ref  # even a short title unit ("3.6. Incident Analysis.") sets the number the sentences after it keep
            norm = normalize(unit)
            if len(norm) < MIN_UNIT_CHARS or norm in seen or norm.endswith(":") or unit.count("|") >= 2:
                continue
            seen.add(norm)
            if _MODAL.search(unit):
                why = "modal"
            elif checklist_audit._first_word(unit) in verbs:  # the bare imperative only: a plural noun such as "Reports are filed ..." also looks like a third-person verb
                why = "imperative"
            elif by_sentence and any(checklist_audit._first_word(sentence_expand.tidy(_NUMBER_PREFIX.sub("", sentence, count=1))) in verbs | _SENTENCE_IMPERATIVES
                                     for sentence in sentence_expand.split_sentences(unit)):
                why = "imperative"  # a later sentence of the paragraph opens with an imperative verb
            else:
                continue
            if check_coverage and _covered(norm, covered_by):
                continue
            out.append({"chunk_id": chunk_id, "offset": offset, "unit": unit, "norm": norm, "why": why, "ref": own_ref or (chunk_ref if by_sentences and by_sentence else ""),
                        "path": [str(p) for p in (chunk.get("section_title_path") or [])], "pages": _page_range(chunk)})
    return out


def _capped(text: str) -> str:
    return text if len(text) <= MAX_TEXT_CHARS else text[:MAX_TEXT_CHARS].rsplit(" ", 1)[0] + " ..."


def _missed_row(c: dict) -> dict:
    return {
        "checklist_item_id": "MISS-" + hashlib.sha256(f"{c['chunk_id']}|{c['norm']}".encode()).hexdigest()[:16],
        "requirement_ids": [],
        "domain_tags": [],
        "source_ref": c["ref"],
        "page_refs": c["pages"],
        "section_title_path": c["path"],
        "applies_to": checklist_audit.applies_to(c["path"]),
        "section_heading": "",
        "parent_ref": "",
        "parent_text": "",
        "source_quote": _capped(c["unit"]),
        "passage": "",
        "item_flags": ["possible_missed", c["why"]],
        "audit_question": "",
        "evidence_to_request": [],
        "generation_notes": "found by a text scan, not extracted",
        "assessor_notes": "",
        "status": "not-started",
        "confidence": None,
        "requires_human_review": True,
        "review_reasons": ["not-extracted"],
    }


def find_possible_missed(chunks: dict, quotes: list[str], extra_verbs=()) -> list[dict]:
    """Checklist-shaped candidate rows (`item_flags` carries `possible_missed`), in document order, not extracted and not duplicated."""
    return [_missed_row(c) for c in _scan(chunks, quotes, extra_verbs)]


_PURPOSE = re.compile(r"\b(?:purpose|goal|objective|intent|aim)\b[^.;:]{0,80}\b(?:is|are) to\b", re.IGNORECASE)  # "The purpose of this analysis is to understand ..." states an aim, not a duty
_STRONG_MODAL = re.compile(r"\b(?:shall|must|will|should|required to)\b", re.IGNORECASE)
_SENTENCE_IMPERATIVES = frozenset({"include"})  # "Include the mission owner ..." is a duty as a sentence opener; "includes ..." is a description, so the verb list the scan uses leaves it out


MIN_SENTENCE_CHARS = 20


def _duty_sentences(unit: str, covered_by: list[str], verbs) -> tuple[list[str], int]:
    """(uncovered, covered): the sentences of a paragraph that carry a duty (a modal, or an opening imperative), without the paragraph number and tidied, split into those not yet
    extracted and the count of those that already are (an extracted row, perhaps with a lead-in attached, contains the sentence)."""
    out, covered = [], 0
    for sentence in sentence_expand.split_sentences(unit):
        body = sentence_expand.tidy(_NUMBER_PREFIX.sub("", sentence, count=1))
        if len(body) < MIN_SENTENCE_CHARS:
            continue
        if not (_MODAL.search(body) or checklist_audit._first_word(body) in verbs | _SENTENCE_IMPERATIVES):
            continue
        if _PURPOSE.search(body) and not _STRONG_MODAL.search(body):
            continue
        norm = normalize(body)
        if _covered(norm, covered_by) or norm in covered_by:  # a short sentence is only covered by an extracted row that says exactly the same
            covered += 1
            continue
        out.append(_capped(body))
    return out, covered


def split_candidates(chunks: dict, quotes: list[str], extra_verbs=()) -> tuple[list[dict], list[dict]]:
    """(promoted, still_missed), judged sentence by sentence. A candidate paragraph that carries its own paragraph number is promoted, one entry per sentence that holds a duty and is
    not extracted yet (the whole sentence, not the paragraph: the second sentence of 3.7 is the requirement, the first only introduces it); each entry has the chunk, its offset in the
    chunk, the sentence, the paragraph number, the section path, the pages and an id. A paragraph whose duty sentences are all extracted already is dropped (the paragraph-level scan
    listed it only because the extracted row carries a lead-in or leaves out a tier tag). The unextracted duty sentences of a paragraph with no number stay possible-missed rows, a
    sentence each. A paragraph with no duty sentence of its own stays one possible-missed row unless an extracted row already contains it."""
    covered_by = [normalize(q) for q in quotes if q]
    verbs = checklist_audit.IMPERATIVE_VERBS | {v.lower() for v in extra_verbs if " " not in v}
    promoted, rest = [], []
    for c in _scan(chunks, quotes, extra_verbs, check_coverage=False, by_sentence=True):
        sentences, already = _duty_sentences(c["unit"], covered_by, verbs)
        if not sentences:
            if not already and not _covered(c["norm"], covered_by):
                rest.append(_missed_row(c))
            continue
        if not c["ref"]:
            rest.extend(_missed_row({**c, "unit": text, "norm": normalize(text)}) for text in sentences)
            continue
        raw = chunks[c["chunk_id"]].get("raw_text") or ""
        for text in sentences:
            pattern = sentence_expand.flex_pattern(text)
            found = pattern.search(raw, c["offset"]) if pattern else None  # from this paragraph on: identical wording in an earlier paragraph is not this one
            at = found.start() if found else c["offset"]
            promoted.append({"chunk_id": c["chunk_id"], "offset": at, "text": text, "ref": c["ref"], "path": c["path"], "pages": c["pages"],
                             "checklist_item_id": "MISS-" + hashlib.sha256(f"{c['chunk_id']}|{at}|{normalize(text)}".encode()).hexdigest()[:16]})
    return promoted, rest

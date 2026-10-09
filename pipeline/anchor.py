"""Anchoring: find where a root quote sits in its chunk's `raw_text` and say how exact the match is (pure functions; docs/PIPELINE_REDESIGN_PLAN.md).

The root is what requirement finding returned. Anchoring never changes it. It records metadata beside it: whether the root is word for word in the source, where, and when it is not,
the closest exact piece of the source. Whitespace and bracket spacing are ignored in matching (the pipeline tidies "Program ." to "Program."), nothing else is.

anchor_status:
  exact              the root is in the chunk exactly once (anchor_start, anchor_end index `raw_text`)
  exact_ambiguous    the root is in the chunk more than once; no position is given
  marker_removed     exact once a leading dash, bullet or list number is taken off
  lead_in_joined     a lead-in ("AFMC will:") was glued onto a list item; the item is exact and is the anchor, and the lead-in is found in the chunk before the item (the nearest occurrence;
                     kept in anchor_lead_in with its position)
  lead_in_from_heading   the item is exact and the glued lead-in is not in the chunk body but is in the chunk's heading breadcrumb ("Air Combat Command shall:" under a heading of that name)
  lead_in_not_in_source  the item is exact but the glued lead-in is nowhere in the chunk (body before the item, or heading); the lead-in is not vouched for
  words_trimmed      exact once a few words are taken off the front or the end (anchor_trim_side says which)
  fuzzy              no exact piece; the closest span is at least FUZZY_MIN similar (anchor_score)
  not_found          nothing close in the chunk
"""
import re

from rapidfuzz import fuzz

from pipeline.sentence_expand import _LEADING_NUMBER, flex_pattern

FUZZY_MIN = 85
MIN_PIECE_CHARS = 25  # a piece shorter than this is not evidence of where the root came from
MAX_TRIM_WORDS = 7
LEAD_IN_WINDOW = 160  # the colon of a glued lead-in is near the start


def _find(text: str, raw: str):
    """All matches of `text` in `raw`, ignoring spacing."""
    pat = flex_pattern(text)
    return list(pat.finditer(raw)) if pat else []


def _result(status, m=None, **extra):
    out = {"anchor_status": status, "anchor_start": None, "anchor_end": None, "anchor_text": None}
    if m is not None:
        out.update(anchor_start=m.start(), anchor_end=m.end(), anchor_text=m.string[m.start():m.end()])
    out.update(extra)
    return out


def anchor(root: str, raw_text: str, breadcrumb: str = "") -> dict:
    """The anchor record for a root quote, the chunk's raw text and (optionally) the chunk's heading breadcrumb. Never raises; an empty chunk or root is `not_found`."""
    root = (root or "").strip()
    raw = raw_text or ""
    if not root or not raw:
        return _result("not_found")

    found = _find(root, raw)
    if len(found) == 1:
        return _result("exact", found[0])
    if len(found) > 1:
        return _result("exact_ambiguous", anchor_matches=len(found))

    ambiguous = 0  # the most matches any exact candidate had: a repeated piece must not be given an arbitrary position by the fuzzy fallback
    lead = _LEADING_NUMBER.match(root)
    body = root[lead.end():].strip() if lead else root
    if body != root and len(body) >= MIN_PIECE_CHARS:
        found = _find(body, raw)
        if len(found) == 1:
            return _result("marker_removed", found[0])
        ambiguous = max(ambiguous, len(found))

    # a lead-in glued onto its list item: "AFMC will: Identify ..." (the item, after its own marker, is exact)
    colon = body.find(":")
    if 0 < colon < LEAD_IN_WINDOW:
        head, tail = body[:colon + 1].strip(), body[colon + 1:].strip()
        item = _LEADING_NUMBER.match(tail)
        item_text = tail[item.end():].strip() if item else tail
        if len(item_text) >= MIN_PIECE_CHARS:
            found = _find(item_text, raw)
            if len(found) == 1:
                before = [m for m in _find(head, raw) if m.end() <= found[0].start()]
                if before:  # the nearest occurrence before the item is the lead-in that governs it
                    return _result("lead_in_joined", found[0], anchor_lead_in=head, anchor_lead_in_start=before[-1].start())
                actor = re.sub(r"\s+(?:shall|will|must|should|may|is to|are to)\s*$", "", head.rstrip(":").strip(), flags=re.IGNORECASE)  # "Air Combat Command shall:" -> the heading names "Air Combat Command"
                if breadcrumb and actor and _find(actor, breadcrumb):
                    return _result("lead_in_from_heading", found[0], anchor_lead_in=head)
                return _result("lead_in_not_in_source", found[0])
            if len(found) > 1:
                ambiguous = max(ambiguous, len(found))

    words = body.split()
    for k in range(1, MAX_TRIM_WORDS + 1):
        for side, piece in (("front", " ".join(words[k:])), ("end", " ".join(words[:-k]))):
            if len(piece) >= MIN_PIECE_CHARS:
                found = _find(piece, raw)
                if len(found) == 1:
                    return _result("words_trimmed", found[0], anchor_words_trimmed=k, anchor_trim_side=side)
                ambiguous = max(ambiguous, len(found))

    if ambiguous > 1:
        return _result("exact_ambiguous", anchor_matches=ambiguous)

    al = fuzz.partial_ratio_alignment(root, raw)
    if al is not None and al.score >= FUZZY_MIN:
        return {"anchor_status": "fuzzy", "anchor_start": al.dest_start, "anchor_end": al.dest_end, "anchor_text": raw[al.dest_start:al.dest_end], "anchor_score": round(al.score, 1)}
    return _result("not_found", anchor_score=round(al.score, 1) if al is not None else 0.0)


ANCHOR_FIELDS = ("anchor_status", "anchor_start", "anchor_end", "anchor_text")

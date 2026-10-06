#!/usr/bin/env python3
"""WP-45.7b: the candidate menu. Code proposes every span the selection resolver may pick; the model only chooses.

For one candidate quote the menu lists verbatim substrings of text the bundle already holds, each with an id (M1, M2, ...) and a kind:

  subject   the quote's own words before its first modal phrase ("The Records Officer" in "The Records Officer shall ...")
  heading   the leaf heading and every ancestor heading of the quote's chunk, each also without its leading section number
  preceding the words between the previous sentence boundary and the quote in its chunk (a list item's lead-in clause that has no
            colon), or the previous sentence when the quote starts a sentence, and that clause's own subject
  lead_in   the nearest sentence ending in a colon before the quote in its chunk (and, at tier R2, in the previous chunk's tail),
            and that sentence's own subject (its words before its modal phrase)
  stem      each governing-clause candidate the production finders produce, and its subject

Nothing here is generated: every `text` is a substring of the quote, a heading, the chunk, or a stem candidate, so a value the model
picks is verbatim by construction. The generator is deterministic and has no model in it. Tier R1 uses the candidate's own chunk and
headings; R2 adds the previous chunk's tail (the same characters the R2 bundle shows). See docs/PHASE45_WP457B_PLAN.md.
"""

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bundle as B  # noqa: E402
import check_resolution as C  # noqa: E402

MAX_SPAN_CHARS = 300  # a lead-in or stem longer than this is cut back to its last 300 characters, at a word boundary
MAX_MENU = 14
_LIST_MARKER = re.compile(r"^\(?(?:[0-9]{1,2}(?:\.[0-9]{1,2})*|[a-zA-Z]{1,2}|[ivxIVX]{1,5})[.)]\s+")
_SENTENCE_START = re.compile(r"(?<=[.;!?])\s+")
_SECTION_NUMBER = re.compile(r"^(?:section\s+)?[0-9]+(?:\.[0-9]+)*\.?\s+", re.IGNORECASE)


def first_modal(text):
    """(start, end, phrase, class) of the earliest table modal in the normalized text, or None. The ambiguous "can" is left out,
    as in the checker's default."""
    text = B.normalize(text)
    best = None
    for rx, phrase, cls in C._PHRASE_RE:
        if phrase in C.AMBIGUOUS:
            continue
        m = rx.search(text.lower())
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), m.end(), phrase, cls)
    return best


def subject_of(text):
    """The words before the first modal phrase, with a leading list marker and trailing punctuation removed; None when the text has
    no modal phrase or nothing sensible before it. The result is a substring of the normalized text."""
    text = B.normalize(text)
    modal = first_modal(text)
    if modal is None:
        return None
    head = text[: modal[0]]
    head = _LIST_MARKER.sub("", head, count=1).strip(" \t,;:-")
    return head or None


def _cap(text):
    if len(text) <= MAX_SPAN_CHARS:
        return text
    cut = text[-MAX_SPAN_CHARS:]
    return cut[cut.find(" ") + 1:] if " " in cut else cut


def lead_in_before(body, quote):
    """The nearest sentence that ends in a colon before the quote's position in `body`, from its sentence start to the colon, or None.
    `body` and `quote` are normalized. When the quote is not found, there is no position and so no lead-in."""
    pos = body.find(quote)
    if pos <= 0:
        return None
    colon = body.rfind(":", 0, pos)
    if colon < 0:
        return None
    before = body[:colon]
    parts = _SENTENCE_START.split(before)
    return _cap(parts[-1].strip() + ":") if parts and parts[-1].strip() else None


def preceding_clause(body, quote):
    """The clause that comes right before the quote in `body`: the words from the last sentence boundary to the quote's start, or, when
    the quote starts a sentence, the whole previous sentence; None when the quote is not found or nothing precedes it."""
    pos = body.find(quote)
    if pos <= 0:
        return None
    parts = _SENTENCE_START.split(body[:pos].rstrip())
    clause = parts[-1].strip()  # after a sentence break this is the previous sentence; otherwise the words up to the quote
    return _cap(clause) if clause else None


def tail_lead_in(text):
    """The last colon-ending sentence in a stretch of text (a previous chunk's tail), or None."""
    colon = text.rfind(":")
    if colon < 0:
        return None
    parts = _SENTENCE_START.split(text[:colon])
    return _cap(parts[-1].strip() + ":") if parts and parts[-1].strip() else None


def build_menu(quote, chunk_id, chunks_by_id, tier="R1", step_c_by_chunk=None):
    """The menu for one candidate: a list of {"id", "kind", "source", "text"}, in a fixed order, without repeated texts.
    Tier R0 has no context and so only the quote's own subject; R1 adds headings, the in-chunk lead-in and the rule stems;
    R2 adds the previous chunk's lead-in."""
    if tier not in B.TIERS:
        raise ValueError(f"tier must be one of {B.TIERS}")
    q = B.normalize(quote)
    entries, seen = [], set()

    def add(kind, source, text):
        text = B.normalize(text or "")
        if text and text.lower() not in seen and len(entries) < MAX_MENU:
            seen.add(text.lower())
            entries.append({"id": f"M{len(entries) + 1}", "kind": kind, "source": source, "text": text})

    add("subject", "candidate quote", subject_of(q))
    chunk = chunks_by_id.get(chunk_id)
    if tier == "R0" or chunk is None:
        return entries
    body = B.normalize(chunk.get("raw_text") or "")
    path = [B.normalize(h) for h in (chunk.get("section_title_path") or []) if B.normalize(h)]
    leaf = B.normalize(chunk.get("parent_header_text") or "")
    for heading in ([leaf] if leaf else []) + path[::-1]:
        add("heading", f"chunk {chunk_id}", heading)
        bare = _SECTION_NUMBER.sub("", heading, count=1)
        if bare != heading:
            add("heading", f"chunk {chunk_id} (without its section number)", bare)
    lead = lead_in_before(body, q)
    if lead:
        add("lead_in", f"chunk {chunk_id}", lead)
        add("lead_in", f"chunk {chunk_id} (its subject)", subject_of(lead))
    clause = preceding_clause(body, q)
    if clause:
        add("preceding", f"chunk {chunk_id}", clause)
        add("preceding", f"chunk {chunk_id} (its subject)", subject_of(clause))
    for source, stem in B.stem_candidates(quote, chunk_id, step_c_by_chunk or {}, chunks_by_id):
        add("stem", source, _cap(stem))
        add("stem", f"{source} (its subject)", subject_of(stem))
    if tier == "R2":
        prev = chunks_by_id.get(chunk_id - 1)
        if prev is not None:
            lead = tail_lead_in(B.normalize(prev.get("raw_text") or "")[-B.NEIGHBOR_CHARS:])
            if lead:
                add("lead_in", f"chunk {prev['chunk_id']} (previous)", lead)
                add("lead_in", f"chunk {prev['chunk_id']} (previous, its subject)", subject_of(lead))
    return entries


def menu_modal(quote, chosen_parent_text=None):
    """The modal phrase and class the code reads for the record: from the quote, or, when the quote has none, from the chosen
    parent span (the "The Records Officer will:" case). (phrase, class) with ("", "none") when neither has a modal. The ambiguous
    "can" is not read as a modal."""
    for text in (quote, chosen_parent_text):
        modal = first_modal(text) if text else None
        if modal:
            return modal[2], modal[3]
    return "", "none"

"""WP-45.7e: the menu generator with the two registered fixes (docs/PHASE45_WP457E_PLAN.md section 1).

`menu.py` is frozen (the WP-45.7d verdict pinned it by hash), so this module reuses everything in it unchanged (the modal reader, subjects,
lead-in and preceding-clause finders, the span cap, the constants) and replaces only `build_menu`. The two changes, and nothing else:

  (a) an entry with fewer than two letters is not offered (a list number, a dash, a lone "c."): such an entry can never be a correct actor or parent;
  (b) a heading is offered only without its section number: the numbered form is no longer offered next to the plain one, because the attachment
      overlap rule counts the number against a match ("2.17. MAJCOM/DRUs." against "MAJCOM/DRUs.").

Every entry is still a verbatim substring of the quote, a heading (with its number removed), the chunk, the previous chunk or a stem candidate.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bundle as B  # noqa: E402
import menu as M1  # noqa: E402

MIN_LETTERS = 2
MAX_SPAN_CHARS, MAX_MENU = M1.MAX_SPAN_CHARS, M1.MAX_MENU
first_modal, subject_of, menu_modal = M1.first_modal, M1.subject_of, M1.menu_modal  # re-exported unchanged


def letters(text):
    return sum(ch.isalpha() for ch in text)


def build_menu(quote, chunk_id, chunks_by_id, tier="R1", step_c_by_chunk=None):
    """The menu for one candidate, as `menu.build_menu`, with the two fixes above. Entries are {"id", "kind", "source", "text"} in a fixed order."""
    if tier not in B.TIERS:
        raise ValueError(f"tier must be one of {B.TIERS}")
    q = B.normalize(quote)
    entries, seen = [], set()

    def add(kind, source, text):
        text = B.normalize(text or "")
        if text and letters(text) >= MIN_LETTERS and text.lower() not in seen and len(entries) < MAX_MENU:
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
        add("heading", f"chunk {chunk_id}", M1._SECTION_NUMBER.sub("", heading, count=1))  # (b): only the form without the number
    lead = M1.lead_in_before(body, q)
    if lead:
        add("lead_in", f"chunk {chunk_id}", lead)
        add("lead_in", f"chunk {chunk_id} (its subject)", subject_of(lead))
    clause = M1.preceding_clause(body, q)
    if clause:
        add("preceding", f"chunk {chunk_id}", clause)
        add("preceding", f"chunk {chunk_id} (its subject)", subject_of(clause))
    for source, stem in B.stem_candidates(quote, chunk_id, step_c_by_chunk or {}, chunks_by_id):
        add("stem", source, M1._cap(stem))
        add("stem", f"{source} (its subject)", subject_of(stem))
    if tier == "R2":
        prev = chunks_by_id.get(chunk_id - 1)
        if prev is not None:
            lead = M1.tail_lead_in(B.normalize(prev.get("raw_text") or "")[-B.NEIGHBOR_CHARS:])
            if lead:
                add("lead_in", f"chunk {prev['chunk_id']} (previous)", lead)
                add("lead_in", f"chunk {prev['chunk_id']} (previous, its subject)", subject_of(lead))
    return entries

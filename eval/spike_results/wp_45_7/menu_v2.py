"""WP-45.7e: the menu generator with the two registered fixes (docs/PHASE45_WP457E_PLAN.md section 1).

`menu.py` is frozen (the WP-45.7d verdict pinned it by hash). This module builds the old menu with it and then **filters** that menu, so the change is
strictly subtractive by construction, including when the old menu hit its entry cap: removing an entry never lets a later candidate in. The two changes,
and nothing else:

  (a) an entry with fewer than two letters is removed (a list number, a dash, a lone "c."): such an entry can never be a correct actor or parent;
  (b) every numbered heading is removed, because the attachment overlap rule counts the section number against a match ("2.17. MAJCOM/DRUs." against
      "MAJCOM/DRUs."). The old menu offers the plain form next to the numbered one; if the old menu's cap cut the plain form, the heading is simply not
      offered rather than offered with its number, and nothing is added in its place.

The surviving entries keep their order and are renumbered M1, M2, ...; each is still a verbatim entry of the old menu, hence a substring of its sources.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import menu as M1  # noqa: E402

MIN_LETTERS = 2
MAX_SPAN_CHARS, MAX_MENU = M1.MAX_SPAN_CHARS, M1.MAX_MENU
first_modal, subject_of, menu_modal = M1.first_modal, M1.subject_of, M1.menu_modal  # re-exported unchanged


def letters(text):
    return sum(ch.isalpha() for ch in text)


def build_menu(quote, chunk_id, chunks_by_id, tier="R1", step_c_by_chunk=None):
    """The old menu for one candidate, filtered by the two fixes above and renumbered. Entries are {"id", "kind", "source", "text"} in the old order."""
    old = M1.build_menu(quote, chunk_id, chunks_by_id, tier, step_c_by_chunk)
    kept = []
    for e in old:
        if letters(e["text"]) < MIN_LETTERS:
            continue  # (a)
        if e["kind"] == "heading" and M1._SECTION_NUMBER.sub("", e["text"], count=1) != e["text"]:
            continue  # (b): headings are offered only without their section number
        kept.append(e)
    return [{**e, "id": f"M{n}"} for n, e in enumerate(kept, 1)]

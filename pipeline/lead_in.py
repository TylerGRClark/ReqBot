"""Find the lead-in that governs a list item, from the document's own text (pure functions; docs/PIPELINE_REDESIGN_PLAN.md, context attaching).

A list item such as "Include the mission owner in the process." means little without the line above it that ends with a colon ("The Director will:"). This finds that line: the nearest
earlier line, in the same chunk or at the end of the previous chunk, that ends with a colon and is not a sibling of the item. Nothing is guessed: the lead-in is an exact line of the
source, or there is none.
"""
import re

from pipeline.sentence_expand import _LEADING_NUMBER, _MARKER, tidy

MAX_UNITS_BACK = 40
MAX_LEAD_IN_CHARS = 300
_DOTTED = re.compile(r"^(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?\s")
_STYLES = (
    ("alpha_p", re.compile(r"^\([a-z]{1,2}\)\s")),
    ("alpha", re.compile(r"^[a-z]{1,2}[.)]\s")),
    ("ALPHA_p", re.compile(r"^\([A-Z]{1,2}\)\s")),
    ("ALPHA", re.compile(r"^[A-Z][.)]\s")),
    ("num_p", re.compile(r"^\(\d{1,3}\)\s")),
    ("num", re.compile(r"^\d{1,3}[.)]\s")),
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.?!])\s+(?=[A-Z(\[\"])")


def _units(text: str) -> list[tuple[int, str]]:
    """(start offset, text) of each paragraph unit: split at list markers, with any text before the first marker as a unit of its own."""
    starts = sorted({m.start() for m in _MARKER.finditer(text)})
    bounds = ([0] if (not starts or starts[0] > 0) else []) + starts + [len(text)]
    return [(a, text[a:b]) for a, b in zip(bounds, bounds[1:]) if text[a:b].strip()]


def _marker_style(unit: str) -> tuple[str, int]:
    """(style, depth): `none` for a plain paragraph; `dotted` with its depth (3.4.3.1 is 4); else a letter or number style. A bare bullet is `bullet`."""
    body = unit.lstrip()
    bullet = bool(re.match(r"^[-•*]\s+", body))
    body = re.sub(r"^[-•*]\s+", "", body)
    if _DOTTED.match(body):
        return "dotted", len(re.match(r"^(?:[A-Z]{1,2})?(\d+(?:\.\d+)+)", body).group(1).split("."))
    for name, pat in _STYLES:
        if pat.match(body):
            return name, 0
    return ("bullet" if bullet else "none"), 0


def _text_of(unit: str) -> str:
    """The unit's words without its marker, and for a long unit only its last sentence (the one that ends in the colon)."""
    body = unit.strip()
    m = _LEADING_NUMBER.match(body)
    body = tidy(body[m.end():] if m else body)
    sentences = _SENTENCE_SPLIT.split(body)
    return sentences[-1].strip() if sentences else body


def _candidate(units: list[tuple[int, str]], index: int, item_style: tuple[str, int]):
    """Scan back from unit `index - 1`: (lead-in text, units used) or None. Stops at a plain paragraph that does not end with a colon."""
    for j in range(index - 1, max(-1, index - 1 - MAX_UNITS_BACK), -1):
        unit = units[j][1]
        style = _marker_style(unit)
        text = _text_of(unit)
        if text.endswith(":"):
            same_style = style[0] == item_style[0] and style[0] not in ("none", "bullet")
            if same_style and not (style[0] == "dotted" and style[1] < item_style[1]):
                continue  # a sibling that also introduces a list (or a deeper one), not the item's parent
            if style[0] == "dotted" and item_style[0] == "dotted" and style[1] >= item_style[1]:
                continue
            return text if len(text) <= MAX_LEAD_IN_CHARS else None
        if style[0] == "none":
            return None  # an ordinary paragraph: the list, if there was one, began after it
    return None


def find_lead_in(raw: str, item_start: int, prev_raw: str = "") -> str | None:
    """The lead-in line for the list item that starts at `item_start` in the chunk's `raw` text, looking in `prev_raw` (the previous chunk) when the list began there; None when the
    item is not a list item or no governing line is found."""
    if item_start is None or not raw:
        return None
    units = _units(raw)
    index = max((i for i, (start, _) in enumerate(units) if start <= item_start), default=None)
    if index is None:
        return None
    item_style = _marker_style(units[index][1])
    if item_style[0] == "none":
        return None  # a plain sentence stands on its own
    found = _candidate(units, index, item_style)
    if found:
        return found
    if any(_marker_style(u)[0] == "none" for _, u in units[:index]):
        return None  # an ordinary paragraph comes before the item in this chunk: the list began after it
    prev_units = _units(prev_raw) if prev_raw else []
    return _candidate(prev_units, len(prev_units), item_style) if prev_units else None

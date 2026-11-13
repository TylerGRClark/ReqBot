"""Choosing a document style automatically (`--style auto`).

The user's own choice always wins: this module is only asked when no style was named. It reads two
things, the text at the top of the first page (the title block) and the PDF's file name, and compares
them with the families listed in `doc_styles/detection.json`. The rules, in order:

  * The file name and the title block each name zero or more families. If both name something and
    they share no family, the answer is `general` ("conflict": a wrong style does more harm than none).
  * If both name the same family, that family is chosen (confidence high).
  * If only the title block names families, the one that appears EARLIEST wins, because a
    document's own identification comes before its references to other documents; if several
    families are named the confidence drops to medium. If two families start at the same place the
    one with a real style beats `general` (an NIST 800-53 cover also matches "any NIST SP").
  * If only the file name names exactly one family, it is chosen (confidence medium).
  * Otherwise `general`, with the reason "no recognizable document type".

It never raises for odd input: empty text and odd names give `general`. The result says why, so a run
can record it (stats) and a person can see what happened and override it with `--style`.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from core import doc_styles

AUTO = "auto"
_DETECTION_FILE = Path(__file__).resolve().parent.parent / "doc_styles" / "detection.json"
TITLE_BLOCK_CHARS = 1500      # how much of the first page is read
TITLE_BLOCK_ITEMS = 40        # and at most this many of the reader's items from page 1


@dataclass(frozen=True)
class Detection:
    style: str                 # the style to use
    family: str | None         # the family recognized, if any
    confidence: str            # "high", "medium", "low" (a conflict) or "none"
    reason: str                # one plain sentence

    def as_record(self) -> dict:
        return {"family": self.family, "confidence": self.confidence, "reason": self.reason}


@dataclass(frozen=True)
class _Family:
    name: str
    style: str
    title: tuple
    filename: tuple


def _validate(data) -> list[_Family]:
    if not isinstance(data, dict) or not isinstance(data.get("families"), list) or not data["families"]:
        raise ValueError("detection.json needs a non-empty 'families' list")
    out, seen = [], set()
    for fam in data["families"]:
        if not isinstance(fam, dict):
            raise ValueError("every family must be an object")
        name, style = fam.get("family"), fam.get("style")
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise ValueError(f"family names must be unique non-empty strings: {name!r}")
        seen.add(name)
        if not isinstance(style, str):
            raise ValueError(f"family '{name}' needs a style name")
        try:
            doc_styles.load_style(style)
        except (FileNotFoundError, ValueError) as e:
            raise ValueError(f"family '{name}' maps to a style that cannot be loaded: {e}") from e
        flags = re.IGNORECASE if fam.get("title_ignore_case") else 0
        title, filename = [], []
        for key, bucket, fl in (("title_patterns", title, flags), ("filename_patterns", filename, re.IGNORECASE)):
            pats = fam.get(key, [])
            if not isinstance(pats, list) or not all(isinstance(p, str) for p in pats):
                raise ValueError(f"family '{name}': {key} must be a list of strings")
            for p in pats:
                try:
                    bucket.append(re.compile(p, fl))
                except re.error as e:
                    raise ValueError(f"family '{name}': bad pattern {p!r}: {e}") from e
        if not title and not filename:
            raise ValueError(f"family '{name}' has no patterns")
        out.append(_Family(name, style, tuple(title), tuple(filename)))
    return out


@lru_cache(maxsize=1)
def _families() -> tuple:
    return tuple(_validate(json.loads(_DETECTION_FILE.read_text(encoding="utf-8"))))


def families() -> list[dict]:
    """The recognized families and the style each maps to (for tests and documentation)."""
    return [{"family": f.name, "style": f.style} for f in _families()]


def detect_style(title_block: str, filename: str = "") -> Detection:
    """The style for a document, from its first page's text and its file name. See the module docstring."""
    block = (title_block or "")[:TITLE_BLOCK_CHARS]
    name = Path(filename or "").name
    title_hits: dict[str, int] = {}
    file_hits: set[str] = set()
    for fam in _families():
        starts = [m.start() for rx in fam.title for m in [rx.search(block)] if m]
        if starts:
            title_hits[fam.name] = min(starts)
        if any(rx.search(name) for rx in fam.filename):
            file_hits.add(fam.name)
    by_name = {f.name: f for f in _families()}

    def pick(names):   # earliest in the title block; a real style beats `general` when they start together
        return min(names, key=lambda n: (title_hits[n], by_name[n].style == "general"))

    if title_hits and file_hits:
        shared = set(title_hits) & file_hits
        if not shared:
            return Detection("general", None, "low", f"the file name says {', '.join(sorted(file_hits))} but the first page says {', '.join(sorted(title_hits))}; using general")
        fam = by_name[pick(shared)]
        return Detection(fam.style, fam.name, "high", f"the file name and the first page both say {fam.name}")
    if title_hits:
        fam = by_name[pick(title_hits)]
        many = len(title_hits) > 1
        why = f"the first page says {fam.name}" + (f" (earliest of {', '.join(sorted(title_hits))})" if many else "")
        return Detection(fam.style, fam.name, "medium" if many else "high", why)
    specific = [n for n in file_hits if by_name[n].style != "general"]
    if len(file_hits) == 1 or len(specific) == 1:   # one family, or one real style beside `general` (a NIST 800-53 file name also matches "any NIST publication")
        fam = by_name[specific[0] if len(specific) == 1 else next(iter(file_hits))]
        return Detection(fam.style, fam.name, "medium", f"the file name says {fam.name}; the first page gave no title")
    return Detection("general", None, "none", "no recognizable document type")


def resolve(requested: str, items, filename: str = ""):
    """(style, detection) for a run. A style named by the user is loaded as it is and is never overridden (detection is None). `auto` reads the first page's items and the file name."""
    if requested != AUTO:
        return doc_styles.load_style(requested), None
    detection = detect_style(title_block_from_items(items), filename)
    return doc_styles.load_style(detection.style), detection


def title_block_from_items(items) -> str:
    """The title block from a reader's items in reading order: the text of the first page's items, in order.

    `items` are objects with `.text` and `.prov` (a list whose first element has `.page_no`), as Docling's items have; anything else is skipped."""
    parts: list[str] = []
    for item in items:
        prov = getattr(item, "prov", None) or []
        page = getattr(prov[0], "page_no", None) if prov else None
        if page != 1:
            if isinstance(page, int) and page > 1:
                break
            continue
        text = getattr(item, "text", None)
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
            if len(parts) >= TITLE_BLOCK_ITEMS or sum(len(p) + 1 for p in parts) >= TITLE_BLOCK_CHARS:
                break
    return "\n".join(parts)

"""Reference labels beside a document: build them once from the PDF reader's items, look a quote up later.

A document style with a reference grammar (core/reference_grammar.py) labels every item the PDF
reader produced with the paragraph reference it sits under ("Encl A, 5.k", "2.10.b(3)"). The
labels are saved in a small file beside the document's other artifacts, `<doc>_references.json`,
so nothing in the requirement records changes: no new field, no new requirement ID, no change to
the text that is embedded for search. The checklist and the search index read the file when they
work out a row's citation (services/checklist_service.py).

Looking a quote up is deliberately cautious. The quote is searched only on the pages its chunk
covers, and when the same words sit under two different references (a sentence repeated at the
top of several sections) the answer is "none" rather than a guess: a blank citation is better than
a wrong one.
"""

import bisect
import json
import logging
import re
from pathlib import Path
from typing import Sequence

from core.doc_styles import style_record
from core.reference_grammar import Item, label_items, parse_grammar

log = logging.getLogger(__name__)

SIDECAR_SUFFIX = "_references.json"
FORMAT = 1
_KEY_CHARS = 45        # how much of a quote is used to find it
_MIN_KEY_CHARS = 30    # a shorter quote is too easy to match by accident
_PAGE_SLACK = 1        # a chunk's quote may begin one page off from the chunk's own page range
_LEADING_MARKER = re.compile(r"^\W*(?:\d{1,2}\.|[a-z]\.|\(\d{1,2}\)|\([a-z]\))\s+")
_KINDS = {"section_header": "heading", "heading": "heading", "title": "heading",
          "list_item": "list_item", "text": "text", "paragraph": "text"}


def normalize(text: str) -> str:
    """Letters and digits only, lower case: the form in which quotes and items are compared."""
    return re.sub(r"\W+", "", text or "").lower()


def sidecar_path(run_dir: Path, doc_key: str) -> Path:
    return Path(run_dir) / f"{doc_key}{SIDECAR_SUFFIX}"


def item_kind(docling_label: str) -> str:
    """The grammar's item kind for a Docling label such as "DocItemLabel.LIST_ITEM"; "other" is ignored."""
    return _KINDS.get(str(docling_label).split(".")[-1].lower(), "other")


def build_sidecar(items: Sequence[dict], style: dict) -> dict:
    """The sidecar content for a document: each item with its page, its text in comparison form and its reference.

    `items` are dicts with kind, text, marker and page, in reading order. The style must carry a
    reference grammar. Raises ValueError otherwise."""
    if not style.get("reference_grammar"):
        raise ValueError(f"Document style '{style.get('name')}' has no reference grammar")
    grammar = parse_grammar(style["reference_grammar"])
    refs = label_items([Item(i.get("kind", "other"), i.get("text") or "", i.get("marker") or "", i.get("page"))
                        for i in items], grammar)
    rows = []
    for item, ref in zip(items, refs):
        n = normalize(item.get("text") or "")
        if n:
            rows.append({"p": item.get("page"), "n": n, "r": ref.text()})
    return {"format": FORMAT, "style": style_record(style), "items": rows}


def write_sidecar(path: Path, content: dict) -> None:
    Path(path).write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")


class ReferenceLookup:
    """Finds the reference a quote sits under, from the sidecar's items."""

    def __init__(self, content: dict):
        self.style = content.get("style") or {}
        self._items = [i for i in content.get("items", []) if isinstance(i, dict) and i.get("n")]

    def find(self, quote: str, page_start=None, page_end=None) -> str:
        """The reference for `quote`, or "" when it is not found, too short to trust, or sits under
        more than one reference in the pages searched."""
        key = normalize(_LEADING_MARKER.sub("", (quote or "").strip()))[:_KEY_CHARS]
        if len(key) < _MIN_KEY_CHARS:
            return ""
        # the chunk's own pages first; only when the quote is not on them, one page either side. Widening first would make a
        # sentence repeated on neighbouring pages look ambiguous when its pages say which one it is.
        for slack in (0, _PAGE_SLACK):
            found = self._refs_for(key, self._window(page_start, page_end, slack))
            if found:
                return next(iter(found)) if len(found) == 1 else ""
        return ""

    @staticmethod
    def _refs_for(key: str, window: list[dict]) -> set[str]:
        text, starts = "", []
        for i in window:
            starts.append(len(text))
            text += i["n"]
        found: set[str] = set()
        pos = text.find(key)
        while pos != -1:
            found.add(window[bisect.bisect_right(starts, pos) - 1]["r"])
            pos = text.find(key, pos + 1)
        return found

    def _window(self, page_start, page_end, slack: int) -> list[dict]:
        if not isinstance(page_start, int) or not isinstance(page_end, int):
            return self._items
        lo, hi = page_start - slack, page_end + slack
        return [i for i in self._items if isinstance(i.get("p"), int) and lo <= i["p"] <= hi]


def load_lookup(run_dir: Path, doc_key: str) -> "ReferenceLookup | None":
    """The lookup for a document, or None when it has no sidecar or the sidecar cannot be used.
    Never raises: a missing or damaged sidecar means the document is cited as before."""
    path = sidecar_path(run_dir, doc_key)
    if not path.exists():
        return None
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(content, dict) or content.get("format") != FORMAT:
            log.warning("Reference labels ignored (unknown format): %s", path)
            return None
        return ReferenceLookup(content)
    except (OSError, ValueError) as e:
        log.warning("Reference labels ignored (%s): %s", e, path)
        return None

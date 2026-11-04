"""Repair a chunk's stored heading path when it has gone stale. Rules only, no model.

A chunk carries `section_ref_path` / `section_title_path`, the headings it sits under.
In numbered documents (AFIs and the like) the path can stay on an earlier heading
while the chunk's own text has moved on: 5 chunks in a row say "3.6 SCA" while their
paragraphs are 3.9 and 3.10, because the parser only advances the path on a
recognised heading and numbered paragraphs do not always count as one. On the 2026-10-24
library about 28% of the chunks that can be checked had a stale path.

The repair compares the chunk's FIRST numbered paragraph with the last numbered entry
of its path. When the paragraph is not under that entry, the numbered part of the path is
rebuilt from the paragraph's ancestors, using headings the document's own text shows
("3.9. Information System Owners (ISO)."). A chunk whose path already contains its first
paragraph is never touched. A chunk that cannot be resolved keeps its stored path.

An ancestor only counts as a heading when it reads like one: a short title, or a short
"... will:" actor line; never a long sentence, and never an instruction ("Ensure ...").
Otherwise a duty sentence would be shown as the section a row belongs to.

Read-time only: the stored chunk file is not changed. A repaired chunk also carries
`stored_section_ref_path` / `stored_section_title_path`, the parser's own paths: the paragraph map keeps reading full
paragraph text, and the prompt windows keep their section boundaries.
"""
from __future__ import annotations

import copy
import re

from services.checklist_audit import IMPERATIVE_VERBS

_NUM = r"((?:[A-Z]\d{0,2}\.)?\d{1,2}(?:\.\d{1,3})+)"
_LINE = re.compile(r"(?m)^\s*(?:[-*•]\s*)?" + _NUM + r"\.?\s+(.+)$")
_TITLE = re.compile(r"(.{3,140}?(?::|\.(?=\s+[A-Z(])|$))")
MAX_TITLE_WORDS = 12
MAX_ACTOR_LINE_WORDS = 20


def _text(chunk: dict) -> str:
    return chunk.get("raw_text") or chunk.get("text") or ""


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _under(num: str, ref: str) -> bool:
    return num == ref or num.startswith(ref + ".")


def _ancestors(num: str) -> list[str]:
    parts = num.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts))]


def _title(num: str, rest: str) -> str:
    rest = _squash(rest)
    m = _TITLE.match(rest)
    return f"{num}. {m.group(1) if m else rest[:140]}".strip()


_MODALS = frozenset({"will", "shall", "must", "may", "should", "can"})


def _is_instruction(word: str) -> bool:
    """An instruction or duty opener: 'Ensure', 'Ensures', 'Reviews', 'Identifies', 'Will'."""
    w = word.lower().strip(",:;")
    if w in _MODALS or w in IMPERATIVE_VERBS:
        return True
    return (w.endswith("s") and w[:-1] in IMPERATIVE_VERBS) or (w.endswith("es") and w[:-2] in IMPERATIVE_VERBS) \
        or (w.endswith("ies") and w[:-3] + "y" in IMPERATIVE_VERBS)


def _heading_like(title: str) -> bool:
    body = title.split(". ", 1)[1] if ". " in title else title
    words = body.split()
    if not words or _is_instruction(words[0]):
        return False
    return len(words) <= MAX_TITLE_WORDS or (body.rstrip().endswith(":") and len(words) <= MAX_ACTOR_LINE_WORDS)


def _titles(chunks: list[dict]) -> dict[str, str]:
    """{paragraph number: title}: the stored paths first, then the headings the text itself shows."""
    table: dict[str, str] = {}
    for c in chunks:
        refs = [str(r).rstrip(".") for r in (c.get("section_ref_path") or [])]
        titles = [str(t) for t in (c.get("section_title_path") or [])]
        for ref, title in zip(reversed(refs), reversed(titles)):  # paths are aligned from the leaf up when their lengths differ
            table.setdefault(ref, title)
    for c in chunks:
        for num, rest in _LINE.findall(_text(c)):
            table.setdefault(num.rstrip("."), _title(num.rstrip("."), rest))
    return table


def repair_heading_paths(chunks: list[dict]) -> list[dict]:
    """The chunks, in the same order, with a stale heading path rebuilt. Inputs are not changed."""
    table = _titles(chunks)
    numbers = {n.rstrip(".") for c in chunks for n, _ in _LINE.findall(_text(c))}
    out: list[dict] = []
    for chunk in chunks:
        fixed = copy.deepcopy(chunk)
        out.append(fixed)
        refs = [str(r).rstrip(".") for r in (chunk.get("section_ref_path") or [])]
        found = [n.rstrip(".") for n, _ in _LINE.findall(_text(chunk))]
        if not refs or not found:
            continue
        first = found[0]
        if _under(first, refs[-1]):
            continue
        has_children = any(n.startswith(first + ".") for n in numbers)
        chain = [a for a in _ancestors(first) + ([first] if has_children else [])
                 if a in table and _heading_like(table[a])]
        if not chain:
            continue
        kept = [r for r in refs if _under(first, r)]
        new_refs = list(dict.fromkeys(kept + [a for a in chain if a not in kept]))
        titles = [str(t) for t in (chunk.get("section_title_path") or [])]
        stored = dict(zip(reversed(refs), reversed(titles)))
        # the parser's own paths: the paragraph map must not read a shortened title as the paragraph, and the prompt windows
        # (checklist_audit.document_lines) use the stored paths as section identities, so a repair must not move a boundary
        fixed["stored_section_ref_path"] = list(chunk.get("section_ref_path") or [])
        fixed["stored_section_title_path"] = titles
        fixed["section_ref_path"] = new_refs
        fixed["section_title_path"] = [stored.get(r) or table.get(r) or r for r in new_refs]
    return out

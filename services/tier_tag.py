"""The compliance tier the document itself assigns to a requirement: "(T-0)" to "(T-3)" in Air Force publications.

Read straight from the text, no model and no guess. A tag counts for a row only when it sits inside the quote or directly after the marked sentence in the passage
(">> sentence << (T-1)."). A tag earlier in the same line belongs to an earlier sentence, and a tag on a parent paragraph is not inherited: an untagged row gets no tier.
"""
import re

_TAG = re.compile(r"\(\s*T\s*-\s*([0-3])\s*\)", re.IGNORECASE)
_AFTER_MARKER = re.compile(r"<<\W{0,3}?\(\s*T\s*-\s*([0-3])\s*\)", re.IGNORECASE)  # "<< (T-1)", "<<  (T-1).", "<< ( T-1 )"


def tier_of(item: dict) -> str:
    """"T-1" for one tier, "T-0/T-1" when the quote itself carries two different tags, "" when the document gives none."""
    found = {m.group(1) for m in _TAG.finditer(item.get("source_quote") or "")}
    if not found:
        found = {m.group(1) for m in _AFTER_MARKER.finditer(item.get("passage") or "")}
    return "/".join(f"T-{n}" for n in sorted(found))

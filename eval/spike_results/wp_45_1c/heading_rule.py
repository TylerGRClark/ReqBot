"""WP-45.1(c)/(d), heading extension (plan section 6): the deterministic H3 rule for when a leaf heading is used.

Frozen before any heading retrieval was run. Pure functions over the stored `section_title_path`; no I/O, no LLM.

H3 uses a record's LEAF heading (never the whole path: docling mis-nests some headings, so an ancestor can name the wrong
party) when either
  (a) the leaf ends with a colon (a list-introducing heading such as "The DAF Chief Information Officer (SAF/CN) shall:"), or
  (b) an ancestor heading contains "responsibilit" and the leaf is not one of the procedural labels below
      (the typical "ROLES AND RESPONSIBILITIES > 2.17. MAJCOM/DRUs." shape, where the leaf names the actor).
Everything else (topical headings, procedural labels, headings with no responsibilities ancestor) gets no prefix.
"""

import ast
import re

PROCEDURAL_LABELS = frozenset(
    {
        "objectives",
        "policy",
        "methodology",
        "actions",
        "general",
        "declaration",
        "background",
        "responsibilities",
        "scope",
        "purpose",
        "applicability",
        "definitions",
        "references",
        "introduction",
        "overview",
        "unclassified",
    }
)
_NUMBERING = re.compile(r"^\s*(?:section\s+\d+\s*:\s*)?(?:\d+(?:\.\d+)*\.?\s+)*", re.IGNORECASE)


def heading_path(payload):
    path = payload.get("section_title_path") or []
    if isinstance(path, str):
        path = ast.literal_eval(path)
    return [str(p).strip() for p in path if str(p).strip()]


def label(heading):
    """The heading with numbering and punctuation removed, lower-cased, for comparison with the procedural labels."""
    return re.sub(r"[^a-z ]", "", _NUMBERING.sub("", heading).lower()).strip()


def leaf_heading(path):
    return path[-1] if path else ""


def h3_applies(path):
    leaf = leaf_heading(path)
    if not leaf:
        return False
    if leaf.rstrip().endswith(":"):
        return True
    if any("responsibilit" in ancestor.lower() for ancestor in path[:-1]) and label(leaf) not in PROCEDURAL_LABELS:
        return True
    return False

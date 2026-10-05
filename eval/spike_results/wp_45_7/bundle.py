"""WP-45.7: the deterministic evidence-bundle builder for the resolver (scratch only; no LLM, no Qdrant).

Given one candidate quote and the chunks of its document, build the numbered evidence spans the resolver is shown
(docs/PHASE45_WP457_PLAN.md, appendix B and section 5, item 1). Three tiers, one change at a time:

  R0  the candidate quote only (today's Step D.5 information)
  R1  + the candidate's own chunk, the leaf heading, and the governing-clause candidates the existing stem finders produce,
      each marked unverified because those rules were right about 40% of the time (WP-45.1(b))
  R2  + the bounded tail of the previous chunk, the bounded head of the next chunk, and any cross-referenced section that
      can be found in the document

Rules (from the plan):
- All text is whitespace-normalized (newlines and repeated spaces collapsed, soft-hyphenated line breaks rejoined) because
  Docling output carries such artifacts; every later containment check normalizes both sides with `normalize`.
- Window safety: the budget uses a conservative 2.5 characters per token and caps the whole prompt near 6,500 estimated
  tokens, leaving room for the answer inside the pinned 8,192. When the bundle is over budget it is cut from the neighbors
  first, then referenced sections, then the own chunk (kept around the candidate); the candidate, the heading and the stem
  candidates are never cut. If even that cannot fit, the bundle is flagged `untreatable` so the runner never calls Ollama.
- Standard library only (plus the repo's own stem finders); no tokenizer package.
"""

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.enrich_requirements import (  # noqa: E402  (the existing deterministic stem finders, reused unchanged)
    _find_cross_chunk_stem,
    _find_heading_stem,
    _find_same_chunk_stem,
)

CHARS_PER_TOKEN = 2.5
NUM_CTX = 8192
PROMPT_TOKEN_CAP = 6500
BUNDLE_TOKEN_CAP = 3000
ANSWER_RESERVE_TOKENS = 600
NEIGHBOR_CHARS = 800
REFERENCE_CHARS = 600
STEM_CHARS = 400
MIN_SPAN_CHARS = 80
TIERS = ("R0", "R1", "R2")

_SOFT_HYPHEN_BREAK = re.compile(r"(?<=[a-z])[­-]\s*\n\s*(?=[a-z])")
_REF_WORD = re.compile(
    r"\b(?:paragraphs?|para\.?|sections?|sec\.?|enclosures?|appendix|attachment|annex|chapter)\s+"
    r"(?P<num>[A-Z]?\d+(?:\.\d+)*(?:\([a-zA-Z0-9]+\))*)",
    re.IGNORECASE,
)
_REF_CONTROL = re.compile(r"\b[A-Z]{2,4}-\d+(?:\([a-zA-Z0-9]+\))*(?!\w)")


def normalize(text):
    """Collapse whitespace and rejoin soft-hyphenated line breaks; the one normalization every check shares."""
    text = _SOFT_HYPHEN_BREAK.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def estimate_tokens(chars):
    return -(-int(chars) * 2 // 5)  # ceil(chars / 2.5)


def cross_references(text):
    """Cross-references found in already-normalized text: [(display, number-or-id)], in order, without repeats."""
    found, seen = [], set()
    for m in _REF_WORD.finditer(text):
        key = m.group("num").rstrip(".")
        if key.lower() not in seen:
            seen.add(key.lower())
            found.append((m.group(0), key))
    for m in _REF_CONTROL.finditer(text):
        if m.group(0).lower() not in seen:
            seen.add(m.group(0).lower())
            found.append((m.group(0), m.group(0)))
    return found


def resolve_reference(key, chunks):
    """The first chunk whose section path names `key` (a number such as 4.2 or a control id such as AC-2), or None."""
    want = key.lower().rstrip(".")
    for chunk in chunks:
        for element in list(chunk.get("section_ref_path") or []) + list(chunk.get("section_title_path") or []):
            first = normalize(element).split(" ")[0].rstrip(".:").lower() if element else ""
            if first == want or normalize(element).lower().rstrip(".") == want:
                return chunk
    return None


@dataclass
class Span:
    id: str
    kind: str  # candidate, chunk, heading, stem, previous, next, reference
    label: str
    text: str
    unverified: bool = False
    priority: int = 0  # higher is cut first
    trimmable: bool = True
    source: str = ""


@dataclass
class Bundle:
    tier: str
    spans: list = field(default_factory=list)
    unresolved_references: list = field(default_factory=list)
    truncated: list = field(default_factory=list)
    untreatable: bool = False

    def render(self):
        lines = ["Evidence (each span has an id; \"unverified\" spans were found by a rule and may be wrong):"]
        for s in self.spans:
            tag = f"{s.label} (unverified)" if s.unverified else s.label
            lines.append(f'[{s.id}] {tag}: "{s.text}"')
        if self.unresolved_references:
            lines.append("References not found in the evidence: " + ", ".join(self.unresolved_references))
        return "\n".join(lines)

    def chars(self):
        return len(self.render())

    def bundle_hash(self):
        return hashlib.sha256(self.render().encode("utf-8")).hexdigest()[:16]

    def to_dict(self):
        return {
            "tier": self.tier,
            "spans": [
                {"id": s.id, "kind": s.kind, "label": s.label, "text": s.text, "unverified": s.unverified, "source": s.source}
                for s in self.spans
            ],
            "unresolved_references": self.unresolved_references,
            "truncated": self.truncated,
            "untreatable": self.untreatable,
            "chars": self.chars(),
            "bundle_hash": self.bundle_hash(),
        }


def stem_candidates(quote, chunk_id, step_c_by_chunk, chunks_by_id):
    """Every governing-clause candidate the existing finders produce, each labeled with where it came from (not just the
    first match): [(source, text)], without repeats."""
    finders = (
        ("same chunk", lambda: _find_same_chunk_stem(quote, chunk_id, step_c_by_chunk)),
        ("previous chunk", lambda: _find_cross_chunk_stem(chunk_id, step_c_by_chunk, chunks_by_id)),
        ("heading", lambda: _find_heading_stem(quote, chunk_id, chunks_by_id)),
    )
    out, seen = [], set()
    for source, find in finders:
        stem = find()
        if stem and normalize(stem) not in seen:
            seen.add(normalize(stem))
            out.append((source, normalize(stem)))
    return out


def prompt_budget_chars(fixed_tokens):
    """Characters the bundle may use: the smaller of the bundle cap and what is left of the prompt cap after the fixed
    instructions and the answer reserve."""
    room = PROMPT_TOKEN_CAP - int(fixed_tokens) - ANSWER_RESERVE_TOKENS
    return int(min(BUNDLE_TOKEN_CAP, room) * CHARS_PER_TOKEN)


def preflight(fixed_tokens, minimum_bundle_chars, num_ctx=NUM_CTX):
    """True if the fixed instructions, the answer reserve and the smallest allowed bundle fit the window at all."""
    need = int(fixed_tokens) + ANSWER_RESERVE_TOKENS + estimate_tokens(minimum_bundle_chars)
    return need <= min(num_ctx, PROMPT_TOKEN_CAP + ANSWER_RESERVE_TOKENS)


def _around(text, needle, width):
    """At most `width` characters of text, kept around `needle` when it is found, else from the start."""
    if len(text) <= width:
        return text
    pos = text.find(needle) if needle else -1
    if pos < 0:
        return text[:width].rstrip() + " ..."
    start = max(0, min(pos - (width - len(needle)) // 2, len(text) - width))
    cut = text[start : start + width].strip()
    return ("... " if start > 0 else "") + cut + (" ..." if start + width < len(text) else "")


def build(quote, chunk_id, chunks_by_id, tier="R1", step_c_by_chunk=None, fixed_tokens=0):
    """Build the bundle for one candidate. `chunks_by_id` is the document's chunk records keyed by chunk_id;
    `step_c_by_chunk` (chunk_id to that chunk's extracted records) feeds the same-chunk stem finder."""
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}")
    step_c_by_chunk = step_c_by_chunk or {}
    q = normalize(quote)
    bundle = Bundle(tier=tier)
    counter = iter(range(1, 100))

    def add(kind, label, text, **kw):
        bundle.spans.append(Span(id=f"E{next(counter)}", kind=kind, label=label, text=text, **kw))

    add("candidate", "candidate quote", q, priority=0, trimmable=False)
    chunk = chunks_by_id.get(chunk_id)
    if tier != "R0" and chunk is not None:
        body = normalize(chunk.get("raw_text") or "")
        heading = normalize(chunk.get("parent_header_text") or (chunk.get("section_title_path") or [""])[-1])
        add("chunk", "same chunk", body, priority=3, source=f"chunk {chunk_id}")
        if heading:
            add("heading", "heading (leaf)", heading, priority=0, trimmable=False, source=f"chunk {chunk_id}")
        for source, stem in stem_candidates(quote, chunk_id, step_c_by_chunk, chunks_by_id):
            add(
                "stem", f"possible governing clause, found by rule: {source}", stem[:STEM_CHARS],
                unverified=True, priority=0, trimmable=False, source=source,
            )
    if tier == "R2" and chunk is not None:
        ordered = [chunks_by_id[k] for k in sorted(chunks_by_id)]
        prev, nxt = chunks_by_id.get(chunk_id - 1), chunks_by_id.get(chunk_id + 1)
        if prev is not None:
            add("previous", "previous chunk, last lines", normalize(prev.get("raw_text") or "")[-NEIGHBOR_CHARS:], priority=5, source=f"chunk {prev['chunk_id']}")
        if nxt is not None:
            add("next", "next chunk, first lines", normalize(nxt.get("raw_text") or "")[:NEIGHBOR_CHARS], priority=6, source=f"chunk {nxt['chunk_id']}")
        # References are read from the candidate's own text only: scanning the whole chunk would pull in references that
        # belong to other sentences.
        shown = {s.source for s in bundle.spans}
        for display, key in cross_references(q):
            target = resolve_reference(key, ordered)
            if target is None:
                bundle.unresolved_references.append(display)
            elif f"chunk {target['chunk_id']}" in shown:
                # already in the bundle (as a neighbor or the own chunk): say so on that span rather than repeating it
                for span in bundle.spans:
                    if span.source == f"chunk {target['chunk_id']}" and span.kind in ("chunk", "previous", "next"):
                        span.label += f" (also the referenced section {key})"
                        break
            else:
                add("reference", f"referenced section {key}", normalize(target.get("raw_text") or "")[:REFERENCE_CHARS], priority=4, source=f"chunk {target['chunk_id']}")
                shown.add(f"chunk {target['chunk_id']}")
    _fit(bundle, prompt_budget_chars(fixed_tokens), q)
    return bundle


def _fit(bundle, budget, quote):
    """Cut the lowest-priority spans until the rendered bundle fits `budget` characters; flag it untreatable if the
    spans that must never be cut already exceed the budget."""
    while bundle.chars() > budget:
        cuttable = [s for s in bundle.spans if s.trimmable and len(s.text) > 0]
        if not cuttable:
            bundle.untreatable = True
            return
        span = max(cuttable, key=lambda s: (s.priority, len(s.text)))
        over = bundle.chars() - budget
        keep = len(span.text) - over - 8
        if keep < MIN_SPAN_CHARS:
            bundle.truncated.append(f"{span.id} {span.kind}: dropped")
            bundle.spans.remove(span)
        else:
            span.text = _around(span.text, quote if span.kind == "chunk" else "", keep)
            bundle.truncated.append(f"{span.id} {span.kind}: trimmed")

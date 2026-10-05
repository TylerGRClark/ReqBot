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
MIN_SPAN_CHARS = 80
TIERS = ("R0", "R1", "R2")

_SOFT_HYPHEN_BREAK = re.compile(r"(?<=[a-z])[­-]\s*\n\s*(?=[a-z])")
_ID = r"(?:[A-Z]?\d+(?:\.\d+)*(?:\([a-zA-Z0-9]+\))*|(?-i:[A-Z])\b)"  # 4.2, 3(a), or a single capital letter (Appendix A)
_REF_WORD = re.compile(
    r"\b(?P<word>paragraphs?|para\.?|sections?|sec\.?|enclosures?|appendix|appendices|attachments?|annex(?:es)?|chapters?)\s+"
    rf"(?P<num>{_ID})",
    re.IGNORECASE,
)
# The repository's section parser (pipeline/section_parser.py) stores named headings as SECTION-1, ENCLOSURE-3, APPENDIX-A.
_NAMED = {
    "section": "SECTION", "sections": "SECTION", "sec": "SECTION",
    "enclosure": "ENCLOSURE", "enclosures": "ENCLOSURE",
    "appendix": "APPENDIX", "appendices": "APPENDIX",
    "annex": "ANNEX", "annexes": "ANNEX",
    "attachment": "ATTACHMENT", "attachments": "ATTACHMENT",
}  # plural forms included: "Enclosures A, B, C, and D" must become ENCLOSURE-A, ENCLOSURE-B, ...
# "section 3.7 of Reference (c)", "Section 3252 of Title 10", "paragraph 4 of the January 19 Memorandum": a reference followed by
# "of/in/from" and a capitalized name that is not one of this document's own section words points at ANOTHER document.
_QUALIFIER = re.compile(r"\s*,?\s*(?:of|in|from)\s+(?:the\s+)?(?P<next>[A-Za-z][\w.\-]*)(?:\s+[\w().\-]+)?")
_SECTION_WORDS = {"enclosure", "section", "paragraph", "appendix", "annex", "attachment", "chapter"}


def _external_qualifier(text, pos):
    """The text of an "of <Name>" qualifier at `pos` if it names another document, else None."""
    m = _QUALIFIER.match(text, pos)
    if not m:
        return None
    first = m.group("next")
    if first[:1].isupper() and first.lower() not in _SECTION_WORDS:
        return m.group(0).strip().lstrip(",").strip().rstrip(".,;:")
    return None
_REF_CONTROL = re.compile(r"\b[A-Z]{2,4}-\d+(?:\([a-zA-Z0-9]+\))*(?!\w)")


def normalize(text):
    """Collapse whitespace and rejoin soft-hyphenated line breaks; the one normalization every check shares."""
    text = _SOFT_HYPHEN_BREAK.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def estimate_tokens(chars):
    return -(-int(chars) * 2 // 5)  # ceil(chars / 2.5)


_LIST_NEXT = re.compile(rf"\s*(?:,\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+|\s*&\s*)(?P<num>{_ID})")


def _keys(word, ident):
    """The section-path keys a reference can match: the bare number or letter, and for a named heading the canonical
    KEYWORD-ID form the section parser stores (Appendix A is APPENDIX-A, Enclosure 3 is ENCLOSURE-3)."""
    ident = ident.rstrip(".")
    named = _NAMED.get(word.lower().rstrip("."))
    # the canonical named form goes first: "Enclosure 3" should find ENCLOSURE-3 before a numbered paragraph 3. A bare number is
    # a fair fallback ("Section 4" can be the path element 4); a bare letter is not (it would collide with unrelated list ids).
    if named:
        return [f"{named}-{ident.upper()}"] + ([] if not ident[:1].isdigit() else [ident])
    return [ident]


def cross_references(text):
    """Cross-references found in already-normalized text, in order, without repeats:
    [(display, keys, explicit)], where `keys` are the section-path forms to try (see `_keys`). `explicit` is true for a
    reference introduced by a word ("paragraph 4.2", "Appendix A", "Paragraphs 2.2, 4.1, and 11.2": every member of the
    list is returned) and false for a bare control identifier such as AC-2, which is only a reference if it resolves to a
    section: AES-256 or SHA-384 look the same and are not."""
    found, seen = [], set()

    def add(display, keys, explicit, key=None):
        key = (key or keys[0]).lower()
        if key not in seen:
            seen.add(key)
            found.append((display, keys, explicit))

    for m in _REF_WORD.finditer(text):
        word = m.group("word")
        group = [(m.group(0), _keys(word, m.group("num")))]
        pos = m.end()
        while True:
            nxt = _LIST_NEXT.match(text, pos)
            if not nxt:
                break
            group.append((f"{word} {nxt.group('num')}", _keys(word, nxt.group("num"))))
            pos = nxt.end()
        qualifier = _external_qualifier(text, pos)
        for display, keys in group:
            if qualifier:  # another document: nothing to look up here, and the display says so
                add(f"{display} {qualifier}", [], True, key=keys[0] + " " + qualifier)
            else:
                add(display, keys, True)
    for m in _REF_CONTROL.finditer(text):
        add(m.group(0), [m.group(0)], False)
    return found


def resolve_reference(keys, chunks):
    """The first chunk whose section path names one of `keys` (4.2, AC-2, APPENDIX-A, ...), trying the keys in order so the
    canonical named form wins over a bare number, or None. A single string is accepted for a one-key lookup."""
    for key in [keys] if isinstance(keys, str) else keys:
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
    instructions. The prompt cap already leaves the answer its room inside the window, so the answer reserve is not taken
    off again here; it is checked once, in `preflight`."""
    room = PROMPT_TOKEN_CAP - int(fixed_tokens)
    return int(min(BUNDLE_TOKEN_CAP, room) * CHARS_PER_TOKEN)


def preflight(fixed_tokens, minimum_bundle_chars, num_ctx=NUM_CTX):
    """True if the fixed instructions, the answer reserve and the smallest allowed bundle fit the window at all."""
    prompt = int(fixed_tokens) + estimate_tokens(minimum_bundle_chars)
    return prompt <= PROMPT_TOKEN_CAP and prompt + ANSWER_RESERVE_TOKENS <= num_ctx


def _around(text, needle, width):
    """At most `width` characters of text, kept around `needle` when it is found, else from the start."""
    if len(text) <= width:
        return text
    pos = text.find(needle) if needle else -1
    if pos < 0:
        return text[:width].rstrip() + " ..."
    padding = max(0, width - len(needle))  # a window narrower than the needle starts at the needle, never inside it
    start = max(0, min(pos - padding // 2, len(text) - width))
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
                "stem", f"possible governing clause, found by rule: {source}", stem,
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
        # A referenced section always gets its own excerpt, even if the same chunk is also the previous or next neighbor:
        # neighbors are cut first when the budget binds, and a label on a neighbor would vanish with it.
        shown = set()
        for display, keys, explicit in cross_references(q):
            target = resolve_reference(keys, ordered) if keys else None  # no keys: it cites another document
            if target is None:
                if explicit:  # a bare identifier that resolves to nothing may be an algorithm name, so it is not reported
                    bundle.unresolved_references.append(display)
            elif target["chunk_id"] not in shown:
                label_id = re.sub(r"^(?:para(?:graph)?s?|sec(?:tion)?s?)\.?\s+", "", display, flags=re.IGNORECASE)
                add("reference", f"referenced section {label_id}", normalize(target.get("raw_text") or "")[:REFERENCE_CHARS], priority=4, source=f"chunk {target['chunk_id']}")
                shown.add(target["chunk_id"])
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

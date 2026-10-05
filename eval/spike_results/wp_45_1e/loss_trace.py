"""WP-45.1(e): follow one labeled obligation through the pipeline and name the first step that lost it (offline, no LLM).

Rules fixed in docs/PHASE45_WP451E_PLAN.md before any result was seen:

- Text is compared as tokens: Unicode NFKC (which also undoes ligatures), lowercase, runs of letters and digits; a leading
  list marker is dropped from the piece.
- A piece's *share* in a text is the fraction of the piece's tokens that fall in in-order matching runs of at least three
  tokens (or the whole piece if it is shorter than three). The runs rule keeps scattered common words from counting.
- *Chunked*: share of at least 0.90 in one chunk, or in two consecutive chunks joined (a piece that straddles a boundary).
- *Covered by records*: the union of the pieces' tokens matched by the source quotes of the records in the piece's chunks.
  Share at least 0.90 is covered, from 0.50 up to 0.90 partly covered, below 0.50 not covered. Several records can jointly
  cover a piece.
- Stages are nested: Step C records, then the ones that survive Step D, then (production only) the ones in the live index.
  The first stage where the piece is no longer covered is where it was lost.
"""

import difflib
import re
import sys
import unicodedata
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import segment as S  # noqa: E402

COVERED = 0.90
PARTIAL = 0.50
MIN_RUN = 3
TOKEN = re.compile(r"[a-z0-9]+")

LOSS_NAMES = {
    "extracted": ("not_extracted", "partly_extracted"),
    "survived_step_d": ("rejected_step_d", "rejected_step_d"),
    "indexed": ("not_indexed", "not_indexed"),
}


def tokens(text, drop_marker=True):
    if drop_marker:
        m = S.LIST_MARKER.match(text)
        if m:
            text = text[m.end() :]
    return TOKEN.findall(unicodedata.normalize("NFKC", text).lower())


def matched_indices(piece, other):
    """Indices of the piece's tokens that fall in matching runs (of at least MIN_RUN tokens) with the other token list."""
    if not piece or not other:
        return set()
    need = min(MIN_RUN, len(piece))
    sm = difflib.SequenceMatcher(None, piece, other, autojunk=False)
    out = set()
    for block in sm.get_matching_blocks():
        if block.size >= need:
            out.update(range(block.a, block.a + block.size))
    return out


def status(share):
    return "covered" if share >= COVERED else "partial" if share >= PARTIAL else "none"


def chunk_ids_holding(piece, chunk_tokens):
    """Ids of the chunk(s) that hold the piece: one chunk at share >= COVERED, else two consecutive chunks joined."""
    n = len(piece)
    if not n:
        return []
    ids = sorted(chunk_tokens)
    hits = [c for c in ids if len(matched_indices(piece, chunk_tokens[c])) / n >= COVERED]
    if hits:
        return hits
    for a, b in zip(ids, ids[1:]):
        if len(matched_indices(piece, chunk_tokens[a] + chunk_tokens[b])) / n >= COVERED:
            return [a, b]
    return []


def union_share(piece, quotes):
    covered = set()
    for q in quotes:
        covered |= matched_indices(piece, q)
    return len(covered) / len(piece) if piece else 0.0


def trace_piece(text, chunk_tokens, extracted, normalized, indexed=None, failure_codes=None):
    """Trace one obligation text.

    chunk_tokens: {chunk_id: token list}; extracted: Step C records [{requirement_id, chunk_id, source_quote}];
    normalized: the Step D survivors (Step D gives records new ids, so they are matched by chunk and quote text, never by
    id); indexed: the set of normalized requirement ids in the live index, or None when the run was never indexed;
    failure_codes: {Step C requirement_id: Step D rejection code}, used by the caller to name the code. Returns the
    first loss, the share and status at each stage, and the records involved.
    """
    piece = tokens(text)
    chunks = chunk_ids_holding(piece, chunk_tokens)
    out = {
        "tokens": len(piece),
        "chunk_ids": chunks,
        "shares": {},
        "status": {},
        "first_loss": None,
    }
    if not chunks:
        out["first_loss"] = "never_chunked"
        return out
    here = [r for r in extracted if r["chunk_id"] in chunks]
    kept = [r for r in normalized if r["chunk_id"] in chunks]
    stages = [("extracted", here), ("survived_step_d", kept)]
    if indexed is not None:
        stages.append(("indexed", [r for r in kept if r["requirement_id"] in indexed]))
    for name, recs in stages:
        share = union_share(piece, [tokens(r["source_quote"], drop_marker=False) for r in recs])
        out["shares"][name] = round(share, 4)
        out["status"][name] = status(share)
        if out["first_loss"] is None and out["status"][name] != "covered":
            out["first_loss"] = LOSS_NAMES[name][0 if out["status"][name] == "none" else 1]
            out["lost_at"] = name

    def touches(r):
        return bool(matched_indices(piece, tokens(r["source_quote"], drop_marker=False)))

    out["covering_extracted"] = [r["requirement_id"] for r in here if touches(r)]
    out["covering_surviving"] = [r["requirement_id"] for r in kept if touches(r)]
    # Step D gives survivors new ids, so a Step C record survived if a survivor has the same chunk and quote; one that did
    # not is rejected whether or not Step D wrote a failure record for it (a duplicate merge, for example, writes none).
    kept_quotes = {(r["chunk_id"], r["source_quote"].strip()) for r in normalized}
    out["rejected_ids"] = [
        r["requirement_id"]
        for r in here
        if touches(r) and (r["chunk_id"], r["source_quote"].strip()) not in kept_quotes
    ]
    out["covered_through_last_stage"] = out["first_loss"] is None
    return out

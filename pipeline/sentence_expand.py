"""WP-45.14: expand an extracted quote to the whole sentence it sits in (pure functions; NOT wired into the pipeline, see docs/PHASE45_WP4514_PLAN.md).

Owner's rule: a requirement is extracted as at minimum the whole sentence, never an incomplete one. `expand` finds the quote in its chunk's text and returns the complete sentence around
it, verbatim (whitespace tidied), so a list tail such as "installation of vulnerable applications, and other breaches of existing AF or DoD policy" becomes the sentence it belongs to,
and two pieces of one sentence expand to the same text (the caller merges them).

A sentence ends at `.`, `?` or `!` (optionally spaced before it and followed by closing quotes or brackets) when the next thing is a space and a capital letter, a digit or an opening
bracket, or the end of the paragraph. It does not end after an abbreviation, a single capital letter, a paragraph number such as `3.6.1.1.`, or at `;` or `:` (so the sentence of a list
item starts where the list's sentence starts). A paragraph unit starts at a line that opens with a bullet or a numbered/lettered marker; the marker itself is not part of the sentence.
"""
import re

MAX_SENTENCE_CHARS = 700
MIN_QUOTE_WORDS = 2  # a one-word quote ("CNSI") is a table cell or a term, not a sentence fragment; it is not expanded

_ABBREVIATIONS = frozenset({
    "u.s", "e.g", "i.e", "no", "nos", "fig", "figs", "sec", "para", "paras", "inc", "vs", "etc", "dr", "mr", "mrs", "ms", "st", "approx", "cf", "al", "dept", "gov", "gen", "col",
    "lt", "sgt", "maj", "capt", "cdr", "adm", "jr", "sr", "ref", "refs", "vol", "chap", "art", "para", "ch", "pp", "p", "ed", "eds", "est", "max", "min",
})
_MARKER_BODY = r"(?:(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?|\d{1,3}[.)]|\([a-zA-Z0-9]{1,3}\)|[a-zA-Z][.)])"  # 3.6.1.1.  1.  2)  (a)  a.  A.
_MARKER = re.compile(r"(?m)^[ \t]*(?:[-•*][ \t]+(?=\S)|(?:[-•*][ \t]*)?(?=" + _MARKER_BODY + r"[ \t]+\S))")
_LEADING_NUMBER = re.compile(r"^[ \t]*(?:[-•*][ \t]+)?(?:" + _MARKER_BODY + r"[ \t]+)*")  # a bare bullet and any run of markers ("- a. ", "3. (a) ")
_TERMINAL = re.compile(r"\s*([.?!])([\"')\]]*)(?=\s+[A-Z0-9(\[\"“]|\s*$)")
_INLINE_MARKER = re.compile(r"^(?:(?:\([a-zA-Z0-9]{1,3}\)|[a-z]\.|\d{1,3}[.)])[ \t]+)+")  # "(g) ", "a. ", "3) " left at the start of a sentence found mid-line
_TIDY_SPACE_BEFORE = re.compile(r"\s+([.,;:)\]])")


def tidy(text: str) -> str:
    """Whitespace collapsed; no space before closing punctuation or after an opening bracket (how the pipeline already tidies quotes)."""
    return _TIDY_SPACE_BEFORE.sub(r"\1", re.sub(r"\s+", " ", text or "").strip()).replace("( ", "(")


def flex_pattern(text: str):
    """A pattern that finds `text` in the chunk's text whatever the spacing: any run of whitespace between words, optional spaces inside brackets and before closing punctuation."""
    pieces = []
    for word in (text or "").split():
        m = re.match(r"^(\(?)(.*?)([.,;:)\]]*)$", word)
        opener, core, closer = m.group(1), m.group(2), m.group(3)
        piece = (r"\(\s*" if opener else "") + re.escape(core)
        for ch in closer:
            piece += r"\s*" + re.escape(ch)
        pieces.append(piece)
    return re.compile(r"\s+".join(pieces)) if pieces else None


def _is_sentence_end(text: str, m: re.Match) -> bool:
    """Whether the terminal punctuation matched at `m` really ends a sentence (not an abbreviation, a lone initial, a paragraph number or a decimal)."""
    if m.group(1) != ".":
        return True
    before = text[: m.start(1)].rstrip()
    token = re.search(r"[\w.()/-]+$", before)
    raw_token = token.group(0) if token else ""
    word = raw_token.strip("()").lower().rstrip(".")
    if not word:
        return True
    if raw_token.endswith(")"):
        return True  # "... of reference (k)." ends the sentence; a bracketed label is not an initial
    if word in _ABBREVIATIONS or (len(word) == 1 and raw_token[:1].isupper()):  # an initial such as "J."
        return False
    num = re.search(r"(?:^|\s)((?:[A-Za-z]{1,2})?\d+(?:\.\d+)+)$", before)
    if num is not None and re.fullmatch(r"(?:[a-z]{1,2})?\d+(?:\.\d+)*", word):
        lead = before[: num.start()].rstrip()
        if not lead or lead[-1] in ".?!":  # a number that opens a sentence is a paragraph number ("3.6.1.1."); one after words is a citation ("DoDI 8510.01.") that can end it
            return False
    return True


def split_sentences(text: str) -> list[str]:
    """The sentences of `text`, verbatim and in order, cut with the same boundary rules `expand` uses (an abbreviation, a lone initial or a paragraph number does not end one)."""
    out, start = [], 0
    for m in _TERMINAL.finditer(text or ""):
        if _is_sentence_end(text, m):
            piece = text[start: m.end()].strip()
            if piece:
                out.append(piece)
            start = m.end()
    tail = (text or "")[start:].strip()
    if tail:
        out.append(tail)
    return out


def _unit_bounds(text: str, s: int, e: int) -> tuple[int, int]:
    starts = [m.start() for m in _MARKER.finditer(text)]
    unit_start = max([p for p in starts if p <= s], default=0)
    unit_end = min([p for p in starts if p >= e and p > unit_start], default=len(text))
    return unit_start, unit_end


def expand(quote: str, chunk_text: str) -> tuple[str, str]:
    """(text, status) for a quote and the text of its chunk. status:
    expanded      the whole sentence around the quote, longer than the quote
    unchanged     the quote already is a whole sentence
    not_located   the quote was not found in the chunk text; returned as given
    too_long      the whole sentence exceeds MAX_SENTENCE_CHARS; the quote is returned as given
    too_short     a single word (a table cell or a term); returned as given
    ambiguous     the quote occurs more than once in the chunk, so the sentence it came from cannot be told; returned as given
    """
    if len((quote or "").split()) < MIN_QUOTE_WORDS:
        return quote, "too_short"
    pat = flex_pattern(quote)
    found = list(pat.finditer(chunk_text or "")) if pat else []
    if not found:
        return quote, "not_located"
    if len(found) > 1:
        return quote, "ambiguous"
    m = found[0]
    s, e = m.span()
    unit_start, unit_end = _unit_bounds(chunk_text, s, e)
    unit = chunk_text[unit_start:unit_end]
    content_start = unit_start + _LEADING_NUMBER.match(unit).end()  # the pattern can match nothing, so it always matches
    start, end = content_start, unit_end
    for t in _TERMINAL.finditer(chunk_text, content_start, unit_end):
        if not _is_sentence_end(chunk_text, t):
            continue
        stop = t.end()
        if stop <= s:
            start = max(start, stop)  # the next sentence begins after this one
        elif stop >= e:
            end = stop
            break
    while start < len(chunk_text) and chunk_text[start].isspace():
        start += 1
    lead = chunk_text[start:s]
    if start < s and lead.strip() and not re.search(r"[.?!:;]", lead) and len(lead.split()) <= 6 and is_complete(quote):
        start = s  # a few words with no punctuation before a quote that opens like a sentence are a term or table cell ("CUI misuse"), not part of it
    marker = _INLINE_MARKER.match(chunk_text[start:end])
    if marker and start + marker.end() <= s:  # drop a list marker that opens the sentence, but never cut into the quote itself
        start += marker.end()
    text = tidy(chunk_text[start:end])
    if len(text) > MAX_SENTENCE_CHARS:
        return quote, "too_long"
    return text, ("unchanged" if tidy(text) == tidy(quote) else "expanded")


def is_complete(quote: str) -> bool:
    """A quote that starts with a capital letter, a digit or an opening bracket and ends with sentence-closing punctuation (or a colon or semicolon that introduces or continues a list)."""
    q = (quote or "").strip()
    if not q:
        return False
    first = next((c for c in q if c.isalnum() or c in "(["), "")
    starts_ok = first.isupper() or first.isdigit() or first in "(["
    return starts_ok and bool(re.search(r"[.?!:;][\"')\]]*$", q))


def _norm_key(text: str) -> str:
    return tidy(text).lower()


def explain_records(records: list[dict], raw_text_by_chunk: dict, section_by_chunk: dict | None = None) -> tuple[list[dict], dict]:
    """Give every record its explained layer: `explained_text`, `explained_parts` and `explain_notes`, built only from pieces of the source. The root (`source_quote`) and the anchor fields are never changed.

    - the sentence the root sits in (the root itself when it is exact, else the exact piece anchoring found: a quote with its list number taken off, a few words trimmed, or the list item of a glued lead-in);
    - for a glued lead-in that anchoring found in the chunk or its heading, the lead-in goes in front ("AFMC will: Identify ...").
    A root that cannot be located is its own explained text, with a note saying so. Records whose explained text is the same sentence in the same chunk are shown once: the first is kept and the
    others' roots are listed in `merged_roots`. Records are copied. Returns (records, counts)."""
    out: list[dict] = []
    seen: dict = {}
    counts: dict = {"merged": 0}
    for rec in records:
        root = (rec.get("source_quote") or "").strip()
        raw = raw_text_by_chunk.get(rec.get("chunk_id"), "")
        status = rec.get("anchor_status")
        end_trimmed = status == "words_trimmed" and rec.get("anchor_trim_side") == "end"  # words at the end that the source lacks are often a table cell read back ("... is End user"); dropping them would lose what tells rows apart
        piece = root if status in (None, "exact") or end_trimmed else (rec.get("anchor_text") or root) if status in ("marker_removed", "words_trimmed", "lead_in_joined", "lead_in_from_heading", "lead_in_not_in_source") else root
        text, outcome = expand(piece, raw)
        reverted = False
        if status == "words_trimmed" and not end_trimmed and outcome not in ("expanded", "unchanged"):
            text, outcome, reverted = root, "not_located", True  # trimming dropped the model's words and no sentence was found to take their place: keep the root rather than a shorter piece
        counts[outcome] = counts.get(outcome, 0) + 1
        notes, parts = [], []
        lead = rec.get("anchor_lead_in") if status in ("lead_in_joined", "lead_in_from_heading") else None
        lead_origin = "heading" if status == "lead_in_from_heading" else "chunk"
        if not lead and outcome in ("expanded", "unchanged") and status in (None, "exact", "marker_removed", "words_trimmed") and not end_trimmed:
            from pipeline import lead_in as _lead_in  # imported here: lead_in uses this module's helpers
            start = rec.get("anchor_start")
            if start is None:
                located = flex_pattern(piece).search(raw) if raw else None
                start = located.start() if located else None
            cid = rec.get("chunk_id")
            prev_cid = cid - 1 if isinstance(cid, int) else None
            # the previous chunk is only consulted when it is in the same section: a list that continues across a chunk boundary stays in its section, and another section's lead-in must not be borrowed
            same_section = section_by_chunk is None or (prev_cid in section_by_chunk and section_by_chunk.get(prev_cid) == section_by_chunk.get(cid))
            lead = _lead_in.find_lead_in(raw, start, raw_text_by_chunk.get(prev_cid, "") if prev_cid is not None and same_section else "")
            if lead and tidy(text).lower().startswith(tidy(lead).lower()):
                lead = None
            if lead:
                lead_origin = "rule"
                notes.append("lead-in attached from the line above that ends with a colon")
        lead_match = _LEADING_NUMBER.match(root)
        only_marker = outcome in ("expanded", "unchanged") and tidy(text).lower() == tidy(root[lead_match.end():] if lead_match else root).lower() and tidy(text).lower() != tidy(root).lower()
        if only_marker:
            notes.append("list number or dash taken off")
        elif outcome == "expanded":
            notes.append("expanded to the whole sentence")
        elif outcome == "unchanged":
            notes.append("already a whole sentence")
        else:
            notes.append(f"not expanded: {outcome.replace('_', ' ')}")  # expand() returns the piece as given in these cases
        if end_trimmed:
            notes.append("end of the quote is not in the source; kept as returned")
        elif reverted:
            notes.append("front words not in the source were kept: no sentence was found to replace them")
        elif status in ("marker_removed", "words_trimmed", "lead_in_joined", "lead_in_from_heading", "lead_in_not_in_source"):
            notes.append({"marker_removed": "list number or dash taken off", "words_trimmed": "a few words at the front that are not in the source taken off",
                          "lead_in_joined": "lead-in kept (found in the chunk)", "lead_in_from_heading": "lead-in kept (found in the chunk's heading)",
                          "lead_in_not_in_source": "lead-in dropped (not in the source)"}[status])
        if lead:
            parts.append({"kind": "lead_in", "text": lead, "origin": lead_origin})
        parts.append({"kind": "sentence", "text": text, "origin": "rule"})
        explained = tidy((lead + " " if lead else "") + text)
        key = (rec.get("chunk_id"), _norm_key(explained))
        mergeable = outcome in ("expanded", "unchanged")  # a root that could not be placed (or occurs twice) is its own record: its text matching another's says nothing about the sentence
        if mergeable and key in seen:
            kept = out[seen[key]]
            kept.setdefault("merged_roots", []).append(root)
            if "merged with other roots in the same sentence" not in kept["explain_notes"]:
                kept["explain_notes"].append("merged with other roots in the same sentence")
            counts["merged"] += 1
            continue
        if mergeable:
            seen[key] = len(out)
        new = dict(rec)
        new["explained_text"] = explained
        new["explained_parts"] = parts
        new["explain_notes"] = notes
        out.append(new)
    return out, counts

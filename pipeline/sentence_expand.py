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

_ABBREVIATIONS = frozenset({
    "u.s", "e.g", "i.e", "no", "nos", "fig", "figs", "sec", "para", "paras", "inc", "vs", "etc", "dr", "mr", "mrs", "ms", "st", "approx", "cf", "al", "dept", "gov", "gen", "col",
    "lt", "sgt", "maj", "capt", "cdr", "adm", "jr", "sr", "ref", "refs", "vol", "chap", "art", "para", "ch", "pp", "p", "ed", "eds", "est", "max", "min",
})
_MARKER = re.compile(r"(?m)^[ \t]*(?:[-•*][ \t]+(?=\S)|(?:[-•*][ \t]*)?(?=(?:(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?|\([a-zA-Z0-9]{1,3}\)|[a-z]\.)[ \t]+\S))")
_LEADING_NUMBER = re.compile(r"^[ \t]*(?:[-•*][ \t]*)?(?:(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?|\([a-zA-Z0-9]{1,3}\)|[a-z]\.)[ \t]+")
_TERMINAL = re.compile(r"\s*([.?!])([\"')\]]*)(?=\s+[A-Z0-9(\[\"“]|\s*$)")
_INLINE_MARKER = re.compile(r"^(?:\([a-zA-Z0-9]{1,3}\)|[a-z]\.|\d{1,3}[.)])[ \t]+")  # "(g) ", "a. ", "3) " left at the start of a sentence found mid-line
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
    if re.fullmatch(r"(?:[a-z]{1,2})?\d+(?:\.\d+)*", word) and re.search(r"(?:^|\s)(?:[A-Za-z]{1,2})?\d+(?:\.\d+)+$", before) is not None:
        return False  # a paragraph number such as "3.6.1.1" or "A2.3"
    return True


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
    """
    pat = flex_pattern(quote)
    m = pat.search(chunk_text or "") if pat else None
    if not m:
        return quote, "not_located"
    s, e = m.span()
    unit_start, unit_end = _unit_bounds(chunk_text, s, e)
    unit = chunk_text[unit_start:unit_end]
    content_start = unit_start + (_LEADING_NUMBER.match(unit).end() if _LEADING_NUMBER.match(unit) else 0)
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

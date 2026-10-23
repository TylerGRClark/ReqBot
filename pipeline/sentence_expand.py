"""Sentence helpers shared by the explained layer and the lead-in rule (pure functions), and the explained layer itself.

`tidy`, `flex_pattern`, `split_sentences` and `is_complete` are used by pipeline/lead_in.py and the fragmentation measurement. A sentence ends at `.`, `?`
or `!` (optionally spaced before it and followed by closing quotes or brackets) when the next thing is a space and a capital letter, a digit or an opening bracket, or the end of the
paragraph. It does not end after an abbreviation, a single capital letter or a paragraph number such as `3.6.1.1.`.

`explain_records` builds each record's explained layer from a clause found by clause labeling (pipeline/clause_labeling.py): the sentence is the clause with its list marker taken
off, and a list item gets its lead-in from pipeline/lead_in.find_lead_in. The old quote-to-sentence stretching (`expand`) and the merging of records that stretched to the same sentence
were deleted with the list-writing extraction step (design: reqbot-agent-docs history/extraction-replacement-design_2026-10-22.md, section 3): a clause already is a whole line of
the document, so there is nothing to stretch and no two rows share one.
"""
import re

_ABBREVIATIONS = frozenset({
    "u.s", "e.g", "i.e", "no", "nos", "fig", "figs", "sec", "para", "paras", "inc", "vs", "etc", "dr", "mr", "mrs", "ms", "st", "approx", "cf", "al", "dept", "gov", "gen", "col",
    "lt", "sgt", "maj", "capt", "cdr", "adm", "jr", "sr", "ref", "refs", "vol", "chap", "art", "para", "ch", "pp", "p", "ed", "eds", "est", "max", "min",
})
_MARKER_BODY = r"(?:(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?|\d{1,3}[.)]|\([a-zA-Z0-9]{1,3}\)|[a-zA-Z][.)])"  # 3.6.1.1.  1.  2)  (a)  a.  A.
_MARKER = re.compile(r"(?m)^[ \t]*(?:[-•*][ \t]+(?=\S)|(?:[-•*][ \t]*)?(?=" + _MARKER_BODY + r"[ \t]+\S))")
_LEADING_NUMBER = re.compile(r"^[ \t]*(?:[-•*][ \t]+)?(?:" + _MARKER_BODY + r"[ \t]+)*")  # a bare bullet and any run of markers ("- a. ", "3. (a) ")
_TERMINAL = re.compile(r"\s*([.?!])([\"')\]]*)(?=\s+[A-Z0-9(\[\"“]|\s*$)")
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
    """The sentences of `text`, verbatim and in order (an abbreviation, a lone initial or a paragraph number does not end one)."""
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


def is_complete(quote: str) -> bool:
    """A quote that starts with a capital letter, a digit or an opening bracket and ends with sentence-closing punctuation (or a colon or semicolon that introduces or continues a list)."""
    q = (quote or "").strip()
    if not q:
        return False
    first = next((c for c in q if c.isalnum() or c in "(["), "")
    starts_ok = first.isupper() or first.isdigit() or first in "(["
    return starts_ok and bool(re.search(r"[.?!:;][\"')\]]*$", q))


def explain_records(records: list[dict], raw_text_by_chunk: dict, section_by_chunk: dict | None = None) -> tuple[list[dict], dict]:
    """Give every record its explained layer: `explained_text`, `explained_parts` and `explain_notes`, built only from pieces of the source. The root (`source_quote`, the clause)
    and the anchor fields are never changed.

    - the sentence: the clause with a leading list marker or paragraph number taken off ("a. Identify ..." -> "Identify ...");
    - a list item gets the lead-in that governs it in front ("AFMC will: Identify ..."): the nearest earlier line ending with a colon, in the same chunk or, when the list began
      there and the previous chunk is in the same section, at the end of the previous chunk (pipeline/lead_in.find_lead_in, unchanged).
    Records are copied, one out for each one in (no merging). Returns (records, counts)."""
    from pipeline import lead_in as _lead_in  # imported here: lead_in uses this module's helpers
    out: list[dict] = []
    counts: dict = {"marker_removed": 0, "lead_in_attached": 0}
    for rec in records:
        root = (rec.get("source_quote") or "").strip()
        lead_match = _LEADING_NUMBER.match(root)
        body = root[lead_match.end():].strip() if lead_match else root
        text = tidy(body) or tidy(root)
        notes: list[str] = []
        if text != tidy(root):
            notes.append("list number or dash taken off")
            counts["marker_removed"] += 1
        cid = rec.get("chunk_id")
        raw = raw_text_by_chunk.get(cid, "")
        prev_cid = cid - 1 if isinstance(cid, int) else None
        # the previous chunk is only consulted when it is in the same section: a list that continues across a chunk boundary stays in its section, and another section's lead-in must not be borrowed
        same_section = section_by_chunk is None or (prev_cid in section_by_chunk and section_by_chunk.get(prev_cid) == section_by_chunk.get(cid))
        lead = _lead_in.find_lead_in(raw, rec.get("anchor_start"), raw_text_by_chunk.get(prev_cid, "") if prev_cid is not None and same_section else "")
        if lead and text.lower().startswith(tidy(lead).lower()):
            lead = None
        parts = []
        if lead:
            notes.append("lead-in attached from the line above that ends with a colon")
            counts["lead_in_attached"] += 1
            parts.append({"kind": "lead_in", "text": lead, "origin": "rule"})
        parts.append({"kind": "sentence", "text": text, "origin": "rule"})
        new = dict(rec)
        new["explained_text"] = tidy((lead + " " if lead else "") + text)
        new["explained_parts"] = parts
        new["explain_notes"] = notes
        out.append(new)
    return out, counts

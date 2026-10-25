"""Audit-layout helpers for the checklist (WP-46.1): who a row applies to, the document's own passage around the quote, and specific rule-based flags.

Pure functions, no model call, no I/O. Everything shown to an auditor here is copied from the document (a heading, or the text of the quote's chunk); the flags are
hints for a reader, never a reason to drop a row.

`applies_to` is the frozen WP-45.1(d) rule "H3" (eval/spike_results/wp_45_1c/heading_rule.py): a record's LEAF heading names the responsible party when it ends with a colon
(a list-introducing heading) or sits under a "responsibilit..." ancestor and is not a procedural label. Never the whole path: Docling mis-nests some headings.
"""
import re

PROCEDURAL_LABELS = frozenset(
    {
        "objectives", "policy", "methodology", "actions", "general", "declaration", "background", "responsibilities", "scope",
        "purpose", "applicability", "definitions", "references", "introduction", "overview", "unclassified",
    }
)
_NUMBERING = re.compile(r"^\s*(?:section\s+\d+\s*:\s*)?(?:\d+(?:\.\d+)*\.?\s+)*", re.IGNORECASE)
_MODAL = re.compile(r"\b(shall|must|will|should|may|required|is responsible|are responsible|is to|are to|ensure|ensures)\b", re.IGNORECASE)
_LIST_MARKER = re.compile(r"^\s*\(?([A-Za-z]|\d{1,3})[.)]\s")
# Wording that defines or describes instead of requiring ("... are referred to as events", "... means ...", "... breaks down ..."). Deliberately narrow: AFIs state duties in
# many shapes ("Issues cyber orders ...", "CFPs implement ..."), and a broad "no obligation word" test flagged a third of a real checklist.
# "This Instruction applies to ...", "It also applies to ...", "does not apply to ...": who the document covers. Rated "not a requirement" by the owner (WP-45.12 ratings); it tells the
# reader who the other rows apply to, so the row is kept and hinted, never dropped.
_APPLICABILITY = re.compile(
    r"\b(?:this|these)\s+(?:instruction|manual|publication|policy|directive|issuance|document|supplement|chapter|section)\s+(?:also\s+)?(?:applies|apply|does\s+not\s+apply|do\s+not\s+apply)\s+to\b"
    r"|^\W*(?:\d+(?:\.\d+)*\.?\s+)?(?:it|they)\s+(?:also\s+)?(?:applies|apply)\s+to\b", re.IGNORECASE)  # adjacent words only: "requires commanders to apply" and "to which this instruction applies must" do not match
_DEFINITION_CUE = re.compile(r"\b(?:is|are|was|were) (?:referred to|defined|known|called|termed|considered) (?:as|to)\b|\bmeans\b|\bis defined\b|\brefers? to\b|\bbreaks? down\b|\bfor example\b|\bsuch as\b", re.IGNORECASE)
# Verbs that open an imperative requirement ("Identify the likely root cause ..."). A hint, not a grammar: a quote that opens with one and has no modal states its duty
# but not who has it, so the reader must take the actor from the heading or the passage.
IMPERATIVE_VERBS = frozenset(
    {
        "identify", "ensure", "establish", "coordinate", "provide", "maintain", "report", "develop", "review", "conduct", "implement", "perform",
        "submit", "notify", "document", "assess", "validate", "monitor", "approve", "oversee", "manage", "support", "execute", "plan", "prepare",
        "protect", "retain", "verify", "update", "train", "advise", "attend", "collaborate", "direct", "designate", "determine", "evaluate",
        "obtain", "request", "research", "safeguard", "secure", "track", "use", "comply", "advocate", "participate", "forward", "complete",
    }
)
PASSAGE_TAIL_CHARS = 500  # of the previous chunk, when the quote starts mid-sentence or is a list item
MARK_OPEN, MARK_CLOSE = ">> ", " <<"


def strip_numbering(heading: str) -> str:
    return _NUMBERING.sub("", heading or "", count=1).strip()


def _label(heading: str) -> str:
    return re.sub(r"[^a-z ]", "", strip_numbering(heading).lower()).strip()


def applies_to(section_title_path) -> str:
    """The leaf heading (numbering removed) when the H3 rule says it names the responsible party; otherwise an empty string."""
    path = [str(p).strip() for p in (section_title_path or []) if str(p).strip()]
    if not path:
        return ""
    leaf = path[-1]
    if leaf.rstrip().endswith(":") or (any("responsibilit" in a.lower() for a in path[:-1]) and _label(leaf) not in PROCEDURAL_LABELS):
        return strip_numbering(leaf)
    return ""


def starts_mid_sentence(quote: str) -> bool:
    """True if the first letter of the quote is lowercase: the quote continues a clause that began before it."""
    for ch in quote or "":
        if ch.isalpha():
            return ch.islower()
    return False


def has_list_marker(quote: str) -> bool:
    return bool(_LIST_MARKER.match(quote or ""))


def _is_verb(word: str, verbs) -> bool:
    """The word is one of the verbs, or its third-person form ("Supports", "Establishes", "Coordinates"): AFIs list duties that way under a role heading."""
    return word in verbs or (word.endswith("s") and word[:-1] in verbs) or (word.endswith("es") and word[:-2] in verbs)


_PARAGRAPH_NUMBER = re.compile(r"^\W*\d+(?:\.\d+)*\.?\s+")


def _first_word(quote: str) -> str:
    text = re.sub(r"^\s*[-•*]\s*", "", quote or "", count=1)
    text = _PARAGRAPH_NUMBER.sub("", _LIST_MARKER.sub("", text, count=1), count=1).lstrip("( ")
    m = re.match(r"[A-Za-z][A-Za-z-]*", text)
    return m.group(0).lower() if m else ""


def item_flags(quote: str, source_ref: str, applies: str, extra_verbs=()) -> list[str]:
    """Specific, rule-based hints for the reader. A row with flags is still a row.

    starts_mid_sentence  the quote begins in lower case: it continues a clause that starts earlier (see the passage)
    list_item            the quote is a list item: its lead-in is above it (see the passage)
    table_fragment       the quote looks like a table cell or scrap (a pipe, a Table reference, or a short lower-case start)
    no_stated_actor      the quote gives a duty in the imperative with no modal and no actor, and no responsible-party heading was found
    applicability_statement    who the document applies to ("This Instruction applies to ...", "does not apply to ...")
    definition_or_description  no modal and the wording defines or describes ("referred to as", "means", "breaks down", "such as")
    """
    quote = quote or ""
    flags = []
    mid = starts_mid_sentence(quote)
    if mid:
        flags.append("starts_mid_sentence")
    if has_list_marker(quote):
        flags.append("list_item")
    if "|" in quote or (source_ref or "").strip().lower().startswith("table") or (mid and len(quote) < 60):
        flags.append("table_fragment")
    verbs = IMPERATIVE_VERBS | {v.lower() for v in extra_verbs if " " not in v}
    modal = bool(_MODAL.search(quote))
    imperative = _is_verb(_first_word(quote), verbs)
    if imperative and not modal and not applies:
        flags.append("no_stated_actor")
    if _APPLICABILITY.search(quote):
        flags.append("applicability_statement")
    if not modal and _DEFINITION_CUE.search(quote):
        flags.append("definition_or_description")
    return flags


def _flex_pattern(text: str):
    """A pattern that finds `text` in the document's text whatever the spacing: any run of whitespace between words, and optional spaces inside brackets and before closing
    punctuation (the extraction pipeline tidies "Program ." to "Program." and "( COMPUSEC )" to "(COMPUSEC)"; the document keeps the original)."""
    pieces = []
    for word in (text or "").split():
        m = re.match(r"^(\(?)(.*?)([.,;:)\]]*)$", word)
        opener, core, closer = m.group(1), m.group(2), m.group(3)
        piece = (r"\(\s*" if opener else "") + re.escape(core)
        for ch in closer:
            piece += r"\s*" + re.escape(ch)
        pieces.append(piece)
    return re.compile(r"\s+".join(pieces)) if pieces else None


def locate_quote(quote: str, raw: str, start: int = 0, span: tuple[int, int] | None = None):
    """The match of `quote` in the chunk text `raw`. With `span` (the clause's stored (start, end) offsets) the clause itself is searched first, so a sentence repeated elsewhere in
    the chunk is not marked instead; a row without offsets, or whose quote is not inside them, is found by text search from `start`."""
    pat = _flex_pattern(quote)
    if not pat:
        return None
    if span and 0 <= span[0] < span[1] <= len(raw):
        m = pat.search(raw, span[0], span[1])
        if m:
            return m
    return pat.search(raw, max(start, 0))


def build_passage(quote: str, chunk, prev_chunk=None, flags=(), start: int = 0, span: tuple[int, int] | None = None) -> tuple[str, bool]:
    """(passage, quote_found): the document's own text around the quote, verbatim, with the quote wrapped in >> << markers.

    The passage is the text of the chunk that holds the quote. When the quote starts mid-sentence or is a list item, the tail of the previous chunk is put in front (the
    lead-in is usually there), separated by an ellipsis. `span` is the clause's (start, end) offsets in the chunk text, when the row stores them. If the chunk is missing the passage is empty; if the quote cannot be located the whole chunk is returned unmarked.
    """
    if not chunk:
        return "", False
    raw = chunk.get("raw_text") or chunk.get("text") or ""
    prefix = ""
    if prev_chunk and ({"starts_mid_sentence", "list_item"} & set(flags)):
        tail = (prev_chunk.get("raw_text") or prev_chunk.get("text") or "")[-PASSAGE_TAIL_CHARS:]
        cut = tail.find(" ")
        prefix = "... " + (tail[cut + 1:] if 0 <= cut < len(tail) - 1 and len(tail) == PASSAGE_TAIL_CHARS else tail).strip() + "\n\n"
    m = locate_quote(quote, raw, start, span)
    if not m:
        return (prefix + raw).strip(), False
    return (prefix + raw[: m.start()] + MARK_OPEN + raw[m.start(): m.end()] + MARK_CLOSE + raw[m.end():]).strip(), True


# WP-46.3: the parent paragraph from the document's own numbering. AFIs number paragraphs as a hierarchy (2.5.1.1.7.2 sits under 2.5.1.1.7 under 2.5.1.1), so the paragraph a row
# belongs to is read straight from the document, verbatim; no model and no guess. A row whose number does not look like a dotted paragraph number (a table tag such as "(T-2)")
# gets none.
_DOTTED = re.compile(r"^(?:[A-Z]{1,2})?\d+(?:\.\d+)+$")  # an attachment paragraph ("A2.2.3.1") is a paragraph number too
_PARA_START = re.compile(r"^\W*((?:[A-Z]{1,2})?\d+(?:\.\d+)+)\.?\s+(.*)$", re.DOTALL)
PARENT_TEXT_CHARS = 300


# a paragraph starts at a line that opens with a bullet, or with a numbered/lettered marker (optionally after a bullet)
_MARKER = re.compile(r"(?m)^[ \t]*(?:[-•*][ \t]+(?=\S)|(?:[-•*][ \t]*)?(?=(?:\d+(?:\.\d+)+\.?|\([a-zA-Z0-9]{1,3}\)|[a-z]\.)[ \t]+\S))")
_SENTENCE = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")
_NUMBER_ONLY = re.compile(r"^\W*(?:[A-Z]{1,2})?\d+(?:\.\d+)+\.?$")


def paragraph_units(raw_text: str) -> list[str]:
    """The paragraphs of a chunk: split at numbered/lettered markers when there are at least two, otherwise at sentence ends."""
    starts = sorted({m.start() for m in _MARKER.finditer(raw_text)})
    if len(starts) >= 2:
        # text before the first marker (the end of a paragraph that began in the previous chunk) is a unit of its own
        bounds = ([0] if starts[0] > 0 and raw_text[: starts[0]].strip() else []) + starts + [len(raw_text)]
        return [raw_text[a:b].strip() for a, b in zip(bounds, bounds[1:]) if raw_text[a:b].strip()]
    pieces = [s.strip() for s in _SENTENCE.split(raw_text) if s.strip()]
    if len(pieces) > 1 and _NUMBER_ONLY.match(pieces[0]):  # "3.6. Incident Analysis. ..." must not be cut into "3.6." and "Incident Analysis. ..."
        pieces = [pieces[0] + " " + pieces[1]] + pieces[2:]
    return pieces


def paragraph_map(units) -> dict:
    """{paragraph number: text} from paragraph units in document order; the first unit that starts with a number wins (chunks overlap)."""
    out: dict = {}
    for unit in units:
        m = _PARA_START.match(unit or "")
        if m and m.group(1) not in out:
            out[m.group(1)] = " ".join(m.group(2).split())
    return out


def parent_paragraph(source_ref: str, para_map: dict) -> tuple[str, str]:
    """(parent number, its text) for a dotted paragraph number: the nearest ancestor present in the document ("2.5.1.1.7.2" -> "2.5.1.1.7" -> "2.5.1.1" ...), or ("", "").

    An ancestor made of a single number ("2") is not looked up: top-level headings are already in the section path. The text is cut at a word boundary."""
    ref = (source_ref or "").strip().rstrip(".")
    if not _DOTTED.match(ref):
        return "", ""
    parts = ref.split(".")
    while len(parts) > 2:
        parts = parts[:-1]
        key = ".".join(parts)
        if key in para_map:
            text = para_map[key]
            if _label(text) in PROCEDURAL_LABELS:  # "Responsibilities." names no one; the reader gets nothing rather than a label
                return "", ""
            if len(text) > PARENT_TEXT_CHARS:
                text = text[:PARENT_TEXT_CHARS].rsplit(" ", 1)[0] + " ..."
            return key, text
    return "", ""


# WP-46.1c: a usable citation for every row. `source_ref` is whatever the extractor recorded; it is often empty, or a tier tag such as "(T-2)", or a table name. The citation an auditor
# needs is the paragraph number, so when `source_ref` is not one it is read back from the document: the last paragraph number that opens a line in the passage before the
# requirement, else the nearest numbered heading in the section path. An inferred citation is marked "(inferred)" and never replaces `source_ref`.
_PARAGRAPH_REF = re.compile(r"^[A-Z]{0,2}\d+(?:\.\d+)+$")
_LINE_NUMBER = re.compile(r"(?m)^\W*((?:[A-Z]{1,2})?\d+(?:\.\d+)+)\.?\s")


def citation(source_ref: str, passage: str, section_title_path, quote: str = "", source_ref_origin: str | None = None) -> str:
    """The paragraph citation for a row: `source_ref` when it is a paragraph number; else the paragraph number the quote itself opens with; else an inferred one marked
    "(inferred)" (the last paragraph number opening a line in the passage before the marked requirement, which needs the marker: with no marker the quote was not located and the
    passage says nothing about where it sits; else the nearest numbered heading); else an empty string.

    `source_ref_origin` is how clause labeling found `source_ref` (pipeline/clause_labeling.source_refs). The clause's own paragraph number (own_number) and a table caption
    (table_caption) are cited as they are; a number read from above the clause (number_above) or from the section path (section_path) is marked "(inferred)"; none means there
    was nothing, and the steps above run. Records from before clause labeling have no origin and keep the rule above."""
    ref = (source_ref or "").strip().rstrip(".")
    if source_ref_origin and ref:
        if source_ref_origin in ("number_above", "section_path"):
            return f"{ref} (inferred)"
        if source_ref_origin in ("own_number", "table_caption"):
            return ref
    if _PARAGRAPH_REF.match(ref):
        return ref
    own = _LINE_NUMBER.match((quote or "").lstrip() + " ")
    if own:
        return own.group(1)
    if MARK_OPEN.strip() in (passage or ""):
        found = _LINE_NUMBER.findall(passage.split(MARK_OPEN.strip(), 1)[0])
        if found:
            return f"{found[-1]} (inferred)"
    for heading in reversed([str(p) for p in (section_title_path or [])]):
        m = _LINE_NUMBER.match(heading.strip() + " ")
        if m:
            return f"{m.group(1)} (inferred)"
    return ""


# A row from a table is cited by the table, not by a paragraph number. The converter files a table under the last heading it saw (Table 3.1 of AFI 17-203 sits in section 3.3 but
# arrives under "3.3.1. Objectives"; Table 3.2 arrives under 3.7.3), and the document itself calls the table only "Table 3.1". The caption opens the table's chunk; a table that
# runs on into the next chunk has no caption there, so a grid chunk without a caption continues the table of the chunk before it. A chunk that holds prose in front of the table
# (a merged chunk) is only the table's for a quote located after the table starts.
_TABLE_CAPTION = re.compile(r"(?m)^[ \t]*(Table\s+(?:[A-Z]{1,2})?\d+(?:\.\d+)*)\.(?=\s)[ \t]*([^\n|]*)")  # "Table 3.1.", "Table A2.1."; "Table 3.1 shows ..." is prose
_GRID_LINE = re.compile(r"(?m)^[ \t]*\|")
MAX_TABLE_CHUNKS = 6
TABLE_HEADING_CHARS = 120


def _is_table_grid(raw_text: str) -> bool:
    return len(_GRID_LINE.findall(raw_text or "")) >= 2


def _grid_end(raw_text: str, last: bool):
    """The first (or last) non-empty line of a chunk when it is a grid line, else None."""
    lines = [line for line in (raw_text or "").splitlines() if line.strip()]
    line = (lines[-1] if last else lines[0]) if lines else ""
    return line if line.lstrip().startswith("|") else None


def _continues(earlier: str, later: str) -> bool:
    """`later` carries on the grid that `earlier` ends with: it opens on a grid line, `earlier` ends on one, and both have the same number of columns. A table with no caption of
    its own that merely follows a captioned table does not qualify unless it looks like the same grid."""
    end, start = _grid_end(earlier, True), _grid_end(later, False)
    return bool(end and start and end.count("|") == start.count("|"))


_LIST_LINE = re.compile(r"^\s*-\s+\S")


def _list_key_label(chunks: dict, chunk_id: int) -> tuple[str, str]:
    """The key to a table's column, set as a bulleted list right after the table under the column's own name (Table 3.1 of AFI 17-203 numbers its "Actions" 1 to 7 in a list under a
    heading "Actions"): a list chunk, or a run of them under the same heading, directly after a captioned table whose grid holds the heading's word. The table's label, else ("", "")."""
    leaf = str(((chunks.get(chunk_id) or {}).get("section_title_path") or [""])[-1]).strip()
    if not leaf:
        return "", ""
    for back in range(MAX_TABLE_CHUNKS):
        chunk = chunks.get(chunk_id - back)
        if chunk is None:
            return "", ""
        raw = chunk.get("raw_text") or ""
        if _is_table_grid(raw):
            grid = " ".join(line for line in raw.splitlines() if line.lstrip().startswith("|"))
            if back == 0 or not re.search(rf"\b{re.escape(leaf)}\b", grid, re.IGNORECASE):
                return "", ""
            return table_label(chunks, chunk_id - back, "")
        lines = [line for line in raw.splitlines() if line.strip()]
        if not lines or not all(_LIST_LINE.match(line) for line in lines) or str(((chunk.get("section_title_path") or [""])[-1])).strip() != leaf:
            return "", ""
    return "", ""


def table_label(chunks: dict, chunk_id, quote: str = "") -> tuple[str, str]:
    """("Table 3.1", "Table 3.1 Incident Reporting Action Matrix") for a row from a table chunk, else ("", ""): the chunk is a table grid and it, or the grid chunks running
    back from it, has a caption such as "Table 3.1.  Incident Reporting Action Matrix.". Read straight from the document; no inference, so no "(inferred)".

    A chunk can also hold prose, or several tables (a merged chunk). So a quote that is located must sit on a grid line, and gets the nearest caption before it; a quote that is not
    located (a row joined from several cells) gets a label only when the chunk is one table with nothing in front of it. Anything else keeps its paragraph citation."""
    if not isinstance(chunk_id, int):
        return "", ""
    for back in range(MAX_TABLE_CHUNKS):
        raw = (chunks.get(chunk_id - back) or {}).get("raw_text") or ""
        if not _is_table_grid(raw):
            return _list_key_label(chunks, chunk_id) if back == 0 else ("", "")
        if back and not _continues(raw, (chunks.get(chunk_id - back + 1) or {}).get("raw_text") or ""):
            return "", ""  # the chunk after this one is not a continuation of its grid
        captions = list(_TABLE_CAPTION.finditer(raw))
        caption = captions[-1] if captions else None  # a chunk behind this one: the table that runs on from it is the last one it holds
        if back == 0:
            first_table = captions[0].start() if captions else _GRID_LINE.search(raw).start()
            pattern = _flex_pattern(quote)
            located = pattern.search(raw) if pattern else None
            if located:
                line_start = raw.rfind("\n", 0, located.start()) + 1
                on_table_line = raw[line_start:].lstrip().startswith("|") or any(c.start() == line_start for c in captions)  # a grid line, or the caption itself
                if located.start() < first_table or not on_table_line:
                    return "", ""  # in the prose in front of, or between, the tables
                caption = ([c for c in captions if c.start() <= located.start()] or [None])[-1]
            elif raw[:first_table].strip() or len(captions) > 1:
                return "", ""  # not located, and prose or several tables make a label a guess
            else:
                caption = captions[0] if captions else None
        if caption:
            number = " ".join(caption.group(1).split())
            title = " ".join(caption.group(2).split()).strip(" .")
            return number, f"{number} {title}".strip()[:TABLE_HEADING_CHARS]
    return "", ""


# A row with no paragraph number to cite is cited by where it sits, read from the document and never inferred: "Front matter" for text ahead of the first numbered paragraph (the cover,
# the compliance statement, a memorandum), or the caption of the figure or table whose unnumbered pages it is on ("Figure A3.1" for a template whose parts carry only roman
# numerals). A numbered paragraph between the caption and the row, or a document with no numbered paragraphs at all, leaves the row with the paragraph rules (no label).
_CAPTION_HEADING = re.compile(r"^\s*((?:Figure|Table)\s+(?:[A-Z]{1,2})?\d+(?:\.\d+)*)\.?(?:\s|$)", re.IGNORECASE)
FRONT_MATTER = "Front matter"
MAX_CAPTION_CHUNKS = 40
_UNSET = object()


def first_numbered_chunk(chunks: dict):
    """The id of the first chunk, in document order, with a line that opens on a dotted paragraph number; None when the document has none."""
    for chunk_id in sorted(c for c in chunks if isinstance(c, int)):
        if _LINE_NUMBER.search((chunks[chunk_id] or {}).get("raw_text") or ""):
            return chunk_id
    return None


def unnumbered_label(chunks: dict, chunk_id, quote: str = "", first_numbered=_UNSET) -> str:
    """"Figure A3.1" for a row on the unnumbered pages that follow a captioned figure or table, "Front matter" for a row ahead of the document's first numbered paragraph, else "".
    `first_numbered` is `first_numbered_chunk(chunks)`, passed in so a document with many such rows reads its chunks once."""
    if not isinstance(chunk_id, int) or chunk_id not in chunks:
        return ""
    own = (chunks[chunk_id] or {}).get("raw_text") or ""
    pattern = _flex_pattern(quote)
    hit = pattern.search(own) if pattern else None
    for back in range(MAX_CAPTION_CHUNKS):
        chunk = chunks.get(chunk_id - back)
        if chunk is None:
            break
        raw = chunk.get("raw_text") or ""
        if back == 0 and hit:
            raw = raw[:hit.start()]  # only what comes before the quote
        if _LINE_NUMBER.search(raw):
            break  # a numbered paragraph is nearer than any caption: the paragraph rules cite this row
        for part in reversed([str(p) for p in (chunk.get("section_title_path") or [])]):
            caption = _CAPTION_HEADING.match(part)
            if caption:
                return " ".join(caption.group(1).split())
    if first_numbered is _UNSET:
        first_numbered = first_numbered_chunk(chunks)
    if first_numbered is None:
        return ""  # the document is not numbered by paragraph: "front matter" would be every row
    if chunk_id < first_numbered:
        return FRONT_MATTER
    if chunk_id == first_numbered and hit:
        first_line = _LINE_NUMBER.search(own)
        if first_line and hit.start() < first_line.start(1):
            return FRONT_MATTER
    return ""


# WP-46.6: the section a row sits in, from the document's own numbering. The converter nests some headings wrongly (a row of 3.6 "Incident Analysis" can arrive under "Actions >
# 3.5.2. Methodology"), and some AFI headings are run-in titles at the start of a paragraph ("3.6. Incident Analysis .  Incident analysis is ...") that are not headings at all.
# So the heading of a number is read from (a) numbered section headings and (b) paragraphs that open with a short Title-Case phrase and a full stop, and a row is placed by its number.
_RUN_IN_TITLE = re.compile(r"^(?P<t>[A-Z][A-Za-z0-9/&'-]*(?:\s+(?:[A-Z][A-Za-z0-9/&'-]*|and|of|the|for|to|in|on|or)){0,7})\s*\.(?:\s+(?=\S)|$)")
SECTION_LEVELS = 2


def heading_map(headings, units) -> dict:
    """{paragraph number: title} from numbered headings (as given) and from run-in titles at the start of numbered paragraphs; a heading wins over a run-in title."""
    out: dict = {}
    for unit in units:
        m = _PARA_START.match(unit or "")
        if m and m.group(1) not in out:
            body = " ".join(m.group(2).split())
            title = _RUN_IN_TITLE.match(body)
            if title:
                out[m.group(1)] = title.group("t").strip()
            elif body.endswith(":") and len(body) <= 600:  # a numbered lead-in paragraph ("2.2.12. AFNC3C, as the lead organization, will:") titles the paragraphs under it
                out[m.group(1)] = re.split(r"(?<=[.!?])\s+(?=[A-Z])", body)[-1]  # of several sentences, the one that introduces the list ("... mission. The AFOSI:")
    for heading in headings:
        m = _PARA_START.match((str(heading) + " ") if heading else "")
        if m:
            out[m.group(1)] = " ".join(m.group(2).split()).strip(" .")
    return out


def section_heading(citation: str, hmap: dict) -> str:
    """"3.6 Incident Analysis" (up to two levels, outermost first, "3.6 Incident Analysis > 3.6.1 Actions") for the nearest numbered ancestors of the row's paragraph number
    that have a title; empty when the number is missing or no ancestor has one."""
    ref = (citation or "").replace("(inferred)", "").strip().rstrip(".")
    if not _PARAGRAPH_REF.match(ref):
        return ""
    parts = ref.split(".")
    found = []
    while len(parts) >= 2:
        key = ".".join(parts)
        if key in hmap and hmap[key] and _label(hmap[key]) not in PROCEDURAL_LABELS:
            found.append(f"{key} {hmap[key]}")
        parts = parts[:-1]
    return " > ".join(reversed(found[:SECTION_LEVELS]))


def applies_to_numbered(citation: str, hmap: dict, section_title_path):
    """Who a row applies to, from the paragraph numbering: the title of the nearest numbered ancestor, when that ancestor names the responsible party.

    Returns the party (numbering-stripped), "" when the numbering says no party applies or names none, or None only when the row has no dotted paragraph number, so the caller can use
    the section path (documents that are not numbered this way). A row that has a dotted number never falls back to the path: the converter nests some headings wrongly, and a wrong
    party on an audit sheet is worse than none. An ancestor names the party when the row sits in a responsibilities section (the converter's top-level path
    entry says so even where its deeper nesting is wrong) or when the title itself introduces a list ("... will:", "... shall:")."""
    ref = (citation or "").replace("(inferred)", "").strip().rstrip(".")
    if not hmap or not _PARAGRAPH_REF.match(ref):
        return None  # no numbering knowledge for this document (or this row): the caller uses the section path
    parts = ref.split(".")
    in_responsibilities = any("responsibilit" in str(p).lower() for p in (section_title_path or []))
    while len(parts) >= 2:
        key = ".".join(parts)
        title = (hmap or {}).get(key, "")
        if title and _label(title) not in PROCEDURAL_LABELS:
            introduces = title.rstrip().endswith(":") or bool(re.search(r"\b(?:will|shall)\s*:?\s*$", title.strip(), re.IGNORECASE))
            if in_responsibilities or introduces:
                return strip_numbering(title).strip()
            return ""
        parts = parts[:-1]
    return ""


# The question and importance-score prompts show the model only a cut of the passage. Cutting the first N characters can drop the marked requirement (the chunk is long, or the
# previous-chunk tail sits in front) or the lead-in of a list item. `prompt_window` is the window rule measured in PREREG7 (eval/clause_labeling/PREREG7_REPORT.md): the lines that
# hold the requirement, the line holding its lead-in, then one line after and one before (same section only, across chunk borders) up to the cap. The requirement is never cut.
QUESTION_PASSAGE_CHARS = 1500  # the draft-question prompt
SCORE_PASSAGE_CHARS = 1200  # the importance-score prompt
LEAD_LOOKBACK_LINES = 40


def squash(text: str) -> str:
    """Letters and digits only, lower case, so a lead-in is found whatever the spacing."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def lead_in_prefix(explained_parts) -> str:
    """The squashed first 60 characters of the row's lead-in (explained_parts kind lead_in), or ""."""
    for p in explained_parts or []:
        if p.get("kind") == "lead_in":
            return squash(p.get("text") or "")[:60]
    return ""


def cut_is_enough(passage: str, cap: int, lead_prefix: str = "") -> bool:
    """True when the plain first `cap` characters of the marked passage already hold the whole marked requirement and the row's lead-in (if it has one)."""
    i = (passage or "").find(MARK_OPEN)
    j = passage.find(MARK_CLOSE, i) if i >= 0 else -1
    if j < 0 or j + len(MARK_CLOSE) > cap:
        return False
    return not lead_prefix or lead_prefix in squash(passage[:cap])


def document_lines(chunks: dict) -> list[tuple[int, tuple, str]]:
    """(chunk_id, section path, line) for every non-empty line of the document, chunks in id order."""
    out = []
    for cid in sorted(k for k in chunks if isinstance(k, int)):
        c = chunks[cid]
        # a section is identified by both paths: headings without a canonical id are missing from the ref path, so sibling prose-titled subsections share it
        path = tuple(tuple(p) if isinstance(p, (list, tuple)) else (str(p),) for p in (c.get("section_ref_path") or [], c.get("section_title_path") or []))
        for ln in (c.get("raw_text") or c.get("text") or "").split("\n"):
            if ln.strip():
                out.append((cid, path, ln.rstrip()))
    return out


def prompt_window(lines, quote_chunk_id: int, marked_raw: str, lead_prefix: str, cap: int) -> str | None:
    """The window of the document around a marked requirement, at most about `cap` characters, or None when the marked text cannot be placed in `lines`.

    `lines` comes from document_lines with the requirement's chunk already carrying the >> << markers (`marked_raw` is that chunk's marked text). A side that was cut is shown as "..."."""
    marked_lines = [ln.rstrip() for ln in marked_raw.split("\n") if ln.strip()]
    first = next((k for k, ln in enumerate(lines) if ln[0] == quote_chunk_id), None)
    if first is None or len(marked_lines) != sum(1 for ln in lines if ln[0] == quote_chunk_id):
        return None
    lines = list(lines)
    for k, ln in enumerate(marked_lines):  # put the marked version of the chunk in place
        lines[first + k] = (quote_chunk_id, lines[first + k][1], ln)
    hit = [k for k in range(first, first + len(marked_lines)) if MARK_OPEN.strip() in lines[k][2] or MARK_CLOSE.strip() in lines[k][2]]
    open_line = next((k for k in range(first, first + len(marked_lines)) if MARK_OPEN.strip() in lines[k][2]), None)
    close_line = next((k for k in range(first, first + len(marked_lines)) if MARK_CLOSE.strip() in lines[k][2]), None)
    if open_line is None or close_line is None:
        return None
    lo, hi = open_line, close_line
    sect = lines[lo][1]

    def size(a, b):
        return sum(len(lines[i][2]) + 1 for i in range(a, b + 1))

    lead = None
    if lead_prefix:
        for i in range(lo, max(-1, lo - 1 - LEAD_LOOKBACK_LINES), -1):
            if lines[i][1] != sect:
                break
            if lead_prefix in squash(lines[i][2]):
                lead = i if i < lo else None  # in the requirement's own line: already inside
                break
    a = lo
    if lead is not None and size(lead, hi) <= cap:
        a = lead
    extra_before = [lead] if lead is not None and a == lo else []
    used = size(a, hi) + sum(len(lines[i][2]) + 1 for i in extra_before)
    if used > cap:  # the requirement (with its lead-in) is over the cap: never cut it; crop its own line around it only when that line is the whole problem
        if lo == hi and not extra_before and len(hit) == 1:
            return _crop_line(lines[lo][2], cap)
        return "\n".join([lines[i][2] for i in extra_before] + [lines[i][2] for i in range(a, hi + 1)])
    nxt, prv = hi + 1, a - 1
    after, before = [], []
    while True:
        moved = False
        if nxt < len(lines) and lines[nxt][1] == sect and used + len(lines[nxt][2]) + 1 <= cap:
            used += len(lines[nxt][2]) + 1
            after.append(nxt)
            nxt += 1
            moved = True
        if prv >= 0 and lines[prv][1] == sect and prv not in extra_before and used + len(lines[prv][2]) + 1 <= cap:
            used += len(lines[prv][2]) + 1
            before.append(prv)
            prv -= 1
            moved = True
        if not moved:
            break
    order = sorted(set(before) | set(extra_before) | set(range(a, hi + 1)) | set(after))
    text = "\n".join(lines[i][2] for i in order)
    if order[0] > 0 and lines[order[0] - 1][1] == sect:
        text = "... " + text
    if order[-1] + 1 < len(lines) and lines[order[-1] + 1][1] == sect:
        text += " ..."
    return text


def _crop_line(line: str, cap: int) -> str:
    """One long line cut around the marked requirement at word boundaries, to about `cap` characters; the marked requirement stays whole."""
    qs, qe = line.find(MARK_OPEN.strip()), line.find(MARK_CLOSE.strip()) + len(MARK_CLOSE.strip())
    budget = cap - (qe - qs)
    if budget <= 0:
        return line[qs:qe]
    s0 = max(0, qs - budget // 2)
    e0 = min(len(line), qe + (budget - (qs - s0)))
    s0 = max(0, min(s0, qs - (budget - (e0 - qe))))
    while 0 < s0 < qs and line[s0 - 1] != " ":
        s0 += 1
    while qe < e0 < len(line) and line[e0] != " ":
        e0 -= 1
    return ("... " if s0 > 0 else "") + line[s0:e0] + (" ..." if e0 < len(line) else "")

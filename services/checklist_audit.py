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


def build_passage(quote: str, chunk, prev_chunk=None, flags=()) -> tuple[str, bool]:
    """(passage, quote_found): the document's own text around the quote, verbatim, with the quote wrapped in >> << markers.

    The passage is the text of the chunk that holds the quote. When the quote starts mid-sentence or is a list item, the tail of the previous chunk is put in front (the
    lead-in is usually there), separated by an ellipsis. If the chunk is missing the passage is empty; if the quote cannot be located the whole chunk is returned unmarked.
    """
    if not chunk:
        return "", False
    raw = chunk.get("raw_text") or chunk.get("text") or ""
    prefix = ""
    if prev_chunk and ({"starts_mid_sentence", "list_item"} & set(flags)):
        tail = (prev_chunk.get("raw_text") or prev_chunk.get("text") or "")[-PASSAGE_TAIL_CHARS:]
        cut = tail.find(" ")
        prefix = "... " + (tail[cut + 1:] if 0 <= cut < len(tail) - 1 and len(tail) == PASSAGE_TAIL_CHARS else tail).strip() + "\n\n"
    pat = _flex_pattern(quote)
    m = pat.search(raw) if pat else None
    if not m:
        return (prefix + raw).strip(), False
    return (prefix + raw[: m.start()] + MARK_OPEN + raw[m.start(): m.end()] + MARK_CLOSE + raw[m.end():]).strip(), True


# WP-46.3: the parent paragraph from the document's own numbering. AFIs number paragraphs as a hierarchy (2.5.1.1.7.2 sits under 2.5.1.1.7 under 2.5.1.1), so the paragraph a row
# belongs to is read straight from the document, verbatim; no model and no guess. A row whose number does not look like a dotted paragraph number (a table tag such as "(T-2)")
# gets none.
_DOTTED = re.compile(r"^\d+(?:\.\d+)+$")
_PARA_START = re.compile(r"^\W*(\d+(?:\.\d+)+)\.?\s+(.*)$", re.DOTALL)
PARENT_TEXT_CHARS = 300


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

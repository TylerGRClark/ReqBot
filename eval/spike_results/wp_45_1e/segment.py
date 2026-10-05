"""WP-45.1(e): cut a PDF page into sentence-sized "pieces" for labeling, without looking at any pipeline output.

Text comes from PyMuPDF, not Docling, so a loss in Docling's parse is visible to the labelers and shows up as a loss point.
The rules are deterministic and fixed before any labeling (the sha256 of this file is recorded in the frozen draw):

1. Lines are the PDF's own text lines, ordered top to bottom, left to right.
2. A paragraph starts at a list marker or after a vertical gap larger than a normal line gap. (A "short last line" rule was
   tried and dropped: the text is ragged on the right, so it split ordinary wrapped sentences.)
3. A line ending in a hyphen followed by a lowercase letter is joined to the next line without the hyphen.
4. A paragraph is cut into sentences at ". ", "? ", "! " followed by a capital letter, digit, quote or bracket, except after
   a known abbreviation or a single capital initial. A leading list marker stays with its first sentence.

Piece ids are "<code>-p<page>-<n>", for example "AFMAN-p012-003".
"""

import re
import statistics

SEGMENTER_VERSION = "1"

DOC_CODES = {"DODI 8410.03": "DODI", "afman17-2101": "AFMAN", "NIST.SP.800-125": "NIST"}

LIST_MARKER = re.compile(
    r"""^\s*(?:
        \((?:[a-z]{1,2}|[0-9]{1,3}|[A-Z])\)          # (a) (aa) (1) (A)
      | [0-9]+(?:\.[0-9]+)+\.?(?=\s)                 # 2.8.2.2.3.  2.4.1.1
      | [0-9]{1,3}\.(?=\s)                           # 1.  12.
      | [A-Za-z]\.(?=\s)                             # a.  A.
      | [•●○▪■◦–—-](?=\s)   # bullets and dashes
    )""",
    re.X,
)
SENTENCE_END = re.compile(r"""([.!?]["”')\]]*)(\s+)(?=["“'(\[]?[A-Z0-9])""")
ABBREVIATIONS = {
    "e.g",
    "i.e",
    "etc",
    "vs",
    "no",
    "nos",
    "sec",
    "secs",
    "fig",
    "para",
    "paras",
    "dr",
    "mr",
    "mrs",
    "ms",
    "inc",
    "corp",
    "co",
    "ltd",
    "gen",
    "lt",
    "col",
    "maj",
    "capt",
    "sgt",
    "dept",
    "ref",
    "approx",
    "u.s",
    "d.c",
    "al",
    "cf",
    "ch",
    "vol",
    "pt",
    "est",
}
GAP_FACTOR = 0.4  # a paragraph gap is more than this share of a normal line height


def page_lines(page):
    """[(y0, y1, x0, x1, text)] for the page's text lines, in reading order."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).replace(" ", " ").strip()
            if text:
                x0, y0, x1, y1 = line["bbox"]
                out.append((y0, y1, x0, x1, text))
    out.sort(key=lambda r: (round(r[0] / 2), r[2]))
    return out


def paragraphs(lines):
    """Join lines into paragraphs by the rules in the module docstring."""
    if not lines:
        return []
    height = statistics.median(y1 - y0 for y0, y1, _, _, _ in lines) or 10.0
    paras, current, prev = [], [], None
    for y0, y1, x0, x1, text in lines:
        starts = bool(LIST_MARKER.match(text))
        if prev is not None:
            if starts or y0 - prev > GAP_FACTOR * height:
                paras.append(current)
                current = []
        current.append(text)
        prev = y1
    paras.append(current)
    return [join_lines(p) for p in paras]


def join_lines(texts):
    out = texts[0]
    for nxt in texts[1:]:
        if out.endswith("-") and nxt[:1].islower():
            out = out[:-1] + nxt
        else:
            out = out + " " + nxt
    return re.sub(r"\s+", " ", out).strip()


def _is_abbreviation(before):
    word = before.rsplit(None, 1)[-1] if before.split() else ""
    word = word.lstrip("(\"'“[").lower()
    if word.rstrip(".") in ABBREVIATIONS:
        return True
    return bool(re.fullmatch(r"[A-Za-z]", word)) or bool(
        re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]?", word)
    )


def split_sentences(paragraph):
    """Cut one paragraph into sentences; a leading list marker stays with the first sentence."""
    m = LIST_MARKER.match(paragraph)
    marker_end = m.end() if m else 0
    pieces, start = [], 0
    for hit in SENTENCE_END.finditer(paragraph, marker_end):
        if _is_abbreviation(paragraph[start : hit.start(1)]):
            continue
        pieces.append(paragraph[start : hit.end(1)])
        start = hit.end()
    pieces.append(paragraph[start:])
    return [p.strip() for p in pieces if p.strip()]


def segment_page(page):
    """The ordered pieces of one fitz page."""
    out = []
    for para in paragraphs(page_lines(page)):
        out.extend(split_sentences(para))
    return out


def piece_id(doc, page_number, n):
    return f"{DOC_CODES[doc]}-p{page_number:03d}-{n:03d}"

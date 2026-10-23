"""Cut a chunk's own text into clauses: sentences and list or table lines, each with its exact offsets (pure functions, no model).

Design: reqbot-agent-docs history/extraction-replacement-design_2026-10-22.md, work package WP-2. Ported rule for rule from the measured experiment
(scratch/clause_label/cl.py and the chunk context of scratch/clause_label3/run3.py: dafman17-1304, 148 chunks -> 870 clauses), so that the labeler later
sees exactly what was tested. Do not "improve" a rule here without re-running that measurement: a different cut changes what the model labels.

Rules, in order:
1. The chunk is read line by line. A line without two letters in a row (a blank line, a table separator such as "|---|---|", a bare page number) ends the
   current block and is skipped.
2. A line is joined to the block above (a hard line wrap) unless it starts a list item or table row (LISTSTART) or the block above already ends a sentence
   or a lead-in (ENDS: . ! ? : ; with closing quotes or brackets, optionally followed by a tier tag such as "(T-2)").
3. Each block is cut into sentences at SENT (end mark, optional closing quote or bracket, white space, then an upper-case letter, digit or opening
   quote/bracket). A tier tag "(T-2)" after the end mark never starts a new sentence; it stays with the sentence it follows, and when a new sentence
   follows the tag (TAG_CUT: end mark, tag, white space, upper-case letter, digit or opening quote/bracket) the cut falls after the tag. No cut after an abbreviation (ABBRRE: "U.S.", "e.g.", "para.",
   "E.O."), a two-level section number ("3.6.", "2.1") or a one- or two-character token ending in a period ("a.", "1."). A deeper number
   ("3.6.1.1.") is NOT protected: the cut falls after it and, having no letters, it is dropped by rule 4, so the clause starts at its sentence and the
   number stays in the chunk text just before the clause start (as measured; a reader that wants the number looks there).
4. A clause is kept only if it has two letters in a row.

Each clause is a dict: chunk_id, clause_index (0-based within the chunk), start and end (text[start:end] is the clause, character for character), text,
is_lead_in (ends with ':', or with ':' and a tier tag such as ": (T-2)."), ctx_lead (the nearest preceding lead-in in the same chunk, None for a lead-in itself; a new lead-in replaces the old one),
heading (the chunk's parent header, else its breadcrumb) and ref (the last entry of the chunk's section reference path).
"""
from __future__ import annotations

import ast
import re

ABBR = ("e.g.", "i.e.", "u.s.", "no.", "para.", "paras.", "fig.", "etc.", "vs.", "dr.", "mr.", "sec.", "art.", "cf.", "inc.", "dept.", "gen.", "col.",
        "lt.", "mil.")  # kept from the experiment for reference; ABBRRE below is the rule that is applied
SENT = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?!\(T-\d\))(?=[\"'(\[]?[A-Z0-9])")
LISTSTART = re.compile(r"^\s*([-*•]\s|\(?[0-9]{1,2}[.)]\s|\(?[a-zA-Z][.)]\s|\([0-9a-zA-Z]{1,3}\)\s|\|)")
ENDS = re.compile(r"[.!?:;][\"')\]]*(\s*\(T-\d\)\.?)?\s*$")
ABBRRE = re.compile(r"^(\(?[A-Za-z]\.){1,}$|^(no|nos|para|paras|fig|etc|vs|dr|mr|sec|art|cf|inc|dept|gen|col|lt|mil|ch|vol|att|atch)\.$", re.I)
_NUMBER_TOKEN = re.compile(r"\d+\.\d+\.?|[A-Za-z0-9]{1,2}\.")
_TWO_LETTERS = re.compile(r"[A-Za-z]{2}")
_CLOSERS = re.compile(r"[\"')\]]*")
_TAG_CUT = re.compile(r"(?<=[.!?])[\"')\]]*\s+\(T-\d\)\s+(?=[\"'(\[]?[A-Z0-9])")  # "...office. (T-1) In addition:": the tag stays with its sentence and the next sentence starts after it
_LEAD_IN_END = re.compile(r":(\s*\(T-\d\)\.?)?$")  # "will:" and, after a tier tag, "options: (T-2)."


def split_clauses(text: str) -> list[tuple[int, int]]:
    """(start, end) of each clause; text[start:end] is the clause itself. Lines are joined unless the next line starts a list item or table row, a line
    without letters intervenes, or the previous line ends a sentence."""
    lines = []
    pos = 0
    for line in text.split("\n"):
        lines.append((pos, line))
        pos += len(line) + 1
    blocks: list[list[int]] = []
    cur = None
    for ls, line in lines:
        if not _TWO_LETTERS.search(line):
            cur = None
            continue
        st = ls + (len(line) - len(line.lstrip()))
        en = ls + len(line.rstrip())
        if cur is not None and not LISTSTART.match(line) and not ENDS.search(text[cur[0]:cur[1]]):
            cur[1] = en
        else:
            cur = [st, en]
            blocks.append(cur)
    out = []
    for bs, be in blocks:
        seg = text[bs:be]
        a = 0
        cuts = [(m.start(), m.end(), False) for m in SENT.finditer(seg)] + [(m.start(), m.end(), True) for m in _TAG_CUT.finditer(seg)]
        for ms, me, after_tag in sorted(cuts):
            pre = seg[a:ms + 1].split()
            last = pre[-1] if pre else ""
            if ABBRRE.match(last) or _NUMBER_TOKEN.fullmatch(last):
                continue
            if after_tag:  # the clause runs to the end of the tag
                out.append((bs + a, bs + seg.index(")", ms) + 1))
            else:
                # The clause keeps every closing quote or bracket after its end mark (no source character is lost); with none it keeps the one following character, as
                # measured. Only the first part changes what the experiment cut: 0 such cuts in the 23-document library.
                out.append((bs + a, bs + ms + max(1, len(_CLOSERS.match(seg[ms:me]).group()))))
            a = me
        out.append((bs + a, be))
    return [(s, e) for s, e in out if e > s and _TWO_LETTERS.search(text[s:e])]


def clauses_of(unit: dict) -> list[dict]:
    """Clauses of one unit {"unit_id", "text", "heading", "ref"}, with the lead-in context. unit_id is stored as chunk_id."""
    t = unit["text"]
    cl = []
    for i, (s, e) in enumerate(split_clauses(t)):
        cl.append(dict(chunk_id=unit["unit_id"], clause_index=i, start=s, end=e, text=t[s:e], is_lead_in=bool(_LEAD_IN_END.search(t[s:e].rstrip()))))
    last = None  # the nearest preceding lead-in; a new lead-in replaces it, and it never crosses into another chunk
    for c in cl:
        c["ctx_lead"] = last if not c["is_lead_in"] else None
        if c["is_lead_in"]:
            last = c["text"]
        c["heading"] = unit.get("heading") or ""
        c["ref"] = unit.get("ref") or ""
    return cl


def _as_list(v) -> list:
    if isinstance(v, list):
        return v
    try:
        parsed = ast.literal_eval(v)
    except Exception:
        return []
    return list(parsed) if isinstance(parsed, (list, tuple)) else []


def chunk_unit(chunk: dict) -> dict:
    """The unit the experiment built from a chunk record: its raw text (else its text), heading = parent header else breadcrumb, ref = last entry of the
    section reference path (a list, or its string form in older files)."""
    refs = _as_list(chunk.get("section_ref_path"))
    return dict(
        unit_id=chunk["chunk_id"],
        text=chunk.get("raw_text") or chunk.get("text") or "",
        heading=chunk.get("parent_header_text") or chunk.get("breadcrumb") or "",
        ref=str(refs[-1]) if refs else "",
    )


def chunk_clauses(chunk: dict) -> list[dict]:
    """Clauses of one chunk record (a line of <doc>_chunks.jsonl)."""
    return clauses_of(chunk_unit(chunk))

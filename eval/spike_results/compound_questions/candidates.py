"""Candidate selection for the compound-question split spike. Pure functions; no model.

A candidate is a checklist row whose draft audit question is over 30 words, or joins 3+ parallel items with commas / 'and' / 'or'.
"""
import json
import re
from pathlib import Path

LONG_WORDS = 30
SERIES_MIN_WORDS = 20  # a short question with a 3-item series (13 to 19 words) is already one glance; the series test only applies from this length
_CONJ = re.compile(r"\b(?:and|or|and/or)\b", re.IGNORECASE)


def word_count(text: str) -> int:
    return len((text or "").split())


def series_length(question: str) -> int:
    """Rough count of parallel items: a run of commas closed by and/or counts commas + 1 ('X, Y, and Z' = 3); two or more bare and/or count the conjunctions + 1
    ('A and B and C' = 3). 0 when there is no series. Deliberately approximate: it only decides which rows the model is asked about."""
    q = question or ""
    commas = q.count(",")
    conj = len(_CONJ.findall(q))
    if commas >= 2 and conj >= 1:
        return commas + 1
    if conj >= 2:
        return conj + 1
    return 0


def is_candidate(question: str) -> tuple[bool, str]:
    if not (question or "").strip():
        return False, ""
    if word_count(question) > LONG_WORDS:
        return True, "long"
    if series_length(question) >= 3 and word_count(question) >= SERIES_MIN_WORDS:
        return True, "series"
    return False, ""


def load_items(path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["items"]

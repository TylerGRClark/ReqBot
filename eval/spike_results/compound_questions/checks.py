"""Mechanical checks for a proposed split of a compound audit question (pure functions; no model, no network).

A split is {"lead": str, "parts": [str, ...]}. `today` is the question shown in the live checklist; `item` is the checklist row.
Every check returns a list of problems (empty = pass). `evaluate()` runs them all and returns {check_name: [problems]}.
A split that fails any check falls back to today's question unchanged (the caller does that; nothing here edits a question).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from services.audit_questions import unverified_terms  # noqa: E402  (read-only import; the service is not modified)

PART_MAX_WORDS = 25
NOUN_PHRASE_MAX_WORDS = 10
MIN_PARTS, MAX_PARTS = 2, 5
COVERAGE_SHARE = 0.5  # a list item counts as covered when MORE than this share of its content stems appears in the split (so 1 of 2 fails, 2 of 3 passes)

# ---- check 1: numbers, time limits, condition words ------------------------------------------------------------------------------------------------------------------------------
_NUMBER_WORDS = r"two|three|four|five|six|seven|eight|nine|ten|twelve|thirty|sixty|ninety|hundred|twice|both"
# canonical label -> regex that finds it in a lower-cased text. Families are listed together where the plain-words swap is harmless ("prior to" / "before").
CONDITION_WORDS = {
    "if/when": r"\b(?:if|when|whenever|once|upon|where|in the event)\b",
    "unless": r"\bunless\b",
    "only": r"\bonly\b|\bsolely\b|\bexclusively\b",
    "until": r"\buntil\b|\btill\b",
    "within": r"\bwithin\b",
    "at least": r"\bat least\b|\bminimum\b|\bat a minimum\b",
    "no later than": r"\bno later than\b|\bnot later than\b|\bby no later\b",
    "no more than": r"\bno more than\b|\bnot to exceed\b|\bat most\b|\bmaximum\b|\bup to\b",
    "before/prior": r"\bbefore\b|\bprior to\b|\bahead of\b",
    "after": r"\bafter\b|\bfollowing\b|\bonce\b",
    "except": r"\bexcept\b|\bother than\b|\bexcluding\b|\bprovided that\b",
    "annually": r"\bannual\w*\b|\byearly\b|\bevery year\b|\beach year\b|\bper year\b",
    "quarterly": r"\bquarter\w*\b",
    "monthly": r"\bmonth\w*\b",
    "weekly": r"\bweek\w*\b",
    "daily": r"\bdaily\b|\bevery day\b|\beach day\b",
    "biennial": r"\bbienni\w*\b|\bsemi-?annual\w*\b|\bbi-?annual\w*\b",
    "not/never": r"\bnot\b|\bnever\b|\bno\b|\bnone\b|\bwithout\b|\bn't\b|\bavoid\w*\b|\bprohibit\w*\b",
    "all/each/every": r"\ball\b|\beach\b|\bevery\b|\bany\b|\bboth\b",
    "as required": r"\bas (?:required|appropriate|needed|applicable|necessary|directed|tasked)\b|\bwhen (?:requested|tasked|directed|required)\b",
    "immediately": r"\bimmediate\w*\b|\bpromptly\b|\bwithout delay\b",
}
_NUMBER = re.compile(r"\b\d[\w,.:/-]*\w|\b\d\b|\b(?:" + _NUMBER_WORDS + r")\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def qualifiers(text: str) -> dict[str, str]:
    """{label: matched text} for every number and condition word in `text`."""
    t = _norm(text)
    out: dict[str, str] = {}
    for m in _NUMBER.finditer(t):
        out["#" + m.group(0).strip(".,;:()")] = m.group(0)
    for label, rx in CONDITION_WORDS.items():
        m = re.search(rx, t)
        if m:
            out[label] = m.group(0)
    return out


def check_qualifiers(today: str, pieces: list[str]) -> list[str]:
    """(1) every number, time limit and condition word of today's question appears in the lead or some part."""
    joined = _norm(" ".join(pieces))
    problems = []
    for label, shown in qualifiers(today).items():
        if label.startswith("#"):
            if not re.search(r"(?<![\w.])" + re.escape(label[1:]) + r"(?![\w])", joined):
                problems.append(f"number '{shown}' dropped")
        elif not re.search(CONDITION_WORDS[label], joined):
            problems.append(f"'{shown}' dropped")
    return problems


# ---- check 2: no invented terms -------------------------------------------------------------------------------------------------------------------------------------------------
def check_terms(today: str, item: dict, pieces: list[str]) -> list[str]:
    """(2) no capitalised term, number or acronym in the split that is absent from today's question or the row's own text (requirement, Applies-to line, parent paragraph)."""
    material = " ".join([today or "", item.get("source_quote") or "", item.get("applies_to") or "", item.get("parent_text") or ""])
    out = []
    for p in pieces:
        out.extend(unverified_terms(p, material))
    return sorted(set(out))


# ---- check 3: shape ---------------------------------------------------------------------------------------------------------------------------------------------------------------
_AUX = re.compile(r"^(?:does|do|did|is|are|was|were|has|have|had|can|could|will|would|shall|should|must|may|might)\b", re.IGNORECASE)


def check_shape(lead: str, parts: list[str]) -> list[str]:
    """(3) the lead is a yes/no question; every part is a yes/no question (at most 25 words) or a short noun-phrase check (at most 10 words, no verb opener); 2 to 5 parts."""
    problems = []
    if not (MIN_PARTS <= len(parts) <= MAX_PARTS):
        problems.append(f"{len(parts)} parts (need {MIN_PARTS} to {MAX_PARTS})")
    if not (lead or "").strip().endswith("?") or not _AUX.match(lead.strip()):
        problems.append("lead is not a yes/no question")
    for i, p in enumerate(parts):
        p = (p or "").strip()
        n = len(p.split())
        if not p:
            problems.append(f"part {i + 1} is empty")
        elif p.endswith("?"):
            if not _AUX.match(p):
                problems.append(f"part {i + 1} is a question but not yes/no")
            if n > PART_MAX_WORDS:
                problems.append(f"part {i + 1} has {n} words")
        else:
            if _AUX.match(p) or n > NOUN_PHRASE_MAX_WORDS or p.endswith("."):
                problems.append(f"part {i + 1} is neither a yes/no question nor a short noun phrase")
    return problems


# ---- check 4: dangling pronouns ---------------------------------------------------------------------------------------------------------------------------------------------------
_PRONOUN = re.compile(r"\b(?:they|them|their|theirs|it|its|he|she|his|her|these|those|such(?!\s+as\b)|this|that)\b", re.IGNORECASE)
_SUBJECT_PRONOUN = re.compile(r"^(?:does|do|did|is|are|was|were|has|have|can|will|should|must|may)\s+(?:it|they|he|she|this|these|those|such|that)\b", re.IGNORECASE)


def check_pronouns(today: str, pieces: list[str]) -> list[str]:
    """(4) no pronoun or demonstrative in the split that is absent from today's question (the split adds a reference), and no piece whose subject is a pronoun."""
    in_today = {m.group(0).lower() for m in _PRONOUN.finditer(today or "")}
    problems = []
    for p in pieces:
        if _SUBJECT_PRONOUN.match(p.strip()):
            problems.append(f"'{' '.join(p.split()[:3])}...' has a pronoun as its subject")
        for m in _PRONOUN.finditer(p):
            w = m.group(0).lower()
            if w not in in_today and w != "that":  # "that" as a conjunction ("ensure that") is not a reference; "this publication" etc. count only when new
                problems.append(f"'{w}' added")
    return sorted(set(problems))


# ---- check 5: modality ------------------------------------------------------------------------------------------------------------------------------------------------------------
_PERMISSIVE = re.compile(r"\b(?:may|can|could|might|permitted|authorized|allowed|encouraged|recommended|optional|should|suggested)\b", re.IGNORECASE)
_MANDATORY = re.compile(r"\b(?:must|shall|required|requires?|mandatory|obligated|need(?:s)? to|have to|has to|ensure[sd]?|will)\b", re.IGNORECASE)
_PERMISSIVE_NOT_SHOULD = re.compile(r"\b(?:may|can|could|might|permitted|authorized|allowed|encouraged|optional)\b", re.IGNORECASE)


def check_modality(today: str, item: dict, pieces: list[str]) -> list[str]:
    """(5) a may / can / should in the source is not turned into must / required / does-the-unit-have-to (and a must is not softened to may)."""
    quote = item.get("source_quote") or ""
    joined = " ".join(pieces)
    problems = []
    if _PERMISSIVE.search(quote) or _PERMISSIVE.search(today or ""):
        added = {m.group(0).lower() for m in re.finditer(r"\b(?:must|shall|required|mandatory|obligated|need to|needs to|have to|has to)\b", joined, re.IGNORECASE)}
        was = {m.group(0).lower() for m in re.finditer(r"\b(?:must|shall|required|mandatory|obligated|need to|needs to|have to|has to)\b", (today or "") + " " + quote, re.IGNORECASE)}
        if added - was:
            problems.append("adds a duty word (" + ", ".join(sorted(added - was)) + ") to a permissive source")
        if _PERMISSIVE.search(today or "") and not _PERMISSIVE.search(joined):
            problems.append("permission / recommendation word of today's question is gone")
    if _MANDATORY.search(quote) and not _PERMISSIVE.search(quote):
        softened = {m.group(0).lower() for m in _PERMISSIVE_NOT_SHOULD.finditer(joined)} - {m.group(0).lower() for m in _PERMISSIVE_NOT_SHOULD.finditer((today or "") + " " + quote)}
        if softened:
            problems.append("softens a duty with " + ", ".join(sorted(softened)))
    return problems


# ---- check 6: item coverage -------------------------------------------------------------------------------------------------------------------------------------------------------
_STOP = frozenset("""that this with from have does they them their there these those which what when where while will shall must should would could been being were such also than then into upon
each every other only more most some both under over unit ensure ensures about between through during within without whether does""".split())
_SEG = re.compile(r",|;|:|\band/or\b|\band\b|\bor\b|\bthen\b", re.IGNORECASE)


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z][a-z'-]*", _norm(text)) if len(w) >= 4 and w not in _STOP}


def items_of(question: str) -> list[str]:
    """The comma / and / or separated segments of a question that carry at least one content word."""
    return [s.strip() for s in _SEG.split(question or "") if _stems(s)]


def check_coverage(today: str, pieces: list[str]) -> list[str]:
    """(6) the parts together cover every item of today's list: each comma / and / or segment of today's question has more than half of its content stems in the split."""
    have = _stems(" ".join(pieces))
    problems = []
    for seg in items_of(today):
        stems = _stems(seg)
        if stems and len(stems & have) / len(stems) <= COVERAGE_SHARE:
            problems.append(f"item not covered: '{seg}'")
    return problems


# ---- check 7 (added by this experiment): the lead keeps today's actor ---------------------------------------------------------------------------------------------------------------
def check_actor(today: str, lead: str) -> list[str]:
    """(7) the lead keeps the actor / scope: the first three words after today's opening auxiliary appear, in order, at the start of the lead's own subject."""
    m = _AUX.match((today or "").strip())
    n = _AUX.match((lead or "").strip())
    if not m or not n:
        return []
    want = (today.strip()[m.end():]).split()[:3]
    got = " ".join((lead.strip()[n.end():]).split()[:6]).lower()
    want_s = " ".join(want).lower()
    return [] if want_s in got or all(re.sub(r"\W", "", w.lower()) in re.sub(r"\W", "", got) for w in want) else [f"actor changed: today '{want_s}', lead '{got}'"]


NAMES = ["qualifiers", "terms", "shape", "pronouns", "modality", "coverage", "actor"]


def evaluate(today: str, item: dict, lead: str, parts: list[str]) -> dict[str, list[str]]:
    pieces = [lead] + list(parts)
    return {
        "qualifiers": check_qualifiers(today, pieces),
        "terms": check_terms(today, item, pieces),
        "shape": check_shape(lead, parts),
        "pronouns": check_pronouns(today, pieces),
        "modality": check_modality(today, item, pieces),
        "coverage": check_coverage(today, pieces),
        "actor": check_actor(today, lead),
    }


def failed(result: dict[str, list[str]]) -> list[str]:
    return [k for k in NAMES if result.get(k)]

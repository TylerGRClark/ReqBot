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
_AUXW = "(?:does|do|did|is|are|was|were|has|have|had|can|could|will|would|shall|should|must|may|might)"
_AUX = re.compile(r"^" + _AUXW + r"\b", re.IGNORECASE)
_COND_OPENER = re.compile(r"^(?:if|when|whenever|unless|upon|where|once|after|before)\b[^?]*,\s*" + _AUXW + r"\b", re.IGNORECASE)  # "If applicable, is a date included?" (added in round 2)


_WH = re.compile(r"^(?:what|who|whom|whose|which|how|why|when|where)\b", re.IGNORECASE)


def _is_yes_no(text: str) -> bool:
    return bool(_AUX.match(text) or _COND_OPENER.match(text))


def check_shape(lead: str, parts: list[str]) -> list[str]:
    """(3) the lead is a yes/no question; every part is a yes/no question (at most 25 words) or a short noun-phrase check (at most 10 words, no verb opener); 2 to 5 parts."""
    problems = []
    if not (MIN_PARTS <= len(parts) <= MAX_PARTS):
        problems.append(f"{len(parts)} parts (need {MIN_PARTS} to {MAX_PARTS})")
    if not (lead or "").strip().endswith("?") or not _is_yes_no(lead.strip()):
        problems.append("lead is not a yes/no question")
    for i, p in enumerate(parts):
        p = (p or "").strip()
        n = len(p.split())
        if not p:
            problems.append(f"part {i + 1} is empty")
        elif p.endswith("?"):
            if not _is_yes_no(p) and _WH.match(p):  # round 2: a short noun-phrase check written with a question mark ("Budget guidance to PMOs?") is allowed under a yes/no lead; a who/what/how question is not
                problems.append(f"part {i + 1} is a question but not yes/no")
            if n > PART_MAX_WORDS:
                problems.append(f"part {i + 1} has {n} words")
        else:
            if _is_yes_no(p) or n > NOUN_PHRASE_MAX_WORDS or p.endswith("."):
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
        sm = _SUBJECT_PRONOUN.match(p.strip())
        pair = " ".join(re.sub(r"\W", "", w) for w in p.strip().lower().split()[1:3])
        acronym_it = bool(sm) and sm.group(0).split()[-1] == "IT" and re.search(r"\bIT\b", today or "") is not None  # IT = Information Technology when today's question says so
        if sm and not acronym_it and pair not in re.sub(r"[^\w ]", "", _norm(today)):  # "Does this publication ...?" is fine when today's question says "this publication" (round 2)
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
each every other only more most some both under over unit ensure ensures about between through during within without whether does including include includes along""".split())
_SEG = re.compile(r",|;|:|\band/or\b|\band\b|\bor\b|\bthen\b", re.IGNORECASE)


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z][a-z'-]*", _norm(text)) if len(w) >= 4 and w not in _STOP}


def items_of(question: str) -> list[str]:
    """The comma / and / or separated segments of a question that carry at least one content word."""
    return [s.strip() for s in _SEG.split(question or "") if _stems(s)]


def _drop_defined_names(today: str, split_text: str) -> str:
    """Round 2: remove "Long Title (ACR)" from today's question when the split uses the acronym ACR (the split may say AF/9 for "the Director, Air Force Studies ... (AF/9)")."""
    for m in re.finditer(r"\(([A-Z][\w/&.-]{1,})\)", today):
        if re.search(r"(?<![\w/])" + re.escape(m.group(1)) + r"(?![\w/])", split_text):
            words = today[:m.start()].split()
            cut = 0
            for w in reversed(words[-14:]):
                if w[:1].isupper() or w.lower().strip(",") in {"of", "and", "for", "the", "&"}:
                    cut += 1
                else:
                    break
            if cut:
                today = " ".join(words[:len(words) - cut]) + " " + today[m.end():]
                break
    return today


def check_coverage(today: str, pieces: list[str]) -> list[str]:
    """(6) the parts together cover every item of today's list: each comma / and / or segment of today's question has more than half of its content stems in the split."""
    have = _stems(" ".join(pieces))
    today = _drop_defined_names(today, " ".join(pieces))
    problems = []
    for seg in items_of(today):
        stems = _stems(seg)
        if stems and len(stems & have) / len(stems) <= COVERAGE_SHARE:
            problems.append(f"item not covered: '{seg}'")
    return problems


# ---- check 7 (added by this experiment): the lead keeps today's actor ---------------------------------------------------------------------------------------------------------------
def check_actor(today: str, lead: str) -> list[str]:
    """(7) the lead keeps the actor / scope: the names and acronyms in the first four words after today's opening auxiliary (or, when there are none, the first two words
    without 'the') appear in the lead; an acronym that today's question gives in parentheses for the actor counts (round 2: the first version compared three raw words,
    which included the verb)."""
    m = _AUX.match((today or "").strip())
    n = _AUX.match((lead or "").strip())
    if not m or not n:
        return []
    words = (today.strip()[m.end():]).split()[:4]
    want = [re.sub(r"[^\w/&.-]", "", w) for w in words if w[:1].isupper() or re.search(r"[A-Z]{2}", w)]
    if not want:
        want = [re.sub(r"[^\w/&.-]", "", w) for w in words[:2] if w.lower().strip(",") not in {"the", "a", "an"}]
    got = _norm(lead.strip()[n.end():])
    missing = [w for w in want if w and w.lower() not in got]
    if missing:
        paren = {a.lower() for a in re.findall(r"\(([A-Z][\w/&.-]+)\)", today[:200])}
        if any(a in got for a in paren):
            return []
        return [f"actor changed: today '{' '.join(words)}', lead lacks {', '.join(missing)}"]
    return []


# ---- gain flag (added at the end of tuning; REPORTED, NOT a fallback reason, because it was not pre-registered) --------------------------------------------------------------------
GAIN_SHARE = 0.8


def check_gain(today: str, lead: str, parts: list[str]) -> list[str]:
    """Flag: the longest piece (lead or part) is more than 80% of today's question (for example a lead that repeats the whole question). Reported beside the checks; it does not
    cause a fallback, because the pre-registration fixed the fallback checks before the tuning data was seen."""
    longest = max(len(p.split()) for p in [lead] + list(parts))
    n = len((today or "").split())
    return [] if longest <= GAIN_SHARE * n else [f"longest piece {longest} words vs today's {n}"]


NAMES = ["qualifiers", "terms", "shape", "pronouns", "modality", "coverage", "actor"]  # the fallback checks; "gain" is a flag only


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
        "gain": check_gain(today, lead, parts),
    }


def failed(result: dict[str, list[str]]) -> list[str]:
    return [k for k in NAMES if result.get(k)]

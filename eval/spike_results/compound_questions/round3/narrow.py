"""Round 3 (narrow variant): the eligibility gate and the hard checks. Pure functions; no model, no network.

Rule 1 (gate): only a plain parallel list under one actor is ever sent to the model: today's question opens Does / Do, joins its items with commas and exactly one "and"
(2 to 4 commas, so 3 to 5 items), and neither the source quote nor today's question holds a permission word, a condition, a limit, an alternative ("or"), a negation or a time limit.
Everything else keeps today's question without a model call.

Rule 2 (hard checks, any failure = today's question): hedge, lead, coverage, parts, distinct, strength, actor.
"""
import re

HERE_NOTE = "see ROUND3_PREREGISTRATION.md"

# ---- gate ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_GATE = re.compile(
    r"\b(?:may|might|can|cannot|could|should|if|unless|only|solely|at least|within|until|till|no later than|not later than|except|when|whenever|whereas|upon|once|prior to|before|after|"
    r"or|and/or|not|never|no|none|without|prohibited|forbidden|as appropriate|as required|as necessary|as needed|as applicable|when applicable|annually|quarterly|monthly|weekly|"
    r"daily|immediately|promptly|minimum|maximum|up to|such as|including|e\.g|i\.e|for example|to include|in addition|also|as well as|both|either|neither|than|but|unlike|while)\b",
    re.IGNORECASE)
_TIME = re.compile(r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|thirty|sixty|ninety)\s*\(?\d*\)?\s*(?:calendar\s+|business\s+|working\s+)?(?:minutes?|hours?|days?|weeks?|months?|years?)\b", re.IGNORECASE)
_AUX_OPEN = re.compile(r"^(?:does|do)\b", re.IGNORECASE)
MAX_COMMAS = 4  # 5 items at most


def gate_words(text: str) -> list[str]:
    out = sorted({m.group(0).lower() for m in _GATE.finditer(text or "")})
    out += sorted({m.group(0).lower() for m in _TIME.finditer(text or "")})
    return out


def eligible(question: str, quote: str) -> tuple[bool, str]:
    """(True, "") when the row is a plain list worth a model call; else (False, reason)."""
    q = (question or "").strip()
    if not _AUX_OPEN.match(q):
        return False, "not an active Does/Do question"
    bad = gate_words(q) or gate_words(quote)
    if bad:
        return False, "gate word: " + ", ".join(bad[:4])
    ands = len(re.findall(r"\band\b", q, re.IGNORECASE))
    commas = q.count(",")
    if ands != 1:
        return False, f"{ands} 'and' (need exactly 1)"
    if not (2 <= commas <= MAX_COMMAS):
        return False, f"{commas} commas (need 2 to {MAX_COMMAS})"
    if re.search(r"[();:]", q):
        return False, "brackets or semicolons"
    return True, ""


def items_expected(question: str) -> int:
    return (question or "").count(",") + 1


# ---- helpers ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
_FUNC = frozenset("""that this with from have does they them their there these those which what when where while will shall must should would could been being were such also than then into
upon each every other only more most some both under over about between through during within without whether have here your you our all any are for and the not""".split())
ALLOWED_EXTRA = frozenset({"follo", "done", "mean"})  # "following" is the lead's template word


def _stem(word: str) -> str:
    w = re.sub(r"'s$", "", word.lower())
    for suf in ("ing", "ed", "es", "s", "e", "d"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "ls":
        w = w[:-1]
    return w[:5]


def stems(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-zA-Z][a-zA-Z'/-]*", text or "") if len(w) >= 4 and w.lower() not in _FUNC}


# ---- (a) hedge words ------------------------------------------------------------------------------------------------------------------------------------------------------------
HEDGES = re.compile(
    r"\b(?:as required|as appropriate|when applicable|if applicable|as applicable|as necessary|as needed|where appropriate|when appropriate|when required|if required|where possible|"
    r"as possible|if possible|when possible|whenever possible|as soon as|necessary|necessarily|properly|proper|appropriate|appropriately|applicable|allow|allows|allowed|allowing|needed|"
    r"adequate|adequately|effective|effectively|sufficient|sufficiently|timely|reasonable|reasonably|accordingly|where applicable|essential|ensure proper)\b", re.IGNORECASE)


def check_hedge(quote: str, pieces: list[str]) -> list[str]:
    """(a) a hedge word in the output that is not in the source quote."""
    have = {m.group(0).lower() for m in HEDGES.finditer(quote or "")}
    new = {m.group(0).lower() for p in pieces for m in HEDGES.finditer(p or "")} - have
    return [f"'{w}' not in the source" for w in sorted(new)]


# ---- (b) lead is a complete question ---------------------------------------------------------------------------------------------------------------------------------------------
_DANGLE = frozenset("to of in with for by on at from if whether that which who and or the a an not as than according accordance ensure ensures ensuring so under over per via".split())
_AUX = re.compile(r"^(?:does|do)\b", re.IGNORECASE)


def check_lead(lead: str) -> list[str]:
    """(b) opens Does/Do, ends with '?', contains the template phrase 'the following', and does not end in a dangling word."""
    l_ = (lead or "").strip()
    problems = []
    if not _AUX.match(l_):
        problems.append("lead does not open with Does/Do")
    if not l_.endswith("?"):
        problems.append("lead does not end with '?'")
    if not re.search(r"\bthe following\b", l_, re.IGNORECASE):
        problems.append("lead lacks 'the following'")
    last = re.sub(r"[^\w]", "", l_.rstrip("?").split()[-1].lower()) if l_.rstrip("?").split() else ""
    if last in _DANGLE:
        problems.append(f"lead ends with '{last}'")
    if len(l_.split()) > 30:
        problems.append("lead over 30 words")
    return problems


# ---- parts shape and the cross-product guard -------------------------------------------------------------------------------------------------------------------------------------
def check_parts(today: str, lead: str, parts: list[str], kind: str | None) -> list[str]:
    """2 to 5 parts and exactly one part per item of the list; each 'verbs' part is a Does/Do question that repeats the lead's actor, each 'objects' part a short noun phrase."""
    problems = []
    n = items_expected(today)
    if kind not in ("verbs", "objects"):
        problems.append(f"kind '{kind}' (rule 1: only a verb list or an object list)")
    if len(parts) != n:
        problems.append(f"{len(parts)} parts for {n} list items")
    for i, p in enumerate(parts):
        p = (p or "").strip()
        words = len(p.split())
        if not p.endswith("?"):
            problems.append(f"part {i + 1} does not end with '?'")
        if words > 25:
            problems.append(f"part {i + 1} has {words} words")
        if kind == "verbs":
            if not _AUX.match(p):
                problems.append(f"part {i + 1} is not a Does/Do question")
        elif kind == "objects":
            if _AUX.match(p) or words > 14:
                problems.append(f"part {i + 1} is not a short noun phrase")
    return problems


# ---- (c) coverage and no additions ------------------------------------------------------------------------------------------------------------------------------------------------
def check_coverage(today: str, quote: str, pieces: list[str]) -> list[str]:
    """(c) every content stem of today's question appears in the lead or a part, and no content stem appears that is in neither today's question nor the source quote."""
    have = stems(" ".join(pieces))
    want = stems(today)
    allowed = want | stems(quote) | ALLOWED_EXTRA
    problems = []
    missing = sorted(want - have)
    if missing:
        problems.append("dropped: " + ", ".join(missing))
    added = sorted(have - allowed)
    if added:
        problems.append("added: " + ", ".join(added))
    return problems


# ---- (d) parts are distinct ------------------------------------------------------------------------------------------------------------------------------------------------------
def check_distinct(parts: list[str]) -> list[str]:
    seen: dict[frozenset, int] = {}
    problems = []
    for i, p in enumerate(parts):
        key = frozenset(stems(p)) or frozenset({re.sub(r"\W", "", p.lower())})
        if key in seen:
            problems.append(f"part {i + 1} repeats part {seen[key] + 1}")
        seen[key] = i
    return problems


# ---- (e) strength and actor ------------------------------------------------------------------------------------------------------------------------------------------------------
_SOFT = re.compile(r"\b(?:may|might|can|could|should|permitted|allowed|optional|encouraged|recommended|authorized)\b", re.IGNORECASE)
_HARD = re.compile(r"\b(?:must|shall|required|requires?|mandatory|obligated|need to|needs to|have to|has to)\b", re.IGNORECASE)


def check_strength(today: str, quote: str, pieces: list[str]) -> list[str]:
    """(e) no permission word and no duty word that the source quote and today's question lack."""
    base = (quote or "") + " " + (today or "")
    joined = " ".join(pieces)
    soft = {m.group(0).lower() for m in _SOFT.finditer(joined)} - {m.group(0).lower() for m in _SOFT.finditer(base)}
    hard = {m.group(0).lower() for m in _HARD.finditer(joined)} - {m.group(0).lower() for m in _HARD.finditer(base)}
    return [f"adds '{w}'" for w in sorted(soft | hard)]


def _norm_words(text: str) -> list[str]:
    return [re.sub(r"[^\w/&.-]", "", w.lower()).replace("'", "") for w in text.split()]


def check_actor(today: str, lead: str) -> list[str]:
    """(e) the lead's actor equals today's actor: the words between the opening Does/Do and the lead's verb are a prefix of today's words after Does/Do (the lead may add only
    the filler verb 'do' / a main verb of today's question before 'all of the following')."""
    t = _norm_words(today)
    l_ = _norm_words(lead)
    if not t or not l_ or t[0] not in ("does", "do") or l_[0] not in ("does", "do"):
        return ["lead or today's question does not open with Does/Do"]
    core = l_[1:]
    for stop in ("all", "the"):
        if stop in core:
            core = core[: core.index(stop)]
            break
    if core and core[-1] == "do":
        core = core[:-1]
    # drop one verb at the end (the lead's main verb) and compare the rest with today's actor words
    if core and t[1:1 + len(core)] == core:
        return []
    if len(core) > 1 and core[-1] in t and t[1:len(core)] == core[:-1]:  # the lead's last word is a verb of today's question that follows the actor
        return []
    return [f"actor changed: today '{' '.join(t[1:5])}', lead '{' '.join(core)}'"]


NAMES = ["hedge", "lead", "parts", "coverage", "distinct", "strength", "actor"]


def evaluate(today: str, quote: str, kind: str | None, lead: str, parts: list[str]) -> dict[str, list[str]]:
    pieces = [lead] + list(parts)
    return {
        "hedge": check_hedge(quote, pieces),
        "lead": check_lead(lead),
        "parts": check_parts(today, lead, parts, kind),
        "coverage": check_coverage(today, quote, pieces),
        "distinct": check_distinct(parts),
        "strength": check_strength(today, quote, pieces),
        "actor": check_actor(today, lead),
    }


def failed(res: dict[str, list[str]]) -> list[str]:
    return [k for k in NAMES if res.get(k)]

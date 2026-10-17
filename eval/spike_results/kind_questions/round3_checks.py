"""Round 3: deterministic checks on permission questions (qualifiers kept, no dangling antecedent, no future / other-party question),
a descriptive-may fallback, and prompt v5. Pure functions; no model, no services edits."""
import re

import kind_questions as kq

_NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10", "twelve": "12"}
_TIME_WORDS = ("temporarily", "annually", "quarterly", "monthly", "weekly", "daily", "within", "until", "during", "before", "after")
_CONDITION_WORDS = ("while", "unless", "only", "provided")
_IF_FAMILY = {"if", "when", "where", "whenever", "once", "upon"}
_PRONOUN_START = re.compile(r"^\W*(?:\([\w-]+\)\s*)?(?:\d+\)\s*)?(?:In addition:\s*)?(?:(?:They|Them|Their|Such|These|Those|It)\b|In such (?:cases|instances)\b)", re.IGNORECASE)
_FUTURE = re.compile(r"\bfuture\b|\bnext (?:revision|version|update)\b", re.IGNORECASE)
_OTHER_PARTY = re.compile(r"\baccepted for credit\b|\bcredit at the\b", re.IGNORECASE)
_GENERIC_LIMIT = re.compile(
    r"^\W*(?:pursuant to|in accordance with|per|as (?:outlined|described|specified|directed|prescribed) in|IAW)\s+(?:the\s+)?(?:applicable|appropriate|this|these|existing|any)?\s*(?:\w+\s+){0,3}?"
    r"(?:provisions|procedures|guidance|policy|policies|regulations|instructions|manual|directives?|requirements)\b", re.IGNORECASE)
_SUBJECT_STOP = frozenset({"this", "that", "such", "with", "from", "which", "other", "also", "however", "their", "they", "them", "these", "those", "have", "been", "will", "shall",
                           "should", "include", "including", "purposes", "addition", "any", "all", "each", "significant"})


def permission_sentence(quote: str):
    """(text before the permission word within its sentence, the whole sentence) for the first genuine permission, or None."""
    m = kq.rk.first_permission(quote)
    if not m:
        return None
    start = max([0] + [x.end() for x in re.finditer(r"[.!?]\s+(?=[A-Z(])", quote[: m.start()])])
    end_m = re.search(r"[.!?](?:\s|$)", quote[m.end():])
    end = m.end() + end_m.end() if end_m else len(quote)
    return quote[start:m.start()], quote[start:end]


def _words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9/'-]*", text or "")}


def _stem(w: str) -> str:
    return re.sub(r"(?:ing|ed|es|s|ly)$", "", w.lower())[:6]


def missing_qualifiers(question: str, quote: str) -> list[str]:
    """Numbers, time words and condition words of the permission's own sentence that the question does not carry."""
    ps = permission_sentence(quote)
    if not ps:
        return []
    sentence = ps[1]
    qw = _words(question)
    miss = []
    plain = re.sub(r"\([A-Z]-\d\)|^\W*(?:\([\w-]+\)\s*)?\d+\)\s*|\b\d+(?:\.\d+)+\.?|\S*[A-Za-z/-]\d+\S*|\S*\d+[A-Za-z/-]\S*", " ", sentence)  # tier marks, list numbers, paragraph numbers, identifiers
    for tok in re.findall(r"\b\d+\b|\b(?:%s)\b" % "|".join(_NUMBER_WORDS), plain, re.IGNORECASE):
        t = tok.lower()
        alt = _NUMBER_WORDS.get(t) or next((w for w, d in _NUMBER_WORDS.items() if d == t), None)
        if t not in qw and (alt is None or alt not in qw):
            miss.append(t)
    sw = _words(sentence)
    for w in _TIME_WORDS + _CONDITION_WORDS:
        equivalents = {"after": {"after", "once", "following", "completed", "been"}, "before": {"before", "prior", "first"}}.get(w, {w})
        if w in sw and not (qw & equivalents):
            miss.append(w)
    if "if" in sw and not (qw & _IF_FAMILY):
        miss.append("if")
    return sorted(set(miss))


def subject_dropped(question: str, quote: str) -> bool:
    """True when fewer than half of the content words of the permission's subject (the 10 words before the modal) are in the question."""
    ps = permission_sentence(quote)
    if not ps:
        return False
    subj = re.sub(r"^\W*(?:\([\w-]+\)\s*)?(?:\d+\)\s*)?(?:In addition:\s*)?", "", ps[0])
    subj = " ".join(subj.split()[-10:])
    cw = [w for w in re.findall(r"[A-Za-z][A-Za-z/'-]{3,}", subj) if w.lower() not in _SUBJECT_STOP]
    if not cw:
        return False
    qstems = {_stem(w) for w in _words(question)}
    return sum(1 for w in cw if _stem(w) in qstems) / len(cw) < 0.5


def rejection(question, quote: str, limit) -> str | None:
    """The reason a permission question must become null, or None."""
    if not question:
        return None
    ps = permission_sentence(quote)
    if _PRONOUN_START.match(quote or "") or re.search(r"\bsuch\b", question, re.IGNORECASE):
        return "dangling reference (leans on a word whose antecedent is outside the row)"
    if _FUTURE.search(ps[1] if ps else quote or ""):
        return "about a future event"
    if _OTHER_PARTY.search(ps[1] if ps else quote or ""):
        return "decision belongs to another party"
    if limit and _GENERIC_LIMIT.match(limit.strip()):
        return "limit only points at 'applicable provisions' (always yes)"
    if limit_in_scope(question, limit):
        return "circular: the limit is repeated in the scope clause"
    miss = missing_qualifiers(question, quote)
    if miss:
        return "question drops a qualifier: " + ", ".join(miss)
    if subject_dropped(question, quote):
        return "question drops the trigger or actor of the permission"
    return None


_DESCRIPTIVE = re.compile(r"\b(?:description|describes|descriptive|merely|general statement|possibility)\b", re.IGNORECASE)


def fallback_keeps_v2(old_question, item: dict, why_null: str | None) -> tuple[bool, str]:
    """Round-2 fallback, plus: when the model says the 'may' only describes, a Do/Does-shaped old question is kept (it turns no grant into a duty), unless it says 'does the unit' or has duty words."""
    keep, reason = kq.fallback_keeps(old_question, item)
    if keep:
        return keep, reason
    q = (old_question or "").strip()
    if q and reason.startswith("existing question is duty-shaped") and why_null and _DESCRIPTIVE.search(why_null) and not kq._DUTY_WORDS.search(q):
        return True, "existing question kept: the 'may' only describes, so the question turns no grant into a duty"
    return keep, reason


_DESCRIPTIVE_MODAL = re.compile(r"\b(?:may|can)\s+(?:also\s+)?(?:necessitate|include|vary|differ|need|result|cause)\b", re.IGNORECASE)


def fallback_after_rejection(old_question, item: dict, why_null: str | None, rejected_by_check: bool) -> tuple[bool, str]:
    """Round-3 fallback: fallback_keeps_v2, plus today's question when a check rejected the new one and the row's modal is descriptive (may necessitate ...)."""
    q = (old_question or "").strip()
    if re.search(r"\bmay\b", q, re.IGNORECASE):
        return False, "existing question restates the 'may' inside the question (awkward; not kept)"
    keep, reason = fallback_keeps_v2(old_question, item, why_null)
    if keep:
        return keep, reason
    if (q and rejected_by_check and _DESCRIPTIVE_MODAL.search(item.get("source_quote") or "") and not re.search(r"\bmust\b|\bshall\b|\brequired\b", q, re.IGNORECASE)
            and not kq.aq.unverified_terms(q, kq.aq.row_material(item))):
        return True, "today's question kept: the sentence's modal only describes an effect (may necessitate ...), and a check rejected the new question"
    return keep, reason


PERMISSION_PROMPT_V5 = """You help an auditor check whether a unit stays within a permission that a regulation gives it.

The requirement below says something MAY be done. A permission is not a duty, so never ask whether the unit does it.

Step 1. Copy from the requirement, word for word, the SCOPE of the permission: who may act, when or how long ("temporarily", "while ...", "up to six months"), and under what condition ("if ...", "only ...", "unless ..."). Every one of these qualifiers must stay in your question. A question that drops a qualifier turns a narrow permission into a blanket rule.
Step 2. Copy the LIMIT: the restriction on using the permission (an approval or office it must go through, a size or time bound, a required condition). It must be a restriction, not a purpose, not a reason, not a means of doing it, and not a pointer to "applicable provisions".
Step 3. Write ONE yes/no question: "When/If <who> <does the permitted thing, with every qualifier from step 1>, <was / is / did> <the limit met>?" Plain words, full noun phrases (no "they", "such", "these").

Example. Requirement: "Junior staff may temporarily approve purchases up to $500 while the supervisor is away, with a written log entry."
Question: "When junior staff temporarily approve a purchase of up to $500 while the supervisor is away, is there a written log entry?"

Answer null (with the reason in "why_null") when:
- the "may" only describes or predicts (may include, may vary, may differ, may need, may be subject to, may necessitate, a possibility);
- no restriction is stated, or the only one is a purpose ("to ..."), a reason ("because of", "due to", "for noncompliance"), a means ("through", "via", "using" a named method that is only the way it is done), or "in accordance with applicable provisions/procedures";
- the subject is a pronoun or demonstrative with no noun in the requirement (They, Such, These, It);
- it is about a future revision, or the decision belongs to someone outside the unit (a college, another agency);
- the question would be answered "yes" simply because the permission was used.
Never write must, shall, required or "does the unit". Never leave a placeholder.

Applies to: {applies}
Requirement: {quote}
Surrounding text (context only):
{passage}

Answer as JSON: {{"grant": "<what is permitted, copied>", "limit": "<the limit, copied, or null>", "question": "<the question or null>", "why_null": "<reason or null>"}}."""
kq.PERMISSION_PROMPTS["v5"] = PERMISSION_PROMPT_V5
PERMISSION_PROMPT_V6 = PERMISSION_PROMPT_V5.replace(
    "Never write must, shall, required or \"does the unit\".",
    "Keep the scope and the limit in separate halves: never repeat the limit's words in the part before the comma, and never write \"is the condition met\". If the limit is \"when X allows\", ask \"does X allow it?\" (or \"did X allow it?\").\nNever write must, shall, required or \"does the unit\".")
kq.PERMISSION_PROMPTS["v6"] = PERMISSION_PROMPT_V6


def limit_in_scope(question: str, limit) -> bool:
    """True when the limit's words are repeated in the scope clause (the part before the first comma), the circular form 'When X includes Y when applicable ..., is it applicable?'."""
    if not question or not limit or "," not in question:
        return False
    head = question.split(",", 1)[0].lower()
    lim = " ".join(re.sub(r"\s+", " ", limit.lower()).split()[:6])
    return len(lim.split()) >= 3 and lim in head or "is the condition met" in question.lower()

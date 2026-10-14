"""Round 4: antecedent-aware permission questions (prompt v7), a bare-pronoun-scope check, a "for any specific X" scope check, a specificity comparison with today's
question, and one decide() used for both the six AFIs (part A) and the seven held-out documents (part B). Pure functions; no model, no services edits.
FROZEN after part A: nothing in this file changes between part A and part B (see ROUND4_PREREGISTRATION.md, Freeze section).
"""
import re

import kind_questions as kq
import round3_checks as r3

RULES_ROUND4 = "kind-questions-round4"
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
_LEAD = re.compile(r"^\W*(?:\d+(?:\.\d+)*\.?\s+|\([\w-]+\)\s*|[-•*]\s*)+")


def antecedent(item: dict, max_chars: int = 420) -> str:
    """The one or two sentences of the passage just before the marked requirement ('>> <<'): what "this", "such", "they" can refer to. Empty when the requirement opens the passage."""
    passage = item.get("passage") or ""
    i = passage.find(">>")
    if i <= 0:
        return ""
    before = re.sub(r"\s+", " ", passage[:i]).strip()
    before = re.sub(r"^\.\.\.\s*", "", before)
    before = re.sub(r"\(\s*T-\s*(?:-\s*)?\d?\s*\)|\(\s*T-\s*-\s*\d\s*\)|\(\s*T-\s*$", " ", before)  # tier marks, whole or cut by the chunk
    before = re.sub(r"(?:(?<=\s)|^)-\s+(?=\d)", " ", before)
    before = re.sub(r"(?:(?<=\s)|^)\d{1,2}(?:\.\d{1,2})+\.?(?=\s|$)", " ", before)  # paragraph numbers
    before = re.sub(r"\s+", " ", before).strip()
    if re.fullmatch(r"[\W\d]*", before):
        return ""
    sents = [s for s in _SENT.split(before) if s.strip()]
    take = sents[-2:] if sents else []
    text = " ".join(_LEAD.sub("", s, count=1).strip() for s in take).strip()
    if len(text) > max_chars:
        text = text[-max_chars:]
        text = text[text.find(" ") + 1:]
    return text


_BARE_SCOPE = re.compile(r"^\W*(?:when|if|where|once|whenever)\s+(?:this|it|they|that|these|those)\b", re.IGNORECASE)
_FOR_ANY = re.compile(r"\b(?:for|in|at|on)\s+(?:any|each|every)\s+(?:specific\s+|given\s+|single\s+)?([A-Za-z][A-Za-z0-9/-]{2,})", re.IGNORECASE)


def bare_pronoun_scope(question: str) -> bool:
    """True when the scope clause's subject is only "this / it / they": the reader cannot tell what is being waived, allowed, requested."""
    return bool(_BARE_SCOPE.match((question or "").strip()))


def dropped_for_any(question: str, quote: str) -> list[str]:
    """Scope words after "for any specific X / each X" in the permission's own sentence that the question lost (e.g. the JMAA of "for any specific JMAA")."""
    ps = r3.permission_sentence(quote)
    if not ps:
        return []
    qstems = {r3._stem(w) for w in r3._words(question)}
    return [m.group(1) for m in _FOR_ANY.finditer(ps[1]) if r3._stem(m.group(1)) not in qstems]


def resolves_antecedent(question: str, item: dict) -> bool:
    """True when the question names something from the antecedent sentence that the permission sentence itself does not contain."""
    ante = antecedent(item)
    if not ante:
        return False
    quote_stems = {r3._stem(w) for w in r3._words(item.get("source_quote") or "")}
    qstems = {r3._stem(w) for w in r3._words(question)}
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z/'-]{4,}", ante) if r3._stem(w) not in quote_stems and w.lower() not in r3._SUBJECT_STOP]
    return any(r3._stem(w) in qstems for w in words)


def rejection(question, item: dict, limit) -> str | None:
    """Why a permission question must become null (round 4 rules), or None."""
    if not question:
        return None
    quote = item.get("source_quote") or ""
    if bare_pronoun_scope(question):
        return "bare 'this/it/they' as the subject of the scope clause"
    if re.search(r"\bsuch\b", question, re.IGNORECASE):
        return "dangling reference ('such')"
    pronoun_source = bool(r3._PRONOUN_START.match(quote))
    if pronoun_source and not resolves_antecedent(question, item):
        return "the sentence opens with a pronoun and the question does not name what it refers to"
    # the rest of the round-3 checks, without its blanket pronoun rule
    ps = r3.permission_sentence(quote)
    if r3._FUTURE.search(ps[1] if ps else quote):
        return "about a future event"
    if r3._OTHER_PARTY.search(ps[1] if ps else quote):
        return "decision belongs to another party"
    if limit and r3._GENERIC_LIMIT.match(limit.strip()):
        return "limit only points at 'applicable provisions' (always yes)"
    if r3.limit_in_scope(question, limit):
        return "circular: the limit is repeated in the scope clause"
    miss = r3.missing_qualifiers(question, quote)
    if miss:
        return "question drops a qualifier: " + ", ".join(miss)
    anyq = dropped_for_any(question, quote)
    if anyq:
        return "question drops a scope word: " + ", ".join(anyq)
    if r3.subject_dropped(question, quote) and not pronoun_source:
        return "question drops the trigger or actor of the permission"
    return None


def coverage(question: str, item: dict) -> int:
    """How many distinct content words (5+ letters) of the permission sentence and its antecedent the question carries."""
    ps = r3.permission_sentence(item.get("source_quote") or "")
    text = (ps[1] if ps else item.get("source_quote") or "") + " " + antecedent(item)
    words = {r3._stem(w) for w in re.findall(r"[A-Za-z][A-Za-z/'-]{4,}", text)}
    qstems = {r3._stem(w) for w in r3._words(question)}
    return len(words & qstems)


def form_failures(question: str, item: dict) -> list[str]:
    """Round-1 automatic checks that reject a question (C5, the verbatim-limit check, only reports)."""
    return [f for f in kq.check_question(question, item, None) if f in ("C1_not_grounded", "C2_placeholder", "C3_not_yes_no", "C4_turns_may_into_duty")]


PERMISSION_PROMPT_V7 = """You help an auditor check whether a unit stays within a permission that a regulation gives it.

The requirement below says something MAY be done. A permission is not a duty, so never ask whether the unit does it.

Step 1. Name the subject. If the requirement opens with "This", "It", "They", "Such" or "In such cases", read the sentences just before it (given below) and name the real thing in your question (for example the requirement that is being waived), never "this" or "it" alone. If the requirement itself names a thing, use that.
Step 2. Copy from the requirement the SCOPE of the permission: who may act, when or how long ("temporarily", "while ...", "up to six months"), under what condition ("if ...", "only ..."), and any "for any specific X" or "each X". Every qualifier must stay in your question.
Step 3. Copy the LIMIT: the restriction on using the permission (an approval, an office it must go through, a size or time bound, a required condition). Not a purpose, not a reason, not only a means.
Step 4. Write ONE yes/no question: "When/If <who> <does the permitted thing, with every qualifier from step 2>, <was / is / did> <the limit met>?" Full noun phrases; name the approving office or document when the limit names one.

Example. Requirement: "This may be delayed for up to 30 days with the wing commander's written approval." Sentence before it: "Units will complete the annual inspection."
Question: "When a unit delays the annual inspection for up to 30 days, is there written approval from the wing commander?"

Answer null (with the reason in "why_null") when: the "may" only describes or predicts; no restriction is stated, or the only one is a purpose, a reason, a means, or "in accordance with applicable provisions"; the sentences before it do not say what a pronoun subject refers to; it is about a future revision or a decision outside the unit; the question would be answered "yes" simply because the permission was used.
Never write must, shall, required or "does the unit". Never leave a placeholder.

Applies to: {applies}
Sentence(s) just before the requirement: {antecedent}
Requirement: {quote}
Surrounding text (context only):
{passage}

Answer as JSON: {{"grant": "<what is permitted, copied>", "limit": "<the limit, copied, or null>", "question": "<the question or null>", "why_null": "<reason or null>"}}."""
kq.PERMISSION_PROMPTS["v7"] = PERMISSION_PROMPT_V7


def build_prompt_v7(item: dict) -> str:
    return PERMISSION_PROMPT_V7.format(applies=item.get("applies_to") or "(none)", antecedent=antecedent(item) or "(none: the requirement opens the passage)",
                                       quote=item.get("source_quote") or "", passage=(item.get("passage") or "")[:1200])


def decide(item: dict, answer: dict | None, live: str | None) -> dict:
    """The round-4 outcome for one permission row: final question (or None), the rule that fired, and notes. `answer` is the model's JSON (grant, limit, question, why_null)."""
    answer = answer or {}
    q, limit, why_null = answer.get("question"), answer.get("limit"), answer.get("why_null")
    q = None if (q is None or kq.aq.no_question(q)) else q.strip()
    limit = None if kq.aq.no_question(limit) else limit
    notes, rule, rejected_by_check = [], ("new boundary question" if q else "no stated limit"), False
    if q and kq.purpose_not_limit(limit):
        q, rule, rejected_by_check = None, f"rejected: limit is only a {kq.purpose_not_limit(limit)}", True
    if q:
        bad = form_failures(q, item)
        if bad:
            q, rule, rejected_by_check = None, "rejected: " + ", ".join(bad), True
    if q:
        why = rejection(q, item, limit)
        if why:
            q, rule, rejected_by_check = None, "rejected: " + why, True
    model_rejected = rejected_by_check
    if q and live:
        ok_live, _ = kq.fallback_keeps(live, item)
        if ok_live and coverage(live, item) > coverage(q, item):
            notes.append("today's question names more of the source than the new one: today's kept")
            q, rule = live, "today's question kept (more specific than the new one)"
        elif coverage(q, item) < coverage(live, item):
            notes.append("new question is less specific than today's")
    if not q:
        keep, reason = r3.fallback_after_rejection(live, item, why_null, rejected_by_check)
        if keep:
            q, rule = live, rule + "; today's question kept (" + reason + ")"
    return {"question": q, "rule": rule, "limit": limit, "why_null": why_null, "model_question_rejected": model_rejected, "notes": notes}

"""Round 5: additive-only policy for the permission path, a main-verb gate, a may-to-duty check, a document-level gate for guidance text, and decide5().
Pure functions; no model, no services edits. Builds on round3_checks / round4_checks.
"""
import re

import kind_questions as kq
import round3_checks as r3
import round4_checks as r4

DOC_GATE_SHARE = 0.25  # a document whose permission + recommendation rows are at least a quarter of all rows is guidance prose, not a duty document

_SUBORD = re.compile(r"\b(?:that|which|who|whom|whose|if|unless|because|although|though|while|whereas|since|when|whenever|once|until|so that)\b", re.IGNORECASE)
_INTRO_START = re.compile(r"^(?:when|if|where|once|upon|after|before|for|in|as|during|although|because|while|per|under|with|by|at|on|to)\b", re.IGNORECASE)
_DUTY_BEFORE = re.compile(r"\b(?:shall|must|will|should|needs?\s+to|have\s+to|has\s+to|(?:is|are)\s+expected\s+to|(?:is|are)\s+responsible|ensures?|(?:is|are)\s+required|(?:is|are)\s+to)\b", re.IGNORECASE)
_NEGATED = re.compile(r"^\W*(?:no|none|neither|nobody|nothing)\b|\bunless\b|\b(?:may|can)\s+not\b|\bnever\b|\bprohibited\b|\bcannot\b", re.IGNORECASE)
_DESCRIPTIVE_AFTER = re.compile(r"^\s*(?:also\s+|further\s+|then\s+)?(?:include|vary|differ|need|result|cause|necessitate|contain|require|involve|be\s+(?:subject|too|more|less|able|considered|deemed|useful|helpful|difficult|a\s+risk))\b", re.IGNORECASE)
_ROLE_CAPABILITY = re.compile(r"^\s*(?:can|could|may)\b", re.IGNORECASE)
_LIMIT_WORDS = re.compile(r"\d|\bonly\b|\bif\b|\bwhen\b|\bunless\b|\bwithin\b|\bthrough\b|\bvia\b|\bby\b|\bwith\b|\bafter\b|\bbefore\b|\buntil\b", re.IGNORECASE)
_INVENTED = re.compile(r"\b(?:recogni[sz]e[sd]?|consents?|acknowledg\w*)\b", re.IGNORECASE)


def main_verb_gate(item: dict) -> tuple[bool, str]:
    """True when may / can / is authorized to is the main verb of the row's own sentence. Detection (stated): take the sentence that holds the first genuine permission word; drop an
    introductory clause up to its comma ("When practical, ..."); keep what follows the last colon or semicolon; the subject region before the modal must (1) hold no subordinator
    (that, which, who, if, when, unless, because, while ...), (2) hold no duty word (shall, must, will, should, need to, ensure, is responsible ...), (3) not be negated (No ..., unless,
    may not, prohibited), (4) not open with a third-person command verb (a role-list bullet whose main verb is the first word), (5) be at most 25 words, and (6) the words after the modal
    must not be a description (may include, may vary, may need, may contain ...)."""
    quote = item.get("source_quote") or ""
    ps = r3.permission_sentence(quote)
    if not ps:
        return False, "no genuine may/can/authorized-to in the sentence"
    before, sentence = ps
    modal = kq.rk.first_permission(quote)
    after = quote[modal.end():modal.end() + 60] if modal else ""
    region = re.sub(r"^\W*(?:\([\w-]+\)\s*)?(?:\d+\)\s*)?(?:In addition:\s*)?", "", before)
    region = re.split(r"[:;]", region)[-1]
    if "," in region and _INTRO_START.match(region.strip()):
        region = region.rsplit(",", 1)[-1]
    if kq._third_person_command(region.strip() or quote) and len(region.split()) >= 2 and not re.match(r"^\W*(?:the|a|an|this|these|those|it)\b", quote, re.IGNORECASE):
        return False, "the sentence opens with a command verb: its main verb is a duty"
    if _NEGATED.search(region) or _NEGATED.search(sentence):
        return False, "prohibition or negated clause"
    if _SUBORD.search(region):
        return False, "may/can sits in a side clause (subordinator in the subject region)"
    if _DUTY_BEFORE.search(region):
        return False, "the main clause states a duty before the may/can"
    if len(region.split()) > 25:
        return False, "long subject region: may/can is probably in a side clause"
    if _DESCRIPTIVE_AFTER.match(after):
        return False, "the may only describes (may include / vary / need / contain ...)"
    if re.search(r"\bauthorit(?:y|ies)\b", region, re.IGNORECASE) and not re.search(r"\bauthorized\s+to\b", sentence, re.IGNORECASE):
        return False, "'authority' as a noun, not a grant"
    return True, "may/can is the main verb of the clause"


def document_gate(kind_counts: dict, rows: int) -> tuple[bool, float]:
    """(permission path allowed, share). Allowed unless permission + recommendation rows are at least DOC_GATE_SHARE of the document's rows."""
    share = (kind_counts.get("permission", 0) + kind_counts.get("recommendation", 0)) / max(1, rows)
    return share < DOC_GATE_SHARE, share


def may_to_duty(question: str, quote: str) -> str | None:
    """A rewrite that asks whether the permitted act happened ("may be used" -> "were used", "may need to be wiped" -> "is data being wiped") instead of whether its limit was met:
    a content verb that follows the source's modal appears in the part of the question that is asked (after the first comma) and not in the scope clause (before it)."""
    modal = kq.rk.first_permission(quote or "")
    if not modal or "," not in question:
        return None
    tail = quote[modal.end():]
    tail = re.split(r"[.;:]|\b(?:if|when|unless|with|through|via|only|for|to allow|in order)\b", tail)[0]
    m = re.match(r"\s*(?:also\s+)?(?:need\s+to\s+)?(?:be(?:en|ing)?\s+)?([A-Za-z]{4,})", tail, re.IGNORECASE)
    verbs = ([m.group(1)] if m else []) + [w for w in re.findall(r"\b[A-Za-z]{4,}ed\b", tail[:80])]  # the permitted verb, and past participles that follow it
    verbs = [w for w in verbs if w.lower() not in {"also", "which", "their", "other", "being", "within", "include", "including", "need"}]
    if not verbs:
        return None
    scope, asked = question.split(",", 1)
    scope_stems = {r3._stem(w) for w in r3._words(scope)}
    asked_stems = {r3._stem(w) for w in r3._words(asked)}
    for v in verbs[:4]:
        st = r3._stem(v)
        if st in asked_stems and st not in scope_stems:
            return f"the question asks whether the permitted act ('{v}') happened instead of whether its limit was met"
    return None


def such_dangling(question: str) -> bool:
    """"such as" is not dangling; "such X" is dangling only when it opens the question (no antecedent yet): within the first six words."""
    for m in re.finditer(r"\bsuch\b(?!\s+as\b)", question, re.IGNORECASE):
        if len(question[:m.start()].split()) < 6:
            return True
    return False


def subject_dropped5(question: str, quote: str) -> bool:
    """r3.subject_dropped, but the subject is only what follows the last colon or semicolon before the modal (a list lead-in such as "The DoD Component heads:" is not the subject)."""
    ps = r3.permission_sentence(quote)
    if not ps:
        return False
    region = re.split(r"[:;]", ps[0])[-1]
    return r3.subject_dropped(question, region + " may")


def rejection5(question, item: dict, limit) -> str | None:
    """r4.rejection with the round-5 changes: "such" handled by position, the may-to-duty check added."""
    if not question:
        return None
    quote = item.get("source_quote") or ""
    if r4.bare_pronoun_scope(question):
        return "bare 'this/it/they' as the subject of the scope clause"
    if such_dangling(question):
        return "dangling reference ('such' with no antecedent yet)"
    pronoun_source = bool(r3._PRONOUN_START.match(quote))
    if pronoun_source and not r4.resolves_antecedent(question, item):
        return "the sentence opens with a pronoun and the question does not name what it refers to"
    ps = r3.permission_sentence(quote)
    if r3._FUTURE.search(ps[1] if ps else quote):
        return "about a future event"
    if r3._OTHER_PARTY.search(ps[1] if ps else quote):
        return "decision belongs to another party"
    if limit and r3._GENERIC_LIMIT.match(limit.strip()):
        return "limit only points at 'applicable provisions' (always yes)"
    miss = r3.missing_qualifiers(question, quote)
    if miss:
        return "question drops a qualifier: " + ", ".join(miss)
    anyq = r4.dropped_for_any(question, quote)
    if anyq:
        return "question drops a scope word: " + ", ".join(anyq)
    if subject_dropped5(question, quote) and not pronoun_source:
        return "question drops the trigger or actor of the permission"
    head = r4.head_subject_dropped(question, quote)
    if head and not pronoun_source:
        return "question drops the thing that is permitted: " + ", ".join(head)
    duty = may_to_duty(question, quote)
    if duty:
        return duty
    return None


_RESTRICTING_TAIL = re.compile(r"\b(?:in accordance with|pursuant to|only|unless|provided|except|per|within|not to exceed|no more than|no later than)\b", re.IGNORECASE)  # a limit that opens with a purpose but also states a restriction


def is_capability(live: str | None) -> bool:
    """A bare capability question: "Can X ...?" that only asks whether something is possible (no number, no limit word)."""
    q = (live or "").strip()
    return bool(q and _ROLE_CAPABILITY.match(q) and not _LIMIT_WORDS.search(q))


def is_invented(live: str | None) -> bool:
    return bool(live and _INVENTED.search(live))


def clearly_better(new_q: str, live: str, limit: str | None, item: dict) -> tuple[bool, str]:
    """Mechanical test for replacing today's question: the new one carries at least 80% of the content words of the stated limit and today's carries under 50%,
    and the new one is not less specific overall."""
    words = {r3._stem(w) for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9/'-]{4,}", limit or "")}
    if not words:
        return False, "no limit words to compare"
    new_cov = len(words & {r3._stem(w) for w in r3._words(new_q)}) / len(words)
    old_cov = len(words & {r3._stem(w) for w in r3._words(live)}) / len(words)
    if new_cov >= 0.8 and old_cov < 0.5 and r4.coverage(new_q, item) >= r4.coverage(live, item):
        return True, f"new question carries {new_cov:.0%} of the limit's words, today's {old_cov:.0%}"
    return False, f"not clearly better (limit words: new {new_cov:.0%}, today's {old_cov:.0%})"


PERMISSION_PROMPT_V8 = r4.PERMISSION_PROMPT_V7.replace(
    "Never write must, shall, required or \"does the unit\". Never leave a placeholder.",
    "Keep \"only\": if the sentence says something may be done only by, in or through a named method, role or form, ask whether it was done only that way.\n"
    "Never turn \"may be used\" into \"was used\" or \"may need to be wiped\" into \"is it wiped\": the permitted act sits in the first half (\"When X is used / When data is wiped\"), the limit in the second.\n"
    "Never write must, shall, required or \"does the unit\". Never leave a placeholder.")
kq.PERMISSION_PROMPTS["v8"] = PERMISSION_PROMPT_V8


def build_prompt_v8(item: dict) -> str:
    return PERMISSION_PROMPT_V8.format(applies=item.get("applies_to") or "(none)", antecedent=r4.antecedent(item) or "(none: the requirement opens the passage)",
                                       quote=item.get("source_quote") or "", passage=(item.get("passage") or "")[:1200])


def decide5(item: dict, answer: dict | None, live: str | None) -> dict:
    """Round-5 outcome for a permission row that passed the gates: final question, action, rule. Additive-only: today's live question is never removed except a bare capability
    question or an invented 'recognize / consent' question, and only when the permission rule found no stated limit."""
    answer = answer or {}
    q, limit, why_null = answer.get("question"), answer.get("limit"), answer.get("why_null")
    q = None if (q is None or kq.aq.no_question(q)) else q.strip()
    limit = None if kq.aq.no_question(limit) else limit
    model_gave = bool(q)
    reject = None
    if q and kq.purpose_not_limit(limit) and not _RESTRICTING_TAIL.search(limit or ""):
        reject = f"limit is only a {kq.purpose_not_limit(limit)}"
    if q and not reject:
        bad = r4.form_failures(q, item)
        if bad:
            reject = ", ".join(bad)
    if q and not reject:
        reject = rejection5(q, item, limit)
    tpl = r4.waiver_template(item)
    notes = []
    if tpl and (not q or reject or r4.antecedent_named(q, item) < 0.6) and not r4.form_failures(tpl, item):
        q, reject, limit = tpl, None, limit or "waiver"
        notes.append("built from the sentence before it")
    if reject:
        notes.append("model question rejected: " + reject)
        q = None
    out = {"model_gave_question": model_gave, "model_question_rejected": bool(reject), "limit": limit, "why_null": why_null, "notes": notes}
    if q:
        if not live:
            return {**out, "question": q, "action": "added", "rule": "new boundary question where today's row has none"}
        if is_capability(live) or is_invented(live):
            return {**out, "question": q, "action": "replaced", "rule": "today's question was a bare capability / invented question; replaced by the boundary question"}
        better, why = clearly_better(q, live, limit, item)
        if better:
            return {**out, "question": q, "action": "replaced", "rule": "replaced today's question: " + why}
        return {**out, "question": live, "action": "kept_live", "rule": "new question not clearly better; today's kept (" + why + ")"}
    # no usable new question: today's question stays, unless it is a bare capability / invented question and the rule found no stated limit
    if live and not reject and not model_gave and (is_capability(live) or is_invented(live)):
        return {**out, "question": None, "action": "removed_capability", "rule": "no stated limit; today's question was only a capability / invented question (removed)"}
    return {**out, "question": live, "action": "kept_live" if live else "none", "rule": ("new question rejected; today's kept" if reject else "no stated limit; today's kept") if live else ("new question rejected; no question" if reject else "no stated limit; no question")}

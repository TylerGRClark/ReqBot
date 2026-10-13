"""Spike: kind-aware draft audit questions. Pure functions only (no model, no I/O); the model call lives in run_experiment.py.
Nothing here is imported by services/; it reads services.requirement_kind and services.audit_questions and wraps them.
"""
import re
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import audit_questions as aq  # noqa: E402
from services import requirement_kind as rk  # noqa: E402

# ---- rules-7 candidate: a leading imperative the shared verb list lacks ------------------------------------------------
RULES7_EXTRA_VERBS = frozenset({"authorize", "authorise", "allow", "permit", "grant", "deny", "delegate", "withhold", "revoke", "suspend", "restrict", "prevent", "lead"})
RULES_VERSION_CANDIDATE = "kind-rules-7-candidate"


@contextmanager
def extended_verbs():
    """The kinds module's verb set extended for the block. The module-level set is swapped and restored; services/ is not edited."""
    saved = rk._COMMAND_VERBS
    rk._COMMAND_VERBS = saved | RULES7_EXTRA_VERBS
    try:
        yield
    finally:
        rk._COMMAND_VERBS = saved


def classify_rules7(item: dict) -> dict:
    with extended_verbs():
        return rk.classify(item)


# ---- pointer rows ------------------------------------------------------------------------------------------------------
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
_SEE_PAREN = re.compile(r"\((?:see|refer to|per)\b[^)]*\)", re.IGNORECASE)
_POINTER_OPEN = re.compile(r"^\W*(?:\([\w-]+\)\s*)?(?:For\b[^,]{0,120},\s*)?(?:refer\s+to|see)\b", re.IGNORECASE)


def _is_pointer_sentence(s: str) -> bool:
    return bool(rk._POINTER.search(s) or rk._POINTS_TO.search(s) or _POINTER_OPEN.match(s))


def _third_person_command(s: str) -> bool:
    """"Provides AF customers guidance ...": a role-list bullet that states a duty in the third person with the actor left out."""
    m = re.match(r"^\W*([A-Za-z][A-Za-z-]*)\b", rk._opening(s))
    if not m:
        return False
    w = m.group(1).lower()
    base = [w[:-3] + "y"] if w.endswith("ies") else []
    base += [w[:-2]] if w.endswith("es") else []
    base += [w[:-1]] if w.endswith("s") else []
    return any(b in (rk._COMMAND_VERBS | RULES7_EXTRA_VERBS) for b in base)


def duty_outside_pointer(quote: str) -> str | None:
    """The sentence that states a duty although the row also points elsewhere, or None. A "(See Table 1.1)" aside does not make its sentence a pointer."""
    with extended_verbs():
        for sentence in _SENTENCE_SPLIT.split(quote.strip()):
            s = _SEE_PAREN.sub("", sentence).strip()
            if not s or _is_pointer_sentence(s):
                continue
            if rk._STRONG_DUTY.search(s) or rk.leading_command(s) or _third_person_command(s):
                return sentence
            if rk.classify({"source_quote": s, "item_flags": [], "citation": ""})["kind"] in ("duty_imperative", "duty_with_actor", "recommendation", "prohibition"):
                return sentence
    return None


def pointer_decision(item: dict) -> dict:
    """{"action": "suppress"|"keep", "reason"}: a pointer row with no duty of its own gets no question; one that also states a duty keeps its question."""
    quote = item.get("source_quote") or ""
    duty = duty_outside_pointer(quote)
    if duty:
        return {"action": "keep", "reason": "also states a duty, so the duty question stays", "duty_sentence": duty}
    return {"action": "suppress", "reason": "only points to another place (a pointer states no duty of its own; the duty is wherever it points)"}


# ---- recommendation rows -----------------------------------------------------------------------------------------------
RECOMMENDED_NOTE = "Recommended, not required: the text says \"should\". A \"no\" is worth noting but is not a violation."


def recommendation_flag(item: dict) -> dict:
    m = rk._SHOULD.search(item.get("source_quote") or "")
    return {"strength": "recommended", "strength_note": RECOMMENDED_NOTE, "matched": m.group(0) if m else None}


# ---- automatic checks --------------------------------------------------------------------------------------------------
_PLACEHOLDER = re.compile(r"\bX\b|\bY\b|the document allows|what the document (?:allows|says|permits)|within what the document|\[[^\]]*\]|<[^>]*>|\{[^}]*\}|\.\.\.|…|\bdoes\s+(?:it|this|that)\b\s*\?", re.IGNORECASE)
_AUX = r"(?:does|do|did|is|are|was|were|has|have|had|can|could|will|would|should)"
_YESNO = re.compile(rf"^\W*(?:(?:when|if|where|once|upon|after|before|whenever|in\s+cases\s+where)\b[^?]*?,\s*)?{_AUX}\b", re.IGNORECASE)
_DUTY_WORDS = re.compile(r"\bdoes\s+the\s+unit\b|\bdo\s+the\s+unit\b|\bmust\b|\bshall\b|\brequired\b|\bhas\s+to\b|\bhave\s+to\b|\bneeds?\s+to\b", re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def check_question(question: str, item: dict, limit: str | None = None) -> list[str]:
    """Names of the automatic checks the question fails (empty list = passes all)."""
    fails = []
    q = (question or "").strip()
    if aq.unverified_terms(q, aq.row_material(item)):
        fails.append("C1_not_grounded")
    if _PLACEHOLDER.search(q):
        fails.append("C2_placeholder")
    if not q.endswith("?") or not _YESNO.match(q):
        fails.append("C3_not_yes_no")
    if _DUTY_WORDS.search(q):
        fails.append("C4_turns_may_into_duty")
    if limit is not None and _norm(limit.strip(" .\"'")) not in _norm(item.get("source_quote") or ""):
        fails.append("C5_limit_not_verbatim")
    return fails


# ---- permission prompt -------------------------------------------------------------------------------------------------
SCHEMA = {
    "type": "object",
    "properties": {"grant": {"type": ["string", "null"]}, "limit": {"type": ["string", "null"]}, "question": {"type": ["string", "null"]}, "why_null": {"type": ["string", "null"]}},
    "required": ["grant", "limit", "question", "why_null"],
}

PERMISSION_PROMPTS = {}
PERMISSION_PROMPT_V1 = """You help an auditor check whether a unit stays within a permission that a regulation gives it.

The requirement below says something MAY be done. That is a permission, not a duty, so never ask whether the unit does it.
Find the limit or condition the requirement itself states for using the permission (a approval or office it must go through, a time or size limit, a trigger such as "if required", a restriction such as "only" or "not to exceed"). Then write ONE yes/no question that asks whether that limit or condition was met when the permission is used.

Rules:
- Use only words and facts from the requirement. Do not add numbers, deadlines, roles, offices, systems or documents that are not in it.
- Begin with "When", "If" or "Where" and the situation in which the permission is used, then ask the yes/no question about the limit. Example: requirement "A commander may delay the inspection up to 30 days with the wing commander's written approval." gives "When a commander delays an inspection, is the delay no more than 30 days and approved in writing by the wing commander?"
- Never ask "does the unit ..." for something that is only allowed. Never write must, shall or required. Never leave a placeholder such as X, and never write filler like "within what the document allows".
- "limit" must be copied word for word from the requirement.
- Answer with question null when the requirement states no limit or condition, or when "may" only describes (may include, may vary, may be a list of examples, a possibility) and grants nothing. Put the reason in "why_null".

Applies to: {applies}
Requirement: {quote}
Surrounding text (for context only; the limit must come from the requirement):
{passage}

Answer as JSON: {{"grant": "<what is permitted, copied from the requirement>", "limit": "<the limit or condition, copied from the requirement, or null>", "question": "<the question or null>", "why_null": "<reason or null>"}}."""


PERMISSION_PROMPTS["v1"] = PERMISSION_PROMPT_V1

PERMISSION_PROMPT_V2 = """You help an auditor check whether a unit stays within a permission that a regulation gives it.

The requirement below says something MAY be done. A permission is not a duty, so never ask whether the unit does it.
Find the limit or condition that the requirement itself states for USING the permission. A real limit restricts who, how, when, how long, by whose approval, or under what circumstances (an approval or office it must go through, a time or size limit, "only", "not to exceed", "with", "in coordination with", "if", "based on"). Then write ONE yes/no question that asks whether that limit or condition was met when the permission is used.

Rules:
- Use only words and facts from the requirement. Do not add numbers, deadlines, roles, offices, systems or documents that are not in it.
- Write it as: "When/If/Where <the permission is used>, <yes/no question about the limit>?" Natural, plain sentence. Examples:
  Requirement: "A commander may delay the inspection up to 30 days with the wing commander's written approval."
  Question: "When a commander delays an inspection, is the delay no more than 30 days and approved in writing by the wing commander?"
  Requirement: "Reports may be released to contractors only after the program office reviews them."
  Question: "When a report is released to a contractor, has the program office reviewed it first?"
- The limit must RESTRICT the permission. These are not limits, so answer null: a restatement of the permission itself, "as necessary", "as appropriate", "when applicable", "if required", a purpose ("to allow ...", "in order to ..."), or an example list.
- Answer null when "may" only describes or predicts and grants nothing: may include, may vary, may differ, may need, may be subject to, may result in, may necessitate, may be a list of examples, a possibility. Put the reason in "why_null".
- Never ask "does the unit ..." for something that is only allowed. Never write must, shall, required or "is it required". Never leave a placeholder such as X, and never write filler like "within what the document allows". Never write "is the limit that".
- "limit" must be copied word for word from the requirement.
- If the requirement states no limit that restricts how, when, by whom or under what circumstances the permission is used, answer question null and say so in "why_null".

Applies to: {applies}
Requirement: {quote}
Surrounding text (for context only; the limit must come from the requirement):
{passage}

Answer as JSON: {{"grant": "<what is permitted, copied from the requirement>", "limit": "<the limit or condition, copied from the requirement, or null>", "question": "<the question or null>", "why_null": "<reason or null>"}}."""
PERMISSION_PROMPTS["v2"] = PERMISSION_PROMPT_V2

PERMISSION_PROMPT_V3 = """You help an auditor check whether a unit stays within a permission that a regulation gives it.

The requirement below says something MAY be done. A permission is not a duty, so never ask whether the unit does it.
Find the limit or condition that the requirement itself states for USING the permission. A real limit restricts who, how, when, how long, by whose approval, or under what circumstances (an approval or office it must go through, a time or size limit, "only", "not to exceed", "with", "in coordination with", "if", "based on"). Then write ONE yes/no question that asks whether that limit or condition was met when the permission is used.

Rules:
- Use only words and facts from the requirement. Do not add numbers, deadlines, roles, offices, systems or documents that are not in it.
- Write it as: "When/If/Where <the permission is used>, <yes/no question about the limit>?" Natural, plain sentence. Examples:
  Requirement: "A commander may delay the inspection up to 30 days with the wing commander's written approval."
  Question: "When a commander delays an inspection, is the delay no more than 30 days and approved in writing by the wing commander?"
  Requirement: "Reports may be released to contractors only after the program office reviews them."
  Question: "When a report is released to a contractor, has the program office reviewed it first?"
- The limit must RESTRICT the permission. These are not limits, so answer null: a restatement of the permission itself, "as necessary", "as appropriate", "when applicable", "if required", a purpose ("to allow ...", "in order to ...", "for additional guidance", "to reflect ..."), a bare adverb ("periodically", "temporarily"), a reason the permission exists, or an example list.
- Test before you answer: if the question would be answered "yes" simply because the permission was used, it asks nothing. Then answer null.
- Answer null when "may" only describes or predicts and grants nothing: may include, may vary, may differ, may need, may be subject to, may result in, may necessitate, may be a list of examples, a possibility. Put the reason in "why_null".
- Never ask "does the unit ..." for something that is only allowed. Never write must, shall, required or "is it required". Never leave a placeholder such as X, and never write filler like "within what the document allows". Never write "is the limit that".
- "limit" must be copied word for word from the requirement.
- If the requirement states no limit that restricts how, when, by whom or under what circumstances the permission is used, answer question null and say so in "why_null".

Applies to: {applies}
Requirement: {quote}
Surrounding text (for context only; the limit must come from the requirement):
{passage}

Answer as JSON: {{"grant": "<what is permitted, copied from the requirement>", "limit": "<the limit or condition, copied from the requirement, or null>", "question": "<the question or null>", "why_null": "<reason or null>"}}."""
PERMISSION_PROMPTS["v3"] = PERMISSION_PROMPT_V3



def build_permission_prompt(item: dict, template: str = PERMISSION_PROMPT_V1) -> str:
    return template.format(applies=item.get("applies_to") or "(none)", quote=item.get("source_quote") or "", passage=(item.get("passage") or "")[:1200])


# ---- round 2 -----------------------------------------------------------------------------------------------------------
_PURPOSE_LIMIT = re.compile(r"^\W*(?:(?:in\s+order\s+to|so\s+as\s+to|to)\s+[a-z]+|for\s+(?:additional|further|more|the\s+purpose|guidance|information|reference|use)\b)", re.IGNORECASE)
_BARE_ADVERB = re.compile(r"^\W*(?:(?!only\b)[a-z]+ly|as\s+(?:required|necessary|appropriate|needed)|when\s+(?:necessary|required|applicable)|if\s+(?:required|necessary))\W*$", re.IGNORECASE)


def purpose_not_limit(limit: str | None) -> str | None:
    """"purpose" or "adverb" when the reported limit is only a purpose or a bare adverb, else None."""
    text = (limit or "").strip()
    if _PURPOSE_LIMIT.match(text):
        return "purpose"
    if _BARE_ADVERB.match(text):
        return "adverb"
    return None


_DUTY_SHAPED = re.compile(r"^\W*(?:do|does|did)\b", re.IGNORECASE)


def fallback_keeps(old_question: str | None, item: dict) -> tuple[bool, str]:
    """May the row's existing question stay when the permission rule gave no question? (keep, reason)"""
    q = (old_question or "").strip()
    if not q:
        return False, "no existing question"
    if aq.unverified_terms(q, aq.row_material(item)):
        return False, "existing question not grounded"
    if _DUTY_WORDS.search(q):
        return False, "existing question has duty words"
    if _DUTY_SHAPED.match(q):
        return False, "existing question is duty-shaped (Does/Do/Did) for a may"
    return True, "existing question is permission-shaped or neutral and grounded"


_SHOULD_IN_IF = re.compile(r"\b(?:determine[sd]?|decide[sd]?|assess(?:es)?)\s+(?:if|whether)\b[^.;]*?\bshould\b|\bshould\s+(?:those|these|this|that|such)\b", re.IGNORECASE)


def should_is_condition(quote: str) -> bool:
    """True when the row's "should" sits inside an if / whether / determine clause or is followed by those/these/this: a condition, not a recommendation."""
    return bool(_SHOULD_IN_IF.search(quote or ""))


def classify_wrapper(item: dict) -> dict:
    """Rules-7 verbs plus the if-clause "should" fix: the condition's "should" is masked before classifying."""
    if should_is_condition(item.get("source_quote") or ""):
        masked = dict(item, source_quote=re.sub(r"\bshould\b", "ought", item["source_quote"], flags=re.IGNORECASE))
        out = classify_rules7(masked)
        out["kind_reasons"] = out["kind_reasons"] + ["a 'should' inside an if-clause was ignored"]
        return out
    return classify_rules7(item)


def recommendation_flag_v2(item: dict) -> dict | None:
    """The recommended flag, or None when the kind (under the wrapper) is not recommendation."""
    return recommendation_flag(item) if classify_wrapper(item)["kind"] == "recommendation" else None


PERMISSION_PROMPT_V4 = PERMISSION_PROMPT_V3.replace(
    "- Test before you answer:",
    "- Alternatives are not limits: \"A or B\", \"may deviate from\", \"may necessitate\", \"may be done by\" describe options or effects. If the only restriction is a purpose or a reason (starts with \"to\" or \"for\"), answer null.\n- Test before you answer:")
PERMISSION_PROMPTS["v4"] = PERMISSION_PROMPT_V4

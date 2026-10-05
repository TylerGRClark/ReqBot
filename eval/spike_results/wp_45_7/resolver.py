"""WP-45.7: the resolver's output schema, prompt and worked examples (scratch only; no LLM is called here).

docs/PHASE45_WP457_PLAN.md appendix B, made concrete. One candidate per call; the model sees only the evidence bundle that
`bundle.py` builds. The shape is enforced at generation time by the JSON Schema `format` constraint (as Step C does with
`_PASS1_FORMAT_SCHEMA`), the prompt lists the allowed values in prose, and the worked examples are strictly valid JSON, so no
`a | b` placeholder is ever shown to the model. `check_resolution.py` validates the answer; the examples below must pass it
against their own bundles (a test enforces that), which keeps the prompt and the checker from drifting apart.
"""

import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bundle as B  # noqa: E402

STATUS = ("obligation", "recommendation", "permission", "prohibition", "scope_or_context", "not_a_requirement", "unresolved")
REQUIREMENT_STATUS = STATUS[:4]
CLASS = ("obligation", "recommendation", "permission", "prohibition", "none")
LOGIC = ("and", "or", "none")
VALUE_FIELDS = ("actor", "action", "target", "applicability", "timing", "parent")  # {value, evidence}
LIST_FIELDS = ("conditions", "exceptions")  # arrays of {value, evidence}
ORDER = (
    "status", "actor", "action", "target", "modality", "applicability", "conditions", "exceptions", "timing",
    "parent", "logic", "standalone_statement", "plain_language", "unresolved_reason",
)

_EVIDENCE = {"type": "array", "items": {"type": "string"}}
_NULLABLE = {"type": ["string", "null"]}


def _wrapped(value_schema):
    return {
        "type": "object",
        "properties": {"value": value_schema, "evidence": _EVIDENCE},
        "required": ["value", "evidence"],
    }


def json_schema():
    """The Ollama `format` schema: enums for status, modality class and logic; every other value a nullable string."""
    props = {
        "status": _wrapped({"type": "string", "enum": list(STATUS)}),
        "modality": {
            "type": "object",
            "properties": {"verbatim": _NULLABLE, "class": {"type": "string", "enum": list(CLASS)}, "evidence": _EVIDENCE},
            "required": ["verbatim", "class", "evidence"],
        },
        "logic": _wrapped({"type": "string", "enum": list(LOGIC)}),
    }
    for name in VALUE_FIELDS + ("standalone_statement", "plain_language", "unresolved_reason"):
        props[name] = _wrapped(_NULLABLE)
    for name in LIST_FIELDS:
        props[name] = {"type": "array", "items": _wrapped({"type": "string"})}
    return {"type": "object", "properties": {k: props[k] for k in ORDER}, "required": list(ORDER)}


INSTRUCTIONS = """You are resolving ONE candidate requirement from a compliance document, using only the evidence below. Do not use outside knowledge. Every field is an object with a "value" and the evidence ids ("E1", "E2", ...) that support it. If the evidence does not support a field, its value is null and its evidence list is empty. Spans marked "unverified" were found by a rule and may be wrong: use one only if the other evidence agrees.

Fields:
- status: obligation (must, shall, will, a mandatory duty), recommendation (should, should not, is recommended, a hint at what to do), permission (may, is authorized to), prohibition (shall not, must not), scope_or_context (says who or what the document covers; it is kept and attached, not a requirement), not_a_requirement (a description or background, not something anyone is asked or allowed to do), or unresolved (the evidence is not enough to decide).
- actor: the party that must act. An approver or authorizer is NOT the actor. A list item with no subject inherits it from the lead-in span you cite.
- action, target: what is done, and to what.
- modality: "verbatim" is the exact modal phrase copied from a cited span (shall, must, will, is required to, should, should not, may, is authorized to, shall not, is prohibited from), or null for an imperative with no modal anywhere in the cited spans. "class" is the strength it carries, in the same words as status: obligation, recommendation, permission, prohibition, or none. Never turn "may" or "should" into "shall"; "should not" is a recommendation, not a prohibition.
- applicability: who or what it applies to. conditions, exceptions: copy them; do not drop an exception. timing: when or how often.
- parent: the governing clause text, if one of the spans is it. logic: and or or if the text says how sibling items combine, otherwise none.
- standalone_statement: one sentence built only from the cited spans that keeps the modality, conditions and exceptions; null if it cannot be built without adding a fact. plain_language: the same meaning in simpler words, adding no number, name or party; null when standalone_statement is null.
- unresolved_reason: what is missing and where it might be, only when status is unresolved.

Examples (invented text). Answer with one JSON object in the same shape."""


def _span(kind, label, text, unverified=False):
    return {"kind": kind, "label": label, "text": text, "unverified": unverified}


def _f(value, *evidence):
    return {"value": value, "evidence": list(evidence)}


def _answer(status, status_ev, actor=None, action=None, target=None, modality=(None, "none", ()), applicability=None,
            conditions=(), exceptions=(), timing=None, parent=None, logic=("none", ()), standalone=None, plain=None,
            reason=None):
    def opt(pair):
        return _f(None) if pair is None else _f(pair[0], *pair[1])

    return {
        "status": _f(status, *status_ev),
        "actor": opt(actor), "action": opt(action), "target": opt(target),
        "modality": {"verbatim": modality[0], "class": modality[1], "evidence": list(modality[2])},
        "applicability": opt(applicability),
        "conditions": [_f(v, *e) for v, e in conditions],
        "exceptions": [_f(v, *e) for v, e in exceptions],
        "timing": opt(timing), "parent": opt(parent),
        "logic": _f(logic[0], *logic[1]),
        "standalone_statement": opt(standalone), "plain_language": opt(plain),
        "unresolved_reason": opt(reason),
    }


EXAMPLES = [
    {
        "title": "a list item that inherits its subject",
        "spans": [
            _span("candidate", "candidate quote", "b. Reviews disposal schedules each year."),
            _span("heading", "heading (leaf)", "4.2 RECORDS OFFICER"),
            _span("stem", "possible governing clause, found by rule: previous chunk", "4.2 The Records Officer will:", True),
        ],
        "unresolved": [],
        "answer": _answer(
            "obligation", ("E1", "E3"),
            actor=("The Records Officer", ("E3",)), action=("Reviews disposal schedules", ("E1",)),
            target=("disposal schedules", ("E1",)), modality=("will", "obligation", ("E3",)),
            timing=("each year", ("E1",)), parent=("4.2 The Records Officer will:", ("E3",)),
            standalone=("The Records Officer will review disposal schedules each year.", ("E1", "E3")),
            plain=("The Records Officer has to look over the disposal schedules every year.", ()),
        ),
    },
    {
        "title": "a prohibition with an exception (the approver is not the actor)",
        "spans": [_span("candidate", "candidate quote", "Contractors shall not transmit logs offshore unless the Program Manager approves in writing.")],
        "unresolved": [],
        "answer": _answer(
            "prohibition", ("E1",),
            actor=("Contractors", ("E1",)), action=("transmit logs offshore", ("E1",)), target=("logs", ("E1",)),
            modality=("shall not", "prohibition", ("E1",)),
            exceptions=[("unless the Program Manager approves in writing", ("E1",))],
            standalone=("Contractors shall not transmit logs offshore unless the Program Manager approves in writing.", ("E1",)),
            plain=("Contractors must not send logs outside the country unless the Program Manager approves in writing.", ()),
        ),
    },
    {
        "title": "a permission, never strengthened",
        "spans": [_span("candidate", "candidate quote", "The Authorizing Official may grant a waiver for up to six months.")],
        "unresolved": [],
        "answer": _answer(
            "permission", ("E1",),
            actor=("The Authorizing Official", ("E1",)), action=("grant a waiver", ("E1",)), target=("a waiver", ("E1",)),
            modality=("may", "permission", ("E1",)), timing=("for up to six months", ("E1",)),
            standalone=("The Authorizing Official may grant a waiver for up to six months.", ("E1",)),
            plain=("The Authorizing Official is allowed to give a waiver that lasts up to six months.", ()),
        ),
    },
    {
        "title": "a negative recommendation (should not stays a recommendation)",
        "spans": [_span("candidate", "candidate quote", "Administrators should not reuse passwords.")],
        "unresolved": [],
        "answer": _answer(
            "recommendation", ("E1",),
            actor=("Administrators", ("E1",)), action=("reuse passwords", ("E1",)), target=("passwords", ("E1",)),
            modality=("should not", "recommendation", ("E1",)),
            standalone=("Administrators should not reuse passwords.", ("E1",)),
            plain=("Administrators are advised not to use the same password twice.", ()),
        ),
    },
    {
        "title": "a cross-reference the evidence does not contain",
        "spans": [_span("candidate", "candidate quote", "Comply with the requirements of paragraph 4.2.")],
        "unresolved": ["paragraph 4.2"],
        "answer": _answer(
            "unresolved", ("E1",), action=("Comply with the requirements of paragraph 4.2", ("E1",)),
            reason=("paragraph 4.2 is not in the evidence", ()),
        ),
    },
    {
        "title": "scope text, kept but not a requirement",
        "spans": [_span("candidate", "candidate quote", "This manual applies to all network operators.")],
        "unresolved": [],
        "answer": _answer("scope_or_context", ("E1",), applicability=("all network operators", ("E1",))),
    },
]


def example_bundle(example):
    """The example's evidence as a real `bundle.Bundle`, so it renders exactly as a live bundle would."""
    b = B.Bundle(tier="R1")
    for i, s in enumerate(example["spans"], 1):
        b.spans.append(B.Span(id=f"E{i}", kind=s["kind"], label=s["label"], text=B.normalize(s["text"]), unverified=s["unverified"]))
    b.unresolved_references = list(example["unresolved"])
    return b


def render_examples():
    parts = []
    for n, ex in enumerate(EXAMPLES, 1):
        parts.append(f"Example {n}: {ex['title']}\n{example_bundle(ex).render()}\nAnswer: {json.dumps(ex['answer'], ensure_ascii=False, separators=(',', ':'))}")
    return "\n\n".join(parts)


def render_prompt(bundle):
    """The full prompt for one candidate: instructions, worked examples, then the live evidence bundle."""
    return f"{INSTRUCTIONS}\n\n{render_examples()}\n\nNow resolve this candidate.\n{bundle.render()}\nAnswer:"


def fixed_prompt():
    """Everything in the prompt except the live evidence bundle."""
    return f"{INSTRUCTIONS}\n\n{render_examples()}\n\nNow resolve this candidate.\n\nAnswer:"


def fixed_tokens():
    """Estimated tokens of the fixed prompt text, at the builder's conservative 2.5 characters per token."""
    return B.estimate_tokens(len(fixed_prompt()))


def prompt_hash():
    return hashlib.sha256((fixed_prompt() + json.dumps(json_schema(), sort_keys=True)).encode("utf-8")).hexdigest()[:16]

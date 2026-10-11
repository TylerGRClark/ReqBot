"""Requirement kind, stage 1 (docs/PIPELINE_REDESIGN_PLAN.md section 10): what sort of statement a checklist row is.

Rule-based and verbatim: it reads the row's own words, its citation and its hint flags, never a model, and writes labels beside the row. It never edits the requirement, never drops a row
and never changes what any reader shows. `unknown` is a legal answer. Stage 1 stores the labels in a sidecar file (`<doc>_kinds.jsonl`, like the draft questions) so the first rules can be
rated before any reader uses them; the plan's step between context attaching and screening comes with the stages that read the kind.
"""
import json
import os
import re
from pathlib import Path

from services import checklist_audit

RULES_VERSION = "kind-rules-2"
KINDS = (
    "duty_with_actor", "duty_imperative", "recommendation", "permission", "prohibition", "exemption", "definition_or_description", "applicability", "pointer", "table_row",
    "form_template_text", "cover_page_text", "unknown",
)

_STRONG = re.compile(r"\b(shall|must|will|is responsible|are responsible|is required|are required|required to|is to|are to|ensure|ensures)\b", re.IGNORECASE)
_STRONG_DUTY = re.compile(r"\b(shall|must|will|is responsible|are responsible|is required|are required|required to)\b", re.IGNORECASE)  # without "ensure": "To ensure ..." opens a purpose clause
_SHOULD = re.compile(r"\bshould\b(?!\s+(?:the|a|an|any|it|they|there)\b)", re.IGNORECASE)  # "should the asset fail" is a condition, not a recommendation
_PERMIT = re.compile(r"\b(may|can|is authorized to|are authorized to|at its discretion|has the option|is permitted|are permitted)\b", re.IGNORECASE)
_PROHIBIT = re.compile(
    r"\b(?:shall|must|should|will|may|can|could|would)\s+not\b(?!\s+(?:limited|only|necessarily))|\bcannot\b|\bnever\b|\bprohibited\b|\bforbidden\b"
    r"|\b(?:is|are)\s+not\s+(?:authorized|permitted|allowed|appropriate|acceptable|permissible|waivable|to)\b|^\W*(?:\([\w-]+\)\s*)?(?:do|does)\s+not\b", re.IGNORECASE)
_EXEMPT = re.compile(
    r"\b(?:does|do)\s+not\s+apply\b|\b(?:is|are)\s+exempt\b|\b(?:does|do)\s+not\s+have\s+to\b|\bnot\s+required\s+to\b|\b(?:is|are)\s+not\s+required\b", re.IGNORECASE)
_POINTER = re.compile(
    r"\b(?:can|may)\s+be\s+found\s+(?:in|at|on)\b|\bare\s+listed\s+in\b|\bis\s+available\s+(?:at|on|in)\b|\brefer\s+to\b|\bsee\s+(?:paragraph|section|attachment|reference|table|figure)\b",
    re.IGNORECASE)
_PURPOSE = re.compile(r"^\W*(?:\([\w-]+\)\s*)?To\s+[a-z]+\b")
_BACK_REFERENCE = re.compile(r"^\W*(?:\([\w-]+\)\s*)?(?:\d+\)?\s*)?(?:In addition:\s*)?(This|These|Such|That|Those|It|They)\b")


# Verbs that open a command in an AFI duty list. The shared list (the "no actor stated" hint) is left alone; these are verbs seen opening rows that kind-rules-1 left `unknown`.
_COMMAND_VERBS = checklist_audit.IMPERATIVE_VERBS | frozenset({
    "adhere", "appoint", "assist", "brief", "categorize", "characterize", "collect", "configure", "confirm", "consolidate", "create", "define", "deliver", "deploy", "design", "engage",
    "enter", "facilitate", "focus", "foster", "fulfill", "incorporate", "include", "inform", "interpret", "isolate", "leverage", "link", "optimize", "pay", "publish", "receive",
    "reconcile", "reduce", "register", "resolve", "serve", "share", "sign", "synchronize", "take", "terminate", "transfer", "understand", "utilize", "work", "act",
})
_TIER_MARK = re.compile(r"^\W*(?:\(\s*[A-Za-z]-\d\s*\)\s*)+")
_IN_ADDITION = re.compile(r"^(?:\d+\)\s*)?In addition:\s*", re.IGNORECASE)
_CONDITION_LEAD = re.compile(r"^(?:as|if|when|where|once|upon|in|for|under|during|before|after|unless)\b[^,;:]{3,140},\s+", re.IGNORECASE)
_ADVERB = re.compile(r"^[a-z]+ly\s+", re.IGNORECASE)
_MODAL_SOON = re.compile(r"^(?:\S+\s+){0,3}?(?<!that )(?<!who )(?<!which )(?:shall|must|will)\b", re.IGNORECASE)  # "Design authorities shall ...": the first word is a noun; "units that will deploy" is not
_ACTOR_COLON = re.compile(r"^(?P<actor>[A-Z][^:;.]{1,70}?):\s+(?P<rest>\S.*)$", re.DOTALL)
_NOT_AN_ACTOR = frozenset({"in addition", "note", "notes", "example", "examples", "exception", "exceptions", "reminder", "caution", "warning", "purpose", "rationale", "for example"})
_RESPONSIBILITY = re.compile(r"\b(?:retain|retains|have|has|assume|assumes|bear|bears)\s+(?:\S+\s+){0,4}?responsibilit(?:y|ies)\b", re.IGNORECASE)


def _opening(text: str) -> str:
    """The quote without list markers, paragraph numbers, tier marks ("(T-1)") and "In addition:"."""
    text = text or ""
    for _ in range(3):
        before = text
        text = re.sub(r"^\s*[-•*]\s*", "", text)
        text = checklist_audit._LIST_MARKER.sub("", text, count=1)
        text = checklist_audit._PARAGRAPH_NUMBER.sub("", text, count=1)
        text = _TIER_MARK.sub("", text, count=1)
        text = _IN_ADDITION.sub("", text, count=1).lstrip()
        if text == before:
            break
    return text


def _command(text: str):
    """The base-form command verb that opens `text`, or None. A leading -ly adverb is skipped ("Immediately notify ..."); "Use of ..." and "Design authorities shall ..." are nouns."""
    probe = _ADVERB.sub("", text, count=1)
    m = re.match(r"([A-Za-z][A-Za-z-]*)\b(.*)", probe, re.DOTALL)
    if not m or m.group(1).lower() not in _COMMAND_VERBS:
        return None
    rest = m.group(2).lstrip()
    if re.match(r"of\b", rest, re.IGNORECASE) or _MODAL_SOON.match(rest):
        return None
    return m.group(1)


def leading_command(quote: str):
    """The verb of a command that opens the sentence, directly or after a condition or role lead ("As the DIB lead, provide ..."); None when the sentence has its own subject."""
    text = _opening(quote)
    if verb := _command(text):
        return verb
    if lead := _CONDITION_LEAD.match(text):
        return _command(_opening(text[lead.end():]))
    return None


def named_actor_then_command(quote: str):
    """("The I-NOSCs", "Report") for "The I-NOSCs: Report suspected events ...": a noun phrase, a colon, a command."""
    m = _ACTOR_COLON.match(_opening(quote))
    if not m or m.group("actor").strip().lower() in _NOT_AN_ACTOR or len(m.group("actor").split()) > 8 or _STRONG.search(m.group("actor")):
        return None
    verb = _command(m.group("rest"))
    return (m.group("actor").strip(), verb) if verb else None


POSITION_KINDS = frozenset({"table_row", "form_template_text", "cover_page_text"})  # decided by where the row sits, not by what it says


def classify(item: dict, *, use_position: bool = True) -> dict:
    """{"kind", "kind_reasons", "kind_tags"} for one checklist item, and `kind_by_wording` when the kind comes from where the row sits (what the kind would be if its position were ignored:
    a duty sentence in a table cell is a table_row and a duty). The first rule that matches decides the kind; the reasons name the rule and the words it matched."""
    quote = item.get("source_quote") or ""
    flags = set(item.get("item_flags") or [])
    citation = str(item.get("citation") or "")
    kind, reasons = None, []

    def decide(name: str, why: str, match=None):
        nonlocal kind, reasons
        if kind is None:
            kind, reasons = name, [why + (f": {match.group(0).strip()!r}" if match else "")]

    if use_position and citation.startswith("Figure"):
        decide("form_template_text", f"cited by a figure caption ({citation})")
    elif use_position and citation == "Front matter" and "applicability_statement" in flags:
        decide("applicability", "says who the document applies to (in the front matter)")
    elif use_position and citation == "Front matter":
        decide("cover_page_text", "cited as front matter")
    elif use_position and citation.startswith("Table"):
        decide("table_row", f"cited by a table caption ({citation})")
    elif "applicability_statement" in flags:
        decide("applicability", "says who the document applies to")
    elif (m := _POINTER.search(quote)) and not _STRONG.search(quote):
        decide("pointer", "points elsewhere", m)
    elif m := _PROHIBIT.search(quote):
        allowed = _PERMIT.search(quote)
        if allowed and allowed.start() < m.start():  # "may extend ..., but shall not authorize consecutive waivers": the grant comes first and the negation limits it
            decide("permission", "grants a permission that a later negation limits", allowed)
        else:
            decide("prohibition", "a negation of an obligation or permission", m)
    elif m := _EXEMPT.search(quote):
        decide("exemption", "says something does not apply or is not required", m)
    elif "definition_or_description" in flags and not _STRONG_DUTY.search(quote):
        decide("definition_or_description", "defines or describes, no obligation word")
    elif _PURPOSE.match(quote) and not _STRONG_DUTY.search(quote):
        decide("unknown", "opens with a purpose clause (To ...) and has no obligation word")
    elif verb := leading_command(quote):
        decide("duty_imperative", f"opens with a command ({verb}) and names no actor")
    elif pair := named_actor_then_command(quote):
        decide("duty_with_actor", f"names its actor ({pair[0]}), then a command ({pair[1]})")
    elif m := _STRONG.search(quote):
        decide("duty_with_actor", "an obligation word", m)
    elif m := _RESPONSIBILITY.search(quote):
        decide("duty_with_actor", "says who retains or has a responsibility", m)
    elif m := _SHOULD.search(quote):
        decide("recommendation", "says what should happen", m)
    elif m := _PERMIT.search(quote):
        decide("permission", "says what may be done", m)
    elif "no_stated_actor" in flags or checklist_audit._is_verb(checklist_audit._first_word(quote), _COMMAND_VERBS):
        decide("duty_imperative", "opens with a command and names no actor")
    else:
        decide("unknown", "no wording cue")

    tags = []
    if _BACK_REFERENCE.match(quote):
        tags.append("refers_back")
    if "list_item" in flags:
        tags.append("list_item")
    if flags & {"starts_mid_sentence", "table_fragment"} and kind != "table_row":
        tags.append("fragment")
    if citation == "Front matter" and kind != "cover_page_text":
        tags.append("front_matter")
    out = {"kind": kind, "kind_reasons": reasons, "kind_tags": tags}
    if kind in POSITION_KINDS and use_position:
        out["kind_by_wording"] = classify(item, use_position=False)["kind"]
    return out


def sidecar_path(requirements_path: Path) -> Path:
    """`<doc>_kinds.jsonl` beside `<doc>_requirements_*.jsonl`."""
    name = re.sub(r"_requirements_(?:normalized|enriched|gated)\.jsonl$", "", requirements_path.name)
    return requirements_path.with_name(f"{name}_kinds.jsonl")


def label_items(items: list[dict]) -> dict[str, dict]:
    """{checklist_item_id: record} for every item that has a requirement text."""
    out = {}
    for item in items:
        if not (item.get("source_quote") or "").strip():
            continue
        out[item["checklist_item_id"]] = {"checklist_item_id": item["checklist_item_id"], **classify(item), "rules_version": RULES_VERSION}
    return out


def write(path: Path, records: dict[str, dict]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records.values()), encoding="utf-8")
    os.replace(tmp, path)


def load(path: Path) -> dict[str, dict]:
    """{checklist_item_id: record}; a missing or unreadable file is an empty set."""
    out: dict[str, dict] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict) and rec.get("checklist_item_id"):
                    out[rec["checklist_item_id"]] = rec
    except OSError:
        pass
    return out


def counts(records: dict[str, dict]) -> dict[str, int]:
    tally = {k: 0 for k in KINDS}
    for rec in records.values():
        tally[rec["kind"]] = tally.get(rec["kind"], 0) + 1
    tally["total"] = len(records)
    return tally

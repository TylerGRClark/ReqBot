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

RULES_VERSION = "kind-rules-8"
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
    r"\b(?:does|do)\s+not\s+apply\b|\b(?:(?:will|shall|must)\s+)?(?:is|are|be)\s+exempt\b|\b(?:does|do)\s+not\s+have\s+to\b|\bnot\s+required\s+to\b|\b(?:is|are)\s+not\s+required\b", re.IGNORECASE)
_POINTER = re.compile(
    r"\b(?:can|may)\s+be\s+found\s+(?:in|at|on|with|within|under|through|via)\b|\bare\s+listed\s+in\b|\b(?:is|are)\s+(?:explained|described|outlined|detailed|addressed|discussed)\s+in\b|\bis\s+available\s+(?:at|on|in)\b|\brefer\s+to\b|\bsee\s+(?:paragraph|section|attachment|reference|table|figure)\b",
    re.IGNORECASE)
_PURPOSE = re.compile(r"^\W*(?:\([\w-]+\)\s*)?To\s+[a-z]+\b")
_BACK_REFERENCE = re.compile(r"^\W*(?:\([\w-]+\)\s*)?(?:\d+\)?\s*)?(?:In addition:\s*)?(This|These|Such|That|Those|It|They)\b")


# Verbs that open a command in an AFI duty list. The shared list (the "no actor stated" hint) is left alone; these are verbs seen opening rows that kind-rules-1 left `unknown`.
_COMMAND_VERBS = checklist_audit.IMPERATIVE_VERBS | frozenset({
    "adhere", "appoint", "are", "assist", "be", "brief", "categorize", "characterize", "charter", "collect", "configure", "confirm", "consolidate", "create", "decide", "define", "deliver", "deploy", "design", "engage",
    "enter", "facilitate", "focus", "foster", "fulfill", "incorporate", "include", "inform", "interpret", "is", "isolate", "leverage", "link", "optimize", "pay", "publish", "receive",
    "reconcile", "reduce", "register", "resolve", "serve", "set", "share", "sign", "synchronize", "take", "terminate", "transfer", "understand", "utilize", "work", "act",
    "contact", "follow", "inspect", "solicit",  # kind-rules-7: opening commands seen on rows left `unknown` in a 228-row sample
    "avoid", "consult", "dispose", "exercise", "limit", "pull", "present", "mitigate", "wear", "generate", "decertify",  # kind-rules-8
})
_TIER_MARK = re.compile(r"^\W*(?:\(\s*[A-Za-z]-\d\s*\)\s*)+")
_IN_ADDITION = re.compile(r"^(?:\d+\)\s*)?In addition:\s*", re.IGNORECASE)
_CONDITION_LEAD = re.compile(r"^(?:as|if|when|where|once|upon|in|for|under|during|before|after|unless)\b[^,;:]{3,140},\s+", re.IGNORECASE)
_ADVERB = re.compile(r"^[a-z]+ly\s+", re.IGNORECASE)
_MODAL_SOON = re.compile(r"^(?:\S+\s+){0,3}?(?<!that )(?<!who )(?<!which )(?:shall|must|will)\b", re.IGNORECASE)  # "Design authorities shall ...": the first word is a noun; "units that will deploy" is not
_ACTOR_COLON = re.compile(r"^(?P<actor>[A-Z][^:;.]{1,70}?):\s+(?P<rest>\S.*)$", re.DOTALL)
_DOCUMENT_AS_ACTOR = re.compile(r"\b(?:this|the)\s+(?:\w+\s+){0,2}?(?:issuance|instruction|publication|directive|manual|policy|memorandum|document|pamphlet)\s*$", re.IGNORECASE)
_CONTACT_AS_NOUN = re.compile(r"^\W*(?:\([\w-]+\)\s*)?(?:contact\s*(?::|(?:information|info|details|numbers?|lists?|persons?|points?|e-?mail|phone)\b)|wear\s+(?:criteria|guidance|standards?)\b)", re.IGNORECASE)  # a label or a noun phrase
_NEGATED_OR_HYPOTHETICAL = re.compile(r"\b(?:not|never|no|could|would|might|may|can|cannot)\b[^.;:]{0,30}$", re.IGNORECASE)  # "do not require", "could result in"
_IMPLIED_DUTY = re.compile(r"\b(?:require\b|mandates\b|needs\s+to\b|(?:is|are|be)\s+only\s+(?:authorized|permitted|issued|allowed)\b|is\s+the\s+only\s+authority\b)", re.IGNORECASE)  # plural "require", not "requires" or "need to" (measured 23 of 28 real against 19 of 31 and 4 of 8); "only authorized" only as a predicate
_NOT_AN_ACTOR = frozenset({"in addition", "note", "notes", "example", "examples", "exception", "exceptions", "reminder", "caution", "warning", "purpose", "rationale", "for example",
                           "scope", "applicability", "summary", "background", "definition", "definitions", "overview", "introduction", "general", "objective", "objectives", "description", "policy", "contact"})
_RESPONSIBILITY = re.compile(r"\b(?:retain|retains|have|has|assume|assumes|bear|bears)\s+(?:\S+\s+){0,4}?responsibilit(?:y|ies)\b|\bresponsibilit(?:y|ies)\b[^.:;]{0,80}?\b(?:are|is|include)\s*:", re.IGNORECASE)


_APPLICABLE_TO = re.compile(r"^\W*(?:\([\w-]+\)\s*)?(?:This|These|The)\s+(?:\S+\s+){0,3}?(?:(?:also\s+)?(?:applies|apply)|(?:is|are)\s+(?:also\s+)?applicable)\s+to\b", re.IGNORECASE)
_PURPOSE_CLAUSE = re.compile(r"\b(?:so\s+that|so|in\s+order\s+that|in\s+order\s+for)\s", re.IGNORECASE)  # "... so coordination can occur": the "can" gives no permission
_RELATIVE_MODAL = re.compile(r"(?:\b(?:that|which|who)\s+|\b(?:through|by|for|in|with|to|from|on|at|under|within|against)\s+(?:which|whom)\s+(?:\S+\s+){0,5})$", re.IGNORECASE)  # "actions that can be taken", "forum through which officials can elevate"
_LEAD_IN = re.compile(r"^(?P<lead>[^:]{0,200}?\b(?:as\s+follows|the\s+following)\s*:+)\s*(?P<rest>\S.*)$", re.IGNORECASE | re.DOTALL)
_POINTS_TO = re.compile(r"\b(?:can|may)\s+be\s+(?:found|located|viewed|seen)\b", re.IGNORECASE)  # "can be found in ..." points; it grants nothing
_THIS_DOCUMENT_PROVIDES = re.compile(r"^\W*This\s+(?:\w+\s+){0,2}?(?:provides|describes|establishes|prescribes|implements)\b", re.IGNORECASE)  # front matter that says what the document is
_RELATIVE_NEGATION = re.compile(r"\b(?:that|which|who)\s+(?:cannot|can\s+not)\b", re.IGNORECASE)  # "Units that cannot meet X must coordinate ...": the relative clause describes the subject of a duty
_EXAMPLES = re.compile(r"^\W*(?:For\s+example,?\s+)?Examples?\b", re.IGNORECASE)


def first_permission(text: str):
    """The first "may / can / is authorized to ..." that grants something: not one inside a purpose clause ("so coordination can occur") or a relative clause ("actions that can be taken")."""
    purpose = _PURPOSE_CLAUSE.search(text)
    limit = purpose.start() if purpose else len(text)
    for m in _PERMIT.finditer(text):
        if m.start() >= limit or _RELATIVE_MODAL.search(text[:m.start()]) or _POINTS_TO.match(text, m.start()):
            continue
        return m
    return None


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
    if (re.match(r"of\b", rest, re.IGNORECASE) and m.group(1).lower() != "dispose") or _MODAL_SOON.match(rest):
        return None
    if m.group(1).lower() == "wear" and re.match(r"(?:criteria|guidance|standards?)\b", rest, re.IGNORECASE):
        return None  # "Wear criteria depends on ...": a noun phrase
    if m.group(2).lstrip(" ").startswith(":") or re.match(r"(?:information|info|details|numbers?|lists?|persons?|points?|e-?mail|phone)\b", rest, re.IGNORECASE):
        return None  # "Contact: John Doe" is a label and "Contact information for assistance ..." a noun phrase, not a command
    return m.group(1)


_THIRD_PERSON_EXTRA = frozenset({  # verbs that open a role's duty in a responsibilities list ("Initiates exceptions ...", "Represents the cybersecurity interests ...")
    "address", "administer", "advise", "advocate", "authorize", "certify", "determine", "evaluate", "execute", "grant", "initiate", "integrate", "perform", "recommend", "represent",
    "review", "verify", "oversee", "approve", "disapprove", "direct", "issue", "notify", "provide", "establish", "develop", "coordinate", "conduct", "maintain", "manage", "monitor", "operate",
})


def _third_person_command(text: str):
    """The verb that opens `text` in its third-person form ("Completes", "Develops", "Identifies"), or None. Only used after "Actor:", where a duty list reads "The ISSO: Completes ...";
    a condition lead ("In coordination with the DoD CIO, establishes ...") is skipped. "Reports of ..." is a noun."""
    probe = _ADVERB.sub("", text, count=1)
    if lead := _CONDITION_LEAD.match(probe):
        probe = probe[lead.end():]
    m = re.match(r"([A-Za-z][A-Za-z-]*)\b(.*)", probe, re.DOTALL)
    if not m:
        return None
    word = m.group(1).lower()
    bases = [word[:-1]] if word.endswith("s") else []
    if word.endswith("es"):
        bases.append(word[:-2])
    if word.endswith("ies"):
        bases.append(word[:-3] + "y")
    rest = m.group(2).lstrip()
    if not any(b in _COMMAND_VERBS or b in _THIRD_PERSON_EXTRA for b in bases) or re.match(r"of\b", rest, re.IGNORECASE) or _MODAL_SOON.match(rest) \
            or re.match(r"(?:is|are|was|were|be|been|has|have|had|does|do|did|will|shall|must|should|may|can|cannot|include|includes|consist|consists|mean|means|involve|involves|remain|remains|occur|occurs|exist|exists|appear|appears)\b", rest, re.IGNORECASE):
        return None  # "Reports shall be filed ..." and "Reports are due ..." have a noun for a subject
    return m.group(1)


_LEAD_PHRASE = re.compile(r"^(?:in coordination with|in addition to|at a minimum|as required|as directed|as necessary|as appropriate|under the authority|when required|if required|in accordance with)\b", re.IGNORECASE)


def opens_with_third_person_duty(quote: str):
    """The third-person verb of "Initiates exceptions ..." or "In coordination with the DoD CIO, USD(A&S), and USD(R&E), provides guidance ...": a role's duty written without its subject,
    as a list item under the role's heading. The lead is skipped only when it is one of the known lead-in phrases."""
    text = _ADVERB.sub("", _opening(quote), count=1)
    if verb := _third_person_command(text):
        return verb
    if _LEAD_PHRASE.match(text):
        head = text[:400]
        for m in re.finditer(r",\s+(?:and\s+)?(?:as [^,;:]{3,60},\s+)?([a-z]+)\b", head):
            if verb := _third_person_command(head[m.start(1):]):
                return verb
    return None


_LAST_COLON = re.compile(r"^(?P<lead>[^:]{3,400}?):\s+(?P<rest>[A-Z]\S.*)$", re.DOTALL)


def lead_then_third_person_duty(quote: str):
    """("As the senior security official ..., the Director", "Provides") for a long lead, one colon, then a third-person verb that opens a duty ("Under the authority ..., the DoD CISO: Provides oversight").
    The lead must be a role phrase, not a label, a list lead-in or a sentence with its own modal."""
    text = _opening(quote)
    m = _LAST_COLON.match(text)
    if not m:
        return None
    lead = m.group("lead").strip()
    if lead.lower() in _NOT_AN_ACTOR or _STRONG.search(lead) or _SHOULD.search(lead) or first_permission(lead) or _DOCUMENT_AS_ACTOR.search(lead):
        return None
    if not re.search(r"\b(?:the|a|an|[A-Z]{2,}|[A-Z]\w+)\b[^:]*$", lead) or lead.endswith((" include", " includes", " following", " as follows")):
        return None
    verb = _third_person_command(m.group("rest"))
    return (lead, verb) if verb else None


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
    text = _opening(quote)
    m = _ACTOR_COLON.match(text)
    if (not m or len(m.group("actor").split()) > 8) and (lead := _CONDITION_LEAD.match(text)):  # "In addition to the responsibilities in Paragraph 2.4., the Commander: Develops ..."
        after = text[lead.end():]
        m = _ACTOR_COLON.match(after[:1].upper() + after[1:]) or m  # "the Commander, ...:" opens in lower case after the lead
    if not m or m.group("actor").strip().lower() in _NOT_AN_ACTOR or len(m.group("actor").split()) > 8 or _STRONG.search(m.group("actor")):
        return None
    if _SHOULD.search(m.group("actor")) or first_permission(m.group("actor")) or _DOCUMENT_AS_ACTOR.search(m.group("actor")):
        return None  # "these processes should: Be standardized" is a recommendation; "this instruction: Establishes policy" is the document describing itself
    verb = _command(m.group("rest")) or _third_person_command(m.group("rest"))
    return (m.group("actor").strip(), verb) if verb else None


def _command_then_tail(text: str, m) -> bool:
    """True when `text` opens with a real command and the pointer or exemption wording `m` is only a tail: in a later sentence or in a trailing "(See Table 1.1)". A row that opens with the pointer
    itself ("Refer to paragraph 4 ...") is a pointer, so "refer" and "see" are not commands here."""
    verb = leading_command(text)
    if not verb or verb.lower() in ("refer", "see", "is", "are", "be"):
        return False
    before = text[:m.start()]
    return bool(re.search(r"[.;]\s", before) or re.search(r"\(\s*$", before))


POSITION_KINDS = frozenset({"table_row", "form_template_text", "cover_page_text"})  # decided by where the row sits, not by what it says


def classify(item: dict, *, use_position: bool = True) -> dict:
    """{"kind", "kind_reasons", "kind_tags"} for one checklist item, and `kind_by_wording` when the kind comes from where the row sits (what the kind would be if its position were ignored:
    a duty sentence in a table cell is a table_row and a duty). The first rule that matches decides the kind; the reasons name the rule and the words it matched."""
    quote = item.get("source_quote") or ""
    flags = set(item.get("item_flags") or [])
    citation = str(item.get("citation") or "")
    kind, reasons = None, []
    text = quote
    lead = _LEAD_IN.match(quote)
    if lead and not _STRONG_DUTY.search(lead.group("lead")):
        text = lead.group("rest")  # "These responsibilities may be summarized as follows:: Execute ...": the lead-in only introduces the list; the item is the row

    def decide(name: str, why: str, match=None):
        nonlocal kind, reasons
        if kind is None:
            kind, reasons = name, [why + (f": {match.group(0).strip()!r}" if match else "")]

    applies = "applicability_statement" in flags or _APPLICABLE_TO.search(quote)
    negated = text
    if (rel := _RELATIVE_NEGATION.search(text)) and _STRONG_DUTY.search(text, rel.end()):  # a "cannot" in a relative clause is a prohibition only when no duty word follows it
        negated = text[:rel.start()] + " " * (rel.end() - rel.start()) + text[rel.end():]
    if use_position and citation.startswith("Figure"):
        decide("form_template_text", f"cited by a figure caption ({citation})")
    elif use_position and citation == "Front matter" and applies:
        decide("applicability", "says who the document applies to (in the front matter)")
    elif use_position and citation == "Front matter" and ((not _STRONG_DUTY.search(text) and not leading_command(text)) or _THIS_DOCUMENT_PROVIDES.match(text)):  # a duty word or a command in the front matter: the wording decides, the location stays a tag
        decide("cover_page_text", "cited as front matter")
    elif use_position and citation.startswith("Table"):
        decide("table_row", f"cited by a table caption ({citation})")
    elif applies:
        decide("applicability", "says who the document applies to")
    elif (m := _POINTER.search(text)) and not _STRONG.search(text) and not _command_then_tail(text, m):
        decide("pointer", "points elsewhere", m)
    elif m := _PROHIBIT.search(negated):
        allowed = first_permission(text)
        if allowed and allowed.start() < m.start():  # "may extend ..., but shall not authorize consecutive waivers": the grant comes first and the negation limits it
            decide("permission", "grants a permission that a later negation limits", allowed)
        else:
            decide("prohibition", "a negation of an obligation or permission", m)
    elif m := _EXEMPT.search(text):
        duty = _STRONG_DUTY.search(text)
        if _command_then_tail(text, m):  # "Execute the responsibilities in 2.22. (T-1) Host Centers/Wings will be exempt if ...": the command is the duty, the exemption is its tail
            decide("duty_imperative", "a command that a later exemption limits", m)
        elif duty and duty.start() < m.start():  # "are required to meet X but are not required to meet Y": the duty comes first and the exemption limits it
            decide("duty_with_actor", "a duty that a later exemption limits", duty)
        else:
            decide("exemption", "says something does not apply or is not required", m)
    elif "definition_or_description" in flags and not _STRONG_DUTY.search(text):
        decide("definition_or_description", "defines or describes, no obligation word")
    elif _EXAMPLES.match(text) and not _STRONG_DUTY.search(text):
        decide("definition_or_description", "gives examples")
    elif _PURPOSE.match(text) and not _STRONG_DUTY.search(text):
        decide("unknown", "opens with a purpose clause (To ...) and has no obligation word")
    elif verb := leading_command(text):
        decide("duty_imperative", (f"opens with a verb and names no subject ({verb})" if verb.lower() in ("is", "are", "be") else f"opens with a command ({verb}) and names no actor")
               + (" (after a lead-in that only introduces the list)" if text is not quote else ""))
    elif pair := named_actor_then_command(text):
        decide("duty_with_actor", f"names its actor ({pair[0]}), then a command ({pair[1]})")
    elif m := _STRONG.search(text):
        decide("duty_with_actor", "an obligation word", m)
    elif m := _RESPONSIBILITY.search(text):
        decide("duty_with_actor", "says who retains or has a responsibility", m)
    elif m := _SHOULD.search(text):
        decide("recommendation", "says what should happen", m)
    elif m := first_permission(text):
        decide("permission", "says what may be done", m)
    elif ("no_stated_actor" in flags or checklist_audit._is_verb(checklist_audit._first_word(text), _COMMAND_VERBS)) and not _CONTACT_AS_NOUN.match(_opening(text)) \
            and not re.match(r"\W*(?:wear|limit|present|exercise|pull|avoid|consult|generate|mitigate|decertify)\s+of\b", _opening(text), re.IGNORECASE):
        decide("duty_imperative", "opens with a command and names no actor")
    elif verb := opens_with_third_person_duty(text):  # kind-rules-8: only rows that would otherwise be `unknown`, so no other kind changes
        decide("duty_imperative", f"opens with a third-person verb and no subject ({verb})")
    elif pair := lead_then_third_person_duty(text):
        decide("duty_with_actor", f"names its actor in a long lead ({pair[0][:60]}), then a third-person verb ({pair[1]})")
    elif (m := _IMPLIED_DUTY.search(text)) and not _NEGATED_OR_HYPOTHETICAL.search(text[max(0, m.start() - 24):m.start()]):
        decide("duty_with_actor", "says what is required or limited", m)
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

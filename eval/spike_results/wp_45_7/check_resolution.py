"""WP-45.7: validate one resolver answer against the evidence bundle it was given (offline; no LLM).

The field-specific rules of docs/PHASE45_WP457_PLAN.md section 4.6. Every containment test runs on whitespace-normalized text
on BOTH sides (`bundle.normalize`), so raw Docling spacing or soft hyphens cannot cause a false failure. A blanket "value is
in the cited span" test would reject correct answers (a status or a logic value never appears in the text) and omitting it
would weaken provenance, so each field type gets its own check:

  extractive   actor, action, target, applicability, timing, parent, conditions, exceptions: cited ids exist, the value is
               found in at least one cited span
  modality     `verbatim` is found in a cited span and its class matches a fixed phrase table; a null phrase needs class
               `none` and is valid only if no cited span holds a deontic modal (checked for requirement statuses only)
  categorical  status, logic: derivation rules where a rule exists; status equals the modality class for requirement
               statuses when the class is not `none`
  composed     standalone_statement, plain_language: no number, acronym or proper name that the cited spans lack, and no
               modal of a different class; plain_language is checked against the standalone sentence and its spans
  explanatory  unresolved_reason: not validated by code

The entailment gate (a model) and the hand audit are separate. Issues are errors unless marked "warn".
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bundle as B  # noqa: E402
import resolver as R  # noqa: E402

# Fixed mapping from modal phrase to class (plan 4.6). Longest phrase wins; matching is on lowercase normalized text.
MODAL_TABLE = {
    "obligation": ["shall", "must", "will", "is required to", "are required to", "required to", "is to", "are to", "has to", "have to"],
    "recommendation": ["should", "is recommended", "are recommended", "is encouraged to", "are encouraged to", "ought",
                       "should not", "ought not", "shouldn't"],
    "permission": ["may", "can", "is authorized to", "are authorized to", "is permitted to", "are permitted to",
                   "is allowed to", "are allowed to"],
    "prohibition": ["shall not", "must not", "may not", "cannot", "will not", "never", "must never", "shall never",
                    "is prohibited from", "are prohibited from", "is forbidden", "are forbidden", "forbidden"],
}
_PHRASES = sorted(((p, c) for c, ps in MODAL_TABLE.items() for p in ps), key=lambda pc: -len(pc[0]))
_PHRASE_RE = [(re.compile(rf"(?<![\w']){re.escape(p)}(?![\w'])"), p, c) for p, c in _PHRASES]

_STOP = {
    "the", "a", "an", "this", "that", "these", "those", "it", "they", "if", "when", "unless", "each", "any", "all", "such",
    "where", "which", "who", "whom", "he", "she", "we", "you", "i", "not", "no", "or", "and", "but", "for", "to", "of", "in",
    "on", "at", "by", "as", "with", "from", "into", "per", "under", "after", "before", "during", "until", "while", "whether",
    "than", "then", "there", "here", "also", "only", "may", "shall", "must", "should", "will", "can", "is", "are", "be",
}
_TOKEN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9\-./]*[A-Za-z0-9])?")


@dataclass
class Issue:
    code: str
    field: str
    message: str
    severity: str = "error"


def phrase_class(phrase):
    """The class of a modal phrase from the fixed table, or None. A phrase may continue past the table entry ("shall be")."""
    text = B.normalize(phrase).lower()
    for _, p, c in _PHRASE_RE:
        if text == p or text.startswith(p + " "):
            return c
    return None


def modals_in(text):
    """[(phrase, class)] for every table phrase in the text, longest match first, without overlapping matches."""
    text = B.normalize(text).lower()
    taken, found = [], []
    for rx, p, c in _PHRASE_RE:
        for m in rx.finditer(text):
            if not any(m.start() < e and s < m.end() for s, e in taken):
                taken.append((m.start(), m.end()))
                found.append((m.start(), p, c))
    return [(p, c) for _, p, c in sorted(found)]


def new_tokens(candidate_text, source_text):
    """Numbers, acronyms and proper names in `candidate_text` that `source_text` does not contain. The first word of a sentence
    and common capitalized words are ignored, and tokens are compared case-insensitively, so reordering a sentence or starting
    it with "The" is not a new name."""
    have = {m.group(0).lower() for m in _TOKEN.finditer(B.normalize(source_text))}
    text = B.normalize(candidate_text)
    out = []
    for m in _TOKEN.finditer(text):
        tok = m.group(0)
        low = tok.lower()
        if low in have or low in _STOP:
            continue
        initial = m.start() == 0 or text[: m.start()].rstrip().endswith((".", "!", "?"))
        if any(ch.isdigit() for ch in tok) or (tok.isupper() and len(tok) >= 2) or (tok[0].isupper() and not initial):
            out.append(tok)
    return sorted(set(out))


def shape_issues(answer):
    """Structural conformance: is every field the shape the schema asked for? (Not whether it is right.)"""
    issues = []
    if not isinstance(answer, dict):
        return [Issue("shape", "", "the answer is not a JSON object")]
    for name in R.ORDER:
        if name not in answer:
            issues.append(Issue("shape", name, "missing"))
    if issues:
        return issues

    def wrapped(name, node):
        ok = isinstance(node, dict) and "value" in node and isinstance(node.get("evidence"), list)
        if not ok:
            issues.append(Issue("shape", name, "needs a value and an evidence list"))
        return ok

    for name in ("status", "logic") + R.VALUE_FIELDS + ("standalone_statement", "plain_language", "unresolved_reason"):
        wrapped(name, answer[name])
    for name in R.LIST_FIELDS:
        if not isinstance(answer[name], list):
            issues.append(Issue("shape", name, "must be an array"))
        else:
            for i, item in enumerate(answer[name]):
                wrapped(f"{name}[{i}]", item)
    mod = answer["modality"]
    if not (isinstance(mod, dict) and "verbatim" in mod and "class" in mod and isinstance(mod.get("evidence"), list)):
        issues.append(Issue("shape", "modality", "needs verbatim, class and an evidence list"))
    status = answer["status"].get("value") if isinstance(answer["status"], dict) else None
    if status not in R.STATUS:
        issues.append(Issue("shape", "status", f"{status!r} is not one of {R.STATUS}"))
    if isinstance(mod, dict) and mod.get("class") not in R.CLASS:
        issues.append(Issue("shape", "modality", f"class {mod.get('class')!r} is not one of {R.CLASS}"))
    logic = answer["logic"].get("value") if isinstance(answer["logic"], dict) else None
    if logic not in R.LOGIC:
        issues.append(Issue("shape", "logic", f"{logic!r} is not one of {R.LOGIC}"))
    return issues


def _cited_text(spans_by_id, ids):
    return " ".join(B.normalize(spans_by_id[i]["text"]) for i in ids if i in spans_by_id)


def check(answer, spans):
    """All issues for one answer. `spans` is a list of {"id", "text", ...} dicts (`Bundle.to_dict()["spans"]`)."""
    issues = shape_issues(answer)
    if issues:
        return issues
    by_id = {s["id"]: s for s in spans}

    def ids_ok(field, node):
        bad = [i for i in node["evidence"] if i not in by_id]
        if bad:
            issues.append(Issue("bad_evidence_id", field, f"cites {bad}, which are not in the bundle"))
        return not bad

    def extractive(field, node):
        if not ids_ok(field, node) or node["value"] in (None, ""):
            return
        if not node["evidence"]:
            issues.append(Issue("uncited_value", field, "has a value but cites no evidence"))
            return
        if B.normalize(node["value"]).lower() not in _cited_text(by_id, node["evidence"]).lower():
            issues.append(Issue("not_in_cited_span", field, f"{node['value']!r} is not in the cited spans"))

    for name in R.VALUE_FIELDS:
        extractive(name, answer[name])
    for name in R.LIST_FIELDS:
        for i, item in enumerate(answer[name]):
            extractive(f"{name}[{i}]", item)
    for name in ("status", "logic", "standalone_statement"):
        ids_ok(name, answer[name])
    ids_ok("modality", answer["modality"])

    status = answer["status"]["value"]
    mod = answer["modality"]
    cited_modality = _cited_text(by_id, [i for i in mod["evidence"] if i in by_id])
    all_cited = _cited_text(by_id, [i for n in R.ORDER for i in _evidence_of(answer[n])])

    # modality: the phrase is copied from a cited span and its class matches the table
    if mod["verbatim"]:
        if B.normalize(mod["verbatim"]).lower() not in cited_modality.lower():
            issues.append(Issue("not_in_cited_span", "modality", f"phrase {mod['verbatim']!r} is not in the cited spans"))
        cls = phrase_class(mod["verbatim"])
        if cls is None:
            issues.append(Issue("unknown_modal_phrase", "modality", f"{mod['verbatim']!r} is not in the phrase table"))
        elif cls != mod["class"]:
            issues.append(Issue("modality_strengthened", "modality", f"phrase {mod['verbatim']!r} is {cls}, class says {mod['class']}"))
    else:
        if mod["class"] != "none":
            issues.append(Issue("modality_class", "modality", "a null phrase needs class none"))
        if status in R.REQUIREMENT_STATUS and modals_in(all_cited):
            issues.append(Issue("modal_in_evidence", "modality", "the cited evidence holds a modal but none was given", "warn"))
    # status and class agree for requirement statuses (a mismatch is a strengthened or weakened modality)
    if status in R.REQUIREMENT_STATUS and mod["class"] != "none" and mod["class"] != status:
        issues.append(Issue("modality_strengthened", "status", f"status {status} but modality class {mod['class']}"))
    if status == "unresolved" and not (answer["unresolved_reason"]["value"] or "").strip():
        issues.append(Issue("missing_reason", "unresolved_reason", "status is unresolved but no reason is given", "warn"))

    # logic needs and/or text in a cited span
    logic = answer["logic"]
    if logic["value"] != "none":
        text = _cited_text(by_id, logic["evidence"]).lower()
        if not re.search(r"\b(and|or)\b", text):
            issues.append(Issue("logic_without_text", "logic", f"{logic['value']!r} needs 'and' or 'or' in a cited span"))

    # composed fields
    standalone = answer["standalone_statement"]
    stand_text = B.normalize(standalone["value"] or "")
    if stand_text:
        if not standalone["evidence"]:
            issues.append(Issue("uncited_value", "standalone_statement", "has a value but cites no evidence"))
        source = _cited_text(by_id, standalone["evidence"])
        added = new_tokens(stand_text, source)
        if added:
            issues.append(Issue("added_token", "standalone_statement", f"adds {added} that the cited spans lack"))
        _modal_issues("standalone_statement", stand_text, mod["class"], issues)
    plain = answer["plain_language"]["value"]
    if plain:
        if not stand_text:
            issues.append(Issue("plain_without_standalone", "plain_language", "plain_language must be null when standalone_statement is null"))
        else:
            added = new_tokens(plain, stand_text + " " + _cited_text(by_id, standalone["evidence"]))
            if added:
                issues.append(Issue("added_token", "plain_language", f"adds {added} that the standalone sentence and its spans lack"))
            _modal_issues("plain_language", plain, mod["class"], issues)
    return issues


def _evidence_of(node):
    if isinstance(node, list):
        return [i for item in node for i in item.get("evidence", [])]
    return node.get("evidence", [])


def _modal_issues(field, text, cls, issues):
    for phrase, found in modals_in(text):
        if cls == "none":
            issues.append(Issue("modality_added", field, f"uses {phrase!r} but the modality class is none"))
        elif found != cls:
            issues.append(Issue("modality_strengthened", field, f"uses {phrase!r} ({found}) but the modality class is {cls}"))


def errors(issues):
    return [i for i in issues if i.severity == "error"]

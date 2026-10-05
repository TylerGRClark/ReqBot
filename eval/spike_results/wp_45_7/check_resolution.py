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
  composed     standalone_statement, plain_language: no number, acronym or proper name that the cited spans lack, and no NEW
               or changed modal of a different class (a modal the source itself contains, such as a subordinate "may", is a
               faithful copy); plain_language is checked against the standalone sentence and its spans
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
    "obligation": ["shall", "must", "will", "is required to", "are required to", "required to", "is to", "are to", "has to", "have to",
                   "needs to", "need to"],
    "recommendation": ["should", "is recommended", "are recommended", "is encouraged to", "are encouraged to", "ought",
                       "should not", "ought not", "shouldn't", "is advised to", "are advised to", "is advised not to",
                       "are advised not to", "advised not to"],
    "permission": ["may", "can", "is authorized to", "are authorized to", "is permitted to", "are permitted to",
                   "is allowed to", "are allowed to"],
    "prohibition": ["shall not", "must not", "may not", "cannot", "will not", "never", "must never", "shall never",
                    "is prohibited from", "are prohibited from", "is forbidden", "are forbidden", "forbidden"],
}
# "can" is ambiguous in running text ("who can get into them" describes ability, not permission). It is accepted as a copied modality
# phrase, and it is counted as a modal in an answer's source, sentences and evidence only when THAT ANSWER declares it as its modality
# (`modality.verbatim == "can"`); otherwise it is ignored. "cannot" is always counted: it is rarely anything but deontic.
AMBIGUOUS = {"can"}
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


def modals_in(text, ambiguous=False):
    """[(phrase, class)] for every table phrase in the text, longest match first, without overlapping matches. The ambiguous
    phrase ("can") is left out unless `ambiguous` is true."""
    text = B.normalize(text).lower()
    taken, found = [], []
    for rx, p, c in _PHRASE_RE:
        if p in AMBIGUOUS and not ambiguous:
            continue
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
        # a sentence also starts after a full stop that is followed by a closing bracket or quote: (as in this one.) The next
        initial = m.start() == 0 or text[: m.start()].rstrip().rstrip(")]}\"'\u201d\u2019").rstrip().endswith((".", "!", "?"))
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

    def wrapped(name, node, strict_string=False):
        ok = isinstance(node, dict) and "value" in node and isinstance(node.get("evidence"), list)
        if not ok:
            issues.append(Issue("shape", name, "needs a value and an evidence list"))
            return False
        value = node["value"]
        if not (isinstance(value, str) or (value is None and not strict_string)):
            issues.append(Issue("shape", name, f"value must be a {'string' if strict_string else 'string or null'}, got {type(value).__name__}"))
            ok = False
        if not all(isinstance(e, str) for e in node["evidence"]):
            issues.append(Issue("shape", name, "evidence must be a list of strings"))
            ok = False
        return ok

    for name in ("status", "logic"):
        wrapped(name, answer[name], strict_string=True)
    for name in R.VALUE_FIELDS + ("standalone_statement", "plain_language", "unresolved_reason"):
        wrapped(name, answer[name])
    for name in R.LIST_FIELDS:
        if not isinstance(answer[name], list):
            issues.append(Issue("shape", name, "must be an array"))
        else:
            for i, item in enumerate(answer[name]):
                wrapped(f"{name}[{i}]", item, strict_string=True)
    mod = answer["modality"]
    if not (isinstance(mod, dict) and "verbatim" in mod and "class" in mod and isinstance(mod.get("evidence"), list)):
        issues.append(Issue("shape", "modality", "needs verbatim, class and an evidence list"))
    elif not (isinstance(mod["verbatim"], str) or mod["verbatim"] is None) or not all(isinstance(e, str) for e in mod["evidence"]):
        issues.append(Issue("shape", "modality", "verbatim must be a string or null and evidence a list of strings"))
    status = answer["status"].get("value") if isinstance(answer["status"], dict) else None
    if not isinstance(status, str) or status not in R.STATUS:
        issues.append(Issue("shape", "status", f"{status!r} is not one of {R.STATUS}"))
    if isinstance(mod, dict) and (not isinstance(mod.get("class"), str) or mod.get("class") not in R.CLASS):
        issues.append(Issue("shape", "modality", f"class {mod.get('class')!r} is not one of {R.CLASS}"))
    logic = answer["logic"].get("value") if isinstance(answer["logic"], dict) else None
    if not isinstance(logic, str) or logic not in R.LOGIC:
        issues.append(Issue("shape", "logic", f"{logic!r} is not one of {R.LOGIC}"))
    return issues


def _cited_text(spans_by_id, ids):
    return " ".join(B.normalize(spans_by_id[i]["text"]) for i in ids if i in spans_by_id)


def _in_one_span(value, spans_by_id, ids):
    """True if the normalized value is found inside at least ONE cited span: two spans that merely end and begin with the two
    halves of a name do not count as containing it."""
    want = B.normalize(value).lower()
    return any(want in B.normalize(spans_by_id[i]["text"]).lower() for i in ids if i in spans_by_id)


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
        if not _in_one_span(node["value"], by_id, node["evidence"]):
            issues.append(Issue("not_in_cited_span", field, f"{node['value']!r} is not in any one cited span"))

    for name in R.VALUE_FIELDS:
        extractive(name, answer[name])
    for name in R.LIST_FIELDS:
        for i, item in enumerate(answer[name]):
            extractive(f"{name}[{i}]", item)
    for name in ("status", "logic", "standalone_statement"):
        ids_ok(name, answer[name])
    for name in ("plain_language", "unresolved_reason"):  # derived or explanatory: their evidence list stays empty
        ids_ok(name, answer[name])
        if answer[name]["evidence"]:
            issues.append(Issue("evidence_not_allowed", name, "evidence must stay empty for this field"))
    ids_ok("modality", answer["modality"])

    status = answer["status"]["value"]
    mod = answer["modality"]
    # "can" counts as a modal for this answer only if the answer itself declares it as its modality phrase
    verbatim_norm = B.normalize(mod["verbatim"] or "").lower()
    can_active = verbatim_norm == "can" or verbatim_norm.startswith("can ")  # "can be granted" is accepted through the "can" entry too
    all_cited = _cited_text(by_id, [i for n in R.ORDER for i in _evidence_of(answer[n])])

    # modality: the phrase is copied from a cited span and its class matches the table. An unresolved answer keeps whatever the
    # model could read and is not validated (plan 4.6): the evidence is insufficient by definition.
    if status == "unresolved":
        pass
    elif mod["verbatim"]:
        if not _in_one_span(mod["verbatim"], by_id, mod["evidence"]):
            issues.append(Issue("not_in_cited_span", "modality", f"phrase {mod['verbatim']!r} is not in any one cited span"))
        cls = phrase_class(mod["verbatim"])
        if cls is None:
            issues.append(Issue("unknown_modal_phrase", "modality", f"{mod['verbatim']!r} is not in the phrase table"))
        elif cls != mod["class"]:
            issues.append(Issue("modality_strengthened", "modality", f"phrase {mod['verbatim']!r} is {cls}, class says {mod['class']}"))
    else:
        if mod["class"] != "none":
            issues.append(Issue("modality_class", "modality", "a null phrase needs class none"))
        if status in R.REQUIREMENT_STATUS and modals_in(all_cited):
            issues.append(Issue("modal_in_evidence", "modality", "the cited evidence holds a modal but none was given"))
    # status and class agree for requirement statuses (a mismatch is a strengthened or weakened modality). Class `none` is a
    # genuinely modal-free OBLIGATION only (an imperative, or a duty with no modal anywhere in the cited evidence): a
    # recommendation, permission or prohibition always has a modal phrase and class of its own.
    if status in R.REQUIREMENT_STATUS:
        if mod["class"] == "none":
            if status != "obligation":
                issues.append(Issue("modality_class", "status", f"status {status} needs a modal phrase and a matching class, not none"))
        elif mod["class"] != status:
            issues.append(Issue("modality_strengthened", "status", f"status {status} but modality class {mod['class']}"))
    if status == "unresolved" and not (answer["unresolved_reason"]["value"] or "").strip():
        issues.append(Issue("missing_reason", "unresolved_reason", "status is unresolved but no reason is given", "warn"))
    if status != "unresolved" and (answer["unresolved_reason"]["value"] or "").strip():
        issues.append(Issue("superfluous_reason", "unresolved_reason", f"status is {status} but an unresolved reason is given", "warn"))

    # logic needs and/or text in a cited span
    logic = answer["logic"]
    if logic["value"] != "none":
        text = _cited_text(by_id, logic["evidence"]).lower()
        if not re.search(rf"\b{logic['value']}\b", text):
            issues.append(Issue("logic_without_text", "logic", f"{logic['value']!r} needs the word {logic['value']!r} in a cited span"))

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
        if status != "unresolved":
            _modal_issues("standalone_statement", stand_text, mod["class"], source, issues, must_keep=True, ambiguous=can_active)
    plain = answer["plain_language"]["value"]
    if plain:
        if not stand_text:
            issues.append(Issue("plain_without_standalone", "plain_language", "plain_language must be null when standalone_statement is null"))
        else:
            added = new_tokens(plain, stand_text + " " + _cited_text(by_id, standalone["evidence"]))
            if added:
                issues.append(Issue("added_token", "plain_language", f"adds {added} that the standalone sentence and its spans lack"))
            if status != "unresolved":
                _modal_issues("plain_language", plain, mod["class"], stand_text, issues, must_keep=True, ambiguous=can_active)
    return issues


def _evidence_of(node):
    if isinstance(node, list):
        return [i for item in node for i in item.get("evidence", [])]
    return node.get("evidence", [])


def _class_counts(text, ambiguous=False):
    counts = {}
    for _, c in modals_in(text, ambiguous):
        counts[c] = counts.get(c, 0) + 1
    return counts


def _modal_issues(field, text, cls, source, issues, must_keep=False, ambiguous=False):
    """Compare the modals of generated text with those of its source, per class, in both directions.

    A class may not appear more often in the text than in the source: that catches a new modal and a subordinate modal
    reassigned to another class (source "must ... may", text "must ... must"), while a modal the source itself contains is a
    faithful copy. For an imperative (class none) any modal is an addition. With `must_keep`, the primary class must still be
    present, so "may grant a waiver" cannot become "grants a waiver" (a dropped permission)."""
    have, want = _class_counts(text, ambiguous), _class_counts(source, ambiguous)
    for c, n in sorted(have.items()):
        if n > want.get(c, 0):
            code = "modality_added" if cls == "none" else "modality_strengthened"
            issues.append(Issue(code, field, f"has {n} {c} modal(s) but the source has {want.get(c, 0)}"))
    if must_keep and cls != "none" and have.get(cls, 0) == 0:
        issues.append(Issue("modality_removed", field, f"the {cls} modal of the source is missing from the sentence"))


# The codes that count toward the zero-tolerance modality rule of gate G2: a modal that was added, removed, strengthened or
# reassigned between the source and the resolver's answer, or a status that disagrees with its modality class.
MODALITY_ERROR_CODES = ("modality_strengthened", "modality_added", "modality_removed", "modality_class", "unknown_modal_phrase")


def modality_errors(issues):
    return [i for i in issues if i.severity == "error" and i.code in MODALITY_ERROR_CODES]


def errors(issues):
    return [i for i in issues if i.severity == "error"]

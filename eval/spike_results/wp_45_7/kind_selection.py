"""WP-45.7d: the kind-selection resolver's schema, prompt, worked examples and assembler (no LLM is called here).

docs/PHASE45_WP457D_PLAN.md section 2, made concrete. The model sees the evidence bundle and the numbered menu of verbatim spans from
`menu.py` and answers `{kind, actor, parent}`: the kind is one of `requirement`, `scope_or_context`, `not_a_requirement`, `unresolved`;
actor and parent are menu ids or "none". It never says how strong a requirement is. The assembler sets the status:

  - for any kind but `requirement`, the status is the kind;
  - for `requirement`, the status is the class of the governing modal, read by code from the first source that has one (the checker's phrase
    table, including the hint phrases; the ambiguous "can" is not read): the candidate quote; the parent the model chose; if it chose none,
    the menu's colon lead-in; then, when the quote starts with a lowercase letter (it continues the clause before it), the menu's preceding
    clause. The chosen actor is never read. With no modal in any source the status is `obligation` with class `none`.

The record keeps where the modal came from (`modal_source`) and every modal the quote holds (`all_modals`); a quote with several modals uses
the first one for its status. Everything in the answer is a verbatim span or a table lookup, so the invented-party and modality gates cannot
fail through the model's wording or its choice of strength; they stay as tests of this assembler.
"""

import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bundle as B  # noqa: E402
import check_resolution as C  # noqa: E402
import menu as M  # noqa: E402
import selection as S  # noqa: E402

NONE = S.NONE
KINDS = ("requirement", "scope_or_context", "not_a_requirement", "unresolved")
STRENGTHS = ("obligation", "recommendation", "permission", "prohibition")
render_menu = S.render_menu
menu_hash = S.menu_hash
example_bundle = S.example_bundle

INSTRUCTIONS = """You are classifying ONE candidate sentence from a compliance document and choosing, from a numbered menu, the spans that say who must act and which clause governs it. Use only the evidence and the menu below; do not use outside knowledge. Answer with one JSON object: {"kind": ..., "actor": "M1" or "none", "parent": "M1" or "none"}. The menu ids are the only values allowed for actor and parent. You do not say how strong a requirement is: that is read from its words.

- kind: requirement (it asks, recommends, allows or forbids someone to do something: a "must" or "shall", a "should", a "may", a "shall not", an imperative, a hint such as "Consider ...", or a short list item under a clause that says so), scope_or_context (says who or what the document covers; it is kept and attached, not a requirement), not_a_requirement (a description, definition, background, or what a technology can do or what may happen; it asks or allows nobody to do anything, even if it contains "can" or "may"), or unresolved (the evidence is not enough to decide). Most descriptive sentences are not_a_requirement.
- actor: the menu entry that only names the party who must act (for example "The Records Officer"). An approver or authorizer is NOT the actor. An entry that ends with a colon, or contains shall, must, will, should or may, is a governing clause: choose it as the parent, never as the actor; if the party is also on the menu as a shorter entry, choose that as the actor. Choose "none" when no entry names the actor, or when the sentence is not a requirement.
- parent: the menu entry that is the governing clause the sentence depends on: a lead-in such as "The Records Officer will:" that the sentence completes, or a heading that names the responsible party. Choose "none" when the sentence is complete by itself (it names who must act and what to do), even if a heading is on the menu, or when no entry is the governing clause. A heading or lead-in that only names a topic is not a parent. Entries marked "preceding" are only the words right before the sentence, often a list number or an unrelated sentence: choose one only if it ends with a colon or names the party.
- A short phrase or list item, even a bare noun phrase, under a lead-in or heading that says what someone must, should or may do or provide is part of that requirement: kind requirement, with the lead-in as its parent. Call a sentence not_a_requirement only when nothing in the evidence assigns it a duty.
- Choose "none" rather than guess. Entries marked "found by rule" may be wrong: choose one only if the evidence agrees. Prefer the shortest entry that names the party over a long one that contains other words.

Examples (invented text). Answer with one JSON object."""


def _examples():
    out = []
    for ex in S.EXAMPLES:
        status = ex["answer"]["status"]
        out.append({**ex, "answer": {"kind": "requirement" if status in STRENGTHS else status, "actor": ex["answer"]["actor"],
                                     "parent": ex["answer"]["parent"]}, "status": status})
    return out


EXAMPLES = _examples()


def json_schema(menu):
    """The Ollama `format` schema for one candidate: the kind enum, and actor and parent restricted to this menu's ids or "none"."""
    ids = [e["id"] for e in menu] + [NONE]
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": list(KINDS)},
            "actor": {"type": "string", "enum": ids},
            "parent": {"type": "string", "enum": ids},
        },
        "required": ["kind", "actor", "parent"],
    }


def render_examples():
    parts = []
    for n, ex in enumerate(EXAMPLES, 1):
        menu = S._example_menu(ex)
        parts.append(f"Example {n}: {ex['title']}\n{example_bundle(ex).render()}\n{render_menu(menu)}\n"
                     f"Answer: {json.dumps(ex['answer'], separators=(',', ':'))}")
    return "\n\n".join(parts)


def render_prompt(bundle, menu):
    return f"{INSTRUCTIONS}\n\n{render_examples()}\n\nNow answer for this candidate.\n{bundle.render()}\n{render_menu(menu)}\nAnswer:"


def fixed_prompt():
    return f"{INSTRUCTIONS}\n\n{render_examples()}\n\nNow answer for this candidate.\n\nAnswer:"


def fixed_tokens():
    return B.estimate_tokens(len(fixed_prompt()))


def prompt_hash():
    template = json_schema([{"id": "M1"}])
    return hashlib.sha256((fixed_prompt() + json.dumps(template, sort_keys=True)).encode("utf-8")).hexdigest()[:16]


def _starts_lowercase(quote):
    """True if the first letter of the quote is lowercase: the quote continues the clause before it."""
    for ch in B.normalize(quote):
        if ch.isalpha():
            return ch.islower()
    return False


def governing_modal(quote, menu, parent_text):
    """(surface phrase, class, source, text) of the governing modal, or ("", "none", "none", None). Sources in order: the quote; the chosen
    parent; when no parent was chosen, the menu's colon lead-in, then (if the quote starts lowercase) a preceding clause with a modal.
    A chosen parent that holds no modal ends the search: nothing is inferred over the model's choice. The chosen actor is never read."""
    def read(text):
        modal = M.first_modal(text) if text else None
        return (B.normalize(text)[modal[0]:modal[1]], modal[3]) if modal else None

    hit = read(quote)
    if hit:
        return hit[0], hit[1], "quote", quote
    if parent_text:
        hit = read(parent_text)
        return (hit[0], hit[1], "parent", parent_text) if hit else ("", "none", "none", None)
    lead = next((e for e in menu if e["kind"] == "lead_in" and e["text"].endswith(":")), None)
    hit = read(lead["text"]) if lead else None
    if hit:
        return hit[0], hit[1], "menu lead-in", lead["text"]
    if _starts_lowercase(quote):
        for e in menu:
            if e["kind"] == "preceding":
                hit = read(e["text"])
                if hit:
                    return hit[0], hit[1], "preceding clause", e["text"]
    return "", "none", "none", None


def assemble(selection, menu, bundle_spans, quote):
    """(answer, spans, info): the answer in the resolver's shape, the span list the checker validates it against, and the record extras
    (`modal_source`, `all_modals`, `status`). Raises ValueError for a kind or id the schema should have made impossible."""
    by_id = {e["id"]: e for e in menu}
    if selection.get("kind") not in KINDS:
        raise ValueError(f"kind {selection.get('kind')!r} is not allowed")
    for name in ("actor", "parent"):
        if selection.get(name) != NONE and selection.get(name) not in by_id:
            raise ValueError(f"{name} {selection.get(name)!r} is not on the menu")
    spans = [dict(s) for s in bundle_spans]
    quote_id = spans[0]["id"]
    node = {name: {"value": None, "evidence": []} for name in ("actor", "parent")}
    texts = {}
    for name in ("actor", "parent"):
        if selection[name] != NONE:
            texts[name] = by_id[selection[name]]["text"]
            node[name] = {"value": texts[name], "evidence": [S._span_for(spans, texts[name], "menu")]}
    kind = selection["kind"]
    all_modals = [{"phrase": p, "class": c} for p, c in C.modals_in(quote)]
    modality = {"verbatim": None, "class": "none", "evidence": []}
    source = "none"
    if kind == "requirement":
        phrase, cls, source, text = governing_modal(quote, menu, texts.get("parent"))
        status = cls if cls != "none" else "obligation"
        if phrase:
            modality = {"verbatim": phrase, "class": cls,
                        "evidence": [quote_id] if source == "quote" else [S._span_for(spans, text, "menu")]}
    else:
        status = kind
    empty = {"value": None, "evidence": []}
    answer = {
        "status": {"value": status, "evidence": [quote_id]},
        "actor": node["actor"], "action": dict(empty), "target": dict(empty), "modality": modality,
        "applicability": dict(empty), "conditions": [], "exceptions": [], "timing": dict(empty), "parent": node["parent"],
        "logic": {"value": "none", "evidence": []},
        "standalone_statement": dict(empty), "plain_language": dict(empty), "unresolved_reason": dict(empty),
    }
    return answer, spans, {"modal_source": source, "all_modals": all_modals, "status": status}


def assemble_full(selection, menu, bundle_spans, quote):
    """Uniform entry point for the runner: (answer, spans, extras)."""
    return assemble(selection, menu, bundle_spans, quote)

"""WP-45.7b: the selection resolver's schema, prompt, worked examples and assembler (no LLM is called here).

docs/PHASE45_WP457B_PLAN.md section 2, made concrete. The model sees the evidence bundle and a numbered menu of verbatim spans built by
`menu.py`, and returns only `{status, actor, parent}`: the status from the fixed enum, the actor and the parent each a menu id or "none".
The Ollama JSON-schema `format` makes the ids an enum, so nothing else can be said. `assemble` then builds the answer in the existing
resolver shape (`resolver.ORDER`): actor and parent are the chosen menu texts, the modality is read by code from the quote (then the chosen parent), and every field the model did not choose is null, so the unchanged checker and scorer apply to it as they are.

Every value is a verbatim span by construction. The assembled answer cites exact-text spans only (the candidate quote and one span per
chosen entry), never a larger span that merely contains the entry: a big chunk cited as evidence would put its own modals in the answer.
"""

import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bundle as B  # noqa: E402
import menu as M  # noqa: E402
import resolver as R  # noqa: E402

NONE = "none"

INSTRUCTIONS = """You are classifying ONE candidate sentence from a compliance document and choosing, from a numbered menu, the spans that say who must act and which clause governs it. Use only the evidence and the menu below; do not use outside knowledge. Answer with one JSON object: {"status": ..., "actor": "M1" or "none", "parent": "M1" or "none"}. The menu ids are the only values allowed for actor and parent.

- status: obligation (must, shall, will, a mandatory duty), recommendation (should, should not, is recommended, a hint at what to do), permission (may, is authorized to), prohibition (shall not, must not), scope_or_context (says who or what the document covers; it is kept and attached, not a requirement), not_a_requirement (a description, definition, background, or what a technology can do or what may happen; it asks or allows nobody to do anything, even if it contains "can" or "may"), or unresolved (the evidence is not enough to decide). Most descriptive sentences are not_a_requirement.
- actor: the menu entry that only names the party who must act (for example "The Records Officer"). An approver or authorizer is NOT the actor. An entry that ends with a colon, or contains shall, must, will, should or may, is a governing clause: choose it as the parent, never as the actor; if the party is also on the menu as a shorter entry, choose that as the actor. Choose "none" when no entry names the actor, or when the sentence is not a requirement.
- parent: the menu entry that is the governing clause the sentence depends on: a lead-in such as "The Records Officer will:" that the sentence completes, or a heading that names the responsible party. Choose "none" when the sentence is complete by itself (it names who must act and what to do), even if a heading is on the menu, or when no entry is the governing clause. A heading or lead-in that only names a topic is not a parent. Entries marked "preceding" are only the words right before the sentence, often a list number or an unrelated sentence: choose one only if it ends with a colon or names the party.
- A short phrase or list item, even a bare noun phrase, under a lead-in or heading that says what someone must, should or may do or provide is part of that requirement: give it that status and choose the lead-in as its parent. Call a sentence not_a_requirement only when nothing in the evidence assigns it a duty.
- Read the status from the modal word in the sentence or in the parent you choose: "will not", "shall not" and "must not" are prohibition; "can" or "may" in a description of what something is able to do is not a permission to anyone. Choose "none" rather than guess. Entries marked "found by rule" may be wrong: choose one only if the evidence agrees. Prefer the shortest entry that names the party over a long one that contains other words.

Examples (invented text). Answer with one JSON object."""


def _entry(kind, text, source="", unverified=False):
    return {"kind": kind, "text": text, "source": source, "unverified": unverified}


EXAMPLES = [
    {
        "title": "a list item whose lead-in names the actor",
        "quote": "(2) Report findings to the Director.",
        "spans": [("chunk", "same chunk", "The Records Officer will: (1) Review logs monthly. (2) Report findings to the Director."),
                  ("heading", "heading (leaf)", "2.3. RECORDS OFFICER")],
        "menu": [_entry("heading", "2.3. RECORDS OFFICER"), _entry("heading", "RECORDS OFFICER"),
                 _entry("lead_in", "The Records Officer will:"), _entry("lead_in", "The Records Officer")],
        "answer": {"status": "obligation", "actor": "M4", "parent": "M3"},
    },
    {
        "title": "a sentence that is complete by itself",
        "quote": "The Auditor shall review access logs every quarter.",
        "spans": [("chunk", "same chunk", "Logs are kept for one year. The Auditor shall review access logs every quarter."),
                  ("heading", "heading (leaf)", "4.1. Log review")],
        "menu": [_entry("subject", "The Auditor"), _entry("heading", "4.1. Log review"), _entry("heading", "Log review")],
        "answer": {"status": "obligation", "actor": "M1", "parent": "none"},
    },
    {
        "title": "a description that is not a requirement",
        "quote": "Virtualization can improve isolation between workloads.",
        "spans": [("chunk", "same chunk", "Virtualization can improve isolation between workloads. It is widely used in data centers."),
                  ("heading", "heading (leaf)", "4.4 Isolation")],
        "menu": [_entry("heading", "4.4 Isolation"), _entry("heading", "Isolation")],
        "answer": {"status": "not_a_requirement", "actor": "none", "parent": "none"},
    },
    {
        "title": "a recommendation",
        "quote": "Organizations should also test restores from backup.",
        "spans": [("chunk", "same chunk", "Organizations should also test restores from backup. Results should be recorded."),
                  ("heading", "heading (leaf)", "6.2 Backups")],
        "menu": [_entry("subject", "Organizations"), _entry("heading", "6.2 Backups"), _entry("heading", "Backups")],
        "answer": {"status": "recommendation", "actor": "M1", "parent": "none"},
    },
    {
        "title": "a bare noun-phrase list item under a lead-in",
        "quote": "(3) Procedures for revising the plan.",
        "spans": [("chunk", "same chunk", "The plan must include: (1) Roles and duties. (2) Review schedules. (3) Procedures for revising the plan."),
                  ("heading", "heading (leaf)", "7.1 Plan contents")],
        "menu": [_entry("heading", "7.1 Plan contents"), _entry("heading", "Plan contents"),
                 _entry("lead_in", "The plan must include:"), _entry("lead_in", "The plan"), _entry("preceding", "(2) Review schedules.")],
        "answer": {"status": "obligation", "actor": "none", "parent": "M3"},
    },
    {
        "title": "a prohibition, and a topic heading that is not a parent",
        "quote": "The vendor will not store credentials in plain text.",
        "spans": [("chunk", "same chunk", "5.2.4. The vendor will not store credentials in plain text."),
                  ("heading", "heading (leaf)", "5. REPORTS")],
        "menu": [_entry("subject", "The vendor"), _entry("heading", "5. REPORTS"), _entry("heading", "REPORTS"), _entry("preceding", "5.2.4.")],
        "answer": {"status": "prohibition", "actor": "M1", "parent": "none"},
    },
    {
        "title": "a scope statement",
        "quote": "This policy applies to all contractor personnel.",
        "spans": [("chunk", "same chunk", "This policy applies to all contractor personnel."),
                  ("heading", "heading (leaf)", "1.2 Applicability")],
        "menu": [_entry("heading", "1.2 Applicability"), _entry("heading", "Applicability")],
        "answer": {"status": "scope_or_context", "actor": "none", "parent": "none"},
    },
]


def json_schema(menu):
    """The Ollama `format` schema for one candidate: the status enum, and the actor and parent restricted to this menu's ids or "none"."""
    ids = [e["id"] for e in menu] + [NONE]
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": list(R.STATUS)},
            "actor": {"type": "string", "enum": ids},
            "parent": {"type": "string", "enum": ids},
        },
        "required": ["status", "actor", "parent"],
    }


def render_menu(menu):
    """The menu as the model sees it, one id and one verbatim span per line."""
    if not menu:
        return 'Menu (choose by id): empty; answer "none" for actor and parent.'
    lines = []
    for e in menu:
        tag = e["kind"] + (", found by rule" if e["kind"] == "stem" else "")
        lines.append(f'{e["id"]} [{tag}] {e["text"]}')
    return "Menu (choose by id):\n" + "\n".join(lines)


def _example_menu(example):
    return [{"id": f"M{i}", **e} for i, e in enumerate(example["menu"], 1)]


def example_bundle(example):
    """The example's evidence as a real `bundle.Bundle` (the candidate quote first), rendered exactly as a live bundle is."""
    b = B.Bundle(tier="R1")
    b.spans.append(B.Span(id="E1", kind="candidate", label="candidate quote", text=B.normalize(example["quote"])))
    for i, (kind, label, text) in enumerate(example["spans"], 2):
        b.spans.append(B.Span(id=f"E{i}", kind=kind, label=label, text=B.normalize(text)))
    return b


def render_examples():
    parts = []
    for n, ex in enumerate(EXAMPLES, 1):
        menu = _example_menu(ex)
        parts.append(f"Example {n}: {ex['title']}\n{example_bundle(ex).render()}\n{render_menu(menu)}\n"
                     f"Answer: {json.dumps(ex['answer'], separators=(',', ':'))}")
    return "\n\n".join(parts)


def render_prompt(bundle, menu):
    """The full prompt for one candidate: instructions, worked examples, the live evidence bundle, then its menu."""
    return f"{INSTRUCTIONS}\n\n{render_examples()}\n\nNow answer for this candidate.\n{bundle.render()}\n{render_menu(menu)}\nAnswer:"


def fixed_prompt():
    """Everything in the prompt except the live evidence bundle and the live menu."""
    return f"{INSTRUCTIONS}\n\n{render_examples()}\n\nNow answer for this candidate.\n\nAnswer:"


def fixed_tokens():
    """Estimated tokens of the fixed prompt text, at the builder's conservative 2.5 characters per token."""
    return B.estimate_tokens(len(fixed_prompt()))


def prompt_hash():
    template = json_schema([{"id": "M1"}])
    return hashlib.sha256((fixed_prompt() + json.dumps(template, sort_keys=True)).encode("utf-8")).hexdigest()[:16]


def menu_hash(menu):
    return hashlib.sha256(json.dumps(menu, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _span_for(spans, text, kind):
    """The id of a span whose text is exactly `text`, adding one (kind `menu`, appended in place) when there is none."""
    want = B.normalize(text)
    for s in spans:
        if B.normalize(s["text"]) == want:
            return s["id"]
    new_id = f"E{len(spans) + 1}"
    spans.append({"id": new_id, "kind": kind, "label": "menu entry", "text": want, "source": "", "unverified": False})
    return new_id


def read_modal(quote, parent=None):
    """The modal the code reads for the record: from the quote, else from the chosen parent (the "The Records Officer will:" lead-in).
    Returns (surface phrase, class, source) with source "quote" or "parent", or ("", "none", None). The chosen actor is never read: a
    lead-in picked as the actor with no parent is a malformed choice and must show up as an error, not borrow its modal. The ambiguous
    "can" is not read. `first_modal` works on the normalized text, so its offsets index the normalized text."""
    for source, text in (("quote", quote), ("parent", parent)):
        modal = M.first_modal(text) if text else None
        if modal:
            return B.normalize(text)[modal[0]:modal[1]], modal[3], source
    return "", "none", None


def assemble(selection, menu, bundle_spans, quote):
    """The answer in the resolver's shape and the span list the checker validates it against.

    `selection` is the model's `{status, actor, parent}`; `menu` the candidate's menu; `bundle_spans` `Bundle.to_dict()["spans"]` (the
    candidate quote is its first span). Raises ValueError for a status or id the schema should have made impossible."""
    by_id = {e["id"]: e for e in menu}
    if selection.get("status") not in R.STATUS:
        raise ValueError(f"status {selection.get('status')!r} is not allowed")
    for name in ("actor", "parent"):
        if selection.get(name) != NONE and selection.get(name) not in by_id:
            raise ValueError(f"{name} {selection.get(name)!r} is not on the menu")
    spans = [dict(s) for s in bundle_spans]
    quote_id = spans[0]["id"]
    chosen = {name: by_id[selection[name]] for name in ("actor", "parent") if selection[name] != NONE}
    node = {name: {"value": None, "evidence": []} for name in ("actor", "parent")}
    for name, entry in chosen.items():
        node[name] = {"value": entry["text"], "evidence": [_span_for(spans, entry["text"], "menu")]}
    phrase, cls, source = read_modal(quote, chosen["parent"]["text"] if "parent" in chosen else None)
    modality = {"verbatim": phrase or None, "class": cls, "evidence": []}
    if phrase:
        modality["evidence"] = [quote_id] if source == "quote" else node["parent"]["evidence"]
    empty = {"value": None, "evidence": []}
    answer = {
        "status": {"value": selection["status"], "evidence": [quote_id]},
        "actor": node["actor"], "action": dict(empty), "target": dict(empty), "modality": modality,
        "applicability": dict(empty), "conditions": [], "exceptions": [], "timing": dict(empty), "parent": node["parent"],
        "logic": {"value": "none", "evidence": []},
        "standalone_statement": dict(empty), "plain_language": dict(empty), "unresolved_reason": dict(empty),
    }
    return answer, spans

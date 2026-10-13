"""WP-45.7: the two discovery prompts (scratch only).

D0 is the Step C prompt that was in production until WP-45.16 adopted D1, frozen in `d0_prompt_template.txt` (so the baseline stays comparable), rendered as `run()` rendered it (the profile's obligation verbs filled in).
D1 is the inclusive discovery prompt of docs/PHASE45_WP457_PLAN.md appendix A: it replaces the opening definition, the
"do not extract" bullets and the example block, and keeps the output rules, the verbatim-quote rule and the
`{source_ref_hints}` / `{chunk_text}` slots. Same output schema for both. Examples are invented text.
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.profiles import default_profile  # noqa: E402
from pipeline import llm_extract_requirements as S  # noqa: E402

ARMS = ("D0", "D1")


def d0_template():
    return (Path(__file__).resolve().parent / "d0_prompt_template.txt").read_text(encoding="utf-8").replace("{obligation_verbs}", ", ".join(default_profile()["obligation_verbs"]))


_D1_HEAD = """You are finding CANDIDATE requirement passages in a cybersecurity compliance document.
Be inclusive: a later step decides which candidates are real, so do not drop a passage because you are unsure.

A candidate is a passage that tells a party what it must, should, may or must not do. Return passages such as:
- shall / must / is required to / will statements
- "should" or "is recommended" statements (recommendations)
- "shall not", "must not", "is prohibited" statements (prohibitions)
- "may" or "is authorized to" statements (permissions)
- Third-person duty statements with no modal verb, often list items under a lead-in such as "The Director will:",
  for example "Reviews access lists annually." Return the item itself, even if its lead-in is not in this text.
- Imperative instructions, for example "Disable unused services."
- When a sentence contains a condition or exception (if, unless, except, provided that), copy the whole sentence.
- Scope or applicability statements ("This manual applies to all network operators"). They are not requirements, but the next
  step keeps and attaches them, so return them.

Do NOT return:
- definitions, change logs, tables of contents, headings
- a cross-reference by itself ("See also AC-3")
- background that describes how something works and tells nobody to do anything
- statements of what a role is or is located in, with no action anyone could perform or be audited on

Return a JSON object with a single "requirements" key whose value is an array.
No markdown code fences. No text before or after the JSON object.
If there are no candidates, return: {"requirements": []}

Each element in the "requirements" array must be a JSON object with exactly these keys:
- "source_quote": (REQUIRED) The exact verbatim quote from the text establishing this candidate
  (under 500 characters). Copy word-for-word — do NOT paraphrase or summarize. If you cannot find
  an exact verbatim quote for a candidate, do NOT include that candidate.
- "source_ref": The document-specific locator for this candidate (e.g., "AC-4", "Section 5.2.1",
  "Para 3.4.1") or "" if none is visible in the text. Copy it exactly as written — do not infer or construct.
"""

# (title-less) invented examples: (text, [source_quote, ...], [source_ref, ...])
_D1_EXAMPLES = [
    (
        "4.2 The Records Officer will:\na. Provides quarterly retention reports to the Program Office.\nb. Reviews disposal schedules each year.\nc. Is based in the Northern Annex.",
        ["a. Provides quarterly retention reports to the Program Office.", "b. Reviews disposal schedules each year."],
        ["4.2", "4.2"],
    ),
    (
        "Users shall not share accounts. Administrators should rotate shared secrets every 90 days. The Authorizing Official may grant a waiver for up to six months.",
        ["Users shall not share accounts.", "Administrators should rotate shared secrets every 90 days.", "The Authorizing Official may grant a waiver for up to six months."],
        ["", "", ""],
    ),
    (
        "Contractors shall encrypt backups unless the Program Manager grants a written exception.\n(1) Keys must be stored apart from the data.\n(2) Key custodians shall be named in writing.",
        ["Contractors shall encrypt backups unless the Program Manager grants a written exception.", "(1) Keys must be stored apart from the data.", "(2) Key custodians shall be named in writing."],
        ["", "(1)", "(2)"],
    ),
    (
        "AC-9 Review. See also AC-3 and IA-2. Where paragraph 4.2 applies, the Agency shall comply with Section 6.",
        ["Where paragraph 4.2 applies, the Agency shall comply with Section 6."],
        ["AC-9"],
    ),
    (
        "Virtualization is the practice of running several operating systems on one machine. It is widely used in data centers.",
        [],
        [],
    ),
]


def d1_template():
    parts = [_D1_HEAD, "\n--- EXAMPLES ---\n"]
    for n, (text, quotes, refs) in enumerate(_D1_EXAMPLES, 1):
        out = {"requirements": [{"source_quote": q, "source_ref": r} for q, r in zip(quotes, refs)]}
        parts.append(f"\nExample {n}:\nText: {json.dumps(text, ensure_ascii=False)}\nOutput: {json.dumps(out, ensure_ascii=False)}\n")
    parts.append("\n--- END EXAMPLES ---\n{source_ref_hints}\nText:\n{chunk_text}")
    return "".join(parts)


def template(arm):
    if arm == "D0":
        return d0_template()
    if arm == "D1":
        return d1_template()
    raise ValueError(f"arm must be one of {ARMS}")


def render(arm, chunk_text):
    return S._render_prompt(template(arm), chunk_text)


def prompt_hash(arm):
    """Hash of the arm's template (not of one rendered chunk), plus the output schema both arms share."""
    return S.compute_prompt_hash(template(arm) + json.dumps(S._PASS1_FORMAT_SCHEMA, sort_keys=True))


SCHEMA = S._PASS1_FORMAT_SCHEMA

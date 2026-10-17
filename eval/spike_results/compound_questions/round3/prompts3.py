"""Round 3 prompt versions (narrow variant). Every worked example uses only words that are in its own source quote; there is no hedge word in any example."""
import hashlib
import json

MODEL = "qwen2.5:14b"
NUM_CTX = 4096
NUM_PREDICT = 400
SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["keep", "split"]},
        "kind": {"type": ["string", "null"], "enum": ["verbs", "objects", None]},
        "lead": {"type": ["string", "null"]},
        "parts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["decision"],
}

V1 = """You help an auditor. Below is one requirement and the audit question already written for it. The question lists three or more items. Decide whether to KEEP the question or SPLIT the list into one short lead question plus one part per item.

Split ONLY when the question is a plain list of one of two kinds:
- "verbs": one actor and a list of actions: "Does the unit do A, do B, and do C?"
- "objects": one actor, one action, and a list of things it acts on or people it acts for: "Does the unit send X to A, B, and C?"
Choose "keep" for anything else: one action that is simply described at length, a purpose or reason ("to ensure ..."), a condition, a definition, or items that are not parallel.

If you split, copy words from the question. Do not reword, do not add any word that is not in the question or the requirement, and never add a qualifier such as "as required", "as appropriate", "properly", "necessary", "allow" or "when applicable".
- "lead": "Does <the question's actor> <the question's main verb, or: do> all of the following<anything in the question that covers the whole list, such as 'in accordance with X'>?"  The lead must be a whole question.
- "parts": exactly one per item, in the question's order.
    - kind "verbs": each part is "Does <the same actor> <that action, with its own object, in the question's words>?"
    - kind "objects": each part is just the item, as a short noun phrase ending with a question mark.
Never use it, they, them, these, those, such or this. Never merge two items and never split one item in two.

Example 1 (verbs)
Requirement: The records custodian will log each request, notify the requester, and file the response.
Question: Does the records custodian log each request, notify the requester, and file the response?
Answer: {{"decision": "split", "kind": "verbs", "lead": "Does the records custodian do all of the following?", "parts": ["Does the records custodian log each request?", "Does the records custodian notify the requester?", "Does the records custodian file the response?"]}}

Example 2 (objects)
Requirement: The inspector will send the report to the commander, the safety office, and the legal office.
Question: Does the inspector send the report to the commander, the safety office, and the legal office?
Answer: {{"decision": "split", "kind": "objects", "lead": "Does the inspector send the report to all of the following?", "parts": ["The commander?", "The safety office?", "The legal office?"]}}

Example 3 (keep)
Requirement: The custodian will review the retention schedule to ensure the schedule lists the records, the owners, and the dates.
Question: Does the custodian review the retention schedule to ensure the schedule lists the records, the owners, and the dates?
Answer: {{"decision": "keep", "kind": null, "lead": null, "parts": []}}

Applies to: {applies}
Requirement: {quote}
Question: {question}

Answer as JSON."""

# V2: written after reading the TUNE results of V1 (one row dropped "for continued network access" from the lead). Only the lead rule and one example change.
V2 = V1.replace(
    """- "lead": "Does <the question's actor> <the question's main verb, or: do> all of the following<anything in the question that covers the whole list, such as 'in accordance with X'>?"  The lead must be a whole question.""",
    """- "lead": "Does <the question's actor> <the question's main verb, or: do> <the words that come before the list> all of the following <the words that come after the list>?"  Nothing the question says may be left out: """
    """every word before the list goes before "all of the following", every word after the list goes after it. The lead must be a whole question.""").replace(
    """Example 3 (keep)""",
    """Example 2b (objects, words after the list)
Requirement: The clerk will send the notice to the owner, the tenant, and the agent for the file.
Question: Does the clerk send the notice to the owner, the tenant, and the agent for the file?
Answer: {{"decision": "split", "kind": "objects", "lead": "Does the clerk send the notice to all of the following for the file?", "parts": ["The owner?", "The tenant?", "The agent?"]}}

Example 3 (keep)""")

VERSIONS = {"v1": V1, "v2": V2}


def build(version: str, item: dict, question: str) -> str:
    return VERSIONS[version].format(applies=item.get("applies_to") or "(none)", quote=(item.get("source_quote") or "").strip(), question=question)


def prompt_id(version: str) -> str:
    return hashlib.sha256(f"{MODEL}\n{json.dumps(SCHEMA, sort_keys=True)}\n{VERSIONS[version]}".encode("utf-8")).hexdigest()[:16]

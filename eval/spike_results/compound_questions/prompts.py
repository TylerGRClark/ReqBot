"""Prompt versions for the compound-question split spike. Each version is a frozen string; the id is a hash of the template, the schema and the model."""
import hashlib
import json

MODEL = "qwen2.5:14b"  # same local model that writes today's questions (services/audit_questions.py MODEL)
NUM_CTX = 4096
NUM_PREDICT = 450
SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["keep", "split"]},
        "lead": {"type": ["string", "null"]},
        "parts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["decision"],
}

V1 = """You help an auditor. Below is one requirement and the audit question already written for it. Some questions pack several checks into one long sentence. Decide whether to KEEP the question as it is, or SPLIT it into a short lead question plus short parts, so the auditor can check each part by walking over and asking one thing.

Choose "keep" when the question is already one check: one action on one thing (a short pair of things that go together, such as "plans and procedures", is still one check).
Choose "split" when the question stacks separate actions, separate conditions or deadlines, or a list of three or more things that each need their own check.

If you split:
- "lead": one short yes/no question with the SAME actor (who must act) and the same scope as the question. It states the main duty in a few words and ends with a question mark.
- "parts": 2 to 5 short yes/no questions, each ONE check, at most 20 words each. Together the parts cover every item, action, number, deadline and condition in the question. Nothing is left out and nothing is added.

Rules:
- Use only words and facts that are in the requirement or the question. Do not add numbers, names, acronyms, roles or documents. Keep acronyms and names exactly as written.
- Keep every number, time limit and condition (if, unless, only, until, within, at least, no later than, annually, when requested, and so on) in the part it belongs to.
- Keep the strength of the requirement: if the requirement says may, can or should, never turn it into must or required; if it says must or shall, never turn it into may.
- Do not use it, they, them, these, those, such or this to point back at something. Name the thing in each part.
- Use the question's own words. Shorten; do not reword.

Example of a split (a made-up requirement):
Requirement: The records custodian will log each request, notify the requester within 5 days, and file the response.
Question: Does the records custodian log each request, notify the requester within 5 days, and file the response?
Answer: {{"decision": "split", "lead": "Does the records custodian handle each request?", "parts": ["Is each request logged?", "Is the requester notified within 5 days?", "Is the response filed?"]}}

Example of a keep (a made-up requirement):
Requirement: The records custodian will review the retention schedule annually.
Question: Does the records custodian review the retention schedule annually?
Answer: {{"decision": "keep", "lead": null, "parts": []}}

Applies to: {applies}
Requirement: {quote}
Question: {question}

Answer as JSON."""

VERSIONS = {"v1": V1}


def build(version: str, item: dict, question: str) -> str:
    return VERSIONS[version].format(applies=item.get("applies_to") or "(none)", quote=(item.get("source_quote") or "").strip(), question=question)


def prompt_id(version: str) -> str:
    return hashlib.sha256(f"{MODEL}\n{json.dumps(SCHEMA, sort_keys=True)}\n{VERSIONS[version]}".encode("utf-8")).hexdigest()[:16]

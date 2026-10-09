"""WP-46.6: draft audit questions for checklist rows (a suggestion for the auditor; never part of the requirement data).

One yes/no question per row, written by a local model from the row's own text only (applies-to line, parent paragraph, the requirement and the passage around it), as in the WP-46.4
experiment (prompt v3; see eval/spike_results/wp_46_4/README.md). Rows that look like fragments, descriptions or definitions get no question. A question that names a number, acronym or
capitalized word that the row's text does not contain is kept but marked, so the auditor checks it.

Questions are written by `reqbot questions --doc DOC` to a sidecar file beside the document's requirements (`<doc>_audit_questions.jsonl`) and read back by `checklist_service.generate`,
so building a checklist never calls a model. A record is reused when the exact prompt it was written from is unchanged.
"""
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

MODEL = "qwen2.5:14b"
NUM_CTX = 4096
NUM_PREDICT = 200
SKIP_FLAGS = frozenset({"starts_mid_sentence", "table_fragment", "definition_or_description", "quote_not_located_in_passage", "no_passage"})  # the row stays; only the question is withheld
PROMPT = """You help an auditor check whether a unit follows a regulation.

Write ONE short yes/no audit question that checks whether the requirement below is being met.
Rules:
- Use only the words and facts in the material below. Do not add numbers, deadlines, roles, systems or documents that are not in it.
- Name who must act if the material says so (the "Applies to" line or the requirement itself). If the requirement does not say who acts and nothing below does either, ask about "the unit".
- If the requirement only gives permission or describes how things are (may, can, is authorized to, is defined as), answer with null.
- If the requirement is a fragment, a definition, a description, or states no duty that can be checked, answer with null.

Applies to: {applies}
Parent paragraph: {parent}
Requirement: {quote}
Passage (the requirement is marked >> <<):
{passage}

Answer as JSON: {{"question": "<the question>"}} or {{"question": null}}."""
PROHIBITION = re.compile(
    r"\b(?:shall|must|should|will|may|can|could|would|do|does|did|is|are|be)\s+not\b(?!\s+(?:limited|only|necessarily))|\bcannot\b|\bnever\b|\bprohibited\b|\bforbidden\b", re.IGNORECASE)
PROHIBITION_RULE = "- This requirement forbids something. Ask whether it is avoided (\"Does the unit avoid ...?\"); do not ask whether it happens.\n"
SCHEMA = {"type": "object", "properties": {"question": {"type": ["string", "null"]}}, "required": ["question"]}
_TERM = re.compile(r"\b(?:\d[\w./-]*|[A-Z]{2,}[\w/&-]*|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)")
_STOP = {"does", "do", "is", "are", "has", "have", "did", "was", "were", "can", "will", "the", "a", "an", "if", "when", "whether", "who", "what", "how", "each", "all", "any", "yes", "no"}


def sidecar_path(requirements_path: Path) -> Path:
    """`<doc>_audit_questions.jsonl` beside `<doc>_requirements_*.jsonl`."""
    name = re.sub(r"_requirements_(?:normalized|enriched|gated)\.jsonl$", "", requirements_path.name)
    return requirements_path.with_name(f"{name}_audit_questions.jsonl")


def unverified_terms(question: str, material: str) -> list[str]:
    """Numbers, acronyms and capitalized words in the question that the row's own text does not contain (the sentence-initial word is ignored)."""
    text = re.sub(r"\s+", " ", material or "").lower()
    low = set(re.findall(r"[a-z0-9][a-z0-9./&'-]*", text))
    out = []
    for m in _TERM.finditer(question or ""):
        words = m.group(0).split()  # word by word: a title with its parenthetical acronym left out is still grounded
        if m.start() == 0 and words:
            words = words[1:]  # the sentence-initial word ("Do", "Does") is ignored; the rest of the match is still checked
        for word in words:
            w = word.lower().strip(".,;:()")
            if len(w) < 3 and not any(ch.isdigit() for ch in w):
                continue
            w = re.sub(r"'s$", "", w)
            inside_longer_token = bool(re.search(r"[\d./&'-]", w)) and w in text  # "I-NOSC" inside a longer token; a plain word must match a whole word ("port" is not "report")
            if w and w not in _STOP and w not in low and not inside_longer_token:
                out.append(word)
    return out


def row_material(item: dict) -> str:
    return " ".join([item.get("applies_to") or "", item.get("parent_text") or "", item.get("source_quote") or "", item.get("passage") or ""])


def build_prompt(item: dict) -> str:
    template = PROMPT
    if PROHIBITION.search(item.get("source_quote") or ""):
        template = template.replace("- If the requirement is a fragment,", PROHIBITION_RULE + "- If the requirement is a fragment,")
    parent = f"{item.get('parent_ref') or ''} {item.get('parent_text') or ''}".strip()
    return template.format(applies=item.get("applies_to") or "(none)", parent=parent or "(none)", quote=item.get("source_quote") or "", passage=(item.get("passage") or "")[:1500])


def skipped_because(item: dict) -> list[str]:
    return sorted(SKIP_FLAGS & set(item.get("item_flags") or []))


def input_hash(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{json.dumps(SCHEMA, sort_keys=True)}\n{prompt}".encode("utf-8")).hexdigest()[:16]


def ollama_call(prompt: str, model: str, ollama_url: str, timeout: int = 120, retries: int = 2) -> str:
    import requests  # local import: services stay importable without the network stack when questions are only read
    payload = {"model": model, "prompt": prompt, "stream": False, "format": SCHEMA, "options": {"temperature": 0.1, "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX}}
    for attempt in range(retries + 1):
        try:
            resp = requests.post(f"{ollama_url.rstrip('/')}/api/generate", json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["response"]
        except requests.RequestException as e:
            if attempt == retries:
                raise
            log.warning("Ollama request failed (%s); retrying in %ds", e, 2 ** (attempt + 1))
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def parse_answer(text: str) -> str | None:
    """The question, or None when the model answered null or an empty string. Raises ValueError for anything that is not the expected JSON."""
    parsed = json.loads(text)
    if not isinstance(parsed, dict) or "question" not in parsed:
        raise ValueError("no question key")
    q = parsed["question"]
    return q.strip() if isinstance(q, str) and q.strip() else None


def load(path: Path) -> dict[str, dict]:
    """{checklist_item_id: record}; an unreadable or missing file is an empty set."""
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


def write(path: Path, records: dict[str, dict]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records.values()), encoding="utf-8")
    os.replace(tmp, path)


def draft_questions(items: list[dict], path: Path, *, model: str = MODEL, ollama_url: str = "", call=None, progress=None) -> dict:
    """Write or refresh the sidecar for `items` (checklist items). `call(prompt) -> text` replaces the Ollama call in tests. Returns counts.
    A record whose input is unchanged is kept; a row whose answer cannot be parsed after one retry is recorded with `error` and is retried on the next run."""
    call = call or (lambda prompt: ollama_call(prompt, model, ollama_url))
    existing = load(path)
    records: dict[str, dict] = dict(existing)  # rows not in this run (another profile, an interrupted run) keep their records; apply() checks each against its row
    counts = {"rows": 0, "questions": 0, "no_question": 0, "skipped_by_code": 0, "reused": 0, "errors": 0, "with_unverified_terms": 0}
    for item in items:
        if not (item.get("source_quote") or "").strip():
            continue
        item_id = item["checklist_item_id"]
        counts["rows"] += 1
        prompt = build_prompt(item)
        h = input_hash(prompt, model)
        skipped = skipped_because(item)
        old = existing.get(item_id)
        if old and old.get("input_hash") == h and not old.get("error") and old.get("skipped_because", []) == skipped:
            records[item_id] = old
            counts["reused"] += 1
        elif skipped:
            records[item_id] = {"checklist_item_id": item_id, "question": None, "skipped_because": skipped, "unverified_terms": [], "model": model, "input_hash": h}
        else:
            question, error = None, None
            for _ in range(2):  # one retry: a malformed answer is a generation failure, not a judgement that the row is not auditable
                try:
                    question, error = parse_answer(call(prompt)), None
                    break
                except (ValueError, KeyError) as e:
                    error = f"malformed response: {e}"
            unver = unverified_terms(question, row_material(item)) if question else []
            records[item_id] = {"checklist_item_id": item_id, "question": question, "skipped_because": [], "unverified_terms": unver, "model": model, "input_hash": h,
                                "generated_at": datetime.now(timezone.utc).isoformat(), **({"error": error} if error else {})}
        rec = records[item_id]
        counts["skipped_by_code"] += bool(rec.get("skipped_because"))
        counts["errors"] += bool(rec.get("error"))
        counts["questions"] += bool(rec.get("question"))
        counts["no_question"] += not rec.get("question") and not rec.get("error")
        counts["with_unverified_terms"] += bool(rec.get("unverified_terms"))
        if progress and counts["rows"] % 25 == 0:
            progress(counts)
            write(path, records)
    write(path, records)
    return counts


def apply(items: list[dict], path: Path) -> int:
    """Fill `audit_question` (and a note) on checklist items from the sidecar; returns how many got a question. Rows without a record are left as they are."""
    records = load(path)
    filled = 0
    for item in items:
        rec = records.get(item["checklist_item_id"])
        if not rec or not rec.get("question") or skipped_because(item):
            continue
        if rec.get("input_hash") != input_hash(build_prompt(item), rec.get("model", MODEL)):
            continue  # written from a different row text, passage or prompt: stale
        item["audit_question"] = rec["question"]
        note = f"Draft audit question written by {rec.get('model', MODEL)} from the text above; check it before use."
        if rec.get("unverified_terms"):
            terms = ", ".join(rec["unverified_terms"])
            note += " Not found in the row's text: " + terms + "."
            reason = f"question-has-terms-not-in-row: {terms}"
            if reason not in item.setdefault("review_reasons", []):
                item["review_reasons"].append(reason)
            item["requires_human_review"] = True
        item["generation_notes"] = (item.get("generation_notes") + " " if item.get("generation_notes") else "") + note
        filled += 1
    return filled

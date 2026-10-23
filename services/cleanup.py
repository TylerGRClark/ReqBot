"""Cleanup flag for checklist rows (docs/CLEANUP_FLAG_PLAN.md): marks a row that is probably not a requirement. A flag only, never a deletion.

A third job beside the draft audit questions and the criticality flag (`reqbot questions --cleanup` runs it; off by default), with its own model call per row and its own sidecar
(`<doc>_cleanup.jsonl`) that `checklist_service.generate` reads back, so building a checklist never calls a model. The wording below is the one locked in the evaluation (strict wording plus
the sentence that "may" permissions count); it is not user-editable. A reply that is not a clear NO keeps the row, so a model error never flags anything.
Every row that has passage text is judged, including rows the questions job withheld a question from (that is where the junk is most likely). Rows with no passage are left unflagged.
"""
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from core.artifact_resolver import doc_key_from_requirements_path
from services import audit_questions

log = logging.getLogger(__name__)

PROMPT_VERSION = "strict-may-1"
NUM_CTX = 8192  # as tested
MAX_PASSAGE_CHARS = 6000
MAX_CONSECUTIVE_FAILURES = audit_questions.MAX_CONSECUTIVE_FAILURES
LABEL = "junk"
PROMPT = """You are checking one sentence taken from a policy or standards document.

Passage:
{passage}

Sentence to check:
"{quote}"

Question: does this sentence tell someone to do something, not to do something, or that they are allowed to do something? That is a requirement. A sentence that says what an office or role does or is responsible for (for example "Coordinates with X to resolve issues" or "Serves as the lead for Y") also counts as a requirement. So does a sentence that allows or permits something, for example "The commander may delegate this duty" or "Units may procure training".
It is NOT a requirement if it only describes, defines, introduces or explains: a heading or title, a date, a statement of what the document covers or why it exists, a definition, a table of contents or cover-page notice, a cut-off fragment of a sentence, or background information.

Answer with one word: YES or NO."""


def sidecar_path(requirements_path: Path) -> Path:
    """`<doc>_cleanup.jsonl` beside `<doc>_requirements_*.jsonl`."""
    name = re.sub(r"_requirements_(?:normalized|enriched|gated)\.jsonl$", "", requirements_path.name)
    return requirements_path.with_name(f"{name}_cleanup.jsonl")


def chunk_texts(requirements_path: Path, items: list[dict]) -> dict[str, str]:
    """{checklist_item_id: text of the chunk the row was found in}: the whole chunk is what the evaluation showed the model (the checklist's passage is a shorter window and flagged two real
    rows the chunk did not). A row with no extracted record or no readable chunk file is left out and the builder falls back to its passage."""
    chunks: dict = {}
    try:
        for line in (requirements_path.parent / f"{doc_key_from_requirements_path(requirements_path)}_chunks.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                chunks[rec.get("chunk_id")] = rec.get("raw_text") or rec.get("text") or ""
        by_req = {}
        for line in requirements_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                by_req[rec.get("requirement_id")] = rec.get("chunk_id")
    except (OSError, ValueError):
        return {}
    out = {}
    for item in items:
        text = next((chunks.get(by_req.get(rid)) for rid in item.get("requirement_ids") or [] if chunks.get(by_req.get(rid))), "")
        if text:
            out[item["checklist_item_id"]] = text
    return out


def build_prompt(item: dict, text: str = "") -> str | None:
    """None when the row has no quote or no passage text to show the model. Judges the root quote (`extracted_quote`), not the explained text the sheet shows. `text` is the whole chunk
    (see `chunk_texts`); without it the item's own passage is shown."""
    quote = (item.get("extracted_quote") or item.get("source_quote") or "").strip()  # the root quote, as in the evaluation
    passage = (text or item.get("passage") or "").strip()
    if not quote or not passage:
        return None
    return PROMPT.format(passage=passage[:MAX_PASSAGE_CHARS], quote=quote)


def input_hash(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}\n{model}\n{prompt}".encode("utf-8")).hexdigest()[:16]


def is_junk(answer) -> bool:
    """Only the word NO flags the row; anything else (YES, NOT SURE, an empty or odd reply) keeps it."""
    return re.match(r"\W*NO\b(?!['\u2019])", str(answer or "").strip().upper()) is not None  # the word NO, not NOT SURE / NONE / NOTHING


def ollama_call(prompt: str, model: str, ollama_url: str, timeout: int = 300) -> str:
    """One short answer; thinking is turned off for models that support it. Raises OSError-family errors when the server cannot be reached."""
    import requests  # local import, as in audit_questions: reading the sidecar needs no network stack
    body = {"model": model, "stream": False, "think": False, "messages": [{"role": "user", "content": prompt}], "options": {"temperature": 0, "num_predict": 4, "num_ctx": NUM_CTX}}
    resp = requests.post(f"{ollama_url.rstrip('/')}/api/chat", json=body, timeout=timeout)
    if resp.status_code == 400 and "think" in resp.text.lower():  # a model without a thinking mode refuses the field
        body.pop("think")
        resp = requests.post(f"{ollama_url.rstrip('/')}/api/chat", json=body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def load(path: Path) -> dict[str, dict]:
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


def judge_rows(items: list[dict], path: Path, *, model: str, ollama_url: str = "", call=None, on_row=None, progress=None, texts: dict | None = None) -> dict:
    """Write or refresh the sidecar for `items`. `call(prompt) -> str` replaces the Ollama call in tests. A record whose input (row text, passage, model, wording) is unchanged is kept.
    Five failed connections in a row stop the run (`aborted`); rows already written are kept. `texts` is {checklist_item_id: chunk text} from `chunk_texts`. Returns counts."""
    texts = texts or {}
    if call is None and not ollama_url:
        raise ValueError("ollama_url is required when no call function is given")
    call = call or (lambda prompt: ollama_call(prompt, model, ollama_url))
    records = load(path)
    counts = {"rows": 0, "judged": 0, "flagged": 0, "no_passage": 0, "reused": 0, "errors": 0}
    total_rows = sum(1 for it in items if (it.get("source_quote") or "").strip())
    failures = 0
    for item in items:
        if not (item.get("source_quote") or "").strip():
            continue
        item_id = item["checklist_item_id"]
        counts["rows"] += 1
        prompt = build_prompt(item, texts.get(item_id, ""))
        if prompt is None:
            records.pop(item_id, None)
            counts["no_passage"] += 1
        else:
            h = input_hash(prompt, model)
            old = records.get(item_id)
            if old and old.get("input_hash") == h:
                counts["reused"] += 1
                counts["flagged"] += bool(old.get("junk"))
            else:
                try:
                    answer = call(prompt)
                except (OSError, KeyError, ValueError) as e:  # requests errors are OSErrors; a reply without the expected fields is a failed call
                    records.pop(item_id, None)
                    counts["errors"] += 1
                    failures += 1
                    log.warning("cleanup: model call failed for %s: %s", item_id, e)
                    if failures >= MAX_CONSECUTIVE_FAILURES:
                        counts["aborted"] = True
                        break
                else:
                    failures = 0
                    junk = is_junk(answer)
                    records[item_id] = {"checklist_item_id": item_id, "junk": junk, "model": model, "prompt_version": PROMPT_VERSION, "input_hash": h,
                                        "generated_at": datetime.now(timezone.utc).isoformat()}
                    counts["judged"] += 1
                    counts["flagged"] += junk
        if on_row:
            on_row(counts["rows"], total_rows)
        if progress and counts["rows"] % 25 == 0:
            progress(counts)
            write(path, records)
    write(path, records)
    return counts


def apply(items: list[dict], path: Path, texts: dict | None = None) -> int:
    """Mark flagged rows from the sidecar; returns how many are flagged. The row gets `junk = True` and the priority cell carries the flag as a suffix ("High · junk", or "junk" alone when
    the row has no rating); the stored rating is never overwritten. A record written from a different row text, passage, model or wording is stale and ignored. With no sidecar nothing changes."""
    records = load(path)
    flagged = 0
    for item in items:
        rec = records.get(item["checklist_item_id"])
        if not rec or not rec.get("junk"):
            continue
        prompt = build_prompt(item, (texts or {}).get(item["checklist_item_id"], ""))
        if prompt is None or rec.get("input_hash") != input_hash(prompt, rec.get("model", "")):
            continue
        item["junk"] = True
        item["criticality"] = f"{item['criticality']} · {LABEL}" if item.get("criticality") else LABEL
        flagged += 1
    return flagged

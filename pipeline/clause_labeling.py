"""Label every clause of a document with the frozen clause-labeling prompt, and build requirement records from the flagged clauses.

Design: reqbot-agent-docs history/extraction-replacement-design_2026-10-22.md, work packages WP-3 (sections 1 and 2) and WP-4 (the switch): this is requirement finding
(Step C) of pipeline/run_pipeline.py. It replaced the step that asked the model to write a list of requirements.

How it works:
- Clauses come from pipeline/clauses.py, in document order (chunk file order, then clause order), and are sent BATCH_SIZE at a time; a batch may span two chunks.
- The prompt's "Lead-in line above" is the checklist's lead-in (pipeline/lead_in.find_lead_in, set in document_clauses): for a list item, the nearest earlier line ending in a colon that is not
  a sibling of the item, looked up in the previous chunk too when it is in the same section; a plain sentence gets none. (Before, it was the nearest colon clause in the chunk, even a stale one.)
- The prompt is pipeline/prompts/clause_label_v3.txt, frozen (sha256 PROMPT_SHA256, checked on load). It holds JSON braces, so it is filled with str.replace, never format().
- Ollama /api/chat, temperature 0, num_ctx 8192, num_predict 300, thinking off (retried without the field for a model that refuses it). Request errors are retried with
  backoff (2, 4, 8 s); a batch whose call still fails is `failed`: it writes no labels, every chunk it touches gets no rows, and the next run in the same folder redoes it.
- An answer must be a JSON list with ids 1..n, each label one of LABELS. Two attempts per batch; still unparsed -> every clause in the batch is UNSURE (kept, so a reader
  checks it) and a line goes to <doc>_parse_failures.jsonl.
- Resume ledger <doc>_raw_responses.jsonl, one line per labeled batch: batch_id, chunk_ids, clause_keys, model, prompt_sha, input_hash, raw_answer, labels, status. A batch whose
  clauses, model and filled prompt (so also each clause's lead-in) are unchanged and whose status is complete or unparsed is reused; a failed one is redone.
- Every clause not labeled NOT_REQUIREMENT becomes a row (section 2 of the design): source_quote is the clause, whitespace tidied (the document's own words, never a model's),
  anchored exactly by the splitter's offsets, cited by the five-step source_ref rule.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline.clauses import _as_list, chunk_clauses
from pipeline.lead_in import find_lead_in
from pipeline.sentence_expand import tidy
from pipeline.table_header import MAX_CHARS as TABLE_CONTEXT_CHARS, document_table_context

log = logging.getLogger(__name__)

LABELS = ("DUTY", "PROHIBITION", "PERMISSION", "NOT_REQUIREMENT", "UNSURE")
NOT_REQUIREMENT = "NOT_REQUIREMENT"
UNSURE = "UNSURE"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "clause_label_v3.txt"
PROMPT_SHA256 = "b9b20379597d04b346f6d7f30b1e6df6257f86fd15c372588dc06a1bbdd8dbc4"
BATCH_SIZE = 4
ATTEMPTS = 2
HEADING_CHARS, PARAGRAPH_CHARS, LEAD_IN_CHARS, CLAUSE_CHARS = 150, 60, 300, 1200  # what the prompt shows; the stored quote is the whole clause
NUM_CTX, NUM_PREDICT = 8192, 300
MAX_RETRIES = 3  # request retries inside one call, with backoff 2, 4, 8 s
MAX_FAILED_IN_A_ROW = 5  # this many failed batches in a row stop the run (the server is down); the rest is left for a resume
SCHEMA_VERSION = "3.0"
PIPELINE_VERSION = "2.0"
STATUS_COMPLETE, STATUS_UNPARSED, STATUS_FAILED = "complete", "unparsed", "failed"
_sleep = time.sleep  # replaced in tests


def load_prompt(path: Path = PROMPT_PATH) -> str:
    """The frozen prompt. A changed file is refused: the labels were measured with these exact bytes."""
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != PROMPT_SHA256:
        raise RuntimeError(f"{path} is not the frozen clause-labeling prompt (sha256 differs); restore it from git")
    return data.decode("utf-8")


def clause_block(items: list[dict]) -> str:
    """The numbered clauses with their context (heading, paragraph, lead-in line above from find_lead_in, table caption and column headers for a grid line; each cut to its limit)."""
    parts = []
    for i, c in enumerate(items, 1):
        ctx = []
        if c["heading"]:
            ctx.append("Heading: " + c["heading"][:HEADING_CHARS])
        if c["ref"]:
            ctx.append("Paragraph: " + c["ref"][:PARAGRAPH_CHARS])
        if c["ctx_lead"]:
            ctx.append("Lead-in line above: " + c["ctx_lead"][:LEAD_IN_CHARS])
        if c.get("ctx_table"):
            ctx.append("Table context: " + c["ctx_table"][:TABLE_CONTEXT_CHARS])
        parts.append("[%d]\nContext: %s\nClause: %s" % (i, " | ".join(ctx) if ctx else "(none)", re.sub(r"[ \t]{2,}", " ", c["text"])[:CLAUSE_CHARS]))
    return "\n\n".join(parts)


def build_prompt(template: str, items: list[dict]) -> str:
    return template.replace("{CLAUSES}", clause_block(items))


def input_hash(model: str, prompt: str) -> str:
    return hashlib.sha256((model + "\n" + prompt).encode("utf-8")).hexdigest()


def parse(answer: str, n: int) -> list[str] | None:
    """Labels for ids 1..n from the model's answer, or None. Text around the JSON list is ignored; a missing or extra id, a non-object entry or an unknown label fails."""
    m = re.search(r"\[.*\]", answer or "", re.S)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(arr, list):
        return None
    got = {}
    for o in arr:
        if not isinstance(o, dict):
            return None
        try:
            i = int(str(o.get("id")).strip("[] "))
        except Exception:
            return None
        label = str(o.get("label", "")).strip().upper().replace(" ", "_")
        if label not in LABELS or i in got:  # one entry per clause: a repeated id is not a usable answer
            return None
        got[i] = label
    if set(got) != set(range(1, n + 1)):
        return None
    return [got[i] for i in range(1, n + 1)]


def ollama_chat(prompt: str, *, model: str, ollama_url: str, timeout: int = 600) -> str:
    """One answer from Ollama /api/chat with thinking off; a model that refuses the `think` field is asked again without it (services/cleanup.ollama_call). Request errors are
    retried MAX_RETRIES times with backoff; then the error is raised (requests errors are OSError subclasses)."""
    import requests

    url = f"{ollama_url.rstrip('/')}/api/chat"
    attempt = 0
    while True:
        body = {"model": model, "stream": False, "think": False, "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT}}
        try:
            resp = requests.post(url, json=body, timeout=timeout)
            if resp.status_code == 400 and "think" in resp.text.lower():
                body.pop("think")
                resp = requests.post(url, json=body, timeout=timeout)
            resp.raise_for_status()
            return ((resp.json() or {}).get("message") or {}).get("content") or ""  # an answer without content counts as unparseable, not as a crash
        except requests.RequestException as e:
            attempt += 1
            if attempt > MAX_RETRIES:
                log.error("Ollama request failed after %d retries: %s", MAX_RETRIES, e)
                raise
            backoff = 2 ** attempt
            log.warning("Ollama request failed (%s); retrying in %ds (attempt %d/%d)", e, backoff, attempt, MAX_RETRIES)
            _sleep(backoff)


def check_server(ollama_url: str, model: str, timeout: int = 10) -> None:
    """Before labeling: raise RuntimeError when the model server cannot be reached (as the deleted list-writing step did), so a run with the server down fails at once with
    a clear message instead of writing an empty extraction file; a model the server does not list only gets a warning (its name may be spelled with a tag)."""
    import requests

    try:
        resp = requests.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=timeout)
        resp.raise_for_status()
        names = {m.get("name") for m in (resp.json() or {}).get("models") or [] if isinstance(m, dict)}
    except requests.RequestException as e:
        log.error("Cannot reach Ollama at %s: %s", ollama_url, e)
        raise RuntimeError(f"Cannot reach Ollama at {ollama_url}: {e}") from e
    if names and model not in names and f"{model}:latest" not in names:
        log.warning("Model '%s' not found in Ollama. Available: %s", model, sorted(n for n in names if n))


def _section_key(chunk: dict) -> tuple:
    return (tuple(_as_list(chunk.get("section_ref_path"))), tuple(_as_list(chunk.get("section_title_path"))))


def document_clauses(chunks: list[dict]) -> list[dict]:
    """Every clause of the document in order: chunk file order, then clause order. The lead-in the labeler is shown (`ctx_lead`) is the one the checklist uses
    (pipeline/lead_in.find_lead_in: sibling logic, looks back into the previous chunk when it is in the same section); a plain sentence (including a line that starts with a bare number) gets none. PREREG8: recall +0.6,
    precision +1.2 against the old nearest-colon-clause rule, 16 of 23 gold-judged flips right."""
    by_id = {c["chunk_id"]: c for c in chunks if "chunk_id" in c}
    out = []
    for chunk in chunks:
        raw = chunk.get("raw_text") or chunk.get("text") or ""
        prev = by_id.get(chunk["chunk_id"] - 1) if isinstance(chunk.get("chunk_id"), int) else None
        prev_raw = (prev.get("raw_text") or prev.get("text") or "") if prev is not None and _section_key(prev) == _section_key(chunk) else ""
        for c in chunk_clauses(chunk):
            c["ctx_lead"] = find_lead_in(raw, c["start"], prev_raw)
            out.append(c)
    document_table_context(chunks, out)  # PREREG11: a table grid line also gets its table's caption and column headers (c["ctx_table"])
    return out


def make_batches(clauses: list[dict], size: int = BATCH_SIZE) -> list[dict]:
    """Consecutive groups of `size` clauses, across chunk boundaries. batch_id is the batch's position; resume matches on the clauses and prompt, not the id."""
    out = []
    for n, i in enumerate(range(0, len(clauses), size)):
        items = clauses[i:i + size]
        out.append({
            "batch_id": f"b{n:05d}",
            "clauses": items,
            "clause_keys": [[c["chunk_id"], c["clause_index"]] for c in items],
            "chunk_ids": list(dict.fromkeys(c["chunk_id"] for c in items)),
        })
    return out


def label_batch(batch: dict, prompt: str, *, model: str, call) -> dict:
    """Ledger record for one batch. `call(prompt) -> str` asks the model; an OSError from it (a request error after backoff) makes the batch `failed`."""
    n = len(batch["clauses"])
    rec = {"batch_id": batch["batch_id"], "chunk_ids": batch["chunk_ids"], "clause_keys": batch["clause_keys"], "model": model, "prompt_sha": PROMPT_SHA256,
           "input_hash": input_hash(model, prompt), "raw_answer": "", "attempts": 0, "labels": None, "status": STATUS_FAILED}
    answers = []
    for _ in range(ATTEMPTS):
        rec["attempts"] += 1
        try:
            answer = call(prompt)
        except OSError as e:
            rec["error"] = str(e)[:300]
            rec["raw_answer"] = answers[-1] if answers else ""
            return rec
        answers.append(answer)
        labels = parse(answer, n)
        if labels:
            rec.update(raw_answer=answer, labels=labels, status=STATUS_COMPLETE)
            return rec
    rec.update(raw_answer=answers[-1], raw_answers=answers, labels=[UNSURE] * n, status=STATUS_UNPARSED)
    return rec


# ---- source_ref: own paragraph number, else table caption, else last number above in the chunk, else last numbered section entry, else ""
_DOTTED = r"(?:[A-Z]{1,2})?\d+(?:\.\d+)+"
_OPENS_WITH_NUMBER = re.compile(rf"^\W*({_DOTTED})\.?\s")
_GAP_IS_NUMBER = re.compile(rf"^\W*({_DOTTED})\.?\W*$")
_LINE_NUMBER = re.compile(rf"(?m)^(?!\s*\|)\W*({_DOTTED})\.?\s")  # a table grid line ("| 3.4.1 | ... |") is not a paragraph number
_TABLE_CAPTION = re.compile(r"(?m)^[ \t]*(Table\s+(?:[A-Z]{1,2})?\d+(?:\.\d+)*)\.(?=\s)")  # "Table 3.1.", "Table A2.1."; "Table 3.1 shows ..." is prose
_ENTRY_NUMBER = re.compile(rf"^\W*({_DOTTED})\.?(?:\s|$)")


def _is_grid_line(text: str) -> bool:
    return text.lstrip().startswith("|")


def own_numbers(text: str, clauses: list[dict]) -> list[str]:
    """For each clause of one chunk: the paragraph number it opens with, or the number standing alone between the previous clause and it (the splitter cuts a number such as
    "3.6.1.1." off its sentence), else "". A table grid line has none: a number in a cell is not the row's paragraph."""
    out = []
    prev_end = 0
    for c in clauses:
        num = ""
        if not _is_grid_line(c["text"]):
            m = _OPENS_WITH_NUMBER.match(c["text"] + " ") or _GAP_IS_NUMBER.match(text[prev_end:c["start"]])
            num = m.group(1) if m else ""
        out.append(num)
        prev_end = c["end"]
    return out


def _section_number(chunk: dict) -> str:
    # Older chunk files store the paths as their string form ("['1', '1.3']"); read them as pipeline/clauses.chunk_unit does.
    for entry in reversed([str(p) for p in _as_list(chunk.get("section_title_path"))]):
        m = _ENTRY_NUMBER.match(entry)
        if m:
            return m.group(1)
    for entry in reversed([str(p).strip().rstrip(".") for p in _as_list(chunk.get("section_ref_path"))]):
        if re.fullmatch(_DOTTED, entry):
            return entry
    return ""


def source_refs(chunk: dict, text: str, clauses: list[dict]) -> list[tuple[str, str]]:
    """(source_ref, source_ref_origin) for each clause of one chunk. Origins: own_number, table_caption, number_above, section_path, none. Only own_number and
    table_caption are read from the clause's own place; the checklist marks the others "(inferred)"."""
    own = own_numbers(text, clauses)
    section = _section_number(chunk)
    out = []
    for i, c in enumerate(clauses):
        if own[i]:
            out.append((own[i], "own_number"))
            continue
        before = text[:c["start"]]
        caption_here = _TABLE_CAPTION.match(c["text"])
        if caption_here or _is_grid_line(c["text"]):
            captions = [caption_here] if caption_here else list(_TABLE_CAPTION.finditer(before))
            if captions:
                out.append((" ".join(captions[-1].group(1).split()), "table_caption"))
                continue
        above = [(m.start(1), m.group(1)) for m in _LINE_NUMBER.finditer(before)] + [(clauses[j]["start"], own[j]) for j in range(i) if own[j]]
        if above:
            out.append((max(above)[1], "number_above"))
        elif section:
            out.append((section, "section_path"))
        else:
            out.append(("", "none"))
    return out


def build_records(chunks: list[dict], labels: dict, *, model: str, skip_chunks=(), document_id: str | None = None) -> list[dict]:
    """Rows for every clause labeled other than NOT_REQUIREMENT, in document order. `labels` is {(chunk_id, clause_index): label}; a clause without a label, or in a chunk of
    `skip_chunks` (touched by a failed batch), gives no row. requirement_id: the stable ID recipe (parse_and_normalize.compute_stable_id) when `document_id` is given, else
    the step's own "R-<chunk>-<clause>" (normalizing assigns the stable ID, as today)."""
    skip = set(skip_chunks)
    rows = []
    for chunk in chunks:
        if chunk["chunk_id"] in skip:
            continue
        text = chunk.get("raw_text") or chunk.get("text") or ""
        clauses = chunk_clauses(chunk)
        refs = source_refs(chunk, text, clauses)
        for c, (ref, origin) in zip(clauses, refs):
            label = labels.get((c["chunk_id"], c["clause_index"]))
            if label is None or label == NOT_REQUIREMENT:
                continue
            quote = tidy(c["text"])
            if document_id is not None:
                from pipeline.parse_and_normalize import compute_stable_id
                rid = compute_stable_id(document_id=document_id, source_ref=ref, source_quote=quote, chunk_id=c["chunk_id"], requirement_type="", description="")
            else:
                rid = f"R-{c['chunk_id']}-{c['clause_index']}"
            rows.append({
                "requirement_id": rid,
                "description": "",
                "source_ref": ref,
                "source_ref_origin": origin,
                "domain_tags": [],
                "requirement_type": "",
                "source_quote": quote,
                "chunk_id": c["chunk_id"],
                "clause_index": c["clause_index"],
                "clause_label": label,
                "anchor_status": "exact",
                "anchor_start": c["start"],
                "anchor_end": c["end"],
                "anchor_text": text[c["start"]:c["end"]],
                "extraction_model": model,
                "label_prompt_sha": PROMPT_SHA256,
                "schema_version": SCHEMA_VERSION,
                "pipeline_version": PIPELINE_VERSION,
            })
    return rows


def _load_ledger(path: Path) -> dict:
    """{(clause keys, input_hash): record} of finished batches (complete or unparsed); a later line for the same batch wins. Failed batches and unreadable lines are left out."""
    done: dict = {}
    if not path.exists():
        return done
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict) or not rec.get("clause_keys") or not rec.get("input_hash"):
                continue  # not a clause-labeling record (an older step's ledger line)
            key = (json.dumps(rec["clause_keys"]), rec["input_hash"])
            if rec.get("status") in (STATUS_COMPLETE, STATUS_UNPARSED) and isinstance(rec.get("labels"), list) and len(rec["labels"]) == len(rec["clause_keys"]):
                done[key] = rec
            else:
                done.pop(key, None)
    return done


def _write_jsonl(path: Path, records: list[dict]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    os.replace(tmp, path)


def run(chunks_jsonl: str, output_dir: str, *, model: str, ollama_url: str = "", timeout: int = 600, call=None, document_id: str | None = None,
        max_chunks: int | None = None) -> str:
    """Label every clause of <doc>_chunks.jsonl and write <doc>_extracted_requirements.jsonl (rewritten whole from the ledger), <doc>_parse_failures.jsonl and the ledger
    <doc>_raw_responses.jsonl in `output_dir`. `call(prompt) -> str` replaces the Ollama call in tests; `max_chunks` labels only the first N chunks (testing). Returns the
    requirements path."""
    if call is None and not ollama_url:
        raise ValueError("ollama_url is required when no call function is given")
    if call is None:
        check_server(ollama_url, model)
    call = call or (lambda prompt: ollama_chat(prompt, model=model, ollama_url=ollama_url, timeout=timeout))
    chunks_path = Path(chunks_jsonl).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = chunks_path.stem.removesuffix("_chunks")
    raw_path = out_dir / f"{stem}_raw_responses.jsonl"
    reqs_path = out_dir / f"{stem}_extracted_requirements.jsonl"
    fail_path = out_dir / f"{stem}_parse_failures.jsonl"

    with open(chunks_path, encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    if max_chunks is not None:  # 0 labels nothing (a limit, not "no limit")
        chunks = chunks[:max_chunks]
    template = load_prompt()
    batches = make_batches(document_clauses(chunks))
    done = _load_ledger(raw_path)
    log.info("Clause labeling: %d chunks, %d batches of up to %d clauses, model=%s", len(chunks), len(batches), BATCH_SIZE, model)

    from pipeline import progress
    finished: list[dict] = []
    current: list[dict] = []  # this run's record for every batch, in order: what the ledger is compacted to at the end
    failed_chunks: set = set()
    counts = {"batches": len(batches), "reused": 0, "labeled": 0, "unparsed": 0, "failed": 0, "not_attempted": 0}
    failed_in_a_row = 0
    with open(raw_path, "a", encoding="utf-8") as ledger:
        for i, batch in enumerate(batches):
            progress.emit("finding", i, len(batches))
            prompt = build_prompt(template, batch["clauses"])
            old = done.get((json.dumps(batch["clause_keys"]), input_hash(model, prompt)))
            if old is not None:
                counts["reused"] += 1
                finished.append(old)
                current.append(old)
                continue
            if failed_in_a_row >= MAX_FAILED_IN_A_ROW:
                counts["not_attempted"] += 1
                failed_chunks.update(batch["chunk_ids"])
                current.append({"batch_id": batch["batch_id"], "chunk_ids": batch["chunk_ids"], "clause_keys": batch["clause_keys"], "model": model,
                                "prompt_sha": PROMPT_SHA256, "input_hash": input_hash(model, prompt), "raw_answer": "", "attempts": 0, "labels": None,
                                "status": STATUS_FAILED, "error": "not_attempted"})
                continue
            rec = label_batch(batch, prompt, model=model, call=call)
            rec["timestamp"] = datetime.now(timezone.utc).isoformat()
            ledger.write(json.dumps(rec, ensure_ascii=False) + "\n")
            ledger.flush()
            current.append(rec)
            if rec["status"] == STATUS_FAILED:
                counts["failed"] += 1
                failed_in_a_row += 1
                failed_chunks.update(batch["chunk_ids"])
                if failed_in_a_row == MAX_FAILED_IN_A_ROW:
                    log.error("%d batches failed in a row; stopping. Run again in the same folder to resume.", failed_in_a_row)
                continue
            failed_in_a_row = 0
            counts["labeled"] += 1
            counts["unparsed"] += rec["status"] == STATUS_UNPARSED
            finished.append(rec)

    # One line per batch of this run: a failure redone since, or a line from another model or prompt, would otherwise stay behind, and
    # index_replace.extraction_gaps reads every "failed" line as a gap. Batches a stopped run never tried are recorded as failed, so the gap is seen.
    _write_jsonl(raw_path, current)

    labels = {}
    for rec in finished:
        for (chunk_id, idx), label in zip(rec["clause_keys"], rec["labels"]):
            labels[(chunk_id, idx)] = label
    rows = build_records(chunks, labels, model=model, skip_chunks=failed_chunks, document_id=document_id)
    _write_jsonl(reqs_path, rows)
    _write_jsonl(fail_path, [{"batch_id": r["batch_id"], "chunk_ids": r["chunk_ids"], "clause_keys": r["clause_keys"], "model": r["model"], "error": "unparsed_labels",
                              "raw_answers": r.get("raw_answers") or [r.get("raw_answer", "")]} for r in finished if r["status"] == STATUS_UNPARSED])
    log.info("Clause labeling done: %s; %d rows", counts, len(rows))
    if failed_chunks:
        log.warning("%d chunk(s) have no rows because a batch failed; run again in the same folder to retry: %s", len(failed_chunks), sorted(failed_chunks))
    if batches and not finished:  # not one batch labeled: the model server or the model is not working; stop the pipeline rather than index an empty document
        raise RuntimeError(f"Clause labeling failed: none of {len(batches)} batches could be labeled with model {model}. Run again in the same folder to resume.")
    if counts["failed"]:  # a partly labeled document must not flow on to normalizing and the index as if it were complete; the ledger and the finished batches are kept, a re-run retries only the failed ones
        raise RuntimeError(f"Clause labeling is incomplete: {counts['failed']} of {len(batches)} batches failed ({len(failed_chunks)} chunks have no rows). Run again in the same folder to resume; finished batches are reused.")
    return str(reqs_path)

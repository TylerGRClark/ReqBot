"""WP-46.6: draft audit questions for checklist rows (a suggestion for the auditor; never part of the requirement data).

One yes/no question per row, written by a local model from the row's own text only (applies-to line, parent paragraph, the requirement and the passage around it), as in the WP-46.4
experiment (prompt v3; see eval/spike_results/wp_46_4/README.md) with the actor rule of prompt v4 (eval/spike_results/question_prompt_v4/README.md: the actor is the one the requirement names, else the "Applies to" line). Rows that look like fragments, descriptions or definitions get no question. A question that names a number, acronym or
capitalized word that the row's text does not contain is kept but marked, so the auditor checks it; so is a question whose subject uses a term found only in the surrounding text,
not in the requirement, its "Applies to" line or its parent paragraph (the actor may have been taken from a neighbouring sentence).

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

from services import checklist_audit, requirement_kind

log = logging.getLogger(__name__)

MODEL = "qwen2.5:14b"
NUM_CTX = 4096
NUM_PREDICT = 200
MAX_CONSECUTIVE_FAILURES = 5  # Ollama unreachable: stop after this many model-call failures in a row instead of timing out on every remaining row
SKIP_FLAGS = frozenset({"starts_mid_sentence", "table_fragment", "definition_or_description", "quote_not_located_in_passage", "no_passage"})  # the row stays; only the question is withheld
PROMPT = """You help an auditor check whether a unit follows a regulation.

Write ONE short yes/no audit question that checks whether the requirement below is being met.
Rules:
- Use only the words and facts in the material below. Do not add numbers, deadlines, roles, systems or documents that are not in it.
- Name who must act. If the requirement itself says who acts (for example "by the program office" or "the commander will"), use that; the "Applies to" line is the actor only when the requirement names none. If neither says, ask about "the unit".
- If the requirement only gives permission or describes how things are (may, can, is authorized to, is defined as), answer with null.
- If the requirement is a fragment, a definition, a description, or states no duty that can be checked, answer with null.

Applies to: {applies}
Parent paragraph: {parent}
Requirement: {quote}
Passage (the requirement is marked >> <<):
{passage}

Answer as JSON: {{"question": "<the question>"}} or {{"question": null}}."""
# A prohibition is a modal negation, cannot / never / prohibited / forbidden, a sentence that opens with "Do not", or "is/are not" followed by a word that forbids ("authorized", "permitted",
# "allowed", "appropriate", "acceptable", "permissible", "waivable", "to"); "Do not" opens the quote or any sentence of it. A plain "does not" / "is not" inside a condition or description ("... if this capability does not exist") is not one:
# it used to turn those rows into "Does the unit avoid ...?" questions that ask the opposite (eval/spike_results/prohibition_rule/README.md).
PROHIBITION = re.compile(
    r"\b(?:shall|must|should|will|may|can|could|would)\s+not\b(?!\s+(?:limited|only|necessarily))|\bcannot\b|\bnever\b|\bprohibited\b|\bforbidden\b"
    r"|\b(?:is|are)\s+not\s+(?:authorized|permitted|allowed|appropriate|acceptable|permissible|waivable|to)\b|(?:^\W*|(?<=[.!?])\s+)(?:\d+\)\s*)?(?:\([\w-]+\)\s*)?(?:do|does)\s+not\b", re.IGNORECASE)
# "This issuance: Does not alter or override existing ... authorities": the document says what it leaves untouched. It is not a duty of the unit, and the model turned it into "Does this issuance alter or override ...?"
# (an inverted question), so the row stays and the question is withheld (found in DODI 8551.01 1.1 by the compound-question review, 2026-10-15).
DOCUMENT_STATES_ITS_OWN_EFFECT = re.compile(
    r"^\W*(?:\([\w-]+\)\s*)?(?:This|The)\s+(?:\w+\s+){0,2}?(?:issuance|instruction|publication|directive|manual|policy|memorandum|document)\s*:?\s*(?:also\s+)?(?:does|do|will)\s+not\b", re.IGNORECASE)
PROHIBITION_RULE = "- This requirement forbids something. Ask whether it is avoided (\"Does the unit avoid ...?\"); do not ask whether it happens.\n"
SCHEMA = {"type": "object", "properties": {"question": {"type": ["string", "null"]}}, "required": ["question"]}
_TERM = re.compile(r"\b(?:\d[\w./-]*|[A-Z]{2,}[\w/&-]*|[A-Z][A-Za-z]*[a-z][A-Z][A-Za-z]*|[A-Z][a-z]+(?![A-Za-z])(?:\s+[A-Z][a-z]+(?![A-Za-z]))*)")  # a number, an acronym, a mixed-case name (StoreFront, FedRAMP, DoD), or capitalized whole words
_STOP = {"does", "do", "is", "are", "has", "have", "did", "was", "were", "can", "will", "the", "a", "an", "if", "when", "whether", "who", "what", "how", "each", "all", "any", "yes", "no", "should", "would", "could", "must", "shall", "may", "might", "there", "this", "that", "these", "those"}


def sidecar_path(requirements_path: Path) -> Path:
    """`<doc>_audit_questions.jsonl` beside `<doc>_requirements_*.jsonl`."""
    name = re.sub(r"_requirements_(?:normalized|enriched|gated)\.jsonl$", "", requirements_path.name)
    return requirements_path.with_name(f"{name}_audit_questions.jsonl")


def unverified_terms(question: str, material: str) -> list[str]:
    """Numbers, acronyms and capitalized words in the question that the row's own text does not contain. A word counts as present when it is a whole word of the text, or a part of a longer
    token split at "/", "-", "." or "&" ("Networx" in "Networx/EIS"), or differs only by a plural ("Installations" for "Installation")."""
    text = re.sub(r"\s+", " ", material or "").lower()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9./&'-]*", text))
    present = set(tokens)
    for token in tokens:
        present.update(part for part in re.split(r"[./&'-]+", token) if part)
    out = []
    for m in _TERM.finditer(question or ""):
        words = m.group(0).split()  # word by word: a title with its parenthetical acronym left out is still grounded
        for word in words:
            w = word.lower().strip(".,;:()")
            if len(w) < 3 and not any(ch.isdigit() for ch in w):
                continue
            w = re.sub(r"'s$", "", w)
            variants = {w, w + "s", w + "es", w[:-1] if w.endswith("s") else w, w[:-2] if w.endswith("es") else w, w[:-3] + "y" if w.endswith("ies") else w}
            inside_longer_token = bool(re.search(r"[\d./&'-]", w)) and w in text  # "I-NOSC" inside a longer token; a plain word must match a whole word ("port" is not "report")
            if w and w not in _STOP and not (variants & present) and not inside_longer_token:
                out.append(word)
    return out


_AUXILIARY = re.compile(r"^(?:does|do|did|have|has|is|are|was|were|can|could|will|would|shall|should|must|may|might)\s+", re.IGNORECASE)
SUBJECT_WORDS = 9  # a question opens "Does <who> <verb> ...": the words that can hold the actor


def passage_only_terms(question: str, item: dict) -> list[str]:
    """Numbers, acronyms and capitalized words in the subject of the question that the surrounding text contains but the requirement, its "Applies to" line and its parent paragraph
    do not. The model may have taken the actor from the sentence before or after; the auditor checks it. Terms absent from the whole row are marked by `unverified_terms`."""
    opening = _AUXILIARY.match((question or "").strip())
    if not opening:
        return []
    subject = " ".join(question.strip()[opening.end():].split()[:SUBJECT_WORDS])
    own = " ".join([item.get("applies_to") or "", item.get("parent_text") or "", item.get("source_quote") or ""])
    in_row = set(unverified_terms(subject, row_material(item)))
    return [t for t in unverified_terms(subject, own) if t not in in_row]


def row_material(item: dict) -> str:
    return " ".join([item.get("applies_to") or "", item.get("parent_text") or "", item.get("source_quote") or "", item.get("passage") or "", *(item.get("prompt_windows") or {}).values()])


def prompt_passage(item: dict, cap: int) -> str:
    """The passage the model is shown: the window around the marked requirement when the checklist stored one for this cut (the plain cut would lose the requirement or its lead-in),
    else the first `cap` characters, as before."""
    window = (item.get("prompt_windows") or {}).get(str(cap))
    return window if window else (item.get("passage") or "")[:cap]


def build_prompt(item: dict) -> str:
    template = PROMPT
    if PROHIBITION.search(item.get("source_quote") or ""):
        template = template.replace("- If the requirement is a fragment,", PROHIBITION_RULE + "- If the requirement is a fragment,")
    parent = f"{item.get('parent_ref') or ''} {item.get('parent_text') or ''}".strip()
    return template.format(applies=item.get("applies_to") or "(none)", parent=parent or "(none)", quote=item.get("source_quote") or "", passage=prompt_passage(item, checklist_audit.QUESTION_PASSAGE_CHARS))


# Kinds (services/requirement_kind.py) whose rows state no duty an auditor can check: no question is drafted for them (the row stays on the checklist). Always on; REQBOT_QUESTION_GATE=off
# turns it off for debugging and a comma list of kinds replaces the set. Measured on a 228-row blind sample (2026-10-16): withholds 7 of 31 questions written for non-requirements and 1 of 153 for real ones.
GATE_KINDS_DEFAULT = frozenset({"cover_page_text", "form_template_text", "pointer", "applicability", "definition_or_description", "permission", "exemption"})


def gate_kinds() -> frozenset:
    raw = os.environ.get("REQBOT_QUESTION_GATE", "").strip().lower()
    if raw in ("0", "off", "false", "no"):
        return frozenset()
    if raw in ("", "1", "on", "true", "yes", "default"):
        return GATE_KINDS_DEFAULT
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


def skipped_because(item: dict) -> list[str]:
    reasons = set(SKIP_FLAGS & set(item.get("item_flags") or []))
    if DOCUMENT_STATES_ITS_OWN_EFFECT.search(item.get("source_quote") or ""):
        reasons.add("document_states_its_own_effect")
    if gated := gate_kinds():
        result = requirement_kind.classify(item)
        kind = result["kind"]
        if kind in requirement_kind.POSITION_KINDS and result.get("kind_by_wording") not in (None, "unknown"):
            kind = result["kind_by_wording"]  # a duty in a figure, front matter or table is still a duty: eligibility follows the wording (docs/PIPELINE_REDESIGN_PLAN.md)
        if kind in gated:
            reasons.add(f"kind:{kind}")
    return sorted(reasons)


# A second opinion for rows the kind rules cannot place (`unknown`, about a quarter of all rows, about 45% of them real requirements): the local model scores how clearly the row is a
# requirement an auditor could check, and a row scoring below the threshold gets no draft question (the row stays on the checklist). Run before the question is written, so a row that
# is skipped also saves its question call: over the library it is about time-neutral. Measured in eval/spike_results/unknown_second_opinion/README.md (prompt S3, threshold 7): on a
# third fresh set of 274 blind-labeled rows it kept 89% of the real ones and dropped 78% of the noise; the worked examples are quotes from public regulations.
SECOND_OPINION_THRESHOLD = 7
LOW_SCORE_REASON = "low_requirement_score"
SCORE_SCHEMA = {"type": "object", "properties": {"score": {"type": "integer"}}, "required": ["score"]}
SCORE_DEFINITION = """A row is a requirement when it tells an organization or person what to do, what not to do, what they are limited to, what must be in place, or what is authorized only under
stated conditions, so that an auditor could check it. These all count: "must", "will" and "shall" duties; "should" duties; advice and recommendations that tell the reader what to do
("consider ...", "it is recommended that ..."); standards for how something is done, worn, kept or reported ("the cap sits squarely on the head"); responsibilities of a named role
("it is every Airman's responsibility to ..."); and limits or conditions ("only authorized when ..."). It is NOT a requirement when it is a description of how things are or of what a tool
or method is like, a definition, background, purpose or scope statement, a summary of changes, a heading or title, a list of names, form or template text, a permission with no limit,
a statement of what the document itself does, or a cut-off fragment."""
SCORE_EXAMPLES = (
    ("System ISSMs validate the approved exemptions against the whitelist according to the current data loss prevention exemption TASKORD, verifying the removed devices/user accounts.", 9),
    ("Consistently apply effective RM concepts and methods to operations, activities and tasks.", 9),
    ("If a duty badge is being worn on the wearer's right, move the missile or excellence-in-competition badges to the wearer's left, 1/2-inch below the bottom row of medals.", 9),
    ("This issuance: Does not alter or override existing Director of National Intelligence authorities and policies regarding the protection of sensitive compartmented information and special acc", 1),
    ("The AN/USQ-225 is operationalized via nomenclated Configuration Elements that reside on or within the host platforms and facilities employed to execute nuclear command and control and operations (e.g., fixed and mobile c", 1),
    ("OPR is A1S.", 1),
)
SCORE_PROMPT = """You help an auditor decide which sentences of a regulation belong on an audit checklist.

{definition}

Examples:
{examples}

Applies to: {applies}
Parent paragraph: {parent}
Sentence to judge: {quote}
Passage (the sentence is marked >> <<):
{passage}

Score from 0 to 10 how clearly the marked sentence is a requirement an auditor could check (0 = clearly not, 10 = clearly yes).
Answer as JSON: {{"score": <integer>}}"""


def wants_second_opinion(item: dict) -> bool:
    return requirement_kind.classify(item)["kind"] == "unknown"


def score_prompt(item: dict) -> str:
    examples = "\n".join(f'- "{quote[:220]}" -> score {score}' for quote, score in SCORE_EXAMPLES)
    parent = (item.get("parent_text") or "").strip() or "(none)"
    return SCORE_PROMPT.format(definition=SCORE_DEFINITION, examples=examples, applies=item.get("applies_to") or "(none)", parent=parent[:400], quote=item.get("source_quote") or "",
                               passage=prompt_passage(item, checklist_audit.SCORE_PASSAGE_CHARS))


def score_hash(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{json.dumps(SCORE_SCHEMA, sort_keys=True)}\n{prompt}".encode("utf-8")).hexdigest()[:16]


def parse_score(text) -> int | None:
    try:
        value = json.loads(text)["score"]
    except (ValueError, KeyError, TypeError):
        return None
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10 else None


def ollama_score_call(prompt: str, model: str, ollama_url: str, timeout: int = 120) -> str:
    import requests
    payload = {"model": model, "prompt": prompt, "stream": False, "format": SCORE_SCHEMA, "options": {"temperature": 0.1, "num_predict": 20, "num_ctx": NUM_CTX}}
    resp = requests.post(f"{ollama_url.rstrip('/')}/api/generate", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["response"]


def ask_score(item: dict, score_call) -> int | None:
    """The model's 0 to 10 score for the row, or None when it cannot be had after one retry (an unreachable server, a timeout or an answer that is not a score): the row then gets its
    question as before. One bad answer is not a judgement that the row is not a requirement."""
    prompt = score_prompt(item)
    for _ in range(2):
        try:
            if (score := parse_score(score_call(prompt))) is not None:
                return score
        except OSError:
            continue
    return None


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


_NO_QUESTION = frozenset({"", "null", "none", "n/a", "na"})


def no_question(text) -> bool:
    """True for no answer, or for the word the model was told to answer with written as a string ("null", "None", "N/A"): that is "no question", never a question to show."""
    return text is None or not isinstance(text, str) or text.strip().strip("\"'.").lower() in _NO_QUESTION


def parse_answer(text: str) -> str | None:
    """The question, or None when the model answered null (as JSON null or as the string "null") or an empty string. Raises ValueError for anything that is not the expected JSON."""
    parsed = json.loads(text)
    if not isinstance(parsed, dict) or "question" not in parsed:
        raise ValueError("no question key")
    q = parsed["question"]
    return None if no_question(q) else q.strip()


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
                    if no_question(rec.get("question")):
                        rec["question"] = None  # a record written when "null" as text was taken for a question
                    out[rec["checklist_item_id"]] = rec
    except OSError:
        pass
    return out


def write(path: Path, records: dict[str, dict]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records.values()), encoding="utf-8")
    os.replace(tmp, path)


def draft_questions(items: list[dict], path: Path, *, model: str = MODEL, ollama_url: str = "", call=None, score_call=None, progress=None, on_row=None) -> dict:
    """Write or refresh the sidecar for `items` (checklist items). `call(prompt) -> text` replaces the Ollama call in tests. Returns counts.
    A record whose input is unchanged is kept; a row whose answer cannot be parsed after one retry is recorded with `error` and is retried on the next run.
    `on_row(done, total)` is called after every row (the job runner's progress: row i of N).
    Rows the kind rules call `unknown` get a second opinion first (`score_call(prompt) -> text`, the local model by default; a test that passes only `call` runs without it): a row scoring
    below SECOND_OPINION_THRESHOLD is recorded without a question and with `skipped_because: ["low_requirement_score"]`."""
    if call is None and not ollama_url:
        raise ValueError("ollama_url is required when no call function is given")
    if call is None and score_call is None:
        score_call = lambda prompt: ollama_score_call(prompt, model, ollama_url)  # noqa: E731
    call = call or (lambda prompt: ollama_call(prompt, model, ollama_url))
    existing = load(path)
    records: dict[str, dict] = dict(existing)  # rows not in this run (another profile, an interrupted run) keep their records; apply() checks each against its row
    consecutive_failures = 0
    counts = {"rows": 0, "questions": 0, "no_question": 0, "skipped_by_code": 0, "reused": 0, "errors": 0, "with_unverified_terms": 0, "second_opinion_calls": 0, "low_requirement_score": 0}
    total_rows = sum(1 for it in items if (it.get("source_quote") or "").strip())
    for item in items:
        if not (item.get("source_quote") or "").strip():
            continue
        item_id = item["checklist_item_id"]
        counts["rows"] += 1
        prompt = build_prompt(item)
        h = input_hash(prompt, model)
        skipped = skipped_because(item)
        old = existing.get(item_id)
        score, h2 = None, None
        if score_call is not None and not skipped and wants_second_opinion(item):
            sp = score_prompt(item)
            h2 = score_hash(sp, model)
            if old and old.get("score_hash") == h2 and old.get("requirement_score") is not None:
                score = old["requirement_score"]
            else:
                counts["second_opinion_calls"] += 1
                score = ask_score(item, score_call)
                h2 = h2 if score is not None else None
        if score is not None and score < SECOND_OPINION_THRESHOLD:
            records[item_id] = {"checklist_item_id": item_id, "question": None, "skipped_because": [LOW_SCORE_REASON], "unverified_terms": [], "model": model, "input_hash": h,
                                "requirement_score": score, "score_hash": h2}
            counts["low_requirement_score"] += 1
        elif old and old.get("input_hash") == h and not old.get("error") and old.get("skipped_because", []) == skipped:
            old["unverified_terms"] = unverified_terms(old["question"], row_material(item)) if old.get("question") else []  # cheap and deterministic: rule changes reach reused questions too
            if score is not None:
                old["requirement_score"], old["score_hash"] = score, h2
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
                except OSError as e:  # requests' exceptions are OSErrors: Ollama unreachable, timed out or answered with an HTTP error
                    error = f"model call failed: {e}"
                    break
            unver = unverified_terms(question, row_material(item)) if question else []
            records[item_id] = {"checklist_item_id": item_id, "question": question, "skipped_because": [], "unverified_terms": unver, "model": model, "input_hash": h,
                                "generated_at": datetime.now(timezone.utc).isoformat(), **({"error": error} if error else {}),
                                **({"requirement_score": score, "score_hash": h2} if score is not None else {})}
        rec = records[item_id]
        consecutive_failures = consecutive_failures + 1 if str(rec.get("error", "")).startswith("model call failed") else 0
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            counts["aborted"] = True
            counts["errors"] += 1
            break
        counts["skipped_by_code"] += bool(rec.get("skipped_because"))
        counts["errors"] += bool(rec.get("error"))
        counts["questions"] += bool(rec.get("question"))
        counts["no_question"] += not rec.get("question") and not rec.get("error")
        counts["with_unverified_terms"] += bool(rec.get("unverified_terms"))
        if on_row:
            on_row(counts["rows"], total_rows)
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
        elsewhere = passage_only_terms(rec["question"], item)
        if elsewhere:
            terms = ", ".join(elsewhere)
            note += " Only in the surrounding text, not in the requirement or its heading: " + terms + "."
            reason = f"question-actor-not-in-row: {terms}"
            if reason not in item.setdefault("review_reasons", []):
                item["review_reasons"].append(reason)
            item["requires_human_review"] = True
        item["generation_notes"] = (item.get("generation_notes") + " " if item.get("generation_notes") else "") + note
        filled += 1
    return filled

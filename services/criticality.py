"""Rough criticality flag for checklist rows (docs/CRITICALITY_FLAG_PLAN.md): a hint about what to look at first, never part of the requirement data.

A second job beside the draft audit questions (`reqbot questions` runs both; `--no-criticality` skips this one), with its own model call per row and its own sidecar file
(`<doc>_criticality.jsonl`) that `checklist_service.generate` reads back, so building a checklist never calls a model. The score is the plain scale below, read from the model's own
probabilities for the digits 1 to 5 (expected value over the first answer token, temperature 0), averaged over three wordings of the instruction. The plain prompt, with no worked examples
and no extra rules, is the one that held up on held-out documents (eval notes on branch spike/criticality-pilot); tuning it on one document did not carry over to another.
The flag marks the top share (a quarter by default) of the scored rows of ONE document by that score. The score ranks rows within a document; it is not an absolute severity.
The scale text below is exactly the text that was tested, including the cut-off sentences in the first three bullets.
Needs a model service that returns token probabilities (Ollama does). When it does not, no score is written and the column stays blank; a score is never guessed.
"""
import hashlib
import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from services import audit_questions

log = logging.getLogger(__name__)

NUM_CTX = audit_questions.NUM_CTX  # the same context size as the questions job, so the model is not reloaded between the two jobs
# Bands by rank within one document (the ranking is what the evidence supports, not the raw number): the top quarter is "look first" and is split into Critical and High
BANDS = (("Critical", 0.05), ("High", 0.25), ("Medium", 0.60), ("Low", 1.0))  # (label, cumulative share of the scored rows)
MAX_QUOTE_CHARS = 1500
MAX_CONSECUTIVE_FAILURES = audit_questions.MAX_CONSECUTIVE_FAILURES
CONTEXT = "requirement from a regulation or policy document"  # used when no document name is given; a named document ("requirement from the publication AFI 17-203") scored closer to the frontier judges
RUBRIC = """RUBRIC (anchored in FIPS 199, "Standards for Security Categorization of Federal Information and Information Systems", potential impact definitions)
FIPS 199 scale of the adverse effect of a loss of confidentiality, integrity or availability on organizational operations, assets or individuals:
- LOW: a limited adverse effect. AMPLIFICATION: A limited adverse effect means that, for example, the loss of confidentiality, integrity, or availability might: (i) cause a degradation in mission capability to an extent and duration that the organization is able to perform its primary functions, but the effectiveness of the functions is noticeably reduced; (ii) result in minor damage to organizational assets; (iii) result in minor financial loss; or (iv) result in minor harm to individuals. The potential impact is MODERATE if— − The loss of confidentiality, integrity, or availability co
- MODERATE: a serious adverse effect. AMPLIFICATION: A serious adverse effect means that, for example, the loss of confidentiality, integrity, or availability might: (i) cause a significant degradation in mission capability to an extent and duration that the organization is able to perform its primary functions, but the effectiveness of the functions is significantly reduced; (ii) result in significant damage to organizational assets; (iii) result in significant financial loss; or (iv) result in significant harm to individuals that does not involve loss of life or serious life threatening in
- HIGH: a severe or catastrophic adverse effect. AMPLIFICATION: A severe or catastrophic adverse effect means that, for example, the loss of confidentiality, integrity, or availability might: (i) cause a severe degradation in or loss of mission capability to an extent and duration that the organization is not able to perform one or more of its primary functions; (ii) result in major damage to organizational assets; (iii) result in major financial loss; or (iv) result in severe or catastrophic harm to individuals involving loss of life or serious life threatening injuries. Security Categorization Applied to Information Types The security category of an information type can be associated with both user information and system information3 and

How to score a requirement (1 to 5): ask "if a unit did not meet this requirement, what adverse effect would it be expected to have on the mission, assets or people?"
5 = critical: severe or catastrophic (FIPS HIGH); the effect reaches beyond the unit (a MAJCOM or combatant-command mission) or risks lives or major loss.
4 = major: serious (FIPS MODERATE); significant degradation of the unit's mission, significant damage or loss.
3 = moderate: limited but real (FIPS LOW): noticeable reduction in effectiveness, or it weakens a protection that other requirements depend on.
2 = minor: minimal effect; good practice with limited consequence.
1 = info: administrative, documentation, or best practice with no direct effect if missed.
Soft guide only: critical is rare (about 2% of requirements), major about 10%; do not force these shares, and say "moderate" or lower when the effect is not clearly serious."""
# (lead-in, closing instruction): the three wordings whose mean is the stored score
WORDINGS = (
    ("Now rate this one.", "Reply with only the digit (1-5)."),
    ("Here is the requirement to evaluate.", "Give your rating as a single digit from 1 to 5 and nothing else."),
    ("Requirement under review:", "How serious is it if this is not met? Answer with one number, 1 to 5."),
)


class ProbabilitiesUnavailable(RuntimeError):
    """The model service answered without token probabilities (not Ollama, or an old version): no score can be read."""


def sidecar_path(requirements_path: Path) -> Path:
    """`<doc>_criticality.jsonl` beside `<doc>_requirements_*.jsonl`."""
    name = re.sub(r"_requirements_(?:normalized|enriched|gated)\.jsonl$", "", requirements_path.name)
    return requirements_path.with_name(f"{name}_criticality.jsonl")


def context_for(document: str = "") -> str:
    return f"requirement from the publication {document.strip()}" if document.strip() else CONTEXT


def prompts(item: dict, context: str = CONTEXT) -> list[str]:
    quote = (item.get("source_quote") or "").strip()[:MAX_QUOTE_CHARS]
    return [f"{RUBRIC}\n{lead}\nContext: {context}\nRequirement: {quote}\n{tail}" for lead, tail in WORDINGS]


def input_hash(item: dict, model: str, context: str = CONTEXT) -> str:
    return hashlib.sha256((model + "\n" + "\n".join(prompts(item, context))).encode("utf-8")).hexdigest()[:16]


def expected_score(probs: dict) -> float | None:
    """The probability-weighted mean of the digits 1 to 5; None when the model gave no probability to any of them."""
    mass = sum(p for d, p in probs.items() if d in (1, 2, 3, 4, 5))
    if mass <= 0:
        return None
    return sum(d * p for d, p in probs.items() if d in (1, 2, 3, 4, 5)) / mass


def ollama_digit_probs(prompt: str, model: str, ollama_url: str, timeout: int = 120) -> dict:
    """{digit: probability} from the first answer token. Raises ProbabilitiesUnavailable when the reply carries no token probabilities; OSError when the server cannot be reached."""
    import requests  # local import, as in audit_questions: reading scores needs no network stack
    body = {"model": model, "stream": False, "logprobs": True, "top_logprobs": 20, "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0, "seed": 1, "num_ctx": NUM_CTX, "num_predict": 1}}
    resp = requests.post(f"{ollama_url.rstrip('/')}/api/chat", json=body, timeout=timeout)
    resp.raise_for_status()
    try:
        top = resp.json()["logprobs"][0]["top_logprobs"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise ProbabilitiesUnavailable("the model service returned no token probabilities") from e
    probs: dict[int, float] = {}
    try:
        for tok in top:
            text = str(tok.get("token", "")).strip()
            if len(text) == 1 and text in "12345":
                probs[int(text)] = probs.get(int(text), 0.0) + math.exp(tok["logprob"])
    except (KeyError, TypeError, AttributeError, ValueError, OverflowError) as e:  # a token entry that is not {"token", "logprob"}: the reply is not usable
        raise ProbabilitiesUnavailable("the model service returned token probabilities in an unexpected shape") from e
    return probs


def withheld_ids(questions_path: Path) -> set[str]:
    """Rows the questions job decided carry no checkable duty (the model answered null, or the row scored low as a requirement): a "look first" flag on them would contradict that."""
    return {i for i, rec in audit_questions.load(questions_path).items() if not rec.get("question") and not rec.get("error")}


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


def score_rows(items: list[dict], path: Path, *, model: str = audit_questions.MODEL, ollama_url: str = "", call=None, on_row=None, progress=None, document: str = "", skip_ids: frozenset | set = frozenset()) -> dict:
    """Write or refresh the sidecar for `items` (checklist items). `call(prompt) -> {digit: probability}` replaces the Ollama call in tests. `document` names the publication in the prompt's context line; `skip_ids` are rows the questions job withheld a question from (see `withheld_ids`). Returns counts.
    A record whose input (row text, wording, model) is unchanged is kept. Rows the questions job withholds a question from (fragments, definitions, no passage) get no score.
    A server that cannot be reached 5 times in a row, or that returns no token probabilities, stops the run (`aborted` / `unavailable`); rows already written are kept."""
    if call is None and not ollama_url:
        raise ValueError("ollama_url is required when no call function is given")
    call = call or (lambda prompt: ollama_digit_probs(prompt, model, ollama_url))
    context = context_for(document)
    records = load(path)
    counts = {"rows": 0, "scored": 0, "skipped_by_code": 0, "reused": 0, "errors": 0}
    total_rows = sum(1 for it in items if (it.get("source_quote") or "").strip())
    failures = 0
    for item in items:
        if not (item.get("source_quote") or "").strip():
            continue
        item_id = item["checklist_item_id"]
        counts["rows"] += 1
        if item_id in skip_ids or audit_questions.skipped_because(item):
            records.pop(item_id, None)
            counts["skipped_by_code"] += 1
        else:
            h = input_hash(item, model, context)
            old = records.get(item_id)
            if old and old.get("input_hash") == h and old.get("score") is not None:
                counts["reused"] += 1
            else:
                scores, error = [], None
                try:
                    for prompt in prompts(item, context):
                        s = expected_score(call(prompt))
                        if s is not None:
                            scores.append(s)
                except ProbabilitiesUnavailable as e:
                    counts["unavailable"] = True
                    counts["errors"] += 1
                    log.error("%s; no criticality scores were written", e)
                    break
                except OSError as e:
                    error = f"model call failed: {e}"
                if not error and len(scores) == len(WORDINGS):  # a mean over fewer wordings is never stored: it would be reused as if complete
                    records[item_id] = {"checklist_item_id": item_id, "score": sum(scores) / len(scores), "scores": [round(s, 4) for s in scores], "model": model, "context": context, "input_hash": h,
                                        "generated_at": datetime.now(timezone.utc).isoformat()}
                    counts["scored"] += 1
                    failures = 0
                else:
                    records.pop(item_id, None)
                    counts["errors"] += 1
                    failures = failures + 1 if error else 0
                    if failures >= MAX_CONSECUTIVE_FAILURES:
                        counts["aborted"] = True
                        break
        if on_row:
            on_row(counts["rows"], total_rows)
        if progress and counts["rows"] % 25 == 0:
            progress(counts)
            write(path, records)
    write(path, records)
    return counts


def apply(items: list[dict], path: Path, skip_ids: frozenset | set = frozenset()) -> int:
    """Put `criticality` (Critical, High, Medium or Low, by the row's rank among the document's scored rows) on checklist items from the sidecar; returns how many rows are scored.
    The 1 to 5 number stays in the sidecar and is never shown. A record written from a different row text, model or document name is stale and ignored. Rows without a record are left as
    they are, so with no sidecar nothing changes."""
    records = load(path)
    scored = []
    for item in items:
        rec = records.get(item["checklist_item_id"])
        if not rec or rec.get("score") is None or item["checklist_item_id"] in skip_ids or audit_questions.skipped_because(item):
            continue
        if rec.get("input_hash") != input_hash(item, rec.get("model", audit_questions.MODEL), rec.get("context", CONTEXT)):
            continue
        scored.append((-rec["score"], item["checklist_item_id"], item))
    scored.sort(key=lambda t: (t[0], t[1]))
    for rank, (_s, _id, item) in enumerate(scored, start=1):
        item["criticality"] = next(label for label, upto in BANDS if rank <= max(1, round(len(scored) * upto)))
    return len(scored)

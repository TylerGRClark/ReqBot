"""HyPE spike: the pure, testable parts (no network, no Qdrant).

Prompt and parsing of generated questions, the grounding filter, point ids, the collapse to
requirement_id, the paired scoring and the pre-registered decision rule. See PREREGISTRATION.md.
"""
import json
import re
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.audit_questions import unverified_terms  # noqa: E402  (the repo's own grounding check)

MAX_QUESTIONS = 3
MIN_QUESTION_CHARS = 15
MAX_QUESTION_CHARS = 300
SCRATCH_PREFIX = "grc_hype_spike_"  # the only collection names this harness will create, write to or delete
# Namespace for question point ids: distinct from the production point namespace, so a question point can never overwrite a requirement point.
HYPE_UUID_NAMESPACE = uuid.UUID("5b0e3a52-7c1f-4d6a-9a43-2f8d1e6c7b90")

QUESTIONS_SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_QUESTIONS}},
    "required": ["questions"],
}

PROMPT = """You help people search a library of regulatory requirements.

Below is one requirement. Write up to {n} different questions a compliance analyst might type into a search box that this requirement answers.
Rules:
- Ask about the meaning, not the exact wording; do not copy a whole phrase from the text.
- Each question must stand alone and make sense without the text beside it.
- Use only facts, names, numbers and acronyms that are in the text. Do not add any that are not.
- If the text is a fragment with no clear meaning, answer with an empty list.

Requirement text:
{text}

Answer as JSON: {{"questions": ["...", "..."]}}"""


def record_text(payload: dict) -> str:
    """The text a question may be grounded in: the record's own text only (parent stem, explained text, quote). Not the source reference, the document name or neighbouring records."""
    values = []
    for key in ("parent_stem", "explained_text", "source_quote"):
        value = (payload.get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    # a part that sits inside another part (the stem inside the explained text, the quote inside either) adds nothing
    return " ".join(v for v in values if not any(v != o and v in o for o in values))


def build_prompt(payload: dict, n: int = MAX_QUESTIONS) -> str:
    return PROMPT.format(n=n, text=record_text(payload))


def parse_questions(raw: str) -> list[str]:
    """Questions from the model's JSON answer; anything that is not a list of strings gives []."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    items = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [" ".join(i.split()) for i in items if isinstance(i, str) and i.strip()]


def ground_questions(questions: list[str], material: str, limit: int = MAX_QUESTIONS) -> tuple[list[str], list[dict]]:
    """(kept, rejected). A question is kept only if every number, acronym and capitalised term in it
    appears in `material` (the record's own text), it is a plausible length, and it is not a duplicate."""
    kept, rejected, seen = [], [], set()
    for q in questions:
        q = " ".join((q or "").split())
        key = q.lower().rstrip("?. ")
        if not (MIN_QUESTION_CHARS <= len(q) <= MAX_QUESTION_CHARS):
            rejected.append({"question": q, "reason": "length"})
        elif key in seen:
            rejected.append({"question": q, "reason": "duplicate"})
        else:
            # the sentence-initial word is capitalised by position, not because it is a name ("Which", "Where");
            # a leading acronym or mixed-case name (CUI, DoD) is left alone
            checked = re.sub(r"^[A-Z][a-z]+\b", lambda m: m.group(0).lower(), q)
            missing = unverified_terms(checked, material)
            if missing:
                rejected.append({"question": q, "reason": "ungrounded", "terms": missing})
            elif len(kept) < limit:
                kept.append(q)
                seen.add(key)
            else:
                rejected.append({"question": q, "reason": "over_limit"})
    return kept, rejected


def question_point_id(requirement_id: str, index: int) -> str:
    return str(uuid.uuid5(HYPE_UUID_NAMESPACE, f"{requirement_id}#q{index}"))


def collapse_to_requirement_id(ranked: list[dict], limit: int | None = None) -> list[dict]:
    """One entry per requirement_id, in the order of its best-ranked point (the first in `ranked`).
    An entry without a requirement_id is dropped. `limit` cuts AFTER collapsing, so a requirement
    that is reachable through several points cannot crowd out others."""
    out, seen = [], set()
    for item in ranked:
        rid = item.get("requirement_id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        out.append(item)
        if limit is not None and len(out) >= limit:
            break
    return out


def live_labels(query: dict, live_ids: set[str]) -> set[str]:
    return {i for i in query.get("relevant_requirement_ids", []) if i in live_ids}


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def decide(a_miss_recall5: float, b_miss_recall5: float, a_gold_p5: float, b_gold_p5: float,
           rule: dict) -> dict:
    """Apply the pre-registered rule (decision_rule.json). Inputs are fractions (0..1); the rule is in points."""
    rise = round((b_miss_recall5 - a_miss_recall5) * 100, 2)
    fall = round((a_gold_p5 - b_gold_p5) * 100, 2)
    need_rise = rule["build_if"]["miss_set_recall_at_5_rise_points_at_least"]
    max_fall = rule["build_if"]["gold_precision_at_5_fall_points_at_most"]
    rise_ok, fall_ok = rise >= need_rise, fall <= max_fall
    return {
        "miss_recall_at_5_rise_points": rise,
        "gold_precision_at_5_fall_points": fall,
        "rise_requirement_met": rise_ok,
        "fall_limit_met": fall_ok,
        "verdict": "BUILD" if rise_ok and fall_ok else "DO NOT BUILD",
    }


# ---------------------------------------------------------------- round 2 (PREREGISTRATION_V2.md)

def normalise(text: str) -> str:
    """Lower-case, keep letters and digits, collapse whitespace: the comparison form for anchor quotes."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


def target_hit(result: dict, requirement_ids: list[str], anchor_norm: str) -> bool:
    """A retrieved record is the target if its requirement_id is listed, or any of its own text fields contains the anchor quote."""
    if result.get("requirement_id") in set(requirement_ids):
        return True
    if not anchor_norm:
        return False
    return any(anchor_norm in normalise(result.get(k) or "") for k in ("source_quote", "explained_text", "parent_stem"))


def gated_ids(checklists: list[dict]) -> set[str]:
    """requirement_ids that belong to a checklist row with a non-empty draft audit question."""
    out = set()
    for doc in checklists:
        for item in doc.get("items", []):
            if (item.get("audit_question") or "").strip():
                out.update(item.get("requirement_ids") or [])
    return out


def gate_c(payload: dict, gate: set[str], min_chars: int = 0) -> bool:
    return payload.get("requirement_id") in gate and len(record_text(payload)) >= min_chars


def paired_bootstrap(diffs: list[float], resamples: int = 10000, seed: int = 20261014) -> tuple[float, float, float]:
    """(mean, lower, upper) of the mean of paired differences, 95% percentile interval, deterministic."""
    import random
    rng, n = random.Random(seed), len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    return sum(diffs) / n, means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def decide_v2(rise_points: float, ci_lower: float, gold_fall_points: float, nonhard_rise_points: float) -> dict:
    """The round-2 rule of PREREGISTRATION_V2.md. Inputs in points (interval bound in points too)."""
    checks = {"rise_at_least_5": rise_points >= 5, "interval_lower_above_0": ci_lower > 0,
              "gold_fall_at_most_2": gold_fall_points <= 2, "gain_not_only_from_hard_rows": nonhard_rise_points > 0}
    return {**checks, "verdict": "BUILD" if all(checks.values()) else "DO NOT BUILD"}

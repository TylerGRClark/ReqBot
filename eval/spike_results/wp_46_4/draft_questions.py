#!/usr/bin/env python3
"""WP-46.4: draft audit questions for a seeded sample of checklist rows (experiment; reads the checklist, calls the local model, writes only under outputs/).

  PYTHONPATH=. python3 eval/spike_results/wp_46_4/draft_questions.py [--doc afi17-203] [--n 30]

The rules are in README.md and were fixed before any output was read.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "eval/spike_results/wp_45_7"):
    sys.path.insert(0, str(p))

import ollama_run as OR  # noqa: E402  (wp_45_7: the shared Ollama call)

from core import config  # noqa: E402
from services.checklist_service import generate  # noqa: E402

MODEL = "qwen2.5:14b"
SEED = 46
SKIP_FLAGS = {"starts_mid_sentence", "table_fragment", "definition_or_description", "quote_not_located_in_passage", "no_passage"}  # v2: no question is asked for these rows
PROMPT_V1 = """You help an auditor check whether a unit follows a regulation.

Write ONE short yes/no audit question that checks whether the requirement below is being met.
Rules:
- Use only the words and facts in the material below. Do not add numbers, deadlines, roles, systems or documents that are not in it.
- Name who must act if the material says so (the "Applies to" line or the requirement itself). If the requirement does not say who acts and nothing below does either, ask about "the unit".
- If the requirement is a fragment, a definition, a description, or states no duty that can be checked, answer with null.

Applies to: {applies}
Parent paragraph: {parent}
Requirement: {quote}
Passage (the requirement is marked >> <<):
{passage}

Answer as JSON: {{"question": "<the question>"}} or {{"question": null}}."""
PROMPT_V2 = PROMPT_V1.replace(
    "- If the requirement is a fragment,",
    "- If the requirement says something must NOT happen (not, never, shall not), ask whether it is avoided (\"Does the unit avoid ...?\"); never turn it into a question about whether it happens.\n"
    "- If the requirement only gives permission or describes how things are (may, can, is authorized to, is defined as), answer with null.\n- If the requirement is a fragment,")
# v3: version 2's prompt rule about prohibitions leaked into plain statements ("Does the unit avoid any action that would prevent ..."), so the prohibition rule is added only when
# the quote contains a prohibition; the permission rule and the code gate stay.
PROHIBITION = re.compile(
    r"\b(?:shall|must|should|will|may|can|could|would|do|does|did|is|are|be)\s+not\b(?!\s+(?:limited|only|necessarily))|\bcannot\b|\bnever\b|\bprohibited\b|\bforbidden\b", re.IGNORECASE)
PROMPT_V3 = PROMPT_V1.replace(
    "- If the requirement is a fragment,",
    "- If the requirement only gives permission or describes how things are (may, can, is authorized to, is defined as), answer with null.\n- If the requirement is a fragment,")
PROHIBITION_RULE = "- This requirement forbids something. Ask whether it is avoided (\"Does the unit avoid ...?\"); do not ask whether it happens.\n"
SCHEMA = {"type": "object", "properties": {"question": {"type": ["string", "null"]}}, "required": ["question"]}
_TERM = re.compile(r"\b(?:\d[\w./-]*|[A-Z]{2,}[\w/&-]*|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)")
_STOP = {"does", "do", "is", "are", "has", "have", "did", "was", "were", "can", "will", "the", "a", "an", "if", "when", "whether", "who", "what", "how", "each", "all", "any", "yes", "no"}


def unverified_terms(question: str, material: str) -> list:
    """Numbers, acronyms and capitalized words in the question that the row's own text does not contain (the sentence-initial word is ignored)."""
    low = set(re.findall(r"[a-z0-9][a-z0-9./&'-]*", re.sub(r"\s+", " ", material or "").lower()))
    out = []
    for m in _TERM.finditer(question or ""):
        if m.start() == 0:
            continue
        for word in m.group(0).split():  # checked word by word: a title with its parenthetical acronym left out is still grounded
            w = word.lower().strip(".,;:()")
            if w and w not in _STOP and w not in low:
                out.append(word)
    return out


def row_material(item: dict) -> str:
    return " ".join([item.get("applies_to") or "", item.get("parent_text") or "", item.get("source_quote") or "", item.get("passage") or ""])


def main():
    cfg = config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--doc", default="afi17-203")
    ap.add_argument("--n", type=int, default=30)  # rows to draw
    ap.add_argument("--variant", type=int, choices=(1, 2, 3), default=3)
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    args = ap.parse_args()
    if args.n < 1:
        sys.exit("--n must be at least 1")
    checklist = generate(Path(cfg.processed_dir).expanduser(), args.doc, "cybersecurity")
    items = [i for i in checklist["items"] if i["source_quote"].strip()]
    sample = sorted(random.Random(SEED).sample(items, min(args.n, len(items))), key=lambda i: items.index(i))
    digest = OR.model_digest(args.ollama_url, MODEL)
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    records, lines = [], [f"# Draft audit questions — {args.doc}, {len(sample)} rows (seeded sample)", "",
                          "Rate each question: **usable** / **edit** / **wrong**. When there is no question: **right to skip** / **should have asked**.", ""]
    prefix = f"v{args.variant}_"
    for n, item in enumerate(sample, 1):
        skipped = sorted(SKIP_FLAGS & set(item["item_flags"])) if args.variant >= 2 else []
        if skipped:  # the row stays on the sheet; only the suggested question is withheld
            records.append({"n": n, "checklist_item_id": item["checklist_item_id"], "source_ref": item["source_ref"], "applies_to": item["applies_to"], "parent_text": item["parent_text"],
                            "source_quote": item["source_quote"], "question": None, "skipped_because": skipped, "unverified_terms": [], "item_flags": item["item_flags"], "model": MODEL,
                            "digest": digest, "seconds": 0})
            lines += [f"## {n}. {item['source_ref'] or '(no ref)'} — p. {', '.join(map(str, item['page_refs']))}", "", f"> {item['source_quote']}", "",
                      f"**Draft question:** *(none: the row looks like a fragment or description — {', '.join(skipped)})*  ", "**Rating:** ", "", "---", ""]
            continue
        passage = (item.get("passage") or "")[:1500]
        template = {1: PROMPT_V1, 2: PROMPT_V2, 3: PROMPT_V3}[args.variant]
        if args.variant == 3 and PROHIBITION.search(item["source_quote"]):
            template = template.replace("- If the requirement is a fragment,", PROHIBITION_RULE + "- If the requirement is a fragment,")
        prompt = template.format(applies=item["applies_to"] or "(none)", parent=(f"{item['parent_ref']} {item['parent_text']}" if item["parent_text"] else "(none)"),
                               quote=item["source_quote"], passage=passage)
        question, error, meta = None, None, {}
        for _attempt in range(2):  # one retry: a malformed answer is a generation failure, not the model's judgement that the row is not auditable
            text, meta = OR.generate(prompt, MODEL, args.ollama_url, num_ctx=4096, num_predict=200, temperature=0.1, schema=SCHEMA, timeout=120)
            try:
                parsed = json.loads(text)
                if not isinstance(parsed, dict) or "question" not in parsed:
                    raise ValueError("no question key")
                question, error = parsed["question"], None
                break
            except ValueError as e:
                error = f"malformed response: {e}"
        question = question.strip() if isinstance(question, str) and question.strip() else None
        unver = unverified_terms(question, row_material(item)) if question else []
        records.append({"n": n, "checklist_item_id": item["checklist_item_id"], "source_ref": item["source_ref"], "applies_to": item["applies_to"], "parent_text": item["parent_text"],
                        "source_quote": item["source_quote"], "question": question, "unverified_terms": unver, "item_flags": item["item_flags"], "model": MODEL, "digest": digest,
                        "generation_error": error, "seconds": meta.get("wall_seconds")})
        lines += [f"## {n}. {item['source_ref'] or '(no ref)'} — p. {', '.join(map(str, item['page_refs']))}", "",
                  f"**Applies to:** {item['applies_to'] or '—'}  ", f"**Parent paragraph:** {(item['parent_ref'] + ' ' + item['parent_text']).strip() or '—'}  ", "",
                  f"> {item['source_quote']}", "",
                  f"**Draft question:** {question if question else ('*(generation error: ' + error + ')*' if error else '*(none: the model judged it not auditable as written)*')}  "]
        if unver:
            lines.append(f"**Check:** unverified terms {unver}  ")
        lines += ["**Rating:** ", "", "---", ""]
    (out_dir / f"{prefix}draft_questions.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    (out_dir / f"{prefix}rating_sheet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    asked = sum(1 for r in records if r["question"])
    print(json.dumps({"rows": len(records), "questions": asked, "no_question": len(records) - asked, "skipped_by_code": sum(1 for r in records if r.get("skipped_because")), "generation_errors": sum(1 for r in records if r.get("generation_error")), "with_unverified_terms": sum(1 for r in records if r["unverified_terms"]), "model": MODEL, "digest": digest}, indent=1))


if __name__ == "__main__":
    main()

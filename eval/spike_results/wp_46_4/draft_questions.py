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
PROMPT = """You help an auditor check whether a unit follows a regulation.

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
SCHEMA = {"type": "object", "properties": {"question": {"type": ["string", "null"]}}, "required": ["question"]}
_TERM = re.compile(r"\b(?:\d[\w./-]*|[A-Z]{2,}[\w/&-]*|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)")
_STOP = {"does", "do", "is", "are", "has", "have", "did", "was", "were", "can", "will", "the", "a", "an", "if", "when", "whether", "who", "what", "how", "each", "all", "any", "yes", "no"}


def unverified_terms(question: str, material: str) -> list:
    """Numbers, acronyms and capitalized words in the question that the row's own text does not contain (the sentence-initial word is ignored)."""
    low = re.sub(r"\s+", " ", material or "").lower()
    out = []
    for m in _TERM.finditer(question or ""):
        term = m.group(0)
        if m.start() == 0 or term.lower() in _STOP:
            continue
        if term.lower() not in low:
            out.append(term)
    return out


def row_material(item: dict) -> str:
    return " ".join([item.get("applies_to") or "", item.get("parent_text") or "", item.get("source_quote") or "", item.get("passage") or ""])


def main():
    cfg = config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--doc", default="afi17-203")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    args = ap.parse_args()
    checklist = generate(Path(cfg.processed_dir).expanduser(), args.doc, "cybersecurity")
    items = [i for i in checklist["items"] if i["source_quote"].strip()]
    sample = sorted(random.Random(SEED).sample(items, min(args.n, len(items))), key=lambda i: items.index(i))
    digest = OR.model_digest(args.ollama_url, MODEL)
    out_dir = Path(__file__).resolve().parent / "outputs"
    records, lines = [], [f"# Draft audit questions — {args.doc}, {len(sample)} rows (seeded sample)", "",
                          "Rate each question: **usable** / **edit** / **wrong**. When there is no question: **right to skip** / **should have asked**.", ""]
    for n, item in enumerate(sample, 1):
        passage = item["passage"][:1500]
        prompt = PROMPT.format(applies=item["applies_to"] or "(none)", parent=(f"{item['parent_ref']} {item['parent_text']}" if item["parent_text"] else "(none)"),
                               quote=item["source_quote"], passage=passage)
        text, meta = OR.generate(prompt, MODEL, args.ollama_url, num_ctx=4096, num_predict=200, temperature=0.1, schema=SCHEMA, timeout=120)
        try:
            question = json.loads(text).get("question")
        except ValueError:
            question = None
        question = question.strip() if isinstance(question, str) and question.strip() else None
        unver = unverified_terms(question, row_material(item)) if question else []
        records.append({"n": n, "checklist_item_id": item["checklist_item_id"], "source_ref": item["source_ref"], "applies_to": item["applies_to"], "parent_text": item["parent_text"],
                        "source_quote": item["source_quote"], "question": question, "unverified_terms": unver, "item_flags": item["item_flags"], "model": MODEL, "digest": digest,
                        "seconds": meta.get("wall_seconds")})
        lines += [f"## {n}. {item['source_ref'] or '(no ref)'} — p. {', '.join(map(str, item['page_refs']))}", "",
                  f"**Applies to:** {item['applies_to'] or '—'}  ", f"**Parent paragraph:** {(item['parent_ref'] + ' ' + item['parent_text']).strip() or '—'}  ", "",
                  f"> {item['source_quote']}", "",
                  f"**Draft question:** {question if question else '*(none: the model judged it not auditable as written)*'}  "]
        if unver:
            lines.append(f"**Check:** unverified terms {unver}  ")
        lines += ["**Rating:** ", "", "---", ""]
    (out_dir / "draft_questions.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    (out_dir / "rating_sheet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    asked = sum(1 for r in records if r["question"])
    print(json.dumps({"rows": len(records), "questions": asked, "no_question": len(records) - asked, "with_unverified_terms": sum(1 for r in records if r["unverified_terms"]), "model": MODEL, "digest": digest}, indent=1))


if __name__ == "__main__":
    main()

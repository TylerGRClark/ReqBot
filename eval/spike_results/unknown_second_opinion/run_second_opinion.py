"""Runner for the unknown-second-opinion experiment. Rules are in README.md (written before this was run)."""
import argparse
import json
import random
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
MODEL = "qwen2.5:14b"
SCHEMA = {"type": "object", "properties": {"score": {"type": "integer"}}, "required": ["score"]}

DEFINITION = """A row is a requirement when it states something an organization or person must do, must not do, is limited to, or is required to have in place, so that an auditor
could check it ("should" duties, prohibitions and limits count). It is NOT a requirement when it is a description, definition, background, purpose or scope statement, a summary of
changes, a heading or title, a list of names, form or template text, a permission with no limit, a statement of what the document itself does, or a cut-off fragment."""

PROMPT = """You help an auditor decide which sentences of a regulation belong on an audit checklist.

{definition}
{examples}
Applies to: {applies}
Parent paragraph: {parent}
Sentence to judge: {quote}
Passage (the sentence is marked >> <<):
{passage}

Score from 0 to 10 how clearly the marked sentence is a requirement an auditor could check (0 = clearly not, 10 = clearly yes).
Answer as JSON: {{"score": <integer>}}"""


def example_block(examples: list[dict]) -> str:
    if not examples:
        return ""
    lines = ["\nExamples:"]
    for e in examples:
        lines.append(f'- "{e["quote"][:220]}" -> score {9 if e["label"] == "requirement" else 1}')
    return "\n".join(lines) + "\n"


def build(row: dict, examples: list[dict]) -> str:
    parent = (row.get("parent") or "").strip() or "(none)"
    return PROMPT.format(definition=DEFINITION, examples=example_block(examples), applies=row.get("applies") or "(none)", parent=parent[:400],
                         quote=row["quote"], passage=(row.get("passage") or "")[:1200])


def ask(prompt: str, url: str):
    payload = {"model": MODEL, "prompt": prompt, "stream": False, "format": SCHEMA, "options": {"temperature": 0.1, "num_predict": 20, "num_ctx": 4096}}
    for _ in range(2):
        try:
            r = requests.post(f"{url.rstrip('/')}/api/generate", json=payload, timeout=120)
            r.raise_for_status()
            return int(json.loads(r.json()["response"])["score"]), None
        except (requests.RequestException, ValueError, KeyError) as e:
            err = str(e)[:80]
    return None, err


def pick_examples(rows: list[dict]) -> list[dict]:
    dev = [r for r in rows if r["split"] == "dev"]
    rnd = random.Random(61)
    real = rnd.sample([r for r in dev if r["label"] == "requirement"], 3)
    notr = rnd.sample([r for r in dev if r["label"] != "requirement"], 3)
    return real + notr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--ollama-url", required=True)
    args = ap.parse_args()
    rows = json.loads(Path(args.rows).expanduser().read_text(encoding="utf-8"))
    examples = pick_examples(rows)
    ex_ids = [e["id"] for e in examples]
    OUT.mkdir(exist_ok=True)
    path = OUT / "scores.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    for n, row in enumerate(rows, 1):
        rec = done.get(row["id"]) or {}
        for arm, ex in (("S1", []), ("S2", examples)):
            if arm in rec:
                continue
            if arm == "S2" and row["id"] in ex_ids:
                rec[arm] = None
                continue
            score, err = ask(build(row, ex), args.ollama_url)
            rec[arm] = score
            if err:
                rec[arm + "_error"] = err
        done[row["id"]] = rec
        if n % 20 == 0 or n == len(rows):
            path.write_text(json.dumps(done), encoding="utf-8")
            print(f"  {n}/{len(rows)}", flush=True)
    (OUT / "example_ids.json").write_text(json.dumps(ex_ids), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

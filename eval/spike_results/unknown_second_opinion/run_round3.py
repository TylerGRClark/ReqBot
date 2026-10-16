"""Round 3: S3 and S4 on the tuning rows, and (once, with --final) the chosen variant on the third fresh set. Rules are in README.md."""
import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_second_opinion as R  # noqa: E402

DEF3 = """A row is a requirement when it tells an organization or person what to do, what not to do, what they are limited to, what must be in place, or what is authorized only under
stated conditions, so that an auditor could check it. These all count: "must", "will" and "shall" duties; "should" duties; advice and recommendations that tell the reader what to do
("consider ...", "it is recommended that ..."); standards for how something is done, worn, kept or reported ("the cap sits squarely on the head"); responsibilities of a named role
("it is every Airman's responsibility to ..."); and limits or conditions ("only authorized when ..."). It is NOT a requirement when it is a description of how things are or of what a tool
or method is like, a definition, background, purpose or scope statement, a summary of changes, a heading or title, a list of names, form or template text, a permission with no limit,
a statement of what the document itself does, or a cut-off fragment."""


def build(row, examples, definition):
    ex = R.example_block(examples)
    parent = (row.get("parent") or "").strip() or "(none)"
    return R.PROMPT.format(definition=definition, examples=ex, applies=row.get("applies") or "(none)", parent=parent[:400], quote=row["quote"], passage=(row.get("passage") or "")[:1200])


def extra_examples(rows, taken):
    rnd = random.Random(73)
    f2 = [r for r in rows if r["set"] == "f2" and r["id"] not in taken]
    real = rnd.sample([r for r in f2 if r["label"] == "requirement"], 3)
    notr = rnd.sample([r for r in f2 if r["label"] != "requirement"], 3)
    return real + notr


def as_example(r):
    return {"quote": r["quote"], "label": "requirement" if r["label"] == "requirement" else "not"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune-rows", required=True)
    ap.add_argument("--ollama-url", required=True)
    args = ap.parse_args()
    rows = json.loads(Path(args.tune_rows).expanduser().read_text(encoding="utf-8"))
    s2_ids = set(json.loads((R.OUT / "example_ids.json").read_text()))
    s2_examples = [as_example(r) for r in rows if r["id"] in s2_ids]
    extra = extra_examples(rows, s2_ids)
    (R.OUT / "round3_example_ids.json").write_text(json.dumps([r["id"] for r in extra]), encoding="utf-8")
    arms = {"S3": (s2_examples, DEF3), "S4": (s2_examples + [as_example(r) for r in extra], DEF3)}
    path = R.OUT / "scores_round3.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    skip = s2_ids | {r["id"] for r in extra}
    for n, row in enumerate(rows, 1):
        rec = done.get(row["id"]) or {}
        for arm, (ex, definition) in arms.items():
            if arm in rec or row["id"] in skip:
                continue
            score, err = R.ask(build(row, ex, definition), args.ollama_url)
            rec[arm] = score
        done[row["id"]] = rec
        if n % 25 == 0 or n == len(rows):
            path.write_text(json.dumps(done), encoding="utf-8")
            print(f"  {n}/{len(rows)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())

"""Runner for the unit-fallback experiment. Rules are in README.md (written before this was run).

Run: PYTHONPATH=. python3 eval/spike_results/question_unit_fallback/run_unit_fallback.py --ollama-url http://<ollama-host>:11434
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

from services import audit_questions as aq
from services import checklist_service as cs

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
PROC = Path.home() / "documents" / "processed"
DOCS = ["afman17-2101", "dafman17-1305", "CJCSI 6510.02G", "dafi36-2903", "DODI 5200.44"]
PER_DOC = 50
SEED = 51

C = aq.PROMPT
N = (C.replace("whether a unit follows a regulation", "whether a regulation is being followed")
      .replace('If neither says, ask about "the unit".', "If neither says, do not name an actor: ask the question impersonally (for example \"Is X ...?\" or \"Are X ...?\").")
      )
O = C.replace("whether a unit follows a regulation", "whether an organization follows a regulation").replace('ask about "the unit"', 'ask about "the organization"')
PROH = aq.PROHIBITION_RULE
PROH_N = PROH.replace('Ask whether it is avoided ("Does the unit avoid ...?")', 'Ask whether it is avoided ("Is X avoided?")')
PROH_O = PROH.replace("the unit", "the organization")
ARMS = {"C": (C, PROH), "C2": (C, PROH), "N": (N, PROH_N), "O": (O, PROH_O)}
for t, p in ARMS.values():
    assert t != "" and p != ""
assert N != C and O != C and PROH_N != PROH and PROH_O != PROH


def build(item, template, proh):
    if aq.PROHIBITION.search(item.get("source_quote") or ""):
        template = template.replace("- If the requirement is a fragment,", proh + "- If the requirement is a fragment,")
    parent = f"{item.get('parent_ref') or ''} {item.get('parent_text') or ''}".strip()
    return template.format(applies=item.get("applies_to") or "(none)", parent=parent or "(none)", quote=item.get("source_quote") or "", passage=(item.get("passage") or "")[:1500])


def ask(prompt, url):
    for _ in range(2):
        try:
            return aq.parse_answer(aq.ollama_call(prompt, aq.MODEL, url)), None
        except (ValueError, KeyError) as e:
            err = f"malformed response: {e}"
        except OSError as e:
            return None, f"model call failed: {e}"
    return None, err


def rows():
    out = []
    for key in DOCS:
        items = [i for i in cs.generate(PROC, key, "cybersecurity")["items"] if (i.get("source_quote") or "").strip() and not aq.skipped_because(i)]
        items.sort(key=lambda i: i["checklist_item_id"])
        out += [(key, i) for i in random.Random(SEED).sample(items, min(PER_DOC, len(items)))]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ollama-url", required=True)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    path = OUT / "runs.jsonl"
    done = {}
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            done[r["id"]] = r
    rs = rows()
    print("rows", len(rs), flush=True)
    for n, (doc, it) in enumerate(rs, 1):
        cid = it["checklist_item_id"]
        rec = done.get(cid) or {"id": cid, "doc": doc, "citation": it.get("citation", ""), "applies": it.get("applies_to"), "parent": it.get("parent_text"),
                                "quote": it.get("source_quote"), "passage": (it.get("passage") or "")[:1500]}
        for arm, (tpl, proh) in ARMS.items():
            if arm in rec:
                continue
            q, err = ask(build(it, tpl, proh), args.ollama_url)
            rec[arm] = q
            if err:
                rec[arm + "_error"] = err
        done[cid] = rec
        if n % 10 == 0 or n == len(rs):
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()), encoding="utf-8")
            print(f"  {n}/{len(rs)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())

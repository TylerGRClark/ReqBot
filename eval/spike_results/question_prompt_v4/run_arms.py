"""Round 2 of the prompt v4 experiment: arms S, R and V5 on the same rows. Rules are in README.md (written before this was run).

Run: PYTHONPATH=. python3 eval/spike_results/question_prompt_v4/run_arms.py --ollama-url http://192.168.90.100:11434
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_prompt_v4 as R  # noqa: E402
from services import audit_questions as aq  # noqa: E402

RULE2_V5 = ('- Name who acts and make that the subject of the question. If the requirement itself says who acts (for example "by the program office" or "the commander '
            'will"), use that; otherwise use the "Applies to" line. If neither says, ask about "the unit". Do not use the passive voice.\n')
ARMS = {
    "S": aq.PROMPT.replace(R.RULE2_V3, R.SCOPE_V4 + R.RULE2_V3),
    "R": aq.PROMPT.replace(R.RULE2_V3, R.RULE2_V4),
    "V5": aq.PROMPT.replace(R.RULE2_V3, R.SCOPE_V4 + RULE2_V5),
}
OUT = R.OUT
UNIT = re.compile(r"^(does|do)\s+the unit\b", re.I)
ACTOR = re.compile(r"^(does|do|have|has)\s+(?!the unit\b)", re.I)
PASSIVE = re.compile(r"^(is|are|was|were)\b", re.I)


def build(template: str, item: dict) -> str:
    if aq.PROHIBITION.search(item.get("source_quote") or ""):
        template = template.replace("- If the requirement is a fragment,", aq.PROHIBITION_RULE + "- If the requirement is a fragment,")
    parent = f"{item.get('parent_ref') or ''} {item.get('parent_text') or ''}".strip()
    return template.format(applies=item.get("applies_to") or "(none)", parent=parent or "(none)", quote=item.get("source_quote") or "", passage=(item.get("passage") or "")[:1500])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ollama-url", required=True)
    args = ap.parse_args()
    path = OUT / "runs_arms.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[r["id"]] = r
    rows = [(s, label, it) for s, label, it in R.pick_rows() if R.eligible(it)]
    print(f"rows: {len(rows)}", flush=True)
    for n, (s, label, it) in enumerate(rows, 1):
        cid = it["checklist_item_id"]
        rec = done.get(cid) or {"id": cid, "set": s, "doc": label, "ref": it.get("citation", ""), "quote": it["source_quote"], "v3_stored": it.get("audit_question") or None,
                                "passage": it.get("passage", "")}
        for arm, template in ARMS.items():
            if arm in rec:
                continue
            q, err = R.ask(build(template, it), args.ollama_url)
            rec[arm] = q
            if err:
                rec[arm + "_error"] = err
        rec["_item"] = None
        done[cid] = rec
        if n % 20 == 0 or n == len(rows):
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()), encoding="utf-8")
            print(f"  {n}/{len(rows)}", flush=True)
    summarize(list(done.values()))


def summarize(recs):
    v4 = {}
    for line in (OUT / "runs.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        v4[r["id"]] = r.get("v4")
    out = {}
    for arm in ("V4", "S", "R", "V5"):
        d = {"rows": 0, "changed": 0, "null_v3": 0, "null_arm": 0, "new_null": 0, "lost_actor": 0, "gained_actor": 0, "errors": 0}
        for r in recs:
            if arm == "V4":
                if r["id"] not in v4:
                    continue
                q = v4[r["id"]]
            else:
                if r.get(arm + "_error"):
                    d["errors"] += 1
                    continue
                q = r.get(arm)
            v3 = r["v3_stored"]
            d["rows"] += 1
            d["changed"] += R.norm(q) != R.norm(v3)
            d["null_v3"] += not v3
            d["null_arm"] += not q
            d["new_null"] += bool(v3) and not q
            d["lost_actor"] += bool(v3 and q and ACTOR.match(v3) and PASSIVE.match(q))
            d["gained_actor"] += bool(v3 and q and UNIT.match(v3) and ACTOR.match(q))
        out[arm] = d
    (OUT / "measures_arms.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.exit(main())

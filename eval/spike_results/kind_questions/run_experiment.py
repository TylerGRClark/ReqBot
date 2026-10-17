"""Run the kind-aware question spike.
  python3 run_experiment.py <scratch_dir> det                       # no model: rules-7 changes, pointers, recommendations
  python3 run_experiment.py <scratch_dir> perm <round> <prompt> [failed_from_round]   # permission questions, one model call per row, serial
Outputs go to ./outputs/ (this folder). Nothing under services/, no sidecar, index or checklist is written.
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kind_questions as kq  # noqa: E402
import round3_checks  # noqa: E402, F401  (registers prompt v5)
from build_rows import load_rows  # noqa: E402
from core import config  # noqa: E402
from services import audit_questions as aq  # noqa: E402
from services import requirement_kind as rk  # noqa: E402

OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)


def row_id(r: dict) -> dict:
    return {"doc": r["_doc"], "citation": r.get("citation"), "checklist_item_id": r["checklist_item_id"], "source_quote": r["source_quote"]}


def det(rows: list[dict]) -> None:
    changes, pointers, recs = [], [], []
    kinds_old = Counter()
    kinds_new = Counter()
    for r in rows:
        old, new = rk.classify(r), kq.classify_rules7(r)
        kinds_old[old["kind"]] += 1
        kinds_new[new["kind"]] += 1
        if old["kind"] != new["kind"]:
            changes.append({**row_id(r), "kind_old": old["kind"], "kind_new": new["kind"], "reason_old": old["kind_reasons"], "reason_new": new["kind_reasons"], "before_question": r.get("audit_question") or None})
        if old["kind"] == "pointer":
            pointers.append({**row_id(r), "kind": "pointer", "before_question": r.get("audit_question") or None, "flags": r.get("item_flags"), **kq.pointer_decision(r)})
        if old["kind"] == "recommendation":
            recs.append({**row_id(r), "kind": "recommendation", "before_question": r.get("audit_question") or None, **kq.recommendation_flag(r)})
    (OUT / "rules7_changes.json").write_text(json.dumps({"counts_old": kinds_old, "counts_new": kinds_new, "changes": changes}, indent=1, ensure_ascii=False))
    (OUT / "pointers.json").write_text(json.dumps(pointers, indent=1, ensure_ascii=False))
    (OUT / "recommendations.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False))
    print("rules-7 kind changes:", len(changes))
    for c in changes:
        print("  ", c["doc"], c["citation"], c["kind_old"], "->", c["kind_new"], "|", c["source_quote"][:90])
    print("pointers:", Counter(p["action"] for p in pointers), "| recommendations:", len(recs))


def call_model(prompt: str, ollama_url: str) -> str:
    import requests
    payload = {"model": aq.MODEL, "prompt": prompt, "stream": False, "format": kq.SCHEMA, "options": {"temperature": 0.1, "num_predict": 300, "num_ctx": aq.NUM_CTX}}
    r = requests.post(f"{ollama_url.rstrip('/')}/api/generate", json=payload, timeout=180)
    r.raise_for_status()
    return r.json()["response"]


def perm(rows: list[dict], rnd: int, prompt_name: str, only_failed_from: int | None) -> None:
    template = kq.PERMISSION_PROMPTS[prompt_name]
    todo = [r for r in rows if kq.classify_rules7(r)["kind"] == "permission"]  # the 3 rows rules-7 turns into duties are not permission rows any more
    prev = {}
    if isinstance(only_failed_from, str):  # a json list of checklist_item_ids to re-run
        ids = set(json.loads(Path(only_failed_from).read_text()))
        todo = [r for r in todo if r["checklist_item_id"] in ids]
    elif only_failed_from:
        prev = {x["checklist_item_id"]: x for x in json.loads((OUT / f"permission_round{only_failed_from}.json").read_text())}
        todo = [r for r in todo if prev[r["checklist_item_id"]]["failures"]]
    url = config.load().ollama_url
    results = []
    for i, r in enumerate(todo, 1):
        prompt = kq.build_permission_prompt(r, template)
        answer, err = {}, None
        for _ in range(2):
            try:
                answer = json.loads(call_model(prompt, url))
                err = None
                break
            except (ValueError, OSError) as e:
                err = str(e)
        q = aq.parse_answer(json.dumps({"question": answer.get("question")})) if answer else None
        limit = answer.get("limit") if answer else None
        limit = None if aq.no_question(limit) else limit
        fails = kq.check_question(q, r, limit) if q else []
        if q and limit is None:
            fails.append("C5_limit_not_verbatim")
        results.append({**row_id(r), "round": rnd, "prompt": prompt_name, "before_question": r.get("audit_question") or None, "grant": answer.get("grant"), "limit": limit,
                        "question": q, "why_null": answer.get("why_null"), "failures": fails, "error": err})
        print(i, len(todo), r["_doc"], r.get("citation"), "Q" if q else "null", fails, flush=True)
        time.sleep(0.2)
    (OUT / f"permission_round{rnd}.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    n_q = sum(1 for x in results if x["question"])
    print(f"round {rnd}: {len(results)} calls, {n_q} questions, {sum(1 for x in results if x['question'] and x['failures'])} failing, errors {sum(1 for x in results if x['error'])}")


if __name__ == "__main__":
    scratch = Path(sys.argv[1])
    rows = load_rows(scratch)
    if sys.argv[2] == "det":
        det(rows)
    else:
        perm(rows, int(sys.argv[3]), sys.argv[4], (int(sys.argv[5]) if sys.argv[5].isdigit() else sys.argv[5]) if len(sys.argv) > 5 else None)

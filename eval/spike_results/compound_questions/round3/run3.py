"""Round 3 runner (narrow variant).

  python3 run3.py select --set tune|fresh               # candidates + gate (no model call) -> outputs/candidates_<set>.json
  python3 run3.py ask    --set tune|fresh --version v1  # model calls for gate-eligible rows only -> outputs/answers_<version>_<set>.json
  python3 run3.py score  --set tune|fresh --version v1  # hard checks -> outputs/results_<version>_<set>.json, summary printed
  python3 run3.py review --set fresh --version v2       # blind review sheet (no machine-check results on it) -> outputs/review_sheet_fresh.md
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[3]))  # repo root, for core.config
import candidates as cand  # noqa: E402  (round 1 selector; unchanged)
import narrow  # noqa: E402
import prompts3  # noqa: E402

OUT = HERE / "outputs"
CHECKLIST_DIR = Path("/tmp/claude-1000/-home-coder/42bb61fb-ebf2-5717-b909-a59a0e80ffd7/scratchpad/cl")
SETS = {
    "tune": ["afi10-2402", "afi17-203", "dafman17-1305"],
    "fresh": ["CJCSI 6510.02G", "DODI 5200.01", "DODI 5200.44", "dafi36-2903"],
}
CAP = {"dafi36-2903": 40}  # candidates, seeded sample
SEED = "compound-split-round3-2026-10-14"


def _file(doc: str) -> Path:
    return CHECKLIST_DIR / (doc.replace(" ", "_") + ".json")


def _index(which: str) -> dict[str, dict]:
    idx = {}
    for doc in SETS[which]:
        for it in cand.load_items(_file(doc)):
            idx[it["checklist_item_id"]] = it
    return idx


def select(which: str) -> list[dict]:
    rows = []
    for doc in SETS[which]:
        items = cand.load_items(_file(doc))
        pool = []
        for it in items:
            q = it.get("audit_question") or ""
            ok, why = cand.is_candidate(q)
            if ok:
                pool.append({"doc": doc, "id": it["checklist_item_id"], "reason": why, "words": cand.word_count(q)})
        pool.sort(key=lambda r: r["id"])
        total = len(pool)
        if doc in CAP and total > CAP[doc]:
            pool = sorted(random.Random(f"{SEED}:{doc}").sample(pool, CAP[doc]), key=lambda r: r["id"])
        idx = {it["checklist_item_id"]: it for it in items}
        for r in pool:
            it = idx[r["id"]]
            ok, why = narrow.eligible(it["audit_question"], it.get("source_quote") or "")
            r["eligible"], r["gate"], r["pool_size"] = ok, why, total
        rows.extend(pool)
        print(f"{doc}: {len(items)} rows, {sum(1 for i in items if i.get('audit_question'))} with a question, {total} candidates, {len(pool)} used, "
              f"{sum(r['eligible'] for r in pool)} pass the gate")
    return rows


def ask(which: str, version: str) -> None:
    import requests
    from core import config
    url = config.load().ollama_url.rstrip("/")
    sel = json.loads((OUT / f"candidates_{which}.json").read_text())
    idx = _index(which)
    path = OUT / f"answers_{version}_{which}.json"
    answers = json.loads(path.read_text()) if path.exists() else {}
    pid = prompts3.prompt_id(version)
    n = 0
    for r in sel:
        if not r["eligible"]:
            continue
        key = r["id"]
        if key in answers and answers[key].get("prompt_id") == pid:
            continue
        item = idx[key]
        payload = {"model": prompts3.MODEL, "prompt": prompts3.build(version, item, item["audit_question"]), "stream": False, "format": prompts3.SCHEMA,
                   "options": {"temperature": 0.1, "num_predict": prompts3.NUM_PREDICT, "num_ctx": prompts3.NUM_CTX}}
        rec = {"prompt_id": pid, "raw": None, "error": None}
        for attempt in range(3):
            try:
                resp = requests.post(f"{url}/api/generate", json=payload, timeout=180)
                resp.raise_for_status()
                rec["raw"], rec["error"] = resp.json()["response"], None
                break
            except requests.RequestException as e:
                rec["error"] = f"model call failed: {e}"
                time.sleep(2 ** (attempt + 1))
        answers[key] = rec
        n += 1
        path.write_text(json.dumps(answers, indent=1))
    print(f"{n} new model calls; {len(answers)} answers in {path.name}")


def parse(raw):
    if raw is None:
        return "error", None, None, [], "no answer"
    try:
        d = json.loads(raw)
        if d["decision"] == "keep":
            return "keep", None, None, [], None
        lead = (d.get("lead") or "").strip()
        parts = [str(p).strip() for p in (d.get("parts") or [])]
        if d["decision"] != "split" or not lead:
            return "error", None, None, [], "malformed"
        return "split", d.get("kind"), lead, parts, None
    except (ValueError, KeyError, TypeError, AttributeError):
        return "error", None, None, [], "malformed"


def score(which: str, version: str) -> dict:
    sel = json.loads((OUT / f"candidates_{which}.json").read_text())
    idx = _index(which)
    answers = json.loads((OUT / f"answers_{version}_{which}.json").read_text())
    rows = []
    for r in sel:
        it = idx[r["id"]]
        today, quote = it["audit_question"], it.get("source_quote") or ""
        rec = {"doc": r["doc"], "id": r["id"], "citation": it.get("citation") or it.get("source_ref") or "", "source_quote": quote, "today": today, "eligible": r["eligible"],
               "gate": r["gate"], "decision": "keep", "kind": None, "lead": None, "parts": [], "checks": {}, "failed": [], "final": "today", "ended": "kept by the gate" if not r["eligible"] else ""}
        if r["eligible"]:
            a = answers.get(r["id"], {})
            decision, kind, lead, parts, err = parse(a.get("raw"))
            if a.get("error"):
                decision, err = "error", a["error"]
            rec.update(decision=decision, kind=kind, lead=lead, parts=parts)
            if decision == "keep":
                rec["ended"] = "model said keep"
            elif decision == "error":
                rec["ended"] = "model error: " + str(err)
            else:
                res = narrow.evaluate(today, quote, kind, lead, parts)
                rec["checks"], rec["failed"] = res, narrow.failed(res)
                rec["raw_hedge_violation"] = bool(res["hedge"])
                if not rec["failed"]:
                    rec["final"], rec["ended"] = "split", "split passed all checks"
                else:
                    rec["ended"] = "split failed: " + ", ".join(rec["failed"])
        rows.append(rec)
    summ = summarize(rows)
    (OUT / f"results_{version}_{which}.json").write_text(json.dumps({"summary": summ, "rows": rows}, indent=1, ensure_ascii=False))
    return summ


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    elig = [r for r in rows if r["eligible"]]
    proposed = [r for r in rows if r["decision"] == "split"]
    passed = [r for r in proposed if r["final"] == "split"]
    by = {}
    for r in proposed:
        for c in r["failed"]:
            by[c] = by.get(c, 0) + 1
    return {
        "candidates": n,
        "kept_by_gate_without_model_call": n - len(elig),
        "sent_to_model": len(elig),
        "model_keep": sum(r["decision"] == "keep" for r in elig),
        "model_errors": sum(r["decision"] == "error" for r in elig),
        "split_proposed": len(proposed),
        "split_passed_all_checks": len(passed),
        "split_pass_rate": round(len(passed) / len(proposed), 3) if proposed else None,
        "fallback_by_check": dict(sorted(by.items())),
        "rule1_violations_kind_not_verbs_or_objects": sum(r["kind"] not in ("verbs", "objects") for r in proposed),
        "hedge_words_in_raw_model_output": sum(bool(r.get("raw_hedge_violation")) for r in proposed),
        "hedge_words_in_passing_splits": sum(bool(r["checks"].get("hedge")) for r in passed),
        "rows_in": n,
        "rows_out": n,
        "rows_dropped": 0,
        "keep_rate_all_candidates": round((n - len(passed)) / n, 3) if n else None,
        "split_share_of_all_candidates": round(len(passed) / n, 3) if n else None,
    }


def review(which: str, version: str) -> None:
    res = json.loads((OUT / f"results_{version}_{which}.json").read_text())
    changed = [r for r in res["rows"] if r["final"] == "split"]
    R = ["# Review sheet: split audit questions, round 3 (blind)\n",
         "Reviewer: you did not write these and have not seen any machine checks. For each row, read the source quote, then today's question, then the proposal.\n",
         "Grade two things. Leave notes if unsure.\n",
         "- **Faithful**: does the proposal ask for exactly what the source quote requires? `Y` = yes, nothing dropped, added or made stronger or weaker (may/should/must, conditions, numbers, who acts). "
         "`N` = something is dropped, added, hedged or changed. `?` = cannot tell.",
         "- **Easier**: would an auditor find it easier to check than today's single question? `Y` / `N` / `same`.",
         "- An invented 'as appropriate' / 'as required' counts as N for Faithful. A part that is only filler counts as N for Easier.\n"]
    for i, r in enumerate(changed, 1):
        R += [f"## {i}. {r['doc']} {r['citation']}\n", f"**Source quote:** {' '.join(r['source_quote'].split())}\n", f"**Today's question:** {r['today']}\n", f"**Proposed lead:** {r['lead']}\n"]
        R += [f"- {chr(97 + k)}) {p}" for k, p in enumerate(r["parts"])]
        R.append("\nFaithful (Y/N/?): ____    Easier (Y/N/same): ____    Notes: ____________________\n")
    (OUT / f"review_sheet_{which}.md").write_text("\n".join(R) + "\n", encoding="utf-8")
    print(len(changed), "rows on the review sheet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["select", "ask", "score", "review"])
    ap.add_argument("--set", dest="which", choices=list(SETS), required=True)
    ap.add_argument("--version", default="v1")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if a.cmd == "select":
        (OUT / f"candidates_{a.which}.json").write_text(json.dumps(select(a.which), indent=1))
    elif a.cmd == "ask":
        ask(a.which, a.version)
    elif a.cmd == "score":
        print(json.dumps(score(a.which, a.version), indent=1))
    else:
        review(a.which, a.version)


if __name__ == "__main__":
    main()

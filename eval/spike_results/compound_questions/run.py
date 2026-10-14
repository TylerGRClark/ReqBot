"""Compound-question split spike runner.

  python3 run.py select  --set tune|test              # build the candidate sample (no model call); writes outputs/candidates_<set>.json
  python3 run.py ask     --set tune|test --version v1 # model calls (cached by prompt id + row id); writes outputs/answers_<version>_<set>.json
  python3 run.py score   --set tune|test --version v1 # applies the mechanical checks, writes outputs/results_<version>_<set>.json and prints the summary

Checklists are built beforehand with `python3 cli/reqbot.py checklist --doc DOC --format json --output <dir>/<DOC with spaces as _>.json` (no model call).
Nothing under services/ or pipeline/ is touched; today's questions are never changed, only proposed splits are recorded.
"""
import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import candidates as cand  # noqa: E402
import checks  # noqa: E402
import prompts  # noqa: E402

OUT = HERE / "outputs"
CHECKLIST_DIR = Path("/tmp/claude-1000/-home-coder/42bb61fb-ebf2-5717-b909-a59a0e80ffd7/scratchpad/cl")
SETS = {
    "tune": ["afi10-2402", "afi17-203", "dafman17-1305"],
    "test": ["afi13-550", "afman17-2101", "afpd_17-1", "DODI 5200.48", "DODI 8551.01"],
}
CAP_PER_DOC = 40
SEED = "compound-split-2026-10-14"


def _doc_file(doc: str) -> Path:
    return CHECKLIST_DIR / (doc.replace(" ", "_") + ".json")


def select(which: str) -> list[dict]:
    rows = []
    for doc in SETS[which]:
        items = cand.load_items(_doc_file(doc))
        pool = []
        for it in items:
            q = it.get("audit_question") or ""
            ok, why = cand.is_candidate(q)
            if ok:
                pool.append({"doc": doc, "id": it["checklist_item_id"], "reason": why, "words": cand.word_count(q)})
        pool.sort(key=lambda r: r["id"])
        total = len(pool)
        picked = random.Random(f"{SEED}:{doc}").sample(pool, min(CAP_PER_DOC, total))
        picked.sort(key=lambda r: r["id"])
        for r in picked:
            r["pool_size"] = total
        rows.extend(picked)
        print(f"{doc}: {len(items)} rows, {sum(1 for i in items if i.get('audit_question'))} with a question, {total} candidates, {len(picked)} sampled")
    return rows


def _row_index(which: str) -> dict[str, dict]:
    idx = {}
    for doc in SETS[which]:
        for it in cand.load_items(_doc_file(doc)):
            idx[it["checklist_item_id"]] = it
    return idx


def ask(which: str, version: str) -> None:
    import requests
    from core import config
    sys.path.insert(0, str(HERE.parents[2]))
    url = config.load().ollama_url.rstrip("/")
    sel = json.loads((OUT / f"candidates_{which}.json").read_text())
    idx = _row_index(which)
    path = OUT / f"answers_{version}_{which}.json"
    answers = json.loads(path.read_text()) if path.exists() else {}
    pid = prompts.prompt_id(version)
    n = 0
    for r in sel:
        key = r["id"]
        if key in answers and answers[key].get("prompt_id") == pid:
            continue
        item = idx[key]
        prompt = prompts.build(version, item, item["audit_question"])
        payload = {"model": prompts.MODEL, "prompt": prompt, "stream": False, "format": prompts.SCHEMA,
                   "options": {"temperature": 0.1, "num_predict": prompts.NUM_PREDICT, "num_ctx": prompts.NUM_CTX}}
        rec = {"prompt_id": pid, "raw": None, "error": None}
        for attempt in range(3):
            try:
                resp = requests.post(f"{url}/api/generate", json=payload, timeout=180)
                resp.raise_for_status()
                rec["raw"] = resp.json()["response"]
                rec["error"] = None
                break
            except requests.RequestException as e:
                rec["error"] = f"model call failed: {e}"
                time.sleep(2 ** (attempt + 1))
        answers[key] = rec
        n += 1
        if n % 10 == 0:
            path.write_text(json.dumps(answers, indent=1))
            print(f"  {n} calls", flush=True)
    path.write_text(json.dumps(answers, indent=1))
    print(f"{n} new model calls; {len(answers)} answers saved to {path.name}")


def parse(raw: str | None) -> tuple[str, str | None, list[str], str | None]:
    """(decision, lead, parts, error)."""
    if raw is None:
        return "error", None, [], "no answer"
    try:
        d = json.loads(raw)
        decision = d["decision"]
        if decision == "keep":
            return "keep", None, [], None
        lead = (d.get("lead") or "").strip()
        parts = [str(p).strip() for p in (d.get("parts") or [])]
        if decision != "split" or not lead:
            return "error", None, [], "malformed"
        return "split", lead, parts, None
    except (ValueError, KeyError, TypeError, AttributeError):
        return "error", None, [], "malformed"


def percentile(values: list[float], p: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def score(which: str, version: str) -> dict:
    sel = json.loads((OUT / f"candidates_{which}.json").read_text())
    idx = _row_index(which)
    answers = json.loads((OUT / f"answers_{version}_{which}.json").read_text())
    rows = []
    for r in sel:
        item = idx[r["id"]]
        today = item["audit_question"]
        decision, lead, parts, err = parse(answers.get(r["id"], {}).get("raw"))
        if answers.get(r["id"], {}).get("error"):
            decision, err = "error", answers[r["id"]]["error"]
        rec = {"doc": r["doc"], "id": r["id"], "citation": item.get("citation") or item.get("source_ref") or "", "reason": r["reason"], "source_quote": item.get("source_quote"),
               "today": today, "decision": decision, "lead": lead, "parts": parts, "error": err, "checks": {}, "failed": [], "final": "today", "today_words": cand.word_count(today)}
        if decision == "split":
            res = checks.evaluate(today, item, lead, parts)
            rec["checks"] = res
            rec["failed"] = checks.failed(res)
            if not rec["failed"]:
                rec["final"] = "split"
        rec["longest_after"] = (max(cand.word_count(p) for p in [lead] + parts) if rec["final"] == "split" else rec["today_words"])
        rows.append(rec)
    summ = summarize(rows)
    (OUT / f"results_{version}_{which}.json").write_text(json.dumps({"summary": summ, "rows": rows}, indent=1, ensure_ascii=False))
    return summ


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    splits = [r for r in rows if r["decision"] == "split"]
    passed = [r for r in splits if r["final"] == "split"]
    reasons: dict[str, int] = {}
    for r in splits:
        for c in r["failed"]:
            reasons[c] = reasons.get(c, 0) + 1
    before = [r["today_words"] for r in rows]
    after = [r["longest_after"] for r in rows]
    bs = [r["today_words"] for r in passed]
    as_ = [r["longest_after"] for r in passed]
    return {
        "candidates": n,
        "keep": sum(r["decision"] == "keep" for r in rows),
        "split_proposed": len(splits),
        "model_errors": sum(r["decision"] == "error" for r in rows),
        "split_passed_all_checks": len(passed),
        "split_pass_rate": round(len(passed) / len(splits), 3) if splits else None,
        "fallback_rows": len(splits) - len(passed),
        "fallback_by_check": dict(sorted(reasons.items())),
        "only_one_check_failed": sum(len(r["failed"]) == 1 for r in splits if r["failed"]),
        "rows_out": n,
        "rows_dropped": 0,  # every candidate row keeps today's question or its split; nothing is removed
        "all_candidates_longest_piece_median_before": statistics.median(before) if before else None,
        "all_candidates_longest_piece_median_after": statistics.median(after) if after else None,
        "all_candidates_longest_piece_p90_before": round(percentile(before, 0.9), 1),
        "all_candidates_longest_piece_p90_after": round(percentile(after, 0.9), 1),
        "changed_rows_median_before": statistics.median(bs) if bs else None,
        "changed_rows_median_after": statistics.median(as_) if as_ else None,
        "changed_rows_p90_before": round(percentile(bs, 0.9), 1),
        "changed_rows_p90_after": round(percentile(as_, 0.9), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["select", "ask", "score"])
    ap.add_argument("--set", dest="which", choices=list(SETS), required=True)
    ap.add_argument("--version", default="v1")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if a.cmd == "select":
        rows = select(a.which)
        (OUT / f"candidates_{a.which}.json").write_text(json.dumps(rows, indent=1))
    elif a.cmd == "ask":
        ask(a.which, a.version)
    else:
        print(json.dumps(score(a.which, a.version), indent=1))


if __name__ == "__main__":
    main()

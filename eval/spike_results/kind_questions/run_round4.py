"""Round 4 runner.
  python3 run_round4.py <scratch_afi> <scratch_held_out> partA     # 12 model calls on the part A rows (prompt v7), then decide()
  python3 run_round4.py <scratch_afi> <scratch_held_out> partB     # frozen rules on the seven held-out documents; serial; stops at the call cap
Outputs: outputs/round4_partA.json, outputs/round4_partB_rows.json, outputs/round4_partB_summary.json. Nothing under services/ and nothing live is written.
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import held_out  # noqa: E402
import kind_questions as kq  # noqa: E402
import round3_checks as r3  # noqa: E402
import round4_checks as r4  # noqa: E402
from build_rows import load_rows  # noqa: E402
from core import config  # noqa: E402
from part_a import PART_A  # noqa: E402
from services import audit_questions as aq  # noqa: E402
from services import requirement_kind as rk  # noqa: E402

OUT = HERE / "outputs"
CALL_CAP = 150


def ask(item: dict, url: str) -> dict:
    import requests
    prompt = r4.build_prompt_v7(item)
    payload = {"model": aq.MODEL, "prompt": prompt, "stream": False, "format": kq.SCHEMA, "options": {"temperature": 0.1, "num_predict": 300, "num_ctx": aq.NUM_CTX}}
    for _ in range(2):
        try:
            r = requests.post(f"{url.rstrip('/')}/api/generate", json=payload, timeout=180)
            r.raise_for_status()
            return json.loads(r.json()["response"])
        except (ValueError, OSError):
            time.sleep(2)
    return {}


def part_a(afi_rows: list[dict]) -> None:
    url = config.load().ollama_url
    r3rows = {x["checklist_item_id"]: x for x in json.loads((OUT / "round3_rows.json").read_text())}
    out = []
    for doc, cit, start in PART_A:
        item = next(r for r in afi_rows if r["_doc"] == doc and (r.get("citation") or "") == cit and r["source_quote"].startswith(start) and r["checklist_item_id"] not in {o["checklist_item_id"] for o in out})
        ans = ask(item, url)
        live = item.get("audit_question") or None
        d = r4.decide(item, ans, live)
        prev = r3rows.get(item["checklist_item_id"], {})
        out.append({"doc": doc, "citation": cit, "checklist_item_id": item["checklist_item_id"], "source_quote": item["source_quote"], "antecedent": r4.antecedent(item), "live_question": live,
                    "round3_question": prev.get("final_question"), "model_answer": ans, **d, "coverage_new": r4.coverage(d["question"], item) if d["question"] else None,
                    "coverage_live": r4.coverage(live, item) if live else None})
        print(doc, cit, "|", d["question"] or "NULL", "|", d["rule"], flush=True)
    qs = Counter(o["question"] for o in out if o["question"])
    for o in out:
        o["identical_to_another_row"] = bool(o["question"] and qs[o["question"]] > 1)
    (OUT / "round4_partA.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("calls:", len(out))


def part_b(rows: list[dict]) -> None:
    url = config.load().ollama_url
    calls = 0
    out = []
    for r in rows:
        live = r.get("audit_question") or None
        k_live, k_new = rk.classify(r), kq.classify_wrapper(r)
        e = {"doc": r["_doc"], "citation": r.get("citation"), "checklist_item_id": r["checklist_item_id"], "source_quote": r["source_quote"], "kind_live": k_live["kind"], "kind_wrapper": k_new["kind"],
             "live_question": live, "final_question": live, "flag": None, "rule": None, "model_called": False, "model_question_rejected": False, "missing_qualifiers": [], "notes": []}
        if k_new["kind"] == "permission":
            if calls >= CALL_CAP:
                e["rule"] = "NOT RUN: call cap reached"
                out.append(e)
                continue
            ans = ask(r, url)
            calls += 1
            d = r4.decide(r, ans, live)
            e.update({"final_question": d["question"], "rule": "permission (" + d["rule"] + ")", "limit": d["limit"], "why_null": d["why_null"], "model_called": True,
                      "model_question_rejected": d["model_question_rejected"], "notes": d["notes"], "model_question_raw": ans.get("question"), "antecedent": r4.antecedent(r)})
            if d["question"] and d["question"] != live:
                e["missing_qualifiers"] = r3.missing_qualifiers(d["question"], r["source_quote"]) + r4.dropped_for_any(d["question"], r["source_quote"])
            print(calls, r["_doc"], r.get("citation"), "|", d["question"] or "NULL", flush=True)
        elif k_new["kind"] == "recommendation":
            f = kq.recommendation_flag(r)
            e.update({"flag": f["strength"], "rule": "recommendation (flag only)"})
        elif k_live["kind"] == "recommendation":
            e.update({"rule": "recommendation flag removed (should inside an if-clause)", "flag": None})
        elif k_live["kind"] == "pointer":
            p = kq.pointer_decision(r)
            e.update({"rule": "pointer (" + p["action"] + ": " + p["reason"] + ")", "final_question": None if p["action"] == "suppress" else live})
        out.append(e)
    (OUT / "round4_partB_rows.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    per_doc = {}
    for d in held_out.HELD_OUT:
        es = [e for e in out if e["doc"] == d]
        perm = [e for e in es if e["model_called"]]
        per_doc[d] = {
            "rows": len(es), "kinds": dict(Counter(e["kind_wrapper"] for e in es if e["kind_wrapper"] in ("permission", "recommendation", "pointer"))),
            "model_calls": len(perm), "new_boundary_questions": sum(1 for e in perm if e["final_question"] and e["final_question"] != e["live_question"] and e["rule"].startswith("permission (new boundary")),
            "null_after": sum(1 for e in perm if not e["final_question"]), "todays_question_kept": sum(1 for e in perm if e["final_question"] and e["final_question"] == e["live_question"]),
            "model_questions_rejected_by_checks": sum(1 for e in perm if e["model_question_rejected"]),
            "model_gave_question": sum(1 for e in perm if e.get("model_question_raw")),
            "pointer_suppressed": sum(1 for e in es if (e["rule"] or "").startswith("pointer (suppress")), "pointer_kept": sum(1 for e in es if (e["rule"] or "").startswith("pointer (keep")),
            "recommended_labels": sum(1 for e in es if e["flag"]), "rows_differ_from_live": sum(1 for e in es if e["final_question"] != e["live_question"] or e["flag"] or e["kind_live"] != e["kind_wrapper"])}
    summary = {"rows": len(out), "rows_dropped": 0, "model_calls": calls, "per_doc": per_doc,
               "check_rejection_rate": {"model_questions": sum(v["model_gave_question"] for v in per_doc.values()), "rejected": sum(v["model_questions_rejected_by_checks"] for v in per_doc.values())},
               "new_questions_missing_qualifier": [f"{e['doc']} {e['citation']}" for e in out if e["missing_qualifiers"]]}
    (OUT / "round4_partB_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    which = sys.argv[3]
    if which == "partA":
        part_a(load_rows(Path(sys.argv[1])))
    else:
        part_b(held_out.load_rows(Path(sys.argv[2])))

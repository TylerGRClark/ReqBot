"""Round 5 runner.
  python3 run_round5.py <scratch_dir> regress     # the seven documents of round 4 (no longer a clean test)
  python3 run_round5.py <scratch_dir> fresh       # dafi36-2903, permission / recommendation / pointer rows only
Outputs: outputs/round5_<mode>_rows.json and outputs/round5_<mode>_summary.json. Nothing under services/ and nothing live is written.
"""
import hashlib
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
import round5_checks as r5  # noqa: E402
from core import config  # noqa: E402
from services import audit_questions as aq  # noqa: E402
from services import requirement_kind as rk  # noqa: E402

OUT = HERE / "outputs"
CALL_CAP = 150
FRESH = "dafi36-2903"


def ask(item: dict, url: str, hint: str | None = None) -> dict:
    import requests
    prompt = r5.build_prompt_v8(item) + (("\n\nNote on your previous answer: " + hint) if hint else "")
    payload = {"model": aq.MODEL, "prompt": prompt, "stream": False, "format": kq.SCHEMA, "options": {"temperature": 0.1, "num_predict": 300, "num_ctx": aq.NUM_CTX}}
    for _ in range(2):
        try:
            r = requests.post(f"{url.rstrip('/')}/api/generate", json=payload, timeout=180)
            r.raise_for_status()
            return json.loads(r.json()["response"])
        except (ValueError, OSError):
            time.sleep(2)
    return {}


def repair_hint(item: dict, d: dict) -> str | None:
    reasons = " ".join(d.get("notes") or [])
    bound = r4.numeric_bound(item.get("source_quote") or "")
    if "model question rejected: question drops" in reasons:
        why = reasons.split("model question rejected: ", 1)[1]
        return f"Your question was rejected because {why}. Write it again keeping that, with every qualifier of the permission."
    if not d.get("model_gave_question") and bound:
        return f"The sentence states a numeric bound ({bound!r}). That is a limit: ask whether it was respected."
    return None


def process(rows: list[dict], docs: list[str], max_calls: int, sample_n: int | None, all_rows: list[dict] | None = None) -> tuple[list[dict], dict]:
    url = config.load().ollama_url
    base = all_rows if all_rows is not None else rows  # the document gate is computed on every row of the document
    kinds = {d: Counter(kq.classify_wrapper(r)["kind"] for r in base if r["_doc"] == d) for d in docs}
    n_rows = {d: sum(1 for r in base if r["_doc"] == d) for d in docs}
    gate = {d: r5.document_gate(kinds[d], n_rows[d]) for d in docs}
    # rows to ask: gate-passing permission rows of documents the document gate allows
    asked_ids = []
    for r in rows:
        if kq.classify_wrapper(r)["kind"] == "permission" and gate[r["_doc"]][0] and r5.main_verb_gate(r)[0]:
            asked_ids.append(r["checklist_item_id"])
    not_sampled = set()
    if sample_n is not None and len(asked_ids) > sample_n:
        keep = set(sorted(asked_ids, key=lambda i: hashlib.sha1(i.encode()).hexdigest())[:sample_n])
        not_sampled = set(asked_ids) - keep
        asked_ids = [i for i in asked_ids if i in keep]
    asked = set(asked_ids)
    out, calls = [], 0
    for r in rows:
        live = r.get("audit_question") or None
        k_live, k_new = rk.classify(r), kq.classify_wrapper(r)
        e = {"doc": r["_doc"], "citation": r.get("citation"), "checklist_item_id": r["checklist_item_id"], "source_quote": r["source_quote"], "kind_live": k_live["kind"], "kind_wrapper": k_new["kind"],
             "live_question": live, "final_question": live, "action": None, "flag": None, "rule": None, "model_called": False, "model_gave_question": False, "model_question_rejected": False,
             "missing_qualifiers": [], "notes": []}
        cid = r["checklist_item_id"]
        if k_new["kind"] == "permission":
            ok_doc, share = gate[r["_doc"]]
            ok_main, why_main = r5.main_verb_gate(r)
            if not ok_doc:
                e.update({"action": "doc_gated", "rule": f"permission path off for this document (permission + recommendation rows are {share:.0%} of its rows)"})
            elif not ok_main:
                e.update({"action": "main_verb_gate", "rule": "permission path not applied: " + why_main})
            elif cid in not_sampled:
                e.update({"action": "not_sampled", "rule": "gate passed; not asked (call budget; today's question kept)"})
            elif cid in asked and calls < max_calls:
                ans = ask(r, url)
                calls += 1
                d = r5.decide5(r, ans, live)
                hint = repair_hint(r, d)
                if hint and calls < max_calls:
                    ans = ask(r, url, hint)
                    calls += 1
                    d = r5.decide5(r, ans, live)
                    e["retried"] = True
                e.update({"final_question": d["question"], "action": d["action"], "rule": d["rule"], "limit": d["limit"], "why_null": d["why_null"], "model_called": True,
                          "model_gave_question": d["model_gave_question"], "model_question_rejected": d["model_question_rejected"], "notes": d["notes"], "model_question_raw": ans.get("question"),
                          "antecedent": r4.antecedent(r)})
                if d["action"] in ("added", "replaced") and d["question"]:
                    e["missing_qualifiers"] = r3.missing_qualifiers(d["question"], r["source_quote"]) + r4.dropped_for_any(d["question"], r["source_quote"])
                    e["may_to_duty"] = r5.may_to_duty(d["question"], r["source_quote"])
                    e["bare_scope"] = r4.bare_pronoun_scope(d["question"])
                print(calls, r["_doc"], r.get("citation"), d["action"], "|", (d["question"] or "-")[:110], flush=True)
            else:
                e.update({"action": "not_run", "rule": "call cap reached"})
        elif k_new["kind"] == "recommendation":
            e.update({"flag": kq.recommendation_flag(r)["strength"], "rule": "recommendation (flag only)", "action": "label"})
        elif k_live["kind"] == "recommendation":
            e.update({"rule": "recommendation flag removed (should inside an if-clause)", "action": "label_removed"})
        elif k_live["kind"] == "pointer":
            p = kq.pointer_decision(r)
            e.update({"rule": "pointer (" + p["action"] + ": " + p["reason"] + ")", "action": "pointer_" + p["action"], "final_question": None if p["action"] == "suppress" else live})
        out.append(e)
    perm = [e for e in out if e["model_called"]]
    summary = {"rows": len(out), "rows_dropped": 0, "model_calls": calls, "asked": len(asked), "not_sampled": len(not_sampled), "documents": {}}
    for d in docs:
        es = [e for e in out if e["doc"] == d]
        summary["documents"][d] = {
            "rows_processed": len(es), "rows_in_document": n_rows[d], "kinds_all": dict(kinds[d]), "permission_plus_recommendation_share": round(gate[d][1], 3), "document_gate_allows_permission_path": gate[d][0],
            "permission_rows": sum(1 for e in es if e["kind_wrapper"] == "permission"),
            "gated_out_main_verb": sum(1 for e in es if e["action"] == "main_verb_gate"), "doc_gated": sum(1 for e in es if e["action"] == "doc_gated"),
            "not_sampled": sum(1 for e in es if e["action"] == "not_sampled"), "model_calls": sum(1 for e in es if e["model_called"]),
            "added": sum(1 for e in es if e["action"] == "added"), "replaced": sum(1 for e in es if e["action"] == "replaced"),
            "kept_live": sum(1 for e in es if e["action"] == "kept_live"), "no_question": sum(1 for e in es if e["action"] == "none"),
            "removed_capability_or_invented": sum(1 for e in es if e["action"] == "removed_capability"),
            "pointer_suppressed": sum(1 for e in es if e["action"] == "pointer_suppress"), "labels": sum(1 for e in es if e["action"] == "label"),
            "model_gave_question": sum(1 for e in es if e["model_gave_question"]), "model_questions_rejected": sum(1 for e in es if e["model_question_rejected"]),
            "rows_differ_from_live": sum(1 for e in es if e["final_question"] != e["live_question"] or e["flag"] or e["kind_live"] != e["kind_wrapper"])}
    summary["check_rejection_rate"] = {"model_questions": sum(1 for e in perm if e["model_gave_question"]), "rejected": sum(1 for e in perm if e["model_question_rejected"])}
    summary["violations"] = {"missing_qualifier": [f"{e['doc']} {e['citation']}" for e in out if e["missing_qualifiers"]],
                             "may_to_duty": [f"{e['doc']} {e['citation']}" for e in out if e.get("may_to_duty")], "bare_scope": [f"{e['doc']} {e['citation']}" for e in out if e.get("bare_scope")]}
    summary["removals"] = [{"row": f"{e['doc']} {e['citation']}", "live": e["live_question"], "rule": e["rule"]} for e in out if e["action"] == "removed_capability"]
    return out, summary


if __name__ == "__main__":
    scratch, mode = Path(sys.argv[1]), sys.argv[2]
    if mode == "regress":
        docs = held_out.HELD_OUT
        rows = held_out.load_rows(scratch, docs)
        out, summary = process(rows, docs, CALL_CAP, None)
    else:
        docs = [FRESH]
        every = held_out.load_rows(scratch, docs)
        rows = [r for r in every if kq.classify_wrapper(r)["kind"] in ("permission", "recommendation", "pointer") or rk.classify(r)["kind"] in ("recommendation", "pointer")]
        budget = CALL_CAP - json.loads((OUT / "round5_regress_summary.json").read_text())["model_calls"]
        # retries can use extra calls: sample at 80% of the remaining budget
        out, summary = process(rows, docs, budget, int(budget * 0.8), every)
    (OUT / f"round5_{mode}_rows.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (OUT / f"round5_{mode}_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k != "documents"}, indent=1, ensure_ascii=False))

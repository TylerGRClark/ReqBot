#!/usr/bin/env python3
"""PREREG10 metrics: the PREREG9 scoring (PREREG8 scorer `label_ctx_metrics`, unchanged, plus the CNSSI gold file) for arms control and heading over the eleven sealed documents,
or with --secondary over the three report-only ones. Per-document and pooled recall/precision, requirement flips with the gold verdict, label agreement. Read only, no model.

    python3 eval/clause_labeling/heading_metrics.py [--json OUT] [--flips FILE] [--secondary]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import label_ctx_metrics as M  # noqa: E402

RUN = Path.home() / "reqbot-work/scratch/heading_lead/run"
DOCS = ["afi17-203", "afi13-550", "DODI 5200.01", "afi17-101", "afman17-204", "DODI 5200.48", "DODI 8551.01", "dafman17-1301", "dafman17-1203", "NIST.SP.800-125", "CNSSI_No1253"]
SECONDARY = ["DODI 8410.03", "CJCSI 6510.02G", "DODI 5200.44"]
NR = M.NR


def gold_all():
    silver, gold = M.silver_sets(), M.gold_sets()
    g = M.SCRATCH / "gold2_cnssi"
    both = json.load(open(g / "gold_both_cnssi.json", encoding="utf-8"))
    for u in M._jsonl(g / "units_gold2_cnssi.jsonl"):
        gold.setdefault(u["document"], (u["split"], []))[1].append((u["text"], both.get(u["unit_id"], [])))
    return silver, gold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--flips")
    ap.add_argument("--secondary", action="store_true")
    a = ap.parse_args()
    docs, root = (SECONDARY, RUN / "secondary") if a.secondary else (DOCS, RUN)
    silver, gold = gold_all()
    arms = {arm: {d: json.load(open(root / arm / f"{d}.json", encoding="utf-8")) for d in docs} for arm in ("control", "heading")}
    out = {}
    subsets = {"pooled": docs, **({} if a.secondary else {"pooled_no_cnssi": [d for d in docs if d != "CNSSI_No1253"]}), **{d: [d] for d in docs}}
    for name, ds in subsets.items():
        row = {}
        for arm, res in arms.items():
            s = M.score({d: res[d] for d in ds if (silver.get(d) or gold.get(d))}, silver, gold)
            s["rows"] = sum(1 for d in ds for v in res[d]["labels"].values() if v != NR)
            s["clauses"] = sum(res[d]["clauses"] for d in ds)
            s["seconds"] = sum(res[d]["seconds"] for d in ds)
            s["bad_batches"] = sum(res[d]["unparsed"] + res[d]["failed"] for d in ds)
            row[arm] = s
        out[name] = row
    flips, changed, judged = [], collections.Counter(), collections.defaultdict(collections.Counter)
    for doc in docs:
        units = M.units_of(doc, silver, gold) if (silver.get(doc) or gold.get(doc)) else []
        nu = [(M.squash(t), reqs) for t, reqs in units]
        for m in arms["control"][doc]["clauses_meta"]:
            if (m["ctx_control"] or "").strip() == (m["ctx_heading"] or "").strip():
                continue
            changed[doc] += 1
            lc, lh = arms["control"][doc]["labels"].get(m["key"], NR), arms["heading"][doc]["labels"].get(m["key"], NR)
            if (lc == NR) == (lh == NR):
                continue
            sq = M.squash(m["text"])
            inside = [reqs for nt, reqs in nu if sq and sq in nt]
            hit = any(M.match(r, m["text"]) for reqs in inside for r in reqs) if inside else None
            verdict = None
            if inside:
                verdict = ("correct" if hit else "wrong") if lh != NR else ("wrong" if hit else "correct")
                judged[doc][verdict] += 1
            flips.append({"doc": doc, "key": m["key"], "control": lc, "heading": lh, "in_gold_unit": bool(inside), "verdict": verdict,
                          "ctx_control": m["ctx_control"], "ctx_heading": m["ctx_heading"], "clause": m["text"]})
    out["_flips"] = {"changed_context": dict(changed), "changed_total": sum(changed.values()), "n_flips": len(flips), "judged_by_doc": {k: dict(v) for k, v in judged.items()},
                     "judged_pooled": dict(sum(judged.values(), collections.Counter()))}
    n = same = nc = sc = 0
    for d in docs:
        for k, lab in arms["control"][d]["labels"].items():
            if k in arms["heading"][d]["labels"]:
                n += 1
                same += lab == arms["heading"][d]["labels"][k]
    for d in docs:
        for m in arms["control"][d]["clauses_meta"]:
            if (m["ctx_control"] or "").strip() != (m["ctx_heading"] or "").strip():
                nc += 1
                sc += arms["control"][d]["labels"].get(m["key"]) == arms["heading"][d]["labels"].get(m["key"])
    out["_agree"] = {"all": {"n": n, "same": same}, "changed_context_only": {"n": nc, "same": sc}}
    if a.flips:
        Path(a.flips).write_text(json.dumps(flips, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for name in subsets:
        c, h = out[name]["control"], out[name]["heading"]
        if c["recall"] is None:
            print(f"{name}: no gold | rows control {c['rows']} heading {h['rows']} | secs {c['seconds']:.0f}/{h['seconds']:.0f} bad batches {c['bad_batches']}/{h['bad_batches']}")
            continue
        print(f"{name}: gold reqs {c['labeled']} | control R {c['recall']:.2f} P {c['precision']:.2f} rows {c['rows']} | heading R {h['recall']:.2f} P {h['precision']:.2f} rows {h['rows']} | "
              f"dR {h['recall']-c['recall']:+.2f} dP {h['precision']-c['precision']:+.2f} | secs {c['seconds']:.0f}/{h['seconds']:.0f} bad batches {c['bad_batches']}/{h['bad_batches']}")
    print("flips", out["_flips"], "agree", out["_agree"])
    for f in flips:
        print(f"[{f['doc']}] {f['control']} -> {f['heading']} gold={f['verdict']}\n  old: {(f['ctx_control'] or '-')[:110]}\n  new: {(f['ctx_heading'] or '-')[:110]}\n  clause: {f['clause'][:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

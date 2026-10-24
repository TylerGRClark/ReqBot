#!/usr/bin/env python3
"""PREREG9 metrics: reuses the PREREG8 scorer (label_ctx_metrics) unchanged; adds the CNSSI gold file, per-document and pooled pass rule, flips, and the number-start count.

    python3 eval/clause_labeling/confirm_metrics.py [--json OUT] [--flips FILE]
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import label_ctx_metrics as M  # noqa: E402

OUT = Path.home() / "reqbot-work/scratch/label_ctx9"
DOCS = ["dafman17-1301", "dafman17-1203", "NIST.SP.800-125", "CNSSI_No1253"]
NR = M.NR


def gold_all():
    silver, gold = M.silver_sets(), M.gold_sets()
    g = M.SCRATCH / "gold2_cnssi"
    both = json.load(open(g / "gold_both_cnssi.json", encoding="utf-8"))
    for u in M._jsonl(g / "units_gold2_cnssi.jsonl"):
        gold.setdefault(u["document"], (u["split"], []))[1].append((u["text"], both.get(u["unit_id"], [])))
    return silver, gold


def load(arm):
    return {d: json.load(open(OUT / arm / f"{d}.json", encoding="utf-8")) for d in DOCS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--flips")
    a = ap.parse_args()
    silver, gold = gold_all()
    ctrl, rule = load("control"), load("rule")
    out = {}
    subsets = {"pooled4": DOCS, "pooled_no_cnssi": DOCS[:3], **{d: [d] for d in DOCS}}
    for name, ds in subsets.items():
        row = {}
        for arm, res in (("control", ctrl), ("rule", rule)):
            s = M.score({d: res[d] for d in ds}, silver, gold)
            s["rows"] = sum(1 for d in ds for v in res[d]["labels"].values() if v != NR)
            s["clauses"] = sum(res[d]["clauses"] for d in ds)
            s["seconds"] = sum(res[d]["seconds"] for d in ds)
            s["unparsed"] = sum(res[d]["unparsed"] + res[d]["failed"] for d in ds)
            row[arm] = s
        out[name] = row
    flips, changed, judged = [], collections.Counter(), collections.defaultdict(collections.Counter)
    for doc in DOCS:
        units = M.units_of(doc, silver, gold)
        nu = [(M.squash(t), reqs) for t, reqs in units]
        for m in ctrl[doc]["clauses_meta"]:
            if (m["ctx_control"] or "").strip() == (m["ctx_rule"] or "").strip():
                continue
            changed[doc] += 1
            lc, lr = ctrl[doc]["labels"].get(m["key"], NR), rule[doc]["labels"].get(m["key"], NR)
            if (lc == NR) == (lr == NR):
                continue
            sq = M.squash(m["text"])
            inside = [reqs for nt, reqs in nu if sq and sq in nt]
            hit = any(M.match(r, m["text"]) for reqs in inside for r in reqs) if inside else None
            verdict = None
            if inside:
                verdict = ("correct" if hit else "wrong") if lr != NR else ("wrong" if hit else "correct")
                judged[doc][verdict] += 1
            flips.append({"doc": doc, "key": m["key"], "control": lc, "rule": lr, "in_gold_unit": bool(inside), "verdict": verdict,
                          "ctx_control": m["ctx_control"], "ctx_rule": m["ctx_rule"], "clause": m["text"]})
    out["_flips"] = {"changed_context": dict(changed), "n_flips": len(flips), "judged_by_doc": {k: dict(v) for k, v in judged.items()},
                     "judged_pooled": dict(sum(judged.values(), collections.Counter())),
                     "judged_no_cnssi": dict(sum((v for k, v in judged.items() if k != "CNSSI_No1253"), collections.Counter()))}
    # label agreement
    n = same = 0
    for d in DOCS:
        for k, lab in ctrl[d]["labels"].items():
            if k in rule[d]["labels"]:
                n += 1
                same += lab == rule[d]["labels"][k]
    out["_agree"] = {"n": n, "same": same}
    # number-start check: bare number then word (no marker), and "13. (b) Sentence" form, that get a lead-in under rule
    pat1, pat2 = re.compile(r"^\s*\d+\s+[A-Za-z]"), re.compile(r"^\s*\d+\.\s*\([a-z]\)\s+[A-Z]")
    ns = {"bare_number_all": 0, "bare_number_with_leadin": [], "numdot_paren_all": 0, "numdot_paren_with_leadin": []}
    for d in DOCS:
        for m in rule[d]["clauses_meta"]:
            for pat, ka, kb in ((pat1, "bare_number_all", "bare_number_with_leadin"), (pat2, "numdot_paren_all", "numdot_paren_with_leadin")):
                if pat.match(m["text"]):
                    ns[ka] += 1
                    if (m["ctx_rule"] or "").strip():
                        ns[kb].append({"doc": d, "key": m["key"], "ctrl_label": ctrl[d]["labels"].get(m["key"]), "rule_label": rule[d]["labels"].get(m["key"]),
                                       "ctx_control": m["ctx_control"], "ctx_rule": m["ctx_rule"], "clause": m["text"]})
    out["_numstart"] = ns
    if a.flips:
        Path(a.flips).write_text(json.dumps({"flips": flips, "numstart": ns}, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps({k: v for k, v in out.items()}, indent=1, ensure_ascii=False), encoding="utf-8")
    for name in subsets:
        c, r = out[name]["control"], out[name]["rule"]
        print(f"{name}: labeled {c['labeled']} | control R {c['recall']:.2f} P {c['precision']:.2f} rows {c['rows']} | rule R {r['recall']:.2f} P {r['precision']:.2f} rows {r['rows']} | dR {r['recall']-c['recall']:+.2f} dP {r['precision']-c['precision']:+.2f} | secs {c['seconds']:.0f}/{r['seconds']:.0f} unparsed {c['unparsed']}/{r['unparsed']}")
    print("flips", {k: v for k, v in out["_flips"].items()}, "agree", out["_agree"])
    print("numstart", {k: (len(v) if isinstance(v, list) else v) for k, v in ns.items()})
    for f in flips:
        print(f"[{f['doc']}] {f['control']} -> {f['rule']} gold={f['verdict']}\n  old: {(f['ctx_control'] or '-')[:110]}\n  new: {(f['ctx_rule'] or '-')[:110]}\n  clause: {f['clause'][:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

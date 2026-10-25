#!/usr/bin/env python3
"""PREREG8 metrics: sealed recall/precision, label flips, agreement, timing for the arms written by label_ctx_run.py. Read only, no model.
Scoring functions (norm, squash, toks, match, silver_sets, gold_sets, quality) are copied unchanged from chunk_size_metrics.py (PREREG6/7).

    python3 eval/clause_labeling/label_ctx_metrics.py [--json OUT] [--flips FILE]
"""
import argparse
import collections
import glob
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fragmentation  # noqa: E402
from pipeline.sentence_expand import tidy  # noqa: E402

SCRATCH = Path.home() / "reqbot-work/scratch"
OUT = SCRATCH / "label_ctx"
DOCS = ["afi17-203", "afi13-550", "DODI 5200.01", "afi17-101", "afman17-204", "DODI 5200.48", "DODI 8551.01"]
ARMS = ["control", "control2", "rule", "b8", "b16", "c4096", "p100", "combo"]
NR = "NOT_REQUIREMENT"

# ---- labeled sets (internal, outside the repository)
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def squash(s: str) -> str:
    """Letters and digits only, lower case: rows are whitespace-tidied (" ," becomes ","), so containment is tested on this form."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def toks(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def match(a: str, b: str, th: float = 0.6) -> bool:
    na, nb = norm(a), norm(b)
    if na in nb or nb in na:
        return True
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return False
    c = collections.Counter(tb)
    ov = 0
    for w in ta:
        if c[w] > 0:
            ov += 1
            c[w] -= 1
    return ov / min(len(ta), len(tb)) >= th


def _jsonl(p) -> list[dict]:
    return [json.loads(ln) for ln in open(p, encoding="utf-8") if ln.strip()]


def silver_sets() -> dict:
    """{doc: (split, [(unit_text, [labeled requirements])])}: requirements both blind copies list (the 0.8 rule of the earlier experiments)."""
    s = SCRATCH / "silver"
    units = {}
    for f in ("units.jsonl", "units2.jsonl", "units3.jsonl"):
        for u in _jsonl(s / f):
            units[u["unit_id"]] = u

    def labs(x):
        d = {}
        for p in glob.glob(str(s / f"labels*/A_{x}_*.jsonl")):
            for r in _jsonl(p):
                d[r["unit_id"]] = r["obligations"]
        return d
    ax, ay = labs("X"), labs("Y")
    out: dict = {}
    for uid, u in units.items():
        if uid in ax and uid in ay:
            reqs = [r for r in ax[uid] if any(match(r, y, 0.8) for y in ay[uid])]
            out.setdefault(u["document"], (u["split"], []))[1].append((u["text"], reqs))
    return out


def gold_sets() -> dict:
    g = SCRATCH / "gold2"
    both = json.load(open(g / "gold_both.json", encoding="utf-8"))
    out: dict = {}
    for u in _jsonl(g / "units_gold2.jsonl"):
        out.setdefault(u["document"], (u["split"], []))[1].append((u["text"], both.get(u["unit_id"], [])))
    return out


def quality(rows: list[str], units: list) -> dict:
    """recall = labeled requirements found / labeled; precision = rows inside the sampled paragraphs that match a labeled requirement / such rows."""
    nreq = cov = flag = ok = 0
    nu = [(squash(t), t, r) for t, r in units]
    for nt, _t, reqs in nu:
        ft = [q for q in rows if (nq := squash(q)) and (nq in nt or nt in nq)]
        nreq += len(reqs)
        cov += sum(1 for r in reqs if any(match(r, t) for t in ft))
        flag += len(ft)
        ok += sum(1 for t in ft if any(match(r, t) for r in reqs))
    return {"labeled": nreq, "found": cov, "rows_in_units": flag, "rows_right": ok}




def load(arm: str):
    d = {}
    for doc in DOCS:
        p = OUT / arm / f"{doc}.json"
        if p.exists():
            d[doc] = json.load(open(p, encoding="utf-8"))
    return d if len(d) == len(DOCS) else None


def units_of(doc, silver, gold):
    return (silver.get(doc) or gold.get(doc))[1]


def score(res, silver, gold, only=None):
    """Pooled quality over the documents; `only(clause_meta) -> bool` restricts the rows counted (list-item subset)."""
    tot = collections.Counter()
    for doc, r in res.items():
        rows = [tidy(m["text"]) for m in r["clauses_meta"] if r["labels"].get(m["key"], NR) != NR and (only is None or only(m))]
        q = quality(rows, units_of(doc, silver, gold))
        tot.update(q)
    return {**tot, "recall": 100 * tot["found"] / tot["labeled"] if tot["labeled"] else None,
            "precision": 100 * tot["rows_right"] / tot["rows_in_units"] if tot["rows_in_units"] else None}


def agreement(a, b):
    n = same = 0
    for doc in a:
        for k, lab in a[doc]["labels"].items():
            if k in b[doc]["labels"]:
                n += 1
                same += lab == b[doc]["labels"][k]
    return {"n": n, "same": same, "pct": 100 * same / n if n else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--flips", default=None)
    a = ap.parse_args()
    silver, gold = silver_sets(), gold_sets()
    arms = {x: load(x) for x in ARMS}
    arms = {k: v for k, v in arms.items() if v}
    out = {}
    for name, res in arms.items():
        s = score(res, silver, gold)
        s.update(seconds=sum(r["seconds"] for r in res.values()), batches=sum(r["batches"] for r in res.values()), unparsed=sum(r["unparsed"] for r in res.values()),
                 failed=sum(r["failed"] for r in res.values()), clauses=sum(r["clauses"] for r in res.values()),
                 rows=sum(1 for r in res.values() for v in r["labels"].values() if v != NR), prompt_sha=sorted({r["prompt_sha"] for r in res.values()}),
                 row_agree_vs_control=agreement(res, arms["control"]) if name != "control" else None,
                 requirement_agree_vs_control=None)
        # agreement on "is a row" (the label kind is not used downstream)
        if name != "control":
            n = same = 0
            for doc in res:
                for k, lab in res[doc]["labels"].items():
                    c = arms["control"][doc]["labels"].get(k)
                    if c is not None:
                        n += 1
                        same += (lab == NR) == (c == NR)
            s["requirement_agree_vs_control"] = {"n": n, "same": same, "pct": 100 * same / n}
        isli = lambda m: fragmentation.is_list_item(m["text"])  # noqa: E731
        s["list_items"] = score(res, silver, gold, only=isli)
        out[name] = s
    # Q1 flips on changed clauses
    if "rule" in arms:
        ctrl, rule = arms["control"], arms["rule"]
        flips, changed, label_changed, judged = [], 0, 0, collections.Counter()
        for doc in DOCS:
            units = units_of(doc, silver, gold)
            nu = [(squash(t), reqs) for t, reqs in units]
            for m in ctrl[doc]["clauses_meta"]:
                if (m["ctx_control"] or "").strip() == (m["ctx_rule"] or "").strip():
                    continue
                changed += 1
                lc, lr = ctrl[doc]["labels"].get(m["key"], NR), rule[doc]["labels"].get(m["key"], NR)
                label_changed += lc != lr
                if (lc == NR) == (lr == NR):
                    continue
                sq = squash(m["text"])
                inside = [reqs for nt, reqs in nu if sq and sq in nt]
                gold_hit = any(match(r, m["text"]) for reqs in inside for r in reqs) if inside else None
                verdict = None
                if inside:
                    verdict = ("correct" if gold_hit else "wrong") if lr != NR else ("wrong" if gold_hit else "correct")
                    judged[verdict] += 1
                flips.append({"doc": doc, "key": m["key"], "control": lc, "rule": lr, "in_gold_unit": bool(inside), "matches_gold": gold_hit, "verdict": verdict,
                              "ctx_control": m["ctx_control"], "ctx_rule": m["ctx_rule"], "clause": m["text"]})
        out["_q1"] = {"clauses_changed": changed, "label_changed": label_changed, "requirement_flips": len(flips), "judged": dict(judged),
                      "to_row": sum(f["rule"] != NR for f in flips), "to_nr": sum(f["rule"] == NR for f in flips)}
        # agreement on changed clauses only
        n = same = 0
        for doc in DOCS:
            for m in ctrl[doc]["clauses_meta"]:
                if (m["ctx_control"] or "").strip() != (m["ctx_rule"] or "").strip():
                    n += 1
                    same += ctrl[doc]["labels"].get(m["key"]) == rule[doc]["labels"].get(m["key"])
        out["_q1"]["changed_agree"] = {"n": n, "same": same}
        if a.flips:
            Path(a.flips).write_text(json.dumps(flips, indent=1, ensure_ascii=False), encoding="utf-8")
            for f in flips:
                print(f"[{f['doc']}] {f['control']} -> {f['rule']} gold={f['verdict']}\n  old ctx: {(f['ctx_control'] or '-')[:110]}\n  new ctx: {(f['ctx_rule'] or '-')[:110]}\n  clause: {f['clause'][:200]}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, v in out.items():
        if k.startswith("_"):
            print(k, v)
        else:
            print(k, {x: (round(y, 2) if isinstance(y, float) else y) for x, y in v.items() if x not in ("list_items",)}, "LI", {x: (round(y, 1) if isinstance(y, float) else y) for x, y in v["list_items"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())

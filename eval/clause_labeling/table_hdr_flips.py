#!/usr/bin/env python3
"""PREREG11: build the blind grading material for the grid-line status flips (control vs header). Writes neutral_flips.txt (no arm information) and KEY_do_not_open.json.

    python3 eval/clause_labeling/table_hdr_flips.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import table_header as TH  # noqa: E402
from table_hdr_metrics import NR, OUT, load  # noqa: E402

LIMIT, SEED, WIN = 80, 11, 600


def main():
    ctrl, hdr = load("control"), load("header")
    flips = []
    for d in ctrl:
        chunks = {}
        for ln in open(OUT / "chunks" / f"{d}_chunks.jsonl", encoding="utf-8"):
            if ln.strip():
                c = json.loads(ln)
                chunks[c["chunk_id"]] = c.get("raw_text") or c.get("text") or ""
        for m in ctrl[d]["clauses_meta"]:
            if not m["is_grid"]:
                continue
            a, b = ctrl[d]["labels"].get(m["key"], NR), hdr[d]["labels"].get(m["key"], NR)
            if (a == NR) == (b == NR):
                continue
            cid = int(m["key"].split(":")[0])
            raw = chunks[cid]
            s = m["start"]
            before, after = raw[max(0, s - WIN):s], raw[s + len(m["text"]):s + len(m["text"]) + WIN]
            if len(before) < WIN and cid - 1 in chunks:
                before = chunks[cid - 1][-(WIN - len(before)):] + "\n" + before
            if len(after) < WIN and cid + 1 in chunks:
                after = after + "\n" + chunks[cid + 1][:WIN - len(after)]
            info = TH.header_info(raw, s)
            hdrtxt = TH.render(info[0], info[1]) if info else "(none found)"
            flips.append({"doc": d, "key": m["key"], "control": a, "header": b, "clause": m["text"], "table": hdrtxt, "before": before, "after": after})
    print("flips", len(flips), "by doc", {d: sum(f["doc"] == d for f in flips) for d in ctrl})
    rnd = random.Random(SEED)
    cn = [f for f in flips if f["doc"] == "CNSSI_No1253"]
    other = [f for f in flips if f["doc"] != "CNSSI_No1253"]
    keep = other + (cn if len(flips) <= LIMIT else rnd.sample(cn, max(0, LIMIT - len(other))))
    rnd.shuffle(keep)
    key = {}
    txt = []
    for i, f in enumerate(keep, 1):
        key[i] = {k: f[k] for k in ("doc", "key", "control", "header")}
        txt.append(f"=== {i} | document: {f['doc']}\nTABLE (header row as found in the source): {f['table']}\nSOURCE BEFORE:\n{f['before']}\n>>> CLAUSE: {f['clause']}\nSOURCE AFTER:\n{f['after']}\n")
    d = OUT / "grading"
    d.mkdir(exist_ok=True)
    (d / "neutral_flips.txt").write_text("\n".join(txt))
    (d / "KEY_do_not_open.json").write_text(json.dumps({"graded": key, "total_flips": len(flips), "not_graded": len(flips) - len(keep)}))
    print("graded", len(keep), "not graded", len(flips) - len(keep))


if __name__ == "__main__":
    main()

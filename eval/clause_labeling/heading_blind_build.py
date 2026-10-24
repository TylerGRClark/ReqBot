#!/usr/bin/env python3
"""PREREG10 rule 5: write the requirement flips of the two arms to a neutral file for blind grading (method of ~/reqbot-work/notes/blind_flips_result_2026-10-24.md).

Each entry shows the document name, the section heading path, about 600 characters of source before and after the clause (previous or next chunk appended at chunk edges) and the
clause. No arm label, no gold label, no earlier grade; order shuffled with a fixed seed. The key (which arm said what) goes to a separate file that graders must not open.

    python3 eval/clause_labeling/heading_blind_build.py --flips FLIPS.json --out DIR [--batches 3]
"""
import argparse
import json
import random
from pathlib import Path

RUN = Path.home() / "reqbot-work/scratch/heading_lead/run"
PROMPT = ("You are grading clauses from US Air Force / DoD policy documents. Definition: a requirement is a duty, prohibition or permission placed on a stated party that an auditor "
          "could check. Each numbered item shows the section heading, text before, the CLAUSE TO JUDGE (between >>> <<<), and text after; use the surrounding text, including any "
          "list lead-in sentence or section heading that the clause completes. For EACH numbered clause answer exactly one line: \"<number>: YES|NO|UNSURE - one-line reason\". "
          "YES = the clause (with its lead-in) is a requirement under the definition. Answer all clauses, nothing else.\n\n")


def norm_map(t):
    out, idx, prev_space = [], [], True
    for i, c in enumerate(t):
        if c.isspace():
            if not prev_space:
                out.append(" ")
                idx.append(i)
            prev_space = True
        else:
            out.append(c)
            idx.append(i)
            prev_space = False
    return "".join(out), idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flips", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batches", type=int, default=3)
    ap.add_argument("--chunks-root", default=str(RUN))
    a = ap.parse_args()
    flips = json.load(open(a.flips, encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = {}
    recs = []
    for x in flips:
        doc = x["doc"]
        if doc not in cache:
            cache[doc] = {c["chunk_id"]: c for c in (json.loads(ln) for ln in open(Path(a.chunks_root) / "chunks" / f"{doc}_chunks.jsonl", encoding="utf-8") if ln.strip())}
        cid = int(x["key"].split(":")[0])
        ch = cache[doc][cid]
        raw = ch.get("raw_text") or ""
        nt, idx = norm_map(raw)
        cl = " ".join(x["clause"].split())
        p = nt.find(cl)
        if p < 0:
            p = nt.find(cl[:60])
        if p < 0:
            print("clause not found in chunk:", doc, x["key"])
            continue
        s, b = idx[p], idx[min(p + len(cl), len(nt)) - 1] + 1
        pre, post = raw[max(0, s - 600):s], raw[b:b + 600]
        if s < 600 and cid - 1 in cache[doc]:
            pre = (cache[doc][cid - 1].get("raw_text") or "")[-(600 - s):] + "\n[chunk boundary]\n" + pre
        if len(raw) - b < 600 and cid + 1 in cache[doc]:
            post = post + "\n[chunk boundary]\n" + (cache[doc][cid + 1].get("raw_text") or "")[:600 - (len(raw) - b)]
        recs.append({"doc": doc, "key": x["key"], "clause": cl, "section": " > ".join(ch.get("section_title_path") or []) or "(none)", "pre": pre.strip(), "post": post.strip(),
                     "control": x["control"], "heading": x["heading"]})
    random.seed(8124)
    random.shuffle(recs)
    key, text = {}, []
    for i, r in enumerate(recs, 1):
        key[i] = {k: r[k] for k in ("doc", "key", "control", "heading")}
        text.append(f"=== CLAUSE {i} ===\nDocument: {r['doc']}\nSection: {r['section']}\nTEXT BEFORE: ...{r['pre']}\nCLAUSE TO JUDGE: >>>{r['clause']}<<<\nTEXT AFTER: {r['post']}...\n")
    (out / "neutral_flips.txt").write_text("\n".join(text), encoding="utf-8")
    (out / "KEY_do_not_open.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    n = len(text)
    step = -(-n // a.batches) if n else 1
    for b in range(a.batches):
        chunk = text[b * step:(b + 1) * step]
        if chunk:
            (out / f"prompt{b + 1}.txt").write_text(PROMPT + "\n".join(chunk), encoding="utf-8")
    print("flips written:", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

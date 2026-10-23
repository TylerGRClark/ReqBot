#!/usr/bin/env python3
"""PREREG7 passage-window measurement. Read only, no model.

For each arm and document it builds the checklist the normal way and, for each row that came from the requirements file, measures
 (1) as shipped: is the marked quote wholly inside the first 1,500 / 1,200 characters of the passage (the draft-question and criticality readers), and is the row's
     lead-in (explained_parts kind lead_in) inside those characters;
 (2) with the window rule below: the same two questions, plus the window's length and whether it reaches outside the quote's own chunk.

WINDOW RULE (designed, not merged; PREREG7). Given the quote (the root, `extracted_quote`) and the chunk stream of the document (chunks in file order; `raw_text` has one line per
document element):
  1. the element lines that hold the quote;
  2. if the row has a lead-in (as pipeline/lead_in.py resolved it and the row stores it), the nearest line at or above the quote that holds it (same section path, at most 40
     lines back, crossing into earlier chunks), with the lines between it and the quote when they fit (else the lead-in line alone);
  3. then extend alternately one line after, one line before, only through lines of chunks with the same section path as the quote's chunk, while the total stays within CAP characters;
  4. if the quote (with its lead-in) alone exceeds CAP, the window is the quote and its lead-in, uncut; if only the quote's own line is too long, the line is cropped around the quote at word boundaries.
A side that is cut off is marked with an ellipsis ("..."). The quote is never cut.

    python3 eval/clause_labeling/chunk_size_windows.py --root ~/reqbot-work/scratch/chunk_size [--arms control,512,1024,A,C] [--json OUT]
"""
import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from services import checklist_audit, checklist_service  # noqa: E402
import chunk_size_metrics as M  # noqa: E402

CAPS = (1500, 1200)
LOOKBACK_LINES = 40


def _lines(chunks: list[dict]) -> list[tuple[int, int, str]]:
    """(index of the chunk in file order, chunk_id, line) for every non-empty line of the document."""
    out = []
    for ci, c in enumerate(chunks):
        for ln in (c.get("raw_text") or "").split("\n"):
            if ln.strip():
                out.append((ci, c["chunk_id"], ln.rstrip()))
    return out


def _path(c: dict) -> tuple:
    p = c.get("section_ref_path") or c.get("section_title_path") or []
    return tuple(p) if isinstance(p, (list, tuple)) else (str(p),)


sq = M.squash


def window(root_quote: str, chunks: list[dict], lines: list, cap: int, lead_pfx: str = "") -> dict | None:
    """The window text for a quote, or None when the quote cannot be located in any chunk line block."""
    pat = checklist_audit._flex_pattern(root_quote)
    if not pat:
        return None
    # find the chunk and the lines the quote sits in
    for ci, c in enumerate(chunks):
        raw = c.get("raw_text") or ""
        m = pat.search(raw)
        if m:
            break
    else:
        return None
    sect = _path(c)
    idx = [i for i, (cj, _cid, _ln) in enumerate(lines) if cj == ci]
    # char offset of each line inside raw (lines were stripped of blanks, so locate by scanning)
    pos, spans = 0, []
    for ln in raw.split("\n"):
        if ln.strip():
            spans.append((pos, pos + len(ln.rstrip())))
        pos += len(ln) + 1
    hit = [k for k, (a, b) in enumerate(spans) if a < m.end() and b > m.start()]
    if not hit:
        return None
    lo, hi = idx[0] + hit[0], idx[0] + hit[-1]
    quote_len = m.end() - m.start()

    def same_section(i):
        return _path(chunks[lines[i][0]]) == sect

    def size(a, b):
        return sum(len(lines[i][2]) + 1 for i in range(a, b + 1))
    # 2. the row's lead-in, as the pipeline already resolved it (pipeline/lead_in.py, stored in explained_parts): the nearest line at or above the quote that holds it
    lead = None
    if lead_pfx:
        for i in range(lo, max(-1, lo - 1 - LOOKBACK_LINES), -1):
            if not same_section(i):
                break
            if lead_pfx in sq(lines[i][2]):
                lead = i if i < lo else None  # in the quote's own line: already inside the window
                break
    a, b = lo, hi
    if lead is not None:
        a = lead if size(lead, hi) <= cap else lo  # the lines between the lead-in and the quote are dropped when they do not fit
    parts_before = []  # extra lines (the lead-in alone when the lines between do not fit)
    if lead is not None and a == lo:
        parts_before = [lead]
    used = size(a, b) + sum(len(lines[i][2]) + 1 for i in parts_before)
    if used > cap:  # 4. quote (and lead-in) alone are over the cap: uncut; crop only the quote's own line when it is the whole problem
        if len(hit) == 1 and quote_len < cap and not parts_before:
            line = lines[lo][2]
            ls = spans[hit[0]][0]
            qs, qe = m.start() - ls, m.end() - ls
            budget = cap - quote_len
            s0 = max(0, qs - budget // 2)
            e0 = min(len(line), qe + (budget - (qs - s0)))
            s0 = max(0, min(s0, qs - (budget - (e0 - qe))))
            while s0 < qs and s0 > 0 and line[s0 - 1] != " ":
                s0 += 1
            while e0 > qe and e0 < len(line) and line[e0] != " ":
                e0 -= 1
            txt = ("... " if s0 > 0 else "") + line[s0:e0] + (" ..." if e0 < len(line) else "")
            return {"text": txt, "chars": len(txt), "outside_chunk": False, "lines": 1}
        txt = "\n".join([lines[i][2] for i in parts_before] + [lines[i][2] for i in range(a, b + 1)])
        return {"text": txt, "chars": len(txt), "outside_chunk": any(lines[i][0] != ci for i in parts_before + list(range(a, b + 1))), "lines": len(parts_before) + b - a + 1}
    # 3. alternate extension: one after, one before, same section only
    nxt, prv = b + 1, a - 1
    ex_after, ex_before = [], []
    while True:
        moved = False
        if nxt < len(lines) and same_section(nxt) and used + len(lines[nxt][2]) + 1 <= cap:
            used += len(lines[nxt][2]) + 1
            ex_after.append(nxt)
            nxt += 1
            moved = True
        if prv >= 0 and same_section(prv) and prv not in parts_before and used + len(lines[prv][2]) + 1 <= cap:
            used += len(lines[prv][2]) + 1
            ex_before.append(prv)
            prv -= 1
            moved = True
        if not moved:
            break
    order = sorted(set(ex_before) | set(parts_before) | set(range(a, b + 1)) | set(ex_after))
    txt = "\n".join(lines[i][2] for i in order)
    if order[0] > 0 and same_section(order[0] - 1):
        txt = "... " + txt
    if order[-1] + 1 < len(lines) and same_section(order[-1] + 1):
        txt = txt + " ..."
    return {"text": txt, "chars": len(txt), "outside_chunk": any(lines[i][0] != ci for i in order), "lines": len(order)}


def lead_prefix(parts) -> str:
    for p in parts or []:
        if p.get("kind") == "lead_in":
            return sq(p.get("text") or "")[:60]
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(M.SCRATCH / "chunk_size"))
    ap.add_argument("--arms", default=",".join(M.ARMS))
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    root = Path(args.root).expanduser()
    res: dict = {}
    for arm in args.arms.split(","):
        agg = {"rows": 0, "rows_with_lead_in": 0, "not_located": 0}
        for cap in CAPS:
            agg.update({f"shipped_quote_in_{cap}": 0, f"shipped_lead_in_in_{cap}": 0, f"win_quote_in_{cap}": 0, f"win_lead_in_in_{cap}": 0, f"win_outside_chunk_{cap}": 0})
        wl = []
        for doc in M.DOCS:
            d = M.run_dir(root, arm, doc)
            if d is None:
                continue
            chunks = M._jsonl(d / f"{doc}_chunks.jsonl")
            lines = _lines(chunks)
            from core.artifact_resolver import resolve_latest_requirement_files
            recs = {}
            f = resolve_latest_requirement_files(root / "out" / arm)[doc]
            for r in M._jsonl(f):
                if r.get("requirement_id"):
                    recs[r["requirement_id"]] = r
            cl = checklist_service.generate(root / "out" / arm, doc, "cybersecurity")
            for it in cl.get("items", []):
                ids = it.get("requirement_ids") or []
                if not ids:
                    continue
                agg["rows"] += 1
                rec = recs.get(ids[0], {})
                lp = lead_prefix(rec.get("explained_parts"))
                agg["rows_with_lead_in"] += bool(lp)
                p = it.get("passage") or ""
                i = p.find(checklist_audit.MARK_OPEN)
                j = p.find(checklist_audit.MARK_CLOSE, i) if i >= 0 else -1
                root_q = it.get("extracted_quote") or it.get("source_quote") or ""
                w = {cap: window(root_q, chunks, lines, cap, lp) for cap in CAPS}
                if w[1500] is None:
                    agg["not_located"] += 1
                for cap in CAPS:
                    if j >= 0 and j + len(checklist_audit.MARK_CLOSE) <= cap:
                        agg[f"shipped_quote_in_{cap}"] += 1
                    if lp and lp in sq(p[:cap]):
                        agg[f"shipped_lead_in_in_{cap}"] += 1
                    if w[cap] is not None:
                        agg[f"win_quote_in_{cap}"] += 1  # by construction the quote is inside whenever it is located
                        agg[f"win_outside_chunk_{cap}"] += w[cap]["outside_chunk"]
                        if lp and lp in sq(w[cap]["text"]):
                            agg[f"win_lead_in_in_{cap}"] += 1
                if w[1500] is not None:
                    wl.append(w[1500]["chars"])
        wl.sort()
        agg.update(win1500_median=wl[len(wl) // 2] if wl else 0, win1500_p95=wl[int(0.95 * (len(wl) - 1))] if wl else 0, win1500_max=wl[-1] if wl else 0)
        res[arm] = agg
        print(arm, json.dumps(agg))
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

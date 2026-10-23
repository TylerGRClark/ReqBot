#!/usr/bin/env python3
"""Metrics for PREREG6 (chunk size and clause labeling). Read only, no model.

Layout it reads (made by the experiment driver in the scratch folder):
    <root>/out/<arm>/<doc>_<stamp>/   one pipeline run per document and arm (arm = control, 512, 1024)
The labeled sets are internal work products under ~/reqbot-work/scratch (silver/, gold2/); they are not in this repository.

    python3 eval/clause_labeling/chunk_size_metrics.py --root ~/reqbot-work/scratch/chunk_size [--json OUT]
"""
import argparse
import collections
import glob
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.clauses import chunk_clauses  # noqa: E402
import fragmentation  # noqa: E402

ARMS = ["control", "512", "1024", "A", "C"]  # PREREG6 arms, then the PREREG7 arms (A: merge_peers off; C: A plus lead-in glue)
DOCS = ["afi17-203", "afi13-550", "afi10-2402", "dafman17-1304"]
SCRATCH = Path.home() / "reqbot-work/scratch"
_END = re.compile(r"[.!?:;][\"')\]]*(\s*\(T-\d+\)\.?)?\s*$")
SHORT_LINE_WORDS = 6


# ---- chunk-level metrics
def last_line(text: str) -> str:
    lines = [ln for ln in (text or "").split("\n") if ln.strip()]
    return lines[-1].strip() if lines else ""


def is_end_cut(raw_text: str) -> bool:
    """PREREG6 metric 1: the chunk's last non-empty line is not a table row, has more than 6 words, and does not end a sentence or lead-in."""
    ln = last_line(raw_text)
    if not ln or ln.startswith("|") or len(ln.split()) <= SHORT_LINE_WORDS:
        return False
    return not _END.search(ln)


def is_start_cut(raw_text: str) -> bool:
    lines = [ln for ln in (raw_text or "").split("\n") if ln.strip()]
    if not lines:
        return False
    first = lines[0].strip()
    if first.startswith("|"):
        return False
    return fragmentation.strip_label(first)[:1].islower()


def chunk_metrics(chunks: list[dict]) -> dict:
    sizes = sorted(len(c.get("raw_text") or "") for c in chunks)
    li = li_with = 0
    for c in chunks:
        for cl in chunk_clauses(c):
            if fragmentation.is_list_item(cl["text"]):
                li += 1
                li_with += cl["ctx_lead"] is not None
    grid = sum(1 for c in chunks for ln in (c.get("raw_text") or "").split("\n") if ln.lstrip().startswith("|"))
    return {
        "chunks": len(chunks),
        "end_cuts": sum(is_end_cut(c.get("raw_text")) for c in chunks),
        "start_cuts": sum(is_start_cut(c.get("raw_text")) for c in chunks),
        "list_item_clauses": li,
        "list_items_with_lead_in_in_chunk": li_with,
        "grid_lines": grid,
        "raw_chars_median": sizes[len(sizes) // 2] if sizes else 0,
        "raw_chars_p90": sizes[int(0.90 * (len(sizes) - 1))] if sizes else 0,
        "raw_chars_p95": sizes[int(0.95 * (len(sizes) - 1))] if sizes else 0,
        "raw_chars_max": sizes[-1] if sizes else 0,
        "chunks_over_1500_chars": sum(1 for n in sizes if n > 1500),
        "chunks_under_150_chars": sum(1 for n in sizes if n < 150),
        "chars_total": sum(sizes),
        "chars_beyond_1500": sum(max(0, n - 1500) for n in sizes),
    }


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


# ---- reading an arm
def run_dir(root: Path, arm: str, doc: str) -> Path | None:
    c = sorted(d for d in (root / "out" / arm).glob(f"{doc}_20*") if (d / f"{doc}_chunks.jsonl").exists())
    return c[-1] if c else None


def label_seconds(log: Path) -> float | None:
    """Seconds between 'Starting requirement finding' and 'Starting normalizing' in the pipeline log."""
    import datetime
    t0 = t1 = None
    for ln in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", ln)
        if not m:
            continue
        t = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        if "Starting requirement finding" in ln and t0 is None:
            t0 = t
        elif "Starting normalizing" in ln and t0 is not None and t1 is None:
            t1 = t
    return (t1 - t0).total_seconds() if t0 and t1 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(SCRATCH / "chunk_size"))
    ap.add_argument("--json", default=None)
    ap.add_argument("--arms", default=",".join(ARMS), help="comma list of arms to read")
    args = ap.parse_args()
    root = Path(args.root).expanduser()
    arms = args.arms.split(",")
    silver, gold = silver_sets(), gold_sets()
    res: dict = {}
    for arm in arms:
        per: dict = {}
        for doc in DOCS:
            d = run_dir(root, arm, doc)
            if d is None:
                continue
            chunks = _jsonl(d / f"{doc}_chunks.jsonl")
            reqs = _jsonl(d / f"{doc}_extracted_requirements.jsonl") if (d / f"{doc}_extracted_requirements.jsonl").exists() else []
            quotes = [r.get("source_quote", "") for r in reqs]
            e = {"chunk": chunk_metrics(chunks), "rows": len(reqs), "quotes": quotes}
            logp = root / "logs" / f"{doc}_{arm}.log"
            e["label_seconds"] = label_seconds(logp) if logp.exists() else None
            if doc in silver:
                split, units = silver[doc]
                e["silver_" + split] = quality(quotes, units)
            if doc in gold:
                split, units = gold[doc]
                e["gold2_" + split] = quality(quotes, units)
            try:
                e["frag"] = fragmentation.run(root / "out" / arm, doc)["documents"][doc]
            except Exception as ex:  # noqa: BLE001
                e["frag_error"] = str(ex)[:200]
            per[doc] = e
        res[arm] = per
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    # compact print
    for arm in arms:
        for doc, e in res[arm].items():
            q = {k: v for k, v in e.items() if k.startswith(("silver_", "gold2_"))}
            print(arm, doc, "rows", e["rows"], "secs", e["label_seconds"], e["chunk"], q, e.get("frag"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

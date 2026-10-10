"""WP-45.6: compare one model's Step C + D output with the 8B baseline for one document (offline; no LLM, no Qdrant).

Both sides are the normalized survivors of the SAME Step D (the baseline directory comes from `run_model.py --stage D`). For
each document it reports, per side: records at Step C and after Step D, Step D rejections by code, the WP-45.1(a) census signals
and attachment-method mix, and Step C completion states and throughput; and the overlap between the two sides.

Matching rule (fixed in docs/PHASE45_WP456_PLAN.md before any run): two records are the SAME record if they are in the same chunk
and their whitespace-normalized quotes are equal or one contains the other. A 14B record can contain two 8B records (a merge) and
the reverse (a split); sets are therefore counted per side: a record is "matched" if it has at least one counterpart.

Run from the repo root:
  python3 eval/spike_results/wp_45_6/compare.py --doc "DODI 8410.03" --new qwen2.5_14b [--scratch DIR]
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_1", _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import census as C  # noqa: E402
from core.profiles import default_profile  # noqa: E402
from pipeline.parse_and_normalize import normalize_text  # noqa: E402

DEFAULT_SCRATCH = Path.home() / "reqbot-work/scratch/wp45_6_scratch"
BASELINE_TAG = "8b_current_stepD"


def read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def same_record(a, b):
    """The plan's rule: same chunk, and normalized quotes equal or one contains the other."""
    if a["chunk_id"] != b["chunk_id"]:
        return False
    qa, qb = a["nq"], b["nq"]
    return bool(qa) and bool(qb) and (qa == qb or qa in qb or qb in qa)


def prepare(records):
    return [
        {
            "requirement_id": r["requirement_id"],
            "chunk_id": r.get("chunk_id"),
            "quote": (r.get("source_quote") or "").strip(),
            "nq": normalize_text((r.get("source_quote") or "").strip()),
        }
        for r in records
    ]


def overlap(base, new):
    """Per-side matching. Returns dict of id lists: base_matched, base_only, new_matched, new_only, plus exact-equal counts."""
    by_chunk = collections.defaultdict(list)
    for r in new:
        by_chunk[r["chunk_id"]].append(r)
    base_matched, new_matched = set(), set()
    exact_pairs = 0
    for b in base:
        for n in by_chunk.get(b["chunk_id"], []):
            if same_record(b, n):
                base_matched.add(b["requirement_id"])
                new_matched.add(n["requirement_id"])
                exact_pairs += b["nq"] == n["nq"]
    return {
        "base_matched": sorted(base_matched),
        "base_only": sorted(
            r["requirement_id"] for r in base if r["requirement_id"] not in base_matched
        ),
        "new_matched": sorted(new_matched),
        "new_only": sorted(
            r["requirement_id"] for r in new if r["requirement_id"] not in new_matched
        ),
        "exact_equal_pairs": exact_pairs,
    }


_CHUNK_LINE = re.compile(
    r"Chunk (\d+)/(\d+) \(id=(\d+)\): (\d+) requirements extracted in ([\d.]+)s"
)


def chunk_timing(run_log):
    """Per-chunk Step C seconds parsed from the pipeline log (the raw records carry no timing); None without a log."""
    p = Path(run_log)
    if not p.exists():
        return None
    secs = sorted(float(m.group(5)) for m in _CHUNK_LINE.finditer(p.read_text(encoding="utf-8")))
    if not secs:
        return None
    return {
        "chunks_timed": len(secs),
        "total_seconds": round(sum(secs), 1),
        "mean_seconds": round(sum(secs) / len(secs), 2),
        "p95_seconds": secs[min(len(secs) - 1, int(0.95 * len(secs)))],
        "max_seconds": secs[-1],
    }


def side_summary(directory, doc, verb_re):
    d = Path(directory)
    normalized = read_jsonl(d / f"{doc}_requirements_normalized.jsonl")
    extracted = read_jsonl(d / f"{doc}_extracted_requirements.jsonl")
    failures = read_jsonl(d / f"{doc}_normalization_failures.jsonl")
    inputs = {
        doc: {
            "chunks": d / f"{doc}_chunks.jsonl",
            "normalized": d / f"{doc}_requirements_normalized.jsonl",
        }
    }
    rows = C.collect(inputs, verb_re)
    n = len(rows)
    signals = {s: sum(1 for r in rows if r["signals"][s]) for s in C.SIGNALS}
    fragment = sum(1 for r in rows if any(r["signals"][s] for s in C.FRAGMENT_SIGNALS))
    methods = collections.Counter(r["method"] for r in rows)
    return {
        "extracted_step_c": len(extracted),
        "survivors": len(normalized),
        "rejected_step_d": len(failures),
        "rejections_by_code": dict(
            collections.Counter(f.get("error", "unknown") for f in failures)
        ),
        "census_signals": signals,
        "fragment_composite": fragment,
        "fragment_rate": round(fragment / n, 4) if n else None,
        "attachment_methods": dict(methods),
        "records": prepare(normalized),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--doc", required=True)
    ap.add_argument(
        "--new", required=True, help="scratch subdirectory tag of the new model, e.g. qwen2.5_14b"
    )
    ap.add_argument("--scratch", default=str(DEFAULT_SCRATCH))
    ap.add_argument("--out")
    args = ap.parse_args()
    verbs = default_profile()["obligation_verbs"]
    verb_re = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in verbs) + r")\b", re.IGNORECASE)
    scratch = Path(args.scratch)
    base_dir, new_dir = scratch / BASELINE_TAG / args.doc, scratch / args.new / args.doc
    base, new = side_summary(base_dir, args.doc, verb_re), side_summary(new_dir, args.doc, verb_re)
    ov = overlap(base["records"], new["records"])
    run = (
        json.loads((new_dir / "run_record.json").read_text(encoding="utf-8"))
        if (new_dir / "run_record.json").exists()
        else {}
    )
    result = {
        "doc": args.doc,
        "baseline": {k: v for k, v in base.items() if k != "records"},
        "new": {k: v for k, v in new.items() if k != "records"},
        "overlap": {k: (v if k == "exact_equal_pairs" else len(v)) for k, v in ov.items()},
        "overlap_ids": ov,
        "new_run": {
            **{
                k: run.get(k)
                for k in (
                    "model",
                    "model_digest",
                    "wall_seconds",
                    "timeout_seconds",
                    "max_vram_bytes",
                    "step_c",
                )
            },
            "chunk_timing": chunk_timing(new_dir / "run.log"),
        },
    }
    out = (
        Path(args.out) if args.out else _HERE / "outputs" / f"comparison_{args.doc}_{args.new}.json"
    )
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    o = result["overlap"]
    print(
        f"{args.doc}: baseline {base['survivors']} survivors, new {new['survivors']}; "
        f"matched base {o['base_matched']} / new {o['new_matched']}; 8B-only {o['base_only']}, new-only {o['new_only']}; "
        f"fragment rate {base['fragment_rate']} vs {new['fragment_rate']}"
    )


if __name__ == "__main__":
    main()

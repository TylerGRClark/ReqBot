"""WP-45 audit verification (read-only). See eval/spike_results/wp_45_audit/README.md."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import sys
import json
import glob
import os
import re
import collections
import logging

pass
logging.disable(logging.CRITICAL)
from pathlib import Path
from core import config as _config
from pipeline import enrich_requirements as E
from pipeline.parse_and_normalize import normalize_text

# --- the report's three probes, verbatim, against the real functions
print(
    "probe1 same-chunk:",
    repr(
        E._find_same_chunk_stem(
            "Keep visitor logs.",
            1,
            {
                1: [
                    {"source_quote": "Backups shall include: nightly snapshots."},
                    {"source_quote": "Keep visitor logs."},
                ]
            },
        )
    ),
)
print(
    "probe2 cross-section:",
    repr(
        E._find_cross_chunk_stem(
            1,
            {0: [{"source_quote": "Backup administrators shall:"}]},
            {
                0: {"section_title_path": ["Backup"]},
                1: {
                    "raw_text": "(2) Retain visitor logs.",
                    "section_title_path": ["Physical security"],
                },
            },
        )
    ),
)

man = json.load(open(str(_ROOT / "eval/spike_results/wp_44/manifest.json")))["documents"]
P = str(_config.load().processed_dir_path())
meth = collections.Counter()
xs_total = xs_mismatch = 0
flagged = []
cand = 0
recs_total = 0
xs_rows = []
for doc, m in man.items():
    d = Path(f"{P}/{m['run_dir']}")
    norm = glob.glob(str(d / "*_requirements_normalized.jsonl"))[0]
    reqs = [json.loads(l) for l in open(norm) if l.strip()]
    sc, cb = E._load_reconstruction_sources(Path(norm))
    recs_total += len(reqs)
    for r in reqs:
        q = (r.get("source_quote") or "").strip()
        cid = r.get("chunk_id")
        if not q or cid is None or not E._is_reconstruction_candidate(q):
            continue
        cand += 1
        s1 = E._find_same_chunk_stem(q, cid, sc)
        if s1:
            meth["same-chunk"] += 1
            raw = normalize_text(cb.get(cid, {}).get("raw_text", ""))
            pq = raw.find(normalize_text(q))
            ps = raw.find(normalize_text(s1))
            why = (
                "target BEFORE stem"
                if (pq >= 0 and ps >= 0 and pq < ps)
                else "stem not in raw_text"
                if ps < 0
                else "gap>400ch"
                if (pq >= 0 and pq - ps > 400)
                else None
            )
            if why:
                flagged.append((doc, cid, why, s1[:60], q[:60]))
            continue
        s2 = E._find_cross_chunk_stem(cid, sc, cb)
        if s2:
            meth["cross-chunk"] += 1
            xs_total += 1
            a = tuple(cb.get(cid, {}).get("section_title_path") or [])
            b = tuple(cb.get(cid - 1, {}).get("section_title_path") or [])
            if a != b:
                xs_mismatch += 1
                xs_rows.append((doc, cid, list(b)[-1:], list(a)[-1:], s2[:50], q[:50]))
            continue
        s3 = E._find_heading_stem(q, cid, cb)
        if s3:
            meth["heading-fallback"] += 1
        else:
            meth["no stem"] += 1
print(f"\nnormalized records={recs_total}; reconstruction candidates={cand}")
print("attachment method:", dict(meth))
print(
    f"cross-chunk attachments whose previous chunk is in a DIFFERENT section path: {xs_mismatch} of {xs_total}"
)
for x in xs_rows[:6]:
    print("  x-chunk", x)
print(
    f"same-chunk attachments with a red flag (order/gap/not-found): {len(flagged)} of {meth['same-chunk']}"
)
for f in flagged[:8]:
    print("  same-chunk", f)

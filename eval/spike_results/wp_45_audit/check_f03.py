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
import collections
import logging

pass
logging.disable(logging.CRITICAL)
from core import config as _config
from pipeline.parse_and_normalize import (
    deduplicate_requirements,
    normalize_text,
    compute_stable_id,
    _dedup_score,
)
import inspect

print("compute_stable_id signature:", inspect.signature(compute_stable_id))
# --- the report's probe, verbatim
recs = [
    {
        "source_ref": "",
        "source_quote": "Be approved by the ISSM.",
        "description": "",
        "confidence": 0.7,
        "chunk_id": n,
        "section_title_path": [s],
    }
    for n, s in [(1, "Remote maintenance"), (2, "External connections")]
]
print(
    "probe: 2 records with different scopes ->", len(deduplicate_requirements(recs)), "after dedup"
)
print(
    "dedup score 0.7conf/200ch =",
    0.7 * 1000 - 200,
    " vs 0.6conf/20ch =",
    0.6 * 1000 - 20,
    "(shorter quote beats higher confidence)",
)

# --- prevalence on the 13 pinned runs: Step C output, grouped the way dedup keys them
man = json.load(open(str(_ROOT / "eval/spike_results/wp_44/manifest.json")))["documents"]
P = str(_config.load().processed_dir_path())
tot = merged_same = merged_cross = merged_cross_scope = 0
examples = []
for doc, m in man.items():
    d = f"{P}/{m['run_dir']}"
    chunks = {
        c["chunk_id"]: c
        for c in (json.loads(l) for l in open(glob.glob(d + "/*_chunks.jsonl")[0]) if l.strip())
    }
    reqs = [
        json.loads(l)
        for l in open(glob.glob(d + "/*_extracted_requirements.jsonl")[0])
        if l.strip()
    ]
    tot += len(reqs)
    groups = collections.defaultdict(list)
    for r in reqs:
        q = normalize_text(r.get("source_quote", ""))
        if q:
            groups[(r.get("source_ref", ""), q)].append(r)
    for (ref, q), g in groups.items():
        if len(g) < 2:
            continue
        cids = {r["chunk_id"] for r in g}
        extra = len(g) - 1
        if len(cids) == 1:
            merged_same += extra
        else:
            merged_cross += extra
            scopes = {tuple(chunks.get(c, {}).get("section_title_path") or []) for c in cids}
            if len(scopes) > 1:
                merged_cross_scope += extra
                if len(examples) < 6:
                    examples.append(
                        (
                            doc,
                            ref,
                            g[0]["source_quote"][:70],
                            sorted(cids),
                            [list(s)[-1:] for s in sorted(scopes)],
                        )
                    )
print(f"\nStep C records: {tot}")
print(
    f"records collapsed by dedup keys: same-chunk repeats={merged_same}, across chunks={merged_cross}, across chunks AND different section paths={merged_cross_scope}"
)
for e in examples:
    print("  e.g.", e)

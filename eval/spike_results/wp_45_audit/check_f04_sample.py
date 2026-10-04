"""F04: 16 random same-chunk stem attachments (seed 45) printed for hand labeling. Labels live in README.md."""

import glob
import json
import logging
import os
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
logging.disable(logging.CRITICAL)
from pipeline import enrich_requirements as E

man = json.load(open(_ROOT / "eval/spike_results/wp_44/manifest.json"))["documents"]
P = os.path.expanduser("~/documents/processed")
pairs = []
for doc, m in man.items():
    norm = glob.glob(f"{P}/{m['run_dir']}/*_requirements_normalized.jsonl")[0]
    sc, cb = E._load_reconstruction_sources(Path(norm))
    for line in open(norm):
        r = json.loads(line)
        q, cid = (r.get("source_quote") or "").strip(), r.get("chunk_id")
        if q and cid is not None and E._is_reconstruction_candidate(q):
            s = E._find_same_chunk_stem(q, cid, sc)
            if s:
                pairs.append((doc, cid, s, q))
random.seed(45)
print(f"same-chunk attachments: {len(pairs)}")
for i, (doc, cid, s, q) in enumerate(random.sample(pairs, 16), 1):
    print(f"{i:2d}. [{doc} c{cid}]\n    STEM : {s[:150]}\n    ITEM : {q[:150]}")

"""WP-45 audit verification (read-only). See eval/spike_results/wp_45_audit/README.md."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
"""F05 census: how many chunks contain items from more than one distinct section path? (offline Steps A+B only)"""
import sys
import json
import logging
import tempfile
import collections

pass
logging.disable(logging.CRITICAL)
from pathlib import Path

pass
from eval import step_d_replay as R
from pipeline import section_parser
from docling.chunking import HybridChunker

man = json.load(open(str(_ROOT / "eval/spike_results/wp_44/manifest.json")))["documents"]
tot_chunks = tot_multi = tot_tie = 0
print(f"{'document':18s} chunks multi-scope(distinct item section paths>1) equal-depth-tie")
for doc in man:
    pdf = R.RAW_PDFS / f"{doc}.pdf"
    if not pdf.exists():
        print(doc, "PDF missing")
        continue
    with tempfile.TemporaryDirectory() as tmp:
        res = section_parser.run(str(pdf), tmp)
        chunks = list(HybridChunker().chunk(res.doc))
    multi = tie = n = 0
    for c in chunks:
        body = [
            i
            for i in c.meta.doc_items
            if getattr(i, "self_ref", None) and res.item_ancestry.get(i.self_ref)
        ]
        paths = [tuple(res.item_ancestry[i.self_ref].get("section_title_path") or []) for i in body]
        n += 1
        if len(set(paths)) > 1:
            multi += 1
            depths = [len(p) for p in paths]
            if (
                depths.count(max(depths)) > 1
                and len({p for p in paths if len(p) == max(depths)}) > 1
            ):
                tie += 1
    tot_chunks += n
    tot_multi += multi
    tot_tie += tie
    print(f"{doc:18s} {n:6d} {multi:10d} {tie:10d}", flush=True)
print(
    f"TOTAL raw HybridChunker chunks={tot_chunks} multi-scope={tot_multi} ({tot_multi / tot_chunks:.1%}) equal-depth ties (last wins)={tot_tie}"
)

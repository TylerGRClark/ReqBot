"""WP-45 audit verification (read-only). See eval/spike_results/wp_45_audit/README.md."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
"""F01 repro with the REAL HybridChunker: does _chunk_raw_text undo the chunker's split of one oversized item?"""
import sys
import logging

pass
logging.disable(logging.CRITICAL)
from docling_core.types.doc import DoclingDocument, DocItemLabel
from docling.chunking import HybridChunker
from pipeline.chunk_text import _chunk_raw_text


def sent(i):
    return f"Requirement number {i}: the system owner shall review audit record number {i} within {i + 5} days and document the result in the log."


big = " ".join(sent(i) for i in range(1, 61))  # one long paragraph, ~60 sentences
doc = DoclingDocument(name="probe")
doc.add_heading(text="1. Audit Review", level=1)
doc.add_text(label=DocItemLabel.TEXT, text=big)
doc.add_text(
    label=DocItemLabel.TEXT,
    text="A short closing paragraph: reports shall be retained for three years.",
)
chunks = list(HybridChunker().chunk(doc))
print("chunks from HybridChunker:", len(chunks))
refs = [[getattr(i, "self_ref", None) for i in c.meta.doc_items] for c in chunks]
print("doc_items refs per chunk:", refs)
print("len(chunk.text) per chunk :", [len(c.text) for c in chunks])
raw = [_chunk_raw_text(c, doc, seen_table_refs=set()) for c in chunks]
print("len(raw_text) per chunk   :", [len(r) for r in raw])
print("full paragraph length     :", len(big))
dup = sum(1 for r in raw if len(r) >= len(big))
print(
    f"RESULT: {dup} of {len(chunks)} chunks carry the FULL paragraph text in raw_text ->",
    "F01 REPRODUCED with the real chunker" if dup > 1 else "not reproduced",
)

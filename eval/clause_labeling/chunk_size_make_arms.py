#!/usr/bin/env python3
"""Make the PREREG7 chunk files (arm A = merge_peers off at 1024 tokens; arm C = A plus lead-in glue) with the production chunking function. Scratch output only. No model.

    python3 eval/clause_labeling/chunk_size_make_arms.py --root ~/reqbot-work/scratch/chunk_size afi17-203 afi13-550 ...
Reads the cached Docling parses the PREREG6 driver used; writes <root>/runs/<arm>/<doc>/<doc>_chunks.jsonl and copies the ancestry file from the control folder.
"""
import argparse
import re
import shutil
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

import docling.chunking as dc  # noqa: E402
from docling_core.transforms.chunker.hierarchical_chunker import DocChunk, DocMeta  # noqa: E402
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer  # noqa: E402
from docling_core.types.doc import DoclingDocument  # noqa: E402

from core.profiles import default_profile  # noqa: E402
from pipeline import chunk_text as ct, section_parser as sp  # noqa: E402

CACHE = Path.home() / "reqbot-work/scratch/wp45_10_cache/d2.94.0/docs/baseline"
MAX_TOKENS = 1024
_LEAD = re.compile(r":(\s*\(T-\d\)\.?)?\s*$")
_ORIG = dc.HybridChunker


def make_tokenizer():
    return HuggingFaceTokenizer.from_pretrained(model_name="sentence-transformers/all-MiniLM-L6-v2", max_tokens=MAX_TOKENS)


def glue_lead_ins(chunks: list, tok) -> list:
    """Arm C: join a chunk that ends in a lead-in (a line ending in a colon) with the chunk after it, same headings, joined size within MAX_TOKENS. One glue, no chaining."""
    out, i = [], 0
    while i < len(chunks):
        a = chunks[i]
        last = next((ln for ln in reversed((a.text or "").split("\n")) if ln.strip()), "")
        if i + 1 < len(chunks) and _LEAD.search(last):
            b = chunks[i + 1]
            same = list(a.meta.headings or []) == list(b.meta.headings or [])
            joined = (a.text or "") + "\n" + (b.text or "")
            if same and tok.count_tokens(joined) <= MAX_TOKENS:
                meta = DocMeta(doc_items=list(a.meta.doc_items) + list(b.meta.doc_items), headings=a.meta.headings, captions=a.meta.captions, origin=a.meta.origin)
                out.append(DocChunk(text=joined, meta=meta))
                i += 2
                continue
        out.append(a)
        i += 1
    return out


def chunker_for(arm: str):
    tok = make_tokenizer()

    class Chunker:
        def __init__(self):
            self.inner = _ORIG(tokenizer=tok, merge_peers=False)

        def chunk(self, doc):
            chunks = list(self.inner.chunk(doc))
            return glue_lead_ins(chunks, tok) if arm == "C" else chunks
    return Chunker


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path.home() / "reqbot-work/scratch/chunk_size"))
    ap.add_argument("docs", nargs="+")
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    skips = list(default_profile().get("skip_sections") or [])
    for d in a.docs:
        p = CACHE / f"{d}.json"
        if not p.exists():
            p = root / f"parse_{d}/{d}.docling.json"
        doc = DoclingDocument.load_from_json(p)
        sections, item_anc, bodies, total = sp._parse_ancestry(doc)
        anc = sp.AncestryResult(ancestry_path="", sections=sections, item_ancestry=item_anc, section_bodies=bodies, doc=doc, heading_count=len(sections), total_items=total)
        for arm in ("A", "C"):
            out = root / "runs" / arm / d
            out.mkdir(parents=True, exist_ok=True)
            dc.HybridChunker = chunker_for(arm)
            try:
                ct.run_structure_aware(str(out / f"{d}_chunks.jsonl"), ancestry_result=anc, skip_sections=skips)
            finally:
                dc.HybridChunker = _ORIG
            shutil.copy2(root / "runs/control" / d / f"{d}_ancestry.json", out / f"{d}_ancestry.json")
            print(d, arm, sum(1 for _ in open(out / f"{d}_chunks.jsonl")), "chunks", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

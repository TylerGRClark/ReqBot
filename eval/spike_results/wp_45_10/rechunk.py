#!/usr/bin/env python3
"""WP-45.10 H1: re-chunk the cached baseline conversions at different HybridChunker token limits through the production chunking function (offline; no LLM).

  python3 rechunk.py --limit 256 --control     # default HybridChunker() vs an explicit 256-token chunker: must be identical
  python3 rechunk.py --limit 1024

The conversion is the cached baseline DoclingDocument, unchanged; only the chunker's `max_tokens` changes and the tokenizer stays the default
(sentence-transformers/all-MiniLM-L6-v2). The production function `pipeline.chunk_text.run_structure_aware` runs unmodified, so its ToC, empty-body and
skipped-section filters and its `raw_text` reconstruction apply. The ancestry map is built with the production helper on the loaded document.
"""

import argparse
import json
import sys
import warnings

import common

warnings.filterwarnings("ignore")

DEFAULT_TOKENIZER = "sentence-transformers/all-MiniLM-L6-v2"


def load_doc(name, variant="baseline"):
    from docling_core.types.doc import DoclingDocument
    return DoclingDocument.load_from_json(common.cache_dir("docs", variant) / f"{name}.json")


def ancestry_result(doc):
    from pipeline import section_parser as sp
    sections, item_ancestry, section_bodies, total_items = sp._parse_ancestry(doc)
    return sp.AncestryResult(ancestry_path="", sections=sections, item_ancestry=item_ancestry, section_bodies=section_bodies, doc=doc,
                             heading_count=len(sections), total_items=total_items)


def chunk(name, limit, out_path, variant="baseline", skip_sections=None):
    """Write the document's chunk records at `limit` tokens (None = Docling's own default HybridChunker()) and return the stats line."""
    import docling.chunking as dc
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
    from pipeline import chunk_text as ct
    original = dc.HybridChunker
    if limit is not None:
        tokenizer = HuggingFaceTokenizer.from_pretrained(model_name=DEFAULT_TOKENIZER, max_tokens=limit)
        dc.HybridChunker = lambda: original(tokenizer=tokenizer)
    try:
        ct.run_structure_aware(str(out_path), ancestry_result=ancestry_result(load_doc(name, variant)), skip_sections=skip_sections or [])
    finally:
        dc.HybridChunker = original
    return sum(1 for _ in open(out_path, encoding="utf-8"))


def skip_sections():
    from core.profiles import default_profile
    return list(default_profile().get("skip_sections") or [])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--default", action="store_true", help="chunk with this release's own default HybridChunker() into chunks/default (the upgrade comparison)")
    ap.add_argument("--control", action="store_true", help="also chunk with the default HybridChunker() and require identical records")
    ap.add_argument("--docs", nargs="*")
    args = ap.parse_args()
    if args.default == (args.limit is not None):
        raise SystemExit("give exactly one of --limit and --default")
    names = args.docs or sorted(common.pinned_documents())
    label = "default" if args.default else str(args.limit)
    out = common.cache_dir("chunks", label)
    common.check_manifest(out, label)
    skips = skip_sections()
    if args.default:
        for name in names:
            n = chunk(name, None, out / f"{name}_chunks.jsonl", skip_sections=skips)
            print(name, "default ->", n, "chunks", flush=True)
        return
    for name in names:
        target = out / f"{name}_chunks.jsonl"
        n = chunk(name, args.limit, target, skip_sections=skips)
        print(name, args.limit, "->", n, "chunks", flush=True)
        if args.control:
            ctrl = common.cache_dir("chunks", "control_default") / f"{name}_chunks.jsonl"
            chunk(name, None, ctrl, skip_sections=skips)
            same = target.read_text(encoding="utf-8") == ctrl.read_text(encoding="utf-8")
            print("  control (explicit 256 vs default HybridChunker()):", "IDENTICAL" if same else "DIFFERENT")
            if not same:
                sys.exit(1)


if __name__ == "__main__":
    main()

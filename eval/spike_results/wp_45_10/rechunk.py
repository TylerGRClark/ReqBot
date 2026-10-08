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
    directory = common.cache_dir("docs", variant, create=False)
    common.check_manifest(directory, variant)  # refuse a conversion written by a different dependency set
    return DoclingDocument.load_from_json(directory / f"{name}.json")


def ancestry_result(doc):
    from pipeline import section_parser as sp
    sections, item_ancestry, section_bodies, total_items = sp._parse_ancestry(doc)
    return sp.AncestryResult(ancestry_path="", sections=sections, item_ancestry=item_ancestry, section_bodies=section_bodies, doc=doc,
                             heading_count=len(sections), total_items=total_items)


def _resolving(original):
    """EXPLORATORY scratch variant (not production code, not a registered rule): merged chunks carry generic `DocItem` objects, so the production
    `_chunk_raw_text` cannot see which are tables or text; resolve each by its `self_ref` in the document to the real item before it runs."""
    def wrapper(chunk, doc=None, *, seen_table_refs=None):
        from docling_core.types.doc.document import RefItem
        try:
            chunk.meta.doc_items = [RefItem(cref=x.self_ref).resolve(doc) for x in chunk.meta.doc_items]
        except Exception:
            pass
        return original(chunk, doc, seen_table_refs=seen_table_refs)
    return wrapper


def chunk(name, limit, out_path, variant="baseline", skip_sections=None, resolve=False):
    """Write the document's chunk records at `limit` tokens (None = Docling's own default HybridChunker()) and return the stats line."""
    import docling.chunking as dc
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
    from pipeline import chunk_text as ct
    original = dc.HybridChunker
    original_raw = ct._chunk_raw_text
    if resolve:
        ct._chunk_raw_text = _resolving(original_raw)
    if limit is not None:
        tokenizer = HuggingFaceTokenizer.from_pretrained(model_name=DEFAULT_TOKENIZER, max_tokens=limit)
        dc.HybridChunker = lambda: original(tokenizer=tokenizer)
    try:
        ct.run_structure_aware(str(out_path), ancestry_result=ancestry_result(load_doc(name, variant)), skip_sections=skip_sections or [])
    finally:
        dc.HybridChunker = original
        ct._chunk_raw_text = original_raw
    return sum(1 for _ in open(out_path, encoding="utf-8"))


def skip_sections():
    from core.profiles import default_profile
    return list(default_profile().get("skip_sections") or [])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--resolve-items", action="store_true", help="EXPLORATORY: resolve generic chunk items to their real types before raw_text is built; outputs go to chunks/r<limit>")
    ap.add_argument("--label", help="name of the output folder under chunks/ (default: the limit, `r<limit>` or `default`); refuses a folder that already holds chunk files")
    ap.add_argument("--default", action="store_true", help="chunk with this release's own default HybridChunker() into chunks/default (the upgrade comparison)")
    ap.add_argument("--control", action="store_true", help="also chunk with the default HybridChunker() and require identical records")
    ap.add_argument("--docs", nargs="*")
    args = ap.parse_args()
    if args.default == (args.limit is not None):
        raise SystemExit("give exactly one of --limit and --default")
    names = args.docs or sorted(common.pinned_documents())
    label = args.label or ("default" if args.default else (("r" if args.resolve_items else "") + str(args.limit)))
    out = common.cache_dir("chunks", label)
    if args.label and any(out.glob("*_chunks.jsonl")):
        raise SystemExit(f"{out} already holds chunk files; choose another --label")
    common.check_manifest(out, label)
    skips = skip_sections()
    if args.default:
        for name in names:
            n = chunk(name, None, out / f"{name}_chunks.jsonl", skip_sections=skips)
            print(name, "default ->", n, "chunks", flush=True)
        return
    for name in names:
        target = out / f"{name}_chunks.jsonl"
        n = chunk(name, args.limit, target, skip_sections=skips, resolve=args.resolve_items)
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

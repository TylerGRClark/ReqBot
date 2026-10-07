#!/usr/bin/env python3
"""WP-45.10: convert the pinned documents with one Docling option changed per variant and cache each DoclingDocument as JSON (offline; no LLM).

  python3 convert.py --variant baseline            # DocumentConverter() exactly as production calls it
  python3 convert.py --variant no_ocr --docs afi17-203
  python3 convert.py --list

Each variant starts from the production converter's own PDF format option (a deep copy) and changes exactly one setting. A setting a release does not have is
reported as unavailable, never substituted. Existing cache files are skipped, so a run resumes. Run it with the interpreter of the Docling release under test.
"""

import argparse
import copy
import json
import sys
import time
import warnings

import common

warnings.filterwarnings("ignore")

VARIANTS = {
    "baseline": "DocumentConverter() with no options (what pipeline/section_parser.py calls)",
    "no_ocr": "do_ocr=False",
    "full_page_ocr": "ocr_options.force_full_page_ocr=True",
    "backend_text": "force_backend_text=True",
    "cells_off": "table_structure_options.do_cell_matching=False",
    "table_fast": "table_structure_options.mode=TableFormerMode.FAST",
}


def _mutate(options, variant):
    from docling.datamodel.pipeline_options import TableFormerMode
    if variant == "no_ocr":
        options.do_ocr = False
    elif variant == "full_page_ocr":
        options.ocr_options.force_full_page_ocr = True
    elif variant == "backend_text":
        if not hasattr(options, "force_backend_text"):
            raise AttributeError("force_backend_text")
        options.force_backend_text = True
    elif variant == "cells_off":
        options.table_structure_options.do_cell_matching = False
    elif variant == "table_fast":
        options.table_structure_options.mode = TableFormerMode.FAST
    elif variant != "baseline":
        raise SystemExit(f"unknown variant {variant!r}")


def converter(variant):
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter
    if variant == "baseline":
        return DocumentConverter()
    base = DocumentConverter()
    fmt = copy.deepcopy(base.format_to_options[InputFormat.PDF])
    _mutate(fmt.pipeline_options, variant)
    return DocumentConverter(format_options={InputFormat.PDF: fmt})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--variant")
    ap.add_argument("--docs", nargs="*", help="document names (default: all 13)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list or not args.variant:
        for k, v in VARIANTS.items():
            print(f"{k:14s} {v}")
        return
    problems = common.verify_pdfs()
    if problems:
        sys.exit("source PDFs differ from the pinned corpus:\n  " + "\n  ".join(problems))
    try:
        conv = converter(args.variant)
    except (AttributeError, ImportError) as exc:
        sys.exit(f"variant {args.variant} is unavailable in docling {common.versions()['docling']}: {exc}")
    out = common.cache_dir("docs", args.variant)
    (out / "_manifest.json").write_text(json.dumps({"variant": args.variant, "versions": common.versions()}, indent=1), encoding="utf-8")
    names = args.docs or sorted(common.pinned_documents())
    for name in names:
        target = out / f"{name}.json"
        if target.exists():
            print("skip", name)
            continue
        t0 = time.time()
        result = conv.convert(str(common.pdf_path(name)))
        result.document.save_as_json(target)
        meta = {"seconds": round(time.time() - t0, 1), "status": str(result.status), "pages": len(result.pages)}
        (out / f"{name}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        print(name, meta, flush=True)


if __name__ == "__main__":
    main()

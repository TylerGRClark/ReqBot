#!/usr/bin/env python3
"""Reference labels for a document, written at PDF-reading time (Step A) under a document style.

Under a style that has a reference grammar (doc_styles/outline-dod.json), every item the PDF
reader produced is labeled with the paragraph reference it sits under, in reading order, and the
labels are saved beside the document's other artifacts as `<doc>_references.json`
(core/reference_lookup.py). The checklist and the search index read that file later.

It runs at this stage because the reader's items still carry the document's own numbering (list
markers, heading numbers, enclosure headings); the stored chunk text has dropped most of it.

Standalone use, to label a document that is already ingested without re-running anything else:

    python3 pipeline/reference_labels.py --pdf raw_pdfs/"DODI 8410.03.pdf" \
        --run-dir ~/documents/processed/"DODI 8410.03_20261024_033314" --style outline-dod
"""

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core import reference_lookup  # noqa: E402
from core.doc_styles import load_style  # noqa: E402

log = logging.getLogger(__name__)


def items_from_docling(doc) -> list[dict]:
    """The reader's items in reading order as {kind, text, marker, page}. The list number the reader
    kept separately is the item's `marker`."""
    out = []
    for item, _level in doc.iterate_items():
        prov = getattr(item, "prov", None) or []
        out.append({
            "kind": reference_lookup.item_kind(getattr(item, "label", "")),
            "text": getattr(item, "text", "") or "",
            "marker": getattr(item, "marker", None) or "",
            "page": prov[0].page_no if prov else None,
        })
    return out


def write_for_document(doc, style: dict, out_dir: Path, doc_key: str) -> Path:
    """Label a Docling document under `style` and save `<doc_key>_references.json` in `out_dir`."""
    content = reference_lookup.build_sidecar(items_from_docling(doc), style)
    path = reference_lookup.sidecar_path(out_dir, doc_key)
    reference_lookup.write_sidecar(path, content)
    labeled = sum(1 for i in content["items"] if i["r"])
    log.info("Reference labels (%s): %d of %d items labeled -> %s", style["name"], labeled, len(content["items"]), path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write reference labels for a document under a document style.")
    parser.add_argument("--pdf", required=True, help="the document's PDF")
    parser.add_argument("--run-dir", required=True, help="the document's processed run folder")
    parser.add_argument("--style", required=True, help="document style name (doc_styles/<name>.json) with a reference grammar")
    parser.add_argument("--doc-key", default=None, help="artifact name prefix (default: the PDF's file name without .pdf)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    style = load_style(args.style)
    if not style.get("reference_grammar"):
        log.error("Document style '%s' has no reference grammar; nothing to label.", args.style)
        return 1
    from pipeline import section_parser
    pdf = Path(args.pdf).resolve()
    doc, _seconds = section_parser._run_docling(pdf, None)
    write_for_document(doc, style, Path(args.run_dir), args.doc_key or pdf.stem)
    return 0


if __name__ == "__main__":
    sys.exit(main())

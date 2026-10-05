"""WP-45.1(e): draw the page sample and cut it into pieces, then freeze both before any labeling.

Pages come from a seeded shuffle of each document's pages that have at least 60 words (PyMuPDF text), taking the first n, so a
later extension (a larger n) keeps every page already drawn. The frozen file records the seed, the full shuffle order, the PDF
and segmenter hashes, and every drawn page's pieces. `--check` recomputes and fails if anything differs from the frozen file.

Extension rule, fixed before labeling: if fewer than 60 obligations remain after adjudication, add the next shuffled page of
each document (n = 5) and keep the first four; never redraw. Three of the twelve drawn pages are front matter or a references
list (DODI 3 and 6, NIST 3), so a thin yield is possible.

Run from the repo root:
  python3 eval/spike_results/wp_45_1e/draw.py            # write outputs/pages_frozen.json (refuses to overwrite)
  python3 eval/spike_results/wp_45_1e/draw.py --check    # verify it
"""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import fitz  # noqa: E402
import segment as S  # noqa: E402

SEED = "wp45.1e"
PAGES_PER_DOC = 4
MIN_WORDS = 60
FROZEN = _HERE / "outputs" / "pages_frozen.json"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def eligible_pages(doc):
    """1-based page numbers with at least MIN_WORDS words of text."""
    return [i + 1 for i, page in enumerate(doc) if len(page.get_text().split()) >= MIN_WORDS]


def shuffle_order(pages, document, seed=SEED):
    order = sorted(pages)
    random.Random(f"{seed}/{document}").shuffle(order)
    return order


def build(pdf_dir, documents=tuple(S.DOC_CODES), n=PAGES_PER_DOC, seed=SEED):
    out = {
        "seed": seed,
        "pages_per_document": n,
        "min_words": MIN_WORDS,
        "segmenter_version": S.SEGMENTER_VERSION,
        "segmenter_sha256": sha256_bytes(Path(S.__file__).read_bytes()),
        "pymupdf": fitz.__doc__.split()[1] if fitz.__doc__ else "",
        "documents": {},
    }
    for document in documents:
        pdf = Path(pdf_dir) / f"{document}.pdf"
        doc = fitz.open(pdf)
        pages = eligible_pages(doc)
        order = shuffle_order(pages, document, seed)
        drawn = order[:n]
        entry = {
            "pdf_sha256": sha256_bytes(pdf.read_bytes()),
            "pages_in_pdf": len(doc),
            "eligible_pages": len(pages),
            "shuffle_order": order,
            "drawn": drawn,
            "pieces": {},
        }
        for page_number in drawn:
            pieces = S.segment_page(doc[page_number - 1])
            entry["pieces"][str(page_number)] = [
                {"id": S.piece_id(document, page_number, k), "text": t}
                for k, t in enumerate(pieces, 1)
            ]
        out["documents"][document] = entry
    texts = sorted(  # by id, so the hash does not depend on the order JSON keys are written in
        p["id"] + "\t" + p["text"]
        for e in out["documents"].values()
        for pg in e["pieces"].values()
        for p in pg
    )
    out["pieces_total"] = len(texts)
    out["pieces_sha256"] = sha256_bytes("\n".join(texts).encode("utf-8"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf-dir", default=str(_ROOT / "raw_pdfs"))
    ap.add_argument(
        "--check", action="store_true", help="verify the frozen file instead of writing it"
    )
    args = ap.parse_args()
    built = build(args.pdf_dir)
    text = json.dumps(built, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        if not FROZEN.exists():
            sys.exit(f"{FROZEN} does not exist")
        if FROZEN.read_text(encoding="utf-8") != text:
            sys.exit(
                "the recomputed draw differs from the frozen file (PDFs, segmenter or PyMuPDF changed)"
            )
        print(
            f"frozen draw verified: {built['pieces_total']} pieces, sha256 {built['pieces_sha256'][:16]}"
        )
        return
    if FROZEN.exists():
        sys.exit(f"{FROZEN} already exists; the draw is frozen. Use --check to verify it.")
    FROZEN.parent.mkdir(exist_ok=True)
    FROZEN.write_text(text, encoding="utf-8")
    drawn = {d: e["drawn"] for d, e in built["documents"].items()}
    print(json.dumps({"drawn": drawn, "pieces_total": built["pieces_total"]}, indent=1))


if __name__ == "__main__":
    main()

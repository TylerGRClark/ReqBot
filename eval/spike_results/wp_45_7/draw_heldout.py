"""WP-45.7: draw the held-out page set, close it over the chunks that discovery will run on, and freeze it before any labeling.

Rules fixed in docs/PHASE45_WP457_PLAN.md (sections 4.1 and 4.2) and in this docstring before anything is labeled:

- Documents: the ten pinned WP-45 documents that are not among the three development documents of WP-45.1(e), plus
  CNSSI No. 1253 (a control catalog; the plan requires that stratum and none of the pinned documents is one). CNSSI 1253 is
  not in the WP-44 manifest, so its chunks were produced by `pipeline/chunk_text.py` (Step B, no LLM) and are pinned here by
  sha256 together with the Docling versions; the draw stops if the file or the hash is missing or different.
- Pages: a page is eligible if it has at least 60 words of PyMuPDF text (the same rule as WP-45.1(e)). 16 pages are drawn:
  (1) one page from every document, the first of that document's seeded shuffle (11 pages);
  (2) one more catalog page, the second of CNSSI 1253's seeded shuffle (a catalog page is dense, so the stratum gets two);
  (3) two table pages, from pages touched by a chunk whose text holds a markdown table (at least six pipe characters),
      the first of a seeded shuffle across the non-catalog documents, not already drawn;
  (4) two more pages, the first of a seeded shuffle of every other eligible page of the non-catalog documents.
  Catalog documents are kept out of steps 3 and 4: 80 of CNSSI 1253's 121 chunks hold tables, so it would otherwise fill the
  table stratum and leave the policy and instruction documents' tables undrawn.
  (The first version of this script drew ten documents and 3 + 3 table and extra pages with no catalog; it was replaced
  before any labeling, after review of #212 pointed out the missing catalog stratum.)
  The seed is fixed below; nothing is redrawn. A later extension keeps every page already drawn.
- Chunks: discovery runs on every chunk whose page range touches a drawn page.
- Closure (plan 4.2): a chunk can span pages, so the labeled page set is every drawn page plus every page any selected chunk
  touches. All of those pages are cut into pieces and labeled; a record from a selected chunk then always lies in labeled text,
  and a drawn page that no chunk covers (the pipeline skipped it) is still labeled, so a loss before extraction stays visible.
  (Found at freeze time, before any labeling: the first version took only chunk-touched pages and left CJCSI 6510.02G page 27,
  which no chunk covers, unlabeled; the drawn pages were added to the rule and the draw regenerated, never edited by hand.)
- The pinned chunk files are checked against the WP-44 manifest hashes before anything is drawn.

Run from the repo root:
  python3 eval/spike_results/wp_45_7/draw_heldout.py            # write outputs/heldout_frozen.json (refuses to overwrite)
  python3 eval/spike_results/wp_45_7/draw_heldout.py --check    # verify it
"""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
_SEG_DIR = _ROOT / "eval/spike_results/wp_45_1e"
for _p in (_ROOT, _SEG_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import segment as S  # noqa: E402  (the WP-45.1(e) page cutter, reused unchanged)

SEED = "wp45.7-heldout"
MIN_WORDS = 60
TABLE_PIPES = 6
TABLE_PAGES = 2
EXTRA_PAGES = 2
CATALOG_EXTRA_PAGES = 1
CATALOG_DOCUMENTS = ("CNSSI_No1253",)
# Step B output for CNSSI 1253, produced with docling 2.94.0 / docling-core 2.99.0; filled in after the run.
CATALOG_CHUNKS_SHA256 = {
    "CNSSI_No1253": "41dd02157fc7751ef00baccd71310413104f98844f089325513e3c2bc6a46c9d",  # 121 chunks, 80 with tables
}
FROZEN = _HERE / "outputs" / "heldout_frozen.json"

# Short, unique ids for piece names; the three development documents are deliberately absent.
DOC_CODES = {
    "CJCSI 6510.02G": "CJCSI",
    "DODI 5200.01": "D5201",
    "DODI 5200.44": "D5244",
    "DODI 5200.48": "D5248",
    "DODI 8551.01": "D8551",
    "afi10-2402": "AFI102",
    "afi13-550": "AFI13",
    "afi17-203": "AFI17",
    "afpd_17-1": "AFPD",
    "dafman17-1305": "DAFM",
    "CNSSI_No1253": "CNSSI",
}
DEV_DOCUMENTS = ("DODI 8410.03", "afman17-2101", "NIST.SP.800-125")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def shuffled(items, key, seed=SEED):
    """A deterministic shuffle of the sorted items, keyed so that each draw step has its own order."""
    order = sorted(items)
    random.Random(f"{seed}/{key}").shuffle(order)
    return order


def piece_id(document, page_number, n):
    return f"{DOC_CODES[document]}-p{page_number:03d}-{n:03d}"


def table_pages(chunks):
    """Pages touched by any chunk that holds a markdown table."""
    pages = set()
    for c in chunks:
        if c["text"].count("|") >= TABLE_PIPES:
            pages.update(range(c["page_start"], c["page_end"] + 1))
    return pages


def select_pages(eligible, tables, seed=SEED, catalogs=()):
    """Return [(document, page, reason)] by the rule in the module docstring.

    eligible: {document: [page, ...]}; tables: {document: set of pages touched by a table chunk};
    catalogs: documents that get CATALOG_EXTRA_PAGES more pages from their own shuffle.
    """
    chosen = []
    taken = set()
    for document in sorted(eligible):
        if not eligible[document]:
            raise ValueError(f"{document} has no page with at least {MIN_WORDS} words; it cannot be drawn from")
        page = shuffled(eligible[document], f"per_document/{document}", seed)[0]
        chosen.append((document, page, "per_document"))
        taken.add((document, page))
    for document in sorted(catalogs):
        order = shuffled(eligible[document], f"per_document/{document}", seed)
        for page in order[1 : 1 + CATALOG_EXTRA_PAGES]:
            chosen.append((document, page, "catalog"))
            taken.add((document, page))
    plain = [d for d in sorted(eligible) if d not in catalogs]
    pool = [(d, p) for d in plain for p in eligible[d] if p in tables.get(d, ()) and (d, p) not in taken]
    for d, p in shuffled(pool, "table", seed)[:TABLE_PAGES]:
        chosen.append((d, p, "table"))
        taken.add((d, p))
    pool = [(d, p) for d in plain for p in eligible[d] if (d, p) not in taken]
    for d, p in shuffled(pool, "extra", seed)[:EXTRA_PAGES]:
        chosen.append((d, p, "extra"))
        taken.add((d, p))
    return chosen


def select_chunks(chunks, drawn_pages):
    """Ids of the chunks whose page range touches a drawn page."""
    drawn = set(drawn_pages)
    return sorted(
        c["chunk_id"] for c in chunks if drawn & set(range(c["page_start"], c["page_end"] + 1))
    )


def closed_pages(chunks, selected_ids, drawn_pages, pages_in_pdf):
    """The label set: every drawn page plus every page any selected chunk touches, within the PDF."""
    wanted = set(selected_ids)
    pages = set(drawn_pages)
    for c in chunks:
        if c["chunk_id"] in wanted:
            pages.update(range(c["page_start"], c["page_end"] + 1))
    return sorted(p for p in pages if 1 <= p <= pages_in_pdf)


def _version(package):
    from importlib import metadata

    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return ""


def _fitz():
    import fitz  # PyMuPDF: needed only to read the PDFs, not a project dependency

    return fitz


def _load_chunks(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _catalog_inputs():
    """Chunk files for the catalog documents (not in the WP-44 manifest): found by name, pinned by sha256."""
    from core import config as _config

    processed = _config.load().processed_dir_path()
    found, problems = {}, []
    for doc in CATALOG_DOCUMENTS:
        paths = sorted(processed.glob(f"{doc}_*/{doc}_chunks.jsonl"))
        if len(paths) != 1:
            problems.append(f"{doc}: expected exactly one chunk file under {processed}, found {len(paths)}")
            continue
        digest = sha256_bytes(paths[0].read_bytes())
        if digest != CATALOG_CHUNKS_SHA256[doc]:
            problems.append(f"{doc}: {paths[0]} has sha256 {digest}, pinned {CATALOG_CHUNKS_SHA256[doc]}")
            continue
        found[doc] = {"chunks": paths[0]}
    if problems:
        sys.exit("pinned catalog inputs are not usable, draw not run:\n  " + "\n  ".join(problems))
    return found


def build(pdf_dir, seed=SEED):
    assert not set(DOC_CODES) & set(DEV_DOCUMENTS)
    sys.path.insert(0, str(_ROOT / "eval/spike_results/wp_45_audit"))
    import _inputs  # the shared pinned-input check: stops if a chunk file is missing or changed

    inputs = _inputs.corpus_inputs("chunks")
    inputs.update(_catalog_inputs())
    fitz = _fitz()
    docs, chunks_by_doc, eligible, tables = {}, {}, {}, {}
    for document in sorted(DOC_CODES):
        pdf = Path(pdf_dir) / f"{document}.pdf"
        doc = fitz.open(pdf)
        docs[document] = (pdf, doc)
        chunks_by_doc[document] = _load_chunks(inputs[document]["chunks"])
        eligible[document] = [
            i + 1 for i, page in enumerate(doc) if len(page.get_text().split()) >= MIN_WORDS
        ]
        tables[document] = table_pages(chunks_by_doc[document]) & set(eligible[document])
    chosen = select_pages(eligible, tables, seed, catalogs=CATALOG_DOCUMENTS)
    out = {
        "seed": seed,
        "min_words": MIN_WORDS,
        "segmenter_version": S.SEGMENTER_VERSION,
        "segmenter_sha256": sha256_bytes(Path(S.__file__).read_bytes()),
        "pymupdf": fitz.__doc__.split()[1] if fitz.__doc__ else "",
        "catalog_chunk_provenance": {
            "documents": list(CATALOG_DOCUMENTS),
            "docling": _version("docling"),
            "docling_core": _version("docling-core"),
            "note": "Step B (pipeline/chunk_text.py) output, pinned by sha256 in CATALOG_CHUNKS_SHA256",
        },
        "documents": {},
    }
    for document in sorted(DOC_CODES):
        pdf, doc = docs[document]
        drawn = sorted((p, why) for d, p, why in chosen if d == document)
        drawn_pages = [p for p, _ in drawn]
        chunks = chunks_by_doc[document]
        selected = select_chunks(chunks, drawn_pages)
        closed = closed_pages(chunks, selected, drawn_pages, len(doc))
        entry = {
            "pdf_sha256": sha256_bytes(pdf.read_bytes()),
            "chunks_sha256": sha256_bytes(Path(inputs[document]["chunks"]).read_bytes()),
            "pages_in_pdf": len(doc),
            "eligible_pages": len(eligible[document]),
            "table_pages_eligible": sorted(tables[document]),
            "drawn": [{"page": p, "reason": why} for p, why in drawn],
            "selected_chunk_ids": selected,
            "closed_pages": closed,
            "pages_added_by_closure": [p for p in closed if p not in drawn_pages],
            "pieces": {},
        }
        for page_number in closed:
            pieces = S.segment_page(doc[page_number - 1])
            entry["pieces"][str(page_number)] = [
                {"id": piece_id(document, page_number, k), "text": t} for k, t in enumerate(pieces, 1)
            ]
        out["documents"][document] = entry
    texts = sorted(
        p["id"] + "\t" + p["text"]
        for e in out["documents"].values()
        for pg in e["pieces"].values()
        for p in pg
    )
    out["pages_drawn_total"] = sum(len(e["drawn"]) for e in out["documents"].values())
    out["pages_closed_total"] = sum(len(e["closed_pages"]) for e in out["documents"].values())
    out["pieces_total"] = len(texts)
    out["pieces_sha256"] = sha256_bytes("\n".join(texts).encode("utf-8"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf-dir", default=str(_ROOT / "raw_pdfs"))
    ap.add_argument("--check", action="store_true", help="verify the frozen file instead of writing it")
    args = ap.parse_args()
    built = build(args.pdf_dir)
    text = json.dumps(built, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        if not FROZEN.exists():
            sys.exit(f"{FROZEN} does not exist")
        if FROZEN.read_text(encoding="utf-8") != text:
            sys.exit("the recomputed draw differs from the frozen file (PDFs, chunks, segmenter or PyMuPDF changed)")
        print(f"frozen draw verified: {built['pieces_total']} pieces, sha256 {built['pieces_sha256'][:16]}")
        return
    if FROZEN.exists():
        sys.exit(f"{FROZEN} already exists; the draw is frozen. Use --check to verify it.")
    FROZEN.parent.mkdir(exist_ok=True)
    FROZEN.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "pages_drawn": built["pages_drawn_total"],
                "pages_closed": built["pages_closed_total"],
                "pieces_total": built["pieces_total"],
                "drawn": {d: [x["page"] for x in e["drawn"]] for d, e in built["documents"].items()},
                "added_by_closure": {
                    d: e["pages_added_by_closure"]
                    for d, e in built["documents"].items()
                    if e["pages_added_by_closure"]
                },
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()

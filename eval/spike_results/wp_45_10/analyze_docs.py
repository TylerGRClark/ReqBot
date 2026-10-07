#!/usr/bin/env python3
"""WP-45.10 H2, H3, H4: compare cached conversions against the baseline conversion of the same Docling release (offline; no LLM).

  python3 analyze_docs.py --variant no_ocr           # H2: text items present in one conversion and not the other
  python3 analyze_docs.py --variant cells_off        # H3: tables whose cell grid differs; the known table defects
  python3 analyze_docs.py --headings                 # H4: Docling's heading level against the numbering-based depth the pipeline uses
  python3 analyze_docs.py --across baseline          # upgrade: this release's baseline against another release's (--other-tag d2.135.0)

Reads `~/wp45_10_cache/<tag>/docs/<variant>/<doc>.json` written by convert.py. Every difference is counted and the first few are printed; the full list is
in the JSON output. Nothing here scores quality beyond what the labeled cases allow (see docs/PHASE45_WP4510_PLAN.md section 3).
"""

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

import common

CAPTION_PHRASE = "incident handling and support activities"  # afi17-203 Table 3.2: the caption merged into every header cell (docs/PHASE42_REQUIREMENTS.md)


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def load(tag, variant, name):
    from docling_core.types.doc import DoclingDocument
    return DoclingDocument.load_from_json(common.CACHE / tag / "docs" / variant / f"{name}.json")


def text_items(doc):
    return collections.Counter(norm(t.text) for t in doc.texts if norm(t.text))


def table_signatures(doc):
    sigs = []
    for t in doc.tables:
        grid = [[norm(c.text) for c in row] for row in (t.data.grid if t.data else [])]
        sigs.append(hashlib.sha256(json.dumps(grid).encode()).hexdigest()[:12])
    return sigs


def table_headers(doc):
    out = []
    for t in doc.tables:
        rows = t.data.grid if t.data else []
        out.append([norm(c.text) for c in rows[0]] if rows else [])
    return out


def no_grid_regions(doc):
    """Items labeled table that are not TableItems (no cell grid): the 'no table grid at all' defect of docs/PHASE42_REQUIREMENTS.md."""
    from docling_core.types.doc import TableItem
    n = 0
    for item, _level in doc.iterate_items():
        if getattr(item, "label", None) is not None and str(getattr(item.label, "value", item.label)) == "table" and not isinstance(item, TableItem):
            n += 1
    return n


def diff_counters(a, b):
    lost = sum((a - b).values())
    extra = sum((b - a).values())
    return lost, extra, list((a - b).elements())[:5], list((b - a).elements())[:5]


def compare(tag, variant, other_tag=None, other_variant=None):
    base_tag, v_tag, v_var = tag, other_tag or tag, other_variant or variant
    rows, totals = {}, collections.Counter()
    for name in sorted(common.pinned_documents()):
        base, var = load(base_tag, "baseline", name), load(v_tag, v_var, name)
        lost, extra, lost_ex, extra_ex = diff_counters(text_items(base), text_items(var))
        sb, sv = table_signatures(base), table_signatures(var)
        differing = sum(1 for x, y in zip(sb, sv) if x != y) if len(sb) == len(sv) else None
        hb, hv = table_headers(base), table_headers(var)
        caption_hdr = (sum(any(CAPTION_PHRASE in c.lower() for c in row) for row in hb), sum(any(CAPTION_PHRASE in c.lower() for c in row) for row in hv))
        rows[name] = {"text_items_lost": lost, "text_items_extra": extra, "lost_examples": lost_ex, "extra_examples": extra_ex,
                      "tables": (len(sb), len(sv)), "tables_with_different_grid": differing, "caption_in_header_tables": caption_hdr,
                      "no_grid_regions": (no_grid_regions(base), no_grid_regions(var))}
        totals["lost"] += lost
        totals["extra"] += extra
        totals["tables_differ"] += differing or 0
        totals["tables_count_mismatch"] += differing is None
        totals["caption_hdr_base"] += caption_hdr[0]
        totals["caption_hdr_var"] += caption_hdr[1]
        totals["nogrid_base"] += rows[name]["no_grid_regions"][0]
        totals["nogrid_var"] += rows[name]["no_grid_regions"][1]
    return rows, dict(totals)


def headings(tag):
    from pipeline import section_parser as sp
    from docling_core.types.doc import SectionHeaderItem
    out, total = {}, collections.Counter()
    for name in sorted(common.pinned_documents()):
        doc = load(tag, "baseline", name)
        agree = disagree = 0
        levels = collections.Counter()
        examples = []
        for item, level in doc.iterate_items():
            if not isinstance(item, SectionHeaderItem):
                continue
            est = sp._estimate_heading_depth(item.text or "")
            lv = getattr(item, "level", None)
            levels[lv] += 1
            if lv == est:
                agree += 1
            else:
                disagree += 1
                if len(examples) < 4:
                    examples.append({"text": norm(item.text)[:60], "docling_level": lv, "numbering_depth": est})
        out[name] = {"headings": agree + disagree, "agree": agree, "disagree": disagree, "docling_levels": dict(levels), "examples": examples}
        total["headings"] += agree + disagree
        total["agree"] += agree
        total["disagree"] += disagree
    return out, dict(total)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--variant")
    ap.add_argument("--headings", action="store_true")
    ap.add_argument("--across", help="compare this release's baseline to --other-tag's variant of this name")
    ap.add_argument("--other-tag")
    ap.add_argument("--out")
    args = ap.parse_args()
    tag = common.tag()
    if args.headings:
        rows, totals = headings(tag)
    elif args.across:
        rows, totals = compare(tag, args.across, other_tag=args.other_tag, other_variant=args.across)
    elif args.variant:
        rows, totals = compare(tag, args.variant)
    else:
        raise SystemExit("give --variant, --across or --headings")
    for name, r in rows.items():
        print(name, {k: v for k, v in r.items() if k not in ("lost_examples", "extra_examples", "examples", "docling_levels")})
    print("TOTALS", totals)
    if args.out:
        Path(common.HERE / args.out).write_text(json.dumps({"versions": common.versions(), "tag": tag, "rows": rows, "totals": totals}, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()

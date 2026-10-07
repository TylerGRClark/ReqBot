#!/usr/bin/env python3
"""WP-45.10 H2, H3, H4: compare cached conversions against the baseline conversion of the same Docling release (offline; no LLM).

  python3 analyze_docs.py --variant no_ocr           # H2: text items present in one conversion and not the other
  python3 analyze_docs.py --variant cells_off        # H3: tables whose cell grid differs; the known table defects
  python3 analyze_docs.py --headings                 # H4: Docling's heading level against the numbering-based depth the pipeline uses
  python3 analyze_docs.py --across baseline          # upgrade: this release's baseline against another release's (--other-tag d2.135.0)

Reads `~/wp45_10_cache/<tag>/docs/<variant>/<doc>.json` written by convert.py. Every difference is counted and kept in full in the JSON output (`--out`). Nothing here scores quality beyond what the labeled cases allow (see docs/PHASE45_WP4510_PLAN.md section 3).
"""

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

import common

# afi17-203 Table 3.2 (page 20): Docling's table model merges the table's caption sentence into the column headers (docs/PHASE42_REQUIREMENTS.md). The first
# detector looked for the table's title and found 0 in every release, which did not reproduce the documented defect; checking the 2.94.0 table showed the merged
# text is the caption sentence below, in the dataframe column headers. This is the corrected detector (changed after reading the first output, disclosed in the
# results).
CAPTION_PHRASE = "this table presents the relationship between the ongoing support activities"


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
    """Per table: the first grid row's cells plus the dataframe column headers (where the caption merge shows)."""
    out = []
    for t in doc.tables:
        rows = t.data.grid if t.data else []
        cells = [norm(c.text) for c in rows[0]] if rows else []
        try:
            cells += [str(c) for c in t.export_to_dataframe(doc).columns] if t.data and t.data.table_cells else []
        except Exception:
            pass
        out.append(cells)
    return out


def label_profile(doc):
    """Item counts by label, and the characters held in `code` items (a legal-policy document has no code; a large share points to mis-labeled prose)."""
    counts = collections.Counter(str(t.label.value) for t in doc.texts)
    code_chars = sum(len(t.text) for t in doc.texts if str(t.label.value) == "code")
    return {"counts": dict(counts), "code_items": counts.get("code", 0), "code_chars": code_chars, "text_chars": sum(len(t.text) for t in doc.texts)}


def no_grid_regions(doc):
    """Items labeled table that are not TableItems (no cell grid): the 'no table grid at all' defect of docs/PHASE42_REQUIREMENTS.md."""
    from docling_core.types.doc import TableItem
    n = 0
    for item, _level in doc.iterate_items():
        if getattr(item, "label", None) is None or str(getattr(item.label, "value", item.label)) != "table":
            continue
        if not isinstance(item, TableItem) or not (item.data and item.data.table_cells):
            n += 1
    return n


def text_shingles(doc, n=6):
    """Word n-gram multiset of the document's text items in reading order: a measure that does not depend on how a release splits paragraphs into items."""
    # alphanumeric words only: the first version split on whitespace and counted "release ." (2.94.0) and "release." (2.135.0) as different text, which is
    # spacing, not content (changed after reading the first output; disclosed in the results)
    words = re.findall(r"\w+", " ".join(norm(t.text).lower() for t in doc.texts if norm(t.text)))
    return collections.Counter(tuple(words[i:i + n]) for i in range(max(0, len(words) - n + 1)))


def shingle_diff(a, b):
    lost = sum(max(0, v - b.get(k, 0)) for k, v in a.items())
    extra = sum(max(0, v - a.get(k, 0)) for k, v in b.items())
    absent = sum(v for k, v in a.items() if k not in b)
    total = sum(a.values())
    return {"base": total, "lost": lost, "lost_share": round(lost / total, 5) if total else 0.0, "absent_entirely": absent, "extra": extra,
            "extra_share": round(extra / total, 5) if total else 0.0}


def diff_counters(a, b):
    lost = sum((a - b).values())
    extra = sum((b - a).values())
    return lost, extra, sorted((a - b).elements()), sorted((b - a).elements())  # every difference, never a sample


def compare(tag, variant, other_tag=None, other_variant=None):
    base_tag, v_tag, v_var = tag, other_tag or tag, other_variant or variant
    rows, totals = {}, collections.Counter()
    for name in sorted(common.pinned_documents()):
        base, var = load(base_tag, "baseline", name), load(v_tag, v_var, name)
        lost, extra, lost_all, extra_all = diff_counters(text_items(base), text_items(var))
        shingles = shingle_diff(text_shingles(base), text_shingles(var))
        sb, sv = table_signatures(base), table_signatures(var)
        differing = sum(1 for x, y in zip(sb, sv) if x != y) if len(sb) == len(sv) else None
        hb, hv = table_headers(base), table_headers(var)
        caption_hdr = (sum(any(CAPTION_PHRASE in c.lower() for c in row) for row in hb), sum(any(CAPTION_PHRASE in c.lower() for c in row) for row in hv))
        lp = (label_profile(base), label_profile(var))
        base_items = sum(text_items(base).values())
        rows[name] = {"text_items_base": base_items, "text_items_lost_share": round(lost / base_items, 5) if base_items else 0.0, "code_items": (lp[0]["code_items"], lp[1]["code_items"]), "code_share_of_chars": (round(lp[0]["code_chars"] / lp[0]["text_chars"], 3), round(lp[1]["code_chars"] / lp[1]["text_chars"], 3)),
                      "list_items": (lp[0]["counts"].get("list_item", 0), lp[1]["counts"].get("list_item", 0)), "text_items_lost": lost, "text_items_extra": extra, "text_6gram": shingles, "lost_items": lost_all, "extra_items": extra_all,
                      "tables": (len(sb), len(sv)), "tables_with_different_grid": differing, "caption_in_header_tables": caption_hdr,
                      "no_grid_regions": (no_grid_regions(base), no_grid_regions(var))}
        for k in ("base", "lost", "absent_entirely", "extra"):
            totals["sh_" + k] += shingles[k]
        totals["code_items_base"] += lp[0]["code_items"]
        totals["code_items_var"] += lp[1]["code_items"]
        totals["list_items_base"] += lp[0]["counts"].get("list_item", 0)
        totals["list_items_var"] += lp[1]["counts"].get("list_item", 0)
        totals["text_items_base"] += base_items
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
    if args.across and not args.other_tag:
        raise SystemExit("--across needs --other-tag (otherwise a release is compared with itself)")
    if args.across and args.other_tag == tag:
        raise SystemExit("--other-tag is this release's own tag")
    if args.headings:
        rows, totals = headings(tag)
    elif args.across:
        rows, totals = compare(tag, args.across, other_tag=args.other_tag, other_variant=args.across)
    elif args.variant:
        rows, totals = compare(tag, args.variant)
    else:
        raise SystemExit("give --variant, --across or --headings")
    for name, r in rows.items():
        print(name, {k: v for k, v in r.items() if k not in ("lost_items", "extra_items", "examples", "docling_levels", "text_items_lost", "text_items_extra")})
    print("TOTALS", totals)
    if args.out:
        Path(common.HERE / args.out).write_text(json.dumps({"versions": common.versions(), "tag": tag, "rows": rows, "totals": totals}, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()

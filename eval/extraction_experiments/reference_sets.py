"""Read a hand-written checklist workbook (for example an IG unit checklist) into plain records for coverage scoring.

Different workbooks name their columns differently, so a column is found by header text, not position. Only what scoring needs is kept: the question
text, the publication and paragraph it cites, and the tier when the sheet has one. The workbooks themselves are internal work product: keep them
and any output of this module outside the repository.

    python3 eval/extraction_experiments/reference_sets.py <workbook.xlsx> [--out records.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

_TEXT_HEADERS = ("requirement", "description", "question", "item description")
_REF_HEADERS = ("reference", "references", "ref", "citation")
_PARA_HEADERS = ("paragraph", "para")
_TIER_HEADERS = ("tier",)
_PUB = re.compile(
    r"(?<![A-Za-z])(DoDI|DoDM|DoDD|DAFI|DAFMAN|DAFPAM|DAFPD|DAFH|DAFVA|AFI|AFMAN|AFPD|AFPAM|AFH|CJCSI|CNSSI|AFTTP)\s?-?\s?(\d{1,4}(?:[-.]\d{1,4})?(?:V\d)?)(?!\d)",
    re.IGNORECASE,
)


def _norm(h) -> str:
    return re.sub(r"[^a-z ]", "", str(h or "").lower()).strip()


def _find(headers: list[str], wanted: tuple) -> int | None:
    for want in wanted:
        for i, h in enumerate(headers):
            if h == want or h.startswith(want):
                return i
    return None


def publication_keys(reference: str) -> list[str]:
    """Normalized publication names found in a citation cell, e.g. "DoDI 5200.48_DAFI16-1403 Para. 3.3e" -> ["DAFI16-1403"]."""
    found = []
    for series, number in _PUB.findall(reference or ""):
        key = f"{series.upper()}{number.upper()}".replace(" ", "")
        if key not in found:
            found.append(key)
    return found


def read_workbook(path: Path) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    records = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        header_at = next((i for i, r in enumerate(rows[:6]) if r and _find([_norm(c) for c in r], _TEXT_HEADERS) is not None), None)
        if header_at is None:
            continue
        headers = [_norm(c) for c in rows[header_at]]
        t, r, p, tier = (_find(headers, h) for h in (_TEXT_HEADERS, _REF_HEADERS, _PARA_HEADERS, _TIER_HEADERS))
        for row in rows[header_at + 1:]:
            text = str(row[t] or "").strip() if t is not None and t < len(row) else ""
            if not text:
                continue
            ref = str(row[r] or "").strip() if r is not None and r < len(row) else ""
            records.append({
                "sheet": ws.title,
                "text": text,
                "reference": ref,
                "publications": publication_keys(ref),
                "paragraph": str(row[p] or "").strip() if p is not None and p < len(row) else "",
                "tier": str(row[tier] or "").strip() if tier is not None and tier < len(row) else "",
            })
    return records


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("workbook")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    records = read_workbook(Path(args.workbook).expanduser())
    text = json.dumps(records, indent=1, ensure_ascii=False)
    if args.out:
        Path(args.out).expanduser().write_text(text, encoding="utf-8")
        print(f"{len(records)} records written to {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

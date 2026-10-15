import importlib.util
import sys
from pathlib import Path

import openpyxl
import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval" / "extraction_experiments"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


reference_sets = _load("reference_sets")
coverage = _load("coverage")


def _workbook(path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CUI"
    ws.append(["Item", "Program Area", "Requirement", "Reference", "Status (Y/N/N/A)", "Comments"])
    ws.append([1, "CUI", "Has the commander ensured CUI is destroyed?", "DoDI5200.48_DAFI16-1403 Ch. 4 Para. 4.5", None, None])
    ws.append([2, "CUI", "", "DoDI 5200.48 Para. 3.6", None, None])  # no text: skipped
    ws2 = wb.create_sheet("Tiers")
    ws2.append(["Item #", "Description", "Reference", "Paragraph", "Tier"])
    ws2.append([1, "Has an AO been assigned?", "AFI 17-101", "3.3", "Tier 0"])
    wb.save(path)
    return path


def test_columns_are_found_by_header_text_on_every_sheet(tmp_path):
    records = reference_sets.read_workbook(_workbook(tmp_path / "w.xlsx"))
    assert records == [
        {"sheet": "CUI", "text": "Has the commander ensured CUI is destroyed?", "reference": "DoDI5200.48_DAFI16-1403 Ch. 4 Para. 4.5",
         "publications": ["DODI5200.48", "DAFI16-1403"], "paragraph": "", "tier": ""},
        {"sheet": "Tiers", "text": "Has an AO been assigned?", "reference": "AFI 17-101", "publications": ["AFI17-101"], "paragraph": "3.3", "tier": "Tier 0"},
    ]


@pytest.mark.parametrize("cell,expected", [
    ("DAFMAN 16-1404 Vols 1-3", ["DAFMAN16-1404"]),
    ("DoDM5200.01V1_DAFMAN16-1404V1 Ch. 7", ["DODM5200.01V1", "DAFMAN16-1404V1"]),
    ("RAT TASK ORD 3 3.C.1.B.", []),
])
def test_publication_keys(cell, expected):
    assert reference_sets.publication_keys(cell) == expected


def test_packets_keep_only_the_publication_and_hide_nothing_about_the_pool_but_its_origin():
    records = [
        {"text": "Q about CUI", "publications": ["DODI5200.48"], "tier": "", "paragraph": "3.4"},
        {"text": "Q about AFI", "publications": ["AFI17-101"], "tier": "Tier 0", "paragraph": "3.3"},
    ]
    packets = coverage.build_packets(records, "afi17-101", ["Is A done?", "", "null", "Is B done?"])
    assert [t["text"] for t in packets["theirs"]] == ["Q about AFI"] and packets["theirs"][0]["id"] == "T01"
    assert sorted(q["text"] for q in packets["pool"]) == ["Is A done?", "Is B done?"]
    assert [q["id"] for q in packets["pool"]] == ["Q001", "Q002"]


def test_scoring_counts_strict_lenient_and_misses():
    a = [{"id": "T01", "verdict": "yes"}, {"id": "T02", "verdict": "yes"}, {"id": "T03", "verdict": "partial"}, {"id": "T04", "verdict": "no"}]
    b = [{"id": "T01", "verdict": "yes"}, {"id": "T02", "verdict": "partial"}, {"id": "T03", "verdict": "partial"}, {"id": "T04", "verdict": "no"}]
    got = coverage.combine(a, b)
    assert (got["items"], got["strict_covered"], got["lenient_covered"], got["both_no"], got["labelers_agree"]) == (4, 1, 3, 1, 3)
    assert got["pairs"] == {"no/no": 1, "partial/partial": 1, "partial/yes": 1, "yes/yes": 1}


def test_scoring_rejects_a_verdict_it_does_not_know():
    with pytest.raises(ValueError):
        coverage.combine([{"id": "T01", "verdict": "maybe"}], [{"id": "T01", "verdict": "yes"}])

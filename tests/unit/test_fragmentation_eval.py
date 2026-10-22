"""The fragmentation counter (eval/clause_labeling/fragmentation.py): hand-written rows and expected counts."""
import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("fragmentation", Path(__file__).resolve().parents[2] / "eval" / "clause_labeling" / "fragmentation.py")
frag = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(frag)

EXACT = {"anchor_status": "exact"}
LEAD = {"anchor_status": "lead_in_joined", "explained_parts": [{"kind": "lead_in", "text": "The CFP will:"}, {"kind": "sentence", "text": "notify the MCCC."}]}


def test_whole_sentence_is_clean():
    f = frag.classify_row("The CFP shall notify the servicing MCCC within 24 hours.", "The CFP shall notify the servicing MCCC within 24 hours.", EXACT)
    assert not any(f.values())


def test_short_lower_case_scrap():
    f = frag.classify_row("and report it", "and report it", EXACT)
    assert f["F2"] and f["F4"] and f["F6"] and f["F7"]
    assert not (f["F3"] or f["F5"] or f["F8"] or f["F9"])


def test_mid_sentence_but_long_is_not_f4():
    text = "and the unit shall report every incident to the servicing center within one day."
    f = frag.classify_row(text, text, EXACT)
    assert f["F2"] and not f["F4"] and f["F6"]  # lower-case start is also "not a complete sentence"


def test_list_scrap_without_lead_in_versus_with_lead_in():
    assert frag.classify_row("(a) Notify the MCCC.", "(a) Notify the MCCC.", EXACT)["F3"]
    with_lead = frag.classify_row("The CFP will: notify the MCCC.", "(a) notify the MCCC.", LEAD)
    assert not with_lead["F3"] and with_lead["F9"] and with_lead["F8"]


def test_table_line_and_non_exact_anchor_and_missing_anchor():
    assert frag.classify_row("AC-2 | Account Management | Moderate", "x", EXACT)["F5"]
    assert frag.classify_row("Do this thing now.", "Do this thing now.", {"anchor_status": "fuzzy"})["F8"]
    assert frag.classify_row("Do this thing now.", "Do this thing now.", {})["F8"]


def test_count_document_hand_counted():
    checklist = {
        "items": [
            {"requirement_ids": ["a"], "source_quote": "The CFP shall notify the servicing MCCC within 24 hours.", "extracted_quote": ""},
            {"requirement_ids": ["b"], "source_quote": "and report it", "extracted_quote": "and report it"},
            {"requirement_ids": [], "source_quote": "Reports are filed daily by the unit.", "extracted_quote": ""},
        ],
        "possible_missed": [{}, {}],
    }
    records = {"a": EXACT, "b": {"anchor_status": "words_trimmed"}}
    c = frag.count_document(checklist, records)
    assert c == {"F1": 2, "F2": 1, "F3": 0, "F4": 1, "F5": 0, "F6": 1, "F7": 1, "F8": 1, "F9": 0, "F10_text_scan": 1, "F10_possible_missed": 2}


def test_main_json_on_a_small_library(tmp_path, monkeypatch, capsys):
    run_dir = tmp_path / "doc1_20261001_000000"
    run_dir.mkdir()
    rec = {"requirement_id": "r1", "document_id": "doc1", "source_pdf": "doc1.pdf", "source_quote": "The CFP shall notify the servicing MCCC within 24 hours.", "anchor_status": "exact", "chunk_id": 0}
    (run_dir / "doc1_requirements_normalized.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    assert frag.main(["--processed-dir", str(tmp_path), "--doc", "doc1", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["totals"]["F1"] == 1 and out["totals"]["F8"] == 0 and out["totals"]["F6"] == 0
    assert frag.main(["--processed-dir", str(tmp_path), "--doc", "nope"]) == 1

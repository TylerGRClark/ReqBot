import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    folder = ROOT / "eval/spike_results/wp_45_8"
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location("shadow_run", folder / "shadow_run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["shadow_run"] = mod
    spec.loader.exec_module(mod)
    return mod


SH = _load()


def test_the_attached_string_is_actor_then_parent_joined_by_a_bar():
    assert SH.attach_string("The Director", "The Director shall:") == "The Director | The Director shall:"
    assert SH.attach_string("", "The Director shall:") == "The Director shall:"
    assert SH.attach_string(None, None) == ""


def test_newest_run_of_each_document_is_chosen(tmp_path):
    for name in ("DODI 5200.01_20260730_215412", "DODI 5200.01_20260802_010101", "afi17-203_20260730_215609", "not_a_run", "stray.txt"):
        (tmp_path / name).mkdir() if "." not in name or name.startswith("DODI") else (tmp_path / name).write_text("x")
    best = SH.newest_runs(tmp_path)
    assert best["DODI 5200.01"].name == "DODI 5200.01_20260802_010101" and best["afi17-203"].name.startswith("afi17-203")
    assert "not" not in best


def _docs():
    chunk = {"chunk_id": 1, "text": "Heading\nThe Director shall: (a) report.", "raw_text": "(a) report.", "breadcrumb": "Heading"}
    recs = [
        {"requirement_id": "r1", "chunk_id": 1, "source_quote": "(a) report.", "parent_stem": ""},
        {"requirement_id": "r2", "chunk_id": None, "source_quote": "x shall y", "parent_stem": "old stem"},
        {"requirement_id": "r3", "chunk_id": 9, "source_quote": "x shall y", "parent_stem": ""},
        {"requirement_id": "r4", "chunk_id": 1, "source_quote": "  ", "parent_stem": ""},
    ]
    return {"D": {"chunks": {1: chunk, 2: {"chunk_id": 2, "text": "", "raw_text": ""}}, "step": {}, "records": recs, "dir": "x"}}


def test_records_without_a_usable_chunk_or_quote_are_flagged_not_sent_and_not_dropped(tmp_path):
    docs = _docs()
    cands, skipped = SH.candidates_from(docs)
    assert [c["candidate_id"] for c in cands] == ["r1"]
    assert {s["requirement_id"]: s["reason"] for s in skipped} == {"r2": "no chunk id", "r3": "chunk not found", "r4": "no quote"}
    ledger = tmp_path / "resolver.jsonl"
    ledger.write_text(json.dumps({"document": "D", "candidate_id": "r1", "status": "complete", "issues": [],
                                  "answer": {"status": {"value": "obligation"}, "actor": {"value": "The Director"}, "parent": {"value": "The Director shall:"}}}) + "\n")
    rows = SH.shadow_rows(docs, ledger)
    assert len(rows) == 4
    assert rows[0]["resolver_string"] == "The Director | The Director shall:" and rows[0]["flag"] is None
    assert all(r["flag"] and r["resolver_string"] == "" for r in rows[1:])
    assert [SH.route(r) for r in rows] == ["production none -> resolver some", "no resolver answer", "no resolver answer", "no resolver answer"]


def test_a_span_that_is_not_in_the_document_is_reported():
    docs = _docs()
    rows = [{"document": "D", "requirement_id": "a", "actor": "The Director", "parent": "Heading"}, {"document": "D", "requirement_id": "b", "actor": "The Secretary", "parent": ""}]
    bad = SH.substring_failures(rows, docs)
    assert [(b["requirement_id"], b["field"]) for b in bad] == [("b", "actor")]


def test_routes_compare_production_and_resolver_stems():
    row = lambda p, r, flag=None: {"production_stem": p, "resolver_string": r, "flag": flag}  # noqa: E731
    assert SH.route(row("", "A")) == "production none -> resolver some"
    assert SH.route(row("A", "")) == "production some -> resolver none"
    assert SH.route(row("A", "a")) == "same" and SH.route(row("A", "B")) == "both some, different" and SH.route(row("", "")) == "both none"

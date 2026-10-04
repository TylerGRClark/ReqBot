"""WP-45.1(b): the audit pack builder's pure functions and the label checker.

The builder needs the 13 pinned documents to run for real, so these tests cover what does not: how a card shows a
chunk (marking, windowing), the seeded stratified draw (determinism, exclusion, hard stops), and every way
check_labels.py must reject a label file. eval/ scripts are loaded by path, as they are run.
"""

import importlib.util
import json
import logging
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_WP = _ROOT / "eval/spike_results/wp_45_1"


def _load(name, path):
    # census.py calls logging.disable(CRITICAL) at import; put logging back so other tests keep their caplog.
    previous = logging.root.manager.disable
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        logging.disable(previous)
    return module


@pytest.fixture(scope="module")
def pack():
    return _load("wp45_audit_pack", _WP / "audit_pack.py")


@pytest.fixture(scope="module")
def checker():
    return _load("wp45_check_labels", _WP / "audit_pack/check_labels.py")


# --- builder ---------------------------------------------------------------------------------------------------


def test_stratum_names(pack):
    assert pack.stratum_of("same-chunk", True) == "same-chunk"
    assert pack.stratum_of("heading", False) == "heading"
    assert pack.stratum_of("none", True) == "none+signal"
    assert pack.stratum_of("none", False) == "none+nosignal"
    assert pack.stratum_of("not-a-candidate", True) == "not-a-candidate+signal"


def test_show_chunk_marks_the_quote_across_whitespace_differences(pack):
    note, text = pack.show_chunk(
        "Intro.\nThe  CIO shall\nreview logs.  Next.", "The CIO shall review logs."
    )
    assert note == ""
    assert f"{pack.MARK_OPEN}The  CIO shall\nreview logs.{pack.MARK_CLOSE}" in text


def test_show_chunk_says_so_when_the_quote_is_not_in_the_chunk(pack):
    note, text = pack.show_chunk("Something else entirely.", "A reworded requirement.")
    assert "does not appear verbatim" in note
    assert pack.MARK_OPEN not in text


def test_show_chunk_windows_a_long_chunk_around_the_quote(pack):
    body = (
        ("filler words here. " * 400) + "The CIO shall review logs. " + ("more filler text. " * 400)
    )
    note, text = pack.show_chunk(body, "The CIO shall review logs.")
    assert f"{pack.MARK_OPEN}The CIO shall review logs.{pack.MARK_CLOSE}" in text
    assert "characters omitted" in text
    assert len(text) < len(body) / 2


def test_show_chunk_refuses_to_alter_text_that_contains_the_markers(pack):
    with pytest.raises(SystemExit):
        pack.show_chunk(f"text with {pack.MARK_OPEN} inside", "text")


def _rows(strata):
    rows, i = [], 0
    for stratum, n in strata.items():
        for _ in range(n):
            rows.append({"stratum": stratum, "index": i})
            i += 1
    return rows


@pytest.fixture
def small_design(pack, monkeypatch):
    population = {"a": 10, "b": 6}
    monkeypatch.setattr(pack, "POPULATION", population)
    monkeypatch.setattr(pack, "SAMPLE", {"a": 4, "b": 2})
    return population


def test_draw_is_deterministic_and_respects_sizes_and_exclusions(pack, small_design):
    first = pack.draw(_rows(small_design), excluded={0, 1})
    second = pack.draw(_rows(small_design), excluded={0, 1})
    assert [r["index"] for r in first] == [r["index"] for r in second]
    assert [r["id"] for r in first] == [f"R{n:03d}" for n in range(1, 7)]
    assert (
        sum(r["stratum"] == "a" for r in first) == 4
        and sum(r["stratum"] == "b" for r in first) == 2
    )
    assert not {0, 1} & {r["index"] for r in first}


def test_draw_can_be_extended_without_a_redraw(pack, small_design, monkeypatch):
    small = {
        r["index"] for r in pack.draw(_rows(small_design), excluded=set()) if r["stratum"] == "a"
    }
    monkeypatch.setattr(pack, "SAMPLE", {"a": 6, "b": 2})
    larger = {
        r["index"] for r in pack.draw(_rows(small_design), excluded=set()) if r["stratum"] == "a"
    }
    assert small < larger


def test_draw_stops_when_a_stratum_population_changes(pack, small_design):
    with pytest.raises(SystemExit):
        pack.draw(_rows({"a": 9, "b": 6}), excluded=set())


def test_draw_stops_when_a_stratum_has_too_few_eligible_records(pack, small_design):
    with pytest.raises(SystemExit):
        pack.draw(_rows(small_design), excluded=set(range(8)))  # leaves 2 of stratum a, sample is 4


def test_draw_stops_on_a_stratum_it_has_no_design_for(pack, small_design):
    rows = _rows(small_design) + [{"stratum": "zzz", "index": 99, "method": "zzz"}]
    with pytest.raises(SystemExit, match="unexpected stratum"):
        pack.draw(rows, excluded=set())


def test_require_chunks_stops_on_a_missing_chunk(pack):
    pack.require_chunks([{"chunk": {"text": "x"}}])
    with pytest.raises(SystemExit):
        pack.require_chunks(
            [{"chunk": None, "chunk_id": 3, "document": "d", "requirement_id": "REQ-1"}]
        )


# --- label checker ---------------------------------------------------------------------------------------------


def _pack_dir(tmp_path, ids_a=("R001", "R002", "R003"), ids_b=("R001", "R003"), eol="\n"):
    for name, ids in (("pack_a.md", ids_a), ("pack_b.md", ids_b)):
        text = "# pass\n\n" + "".join(f"## {i}\nbody{eol}{eol}" for i in ids)
        (tmp_path / name).write_bytes(text.replace("\n", eol).encode())
    return tmp_path


def _write(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def _a(**over):
    base = {"standalone": "complete", "lead_in_location": None, "lead_in_text": None, "note": ""}
    return {**base, **over}


GOOD_A = [
    {
        "id": "R001",
        **_a(standalone="needs_lead_in", lead_in_location="same_chunk", lead_in_text="The PM:"),
    },
    {"id": "R002", **_a()},
    {"id": "R003", **_a(standalone="needs_lead_in", lead_in_location="not_shown")},
]
GOOD_B = [
    {"id": "R001", "stem_verdict": "right", "note": ""},
    {"id": "R003", "stem_verdict": "wrong_sibling", "note": ""},
]


def test_valid_labels_pass(checker, tmp_path):
    d = _pack_dir(tmp_path)
    a, b = _write(tmp_path / "a.jsonl", GOOD_A), _write(tmp_path / "b.jsonl", GOOD_B)
    assert checker.check(d, a, b) == []
    assert checker.check(d, a, None) == []


def test_crlf_pack_files_are_read(checker, tmp_path):
    d = _pack_dir(tmp_path, eol="\r\n")
    assert checker.card_ids(d / "pack_a.md") == ["R001", "R002", "R003"]


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda r: r[1:], "no label for R001"),
        (lambda r: r + [r[0]], "more than once"),
        (lambda r: r + [{"id": "R999", **_a()}], "not a card"),
        (lambda r: [{**r[0], "standalone": "maybe"}] + r[1:], "standalone must be one of"),
        (lambda r: [{**r[0], "lead_in_text": ""}] + r[1:], "lead_in_text is required"),
        (lambda r: [r[0], {**r[1], "lead_in_location": "same_chunk"}, r[2]], "must be null unless"),
        (
            lambda r: r[:2] + [{**r[2], "lead_in_text": "abc"}],
            "must be null when lead_in_location is not_shown",
        ),
        (
            lambda r: [r[0], r[1], {**r[2], "lead_in_location": "elsewhere"}],
            "lead_in_location must be one of",
        ),
    ],
)
def test_pass_a_problems_are_reported(checker, tmp_path, mutate, expected):
    d = _pack_dir(tmp_path)
    a = _write(tmp_path / "a.jsonl", mutate([dict(r) for r in GOOD_A]))
    assert any(expected in p for p in checker.check(d, a, None))


def test_pass_b_problems_are_reported(checker, tmp_path):
    d = _pack_dir(tmp_path)
    a = _write(tmp_path / "a.jsonl", GOOD_A)
    bad = _write(tmp_path / "b.jsonl", [{"id": "R001", "stem_verdict": "ok"}, GOOD_B[1]])
    assert any("stem_verdict must be one of" in p for p in checker.check(d, a, bad))
    short = _write(tmp_path / "b2.jsonl", GOOD_B[:1])
    assert any("no label for R003" in p for p in checker.check(d, a, short))


def test_malformed_lines_are_reported_not_raised(checker, tmp_path):
    d = _pack_dir(tmp_path)
    a = tmp_path / "a.jsonl"
    a.write_text("not json\n[1, 2]\n", encoding="utf-8")
    problems = checker.check(d, a, None)
    assert any("not valid JSON" in p for p in problems)
    assert any('string "id"' in p for p in problems)

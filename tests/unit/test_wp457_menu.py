"""WP-45.7b: the candidate-menu generator and its offline ceiling measurement (offline; no LLM, no corpus)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_7"


def _load(name):
    for p in (str(_DIR), str(_DIR.parents[2])):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(f"wp457b_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wp457b_{name}"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def M():
    return _load("menu")


@pytest.fixture(scope="module")
def MM():
    return _load("measure_menu")


def _chunk(cid, text, heading="", title_path=()):
    return {"chunk_id": cid, "raw_text": text, "parent_header_text": heading, "section_title_path": list(title_path)}


def test_first_modal_is_the_earliest_and_skips_can(M):
    assert M.first_modal("The Officer can decide and shall report.")[2:] == ("shall", "obligation")
    assert M.first_modal("It should be done, and it must be logged.")[2:] == ("should", "recommendation")
    assert M.first_modal("The system can run.") is None
    assert M.first_modal("Disable unused services.") is None


def test_subject_of_cuts_at_the_modal_and_drops_list_markers(M):
    assert M.subject_of("The Records Officer shall review logs.") == "The Records Officer"
    assert M.subject_of("(a) The Director, DISA, will ensure access.") == "The Director, DISA"
    assert M.subject_of("2.1.5. Components must comply.") == "Components"
    assert M.subject_of("Disable unused services.") is None
    assert M.subject_of("Shall be reviewed yearly.") is None  # nothing before the modal


def test_lead_in_before_is_the_nearest_colon_sentence(M):
    body = "Intro text. The Records Officer will: (1) review logs; (2) report. Other text."
    assert M.lead_in_before(body, "(2) report.") == "The Records Officer will:"
    assert M.lead_in_before(body, "Intro text.") is None  # nothing before it
    assert M.lead_in_before("No colons here (1) item.", "(1) item.") is None
    assert M.lead_in_before(body, "not in the body") is None


def test_a_colon_must_govern_what_follows_it(M):
    """Review finding: the nearest colon is not always a lead-in. Prose after it, a URL or a time are not governed items."""
    assert M.lead_in_before("Note: background text. (1) Encrypt data.", "(1) Encrypt data.") is None
    assert M.lead_in_before("See https://example.org/page for details. (1) Encrypt data.", "(1) Encrypt data.") is None
    assert M.lead_in_before("Meet at 10:30 daily. Encrypt data.", "Encrypt data.") is None
    # a nested colon that governs nothing falls back to the earlier colon that does
    body = "The Officer will: (a) do this: details follow; (b) report."
    assert M.lead_in_before(body, "(b) report.") == "The Officer will:"
    # list markers: numbered, lettered, bulleted, and the quote directly after the colon
    assert M.lead_in_before("The Officer will: - report.", "report.") == "The Officer will:"
    assert M.lead_in_before("The Officer will: report.", "report.") == "The Officer will:"
    assert M.tail_lead_in("Text. Note: prose here.") is None
    assert M.tail_lead_in("Text. The Officer will: (1) report;") == "The Officer will:"
    assert M.tail_lead_in("Text. The Officer will:") == "The Officer will:"


def test_preceding_clause_is_the_clause_before_the_quote(M):
    body = "First sentence. Air Force Chief of Safety, in coordination with AF/A10, will develop standards."
    assert M.preceding_clause(body, "develop standards.") == "Air Force Chief of Safety, in coordination with AF/A10, will"
    assert M.preceding_clause("Alpha beta. Gamma delta.", "Gamma delta.") == "Alpha beta."
    assert M.preceding_clause("Alpha.", "Alpha.") is None
    assert M.preceding_clause("Alpha.", "missing") is None


def test_menu_tiers_and_ordering(M):
    chunks = {
        1: _chunk(1, "Opening. The Records Officer will:", title_path=["SECTION 2", "2.3. RECORDS OFFICER"]),
        2: _chunk(2, "(1) Review logs monthly. (2) Report findings.", heading="2.3. RECORDS OFFICER", title_path=["SECTION 2", "2.3. RECORDS OFFICER"]),
    }
    r0 = M.build_menu("The Auditor shall review logs.", 2, chunks, "R0")
    assert [e["kind"] for e in r0] == ["subject"] and r0[0]["text"] == "The Auditor"
    r1 = M.build_menu("(2) Report findings.", 2, chunks, "R1")
    kinds = [(e["kind"], e["text"]) for e in r1]
    assert ("heading", "2.3. RECORDS OFFICER") in kinds
    assert ("heading", "RECORDS OFFICER") in kinds  # the section number is also offered stripped
    assert ("heading", "SECTION 2") in kinds
    assert any(k == "preceding" for k, _ in kinds)
    assert [e["id"] for e in r1] == [f"M{i}" for i in range(1, len(r1) + 1)]
    r2 = M.build_menu("(1) Review logs monthly.", 2, chunks, "R2")
    assert any(e["kind"] == "lead_in" and e["text"].startswith("The Records Officer will:") for e in r2)
    assert not any("previous" in e["source"] for e in r1)  # the previous chunk is an R2-only source
    with pytest.raises(ValueError):
        M.build_menu("x", 1, chunks, "R9")


def test_unknown_chunk_gives_only_the_quote_subject(M):
    assert [e["kind"] for e in M.build_menu("The Auditor shall act.", 99, {}, "R2")] == ["subject"]


def test_every_menu_text_is_verbatim_in_its_sources(M):
    """The design's claim: nothing is generated, every entry is a substring of the quote, a heading, the chunk or the previous chunk."""
    chunks = {
        1: _chunk(1, "Preface. Responsibilities of the Director, DISA, are as follows: items follow", title_path=["PART 1"]),
        2: _chunk(2, "Disable unused services. The Director, DISA, shall ensure access.", heading="3.2. ACCESS", title_path=["PART 1", "3.2. ACCESS"]),
    }
    quote = "Disable unused services."
    for tier in ("R1", "R2"):
        sources = [M.B.normalize(quote)] + [M.B.normalize(c["raw_text"]) for c in chunks.values()]
        sources += [M.B.normalize(h) for c in chunks.values() for h in c["section_title_path"] + [c["parent_header_text"]]]
        stripped = [M._SECTION_NUMBER.sub("", s, count=1) for s in sources]
        for e in M.build_menu(quote, 2, chunks, tier):
            assert any(e["text"] in s for s in sources + stripped), (tier, e)


def test_menu_has_no_repeats_and_is_capped(M):
    chunks = {2: _chunk(2, "Body. The Auditor shall act.", heading="HEAD", title_path=[f"H{i}" for i in range(30)])}
    menu = M.build_menu("The Auditor shall act.", 2, chunks, "R1")
    texts = [e["text"].lower() for e in menu]
    assert len(texts) == len(set(texts)) and len(menu) <= M.MAX_MENU


def test_spans_are_cut_back_to_the_cap_at_a_word_boundary(M):
    long = " ".join(["word"] * 200)
    cut = M._cap(long)
    assert len(cut) <= M.MAX_SPAN_CHARS and long.endswith(cut) and cut.startswith("word")


def test_menu_modal_reads_the_quote_then_the_chosen_parent(M):
    assert M.menu_modal("The Officer should review logs.") == ("should", "recommendation")
    assert M.menu_modal("(1) Review logs.", "The Records Officer will:") == ("will", "obligation")
    assert M.menu_modal("(1) Review logs.", None) == ("", "none")
    assert M.menu_modal("The system can run.", "The system can run.") == ("", "none")  # "can" is not read as a modal


def test_reachable_uses_the_attachment_overlap_rule(MM):
    complete = {"standalone": "complete", "lead_in_text": ""}
    needs = {"standalone": "needs_lead_in", "lead_in_text": "The Records Officer will:"}
    assert MM.reachable(complete, [])  # choosing nothing is right
    assert MM.reachable(needs, [{"text": "The Records Officer"}])
    assert not MM.reachable(needs, [{"text": "SECTION 2"}, {"text": "The Auditor"}])
    assert not MM.reachable(needs, [])


def test_measure_reports_ceiling_sizes_and_misses(MM):
    chunks = {2: _chunk(2, "The Records Officer will: (1) Review logs. (2) Report findings.", title_path=["2.3. RECORDS OFFICER"])}
    docs = {"doc": (chunks, {})}
    golds = [
        {"candidate_id": "a", "document": "doc", "chunk_id": 2, "quote": "(2) Report findings.", "standalone": "needs_lead_in",
         "lead_in_location": "same_chunk", "lead_in_text": "The Records Officer will:"},
        {"candidate_id": "b", "document": "doc", "chunk_id": 2, "quote": "(1) Review logs.", "standalone": "needs_lead_in",
         "lead_in_location": "previous_chunk", "lead_in_text": "Quarterly Reviewer shall:"},
        {"candidate_id": "c", "document": "doc", "chunk_id": 2, "quote": "The Auditor shall act.", "standalone": "complete",
         "lead_in_location": None, "lead_in_text": ""},
    ]
    out = MM.measure(golds, docs, "R1")
    assert out["scored"] == 3 and out["needs_lead_in"] == 2
    assert out["ceiling"] == pytest.approx(2 / 3) and out["ceiling_needs_lead_in"] == pytest.approx(1 / 2)
    assert [m["candidate_id"] for m in out["misses"]] == ["b"]
    assert out["by_lead_in_location"] == {"previous_chunk": {"n": 1, "reachable": 0}, "same_chunk": {"n": 1, "reachable": 1}}
    assert out["passes_s1"] is False and len(out["generator_sha256"]) == 16


def test_evaluation_half_is_refused_without_final():
    done = subprocess.run([sys.executable, str(_DIR / "measure_menu.py"), "--tier", "R1", "--half", "evaluation"],
                          capture_output=True, text=True)
    assert done.returncode != 0 and "--final" in (done.stderr + done.stdout)

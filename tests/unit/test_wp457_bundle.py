"""WP-45.7: the deterministic evidence-bundle builder (offline; no LLM)."""

import importlib.util
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_7"


@pytest.fixture(scope="module")
def B():
    spec = importlib.util.spec_from_file_location("wp457_bundle", _DIR / "bundle.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["wp457_bundle"] = module
    spec.loader.exec_module(module)
    return module


def _chunk(cid, text, heading="", ref_path=(), title_path=()):
    return {
        "chunk_id": cid,
        "raw_text": text,
        "parent_header_text": heading,
        "section_ref_path": list(ref_path),
        "section_title_path": list(title_path),
    }


def _doc():
    return {
        1: _chunk(1, "3.4 The Records Officer will:", "3.4 RECORDS", ["3", "3.4"], ["3. DUTIES", "3.4 RECORDS"]),
        2: _chunk(2, "a. Provides quarterly retention reports to the Program Office.", "3.4 RECORDS", ["3", "3.4"], ["3. DUTIES", "3.4 RECORDS"]),
        3: _chunk(3, "4.2 Reports are due by 1 March.", "4.2 REPORTS", ["4", "4.2"], ["4. REPORTS", "4.2 REPORTS"]),
    }


def test_normalize_collapses_whitespace_and_rejoins_soft_hyphenated_breaks(B):
    assert B.normalize("Section\n4   applies") == "Section 4 applies"
    assert B.normalize("informa-\ntion security") == "information security"
    assert B.normalize("informa­\ntion") == "information"
    assert B.normalize("well-known term") == "well-known term"  # a real hyphen inside a line stays
    assert B.normalize(None) == ""


def test_cross_references_are_found_on_normalized_text_and_not_repeated(B):
    text = B.normalize("Comply with Section\n4 and paragraph  2.3, see AC-2(4) and section 4 again.")
    keys = [k for _, k in B.cross_references(text)]
    assert keys == ["4", "2.3", "AC-2(4)"]


def test_a_reference_is_resolved_by_the_section_path_or_reported_missing(B):
    chunks = [_doc()[k] for k in (1, 2, 3)]
    assert B.resolve_reference("4.2", chunks)["chunk_id"] == 3
    assert B.resolve_reference("3.4", chunks)["chunk_id"] == 1
    assert B.resolve_reference("9.9", chunks) is None


def test_tiers_add_context_one_layer_at_a_time(B):
    q = "a. Provides quarterly retention reports to the Program Office."
    r0, r1, r2 = (B.build(q, 2, _doc(), t) for t in B.TIERS)
    assert [s.kind for s in r0.spans] == ["candidate"]
    kinds1 = [s.kind for s in r1.spans]
    assert kinds1[:3] == ["candidate", "chunk", "heading"] and "previous" not in kinds1 and "next" not in kinds1
    kinds2 = [s.kind for s in r2.spans]
    assert "previous" in kinds2 and "next" in kinds2
    assert [s.id for s in r2.spans] == [f"E{i}" for i in range(1, len(r2.spans) + 1)]  # ids are consecutive from E1


def test_a_cross_reference_in_the_candidate_adds_the_referenced_section_or_lists_it_as_missing(B):
    doc = _doc()
    doc[7] = _chunk(7, "6.1 Waivers last six months.", "6.1 WAIVERS", ["6", "6.1"], ["6. WAIVERS", "6.1 WAIVERS"])
    b = B.build("Comply with paragraph 6.1 and section 8.", 2, doc, "R2")
    refs = [s for s in b.spans if s.kind == "reference"]
    assert len(refs) == 1 and "Waivers last six months" in refs[0].text and refs[0].label == "referenced section 6.1"
    assert b.unresolved_references == ["section 8"]
    assert "References not found in the evidence: section 8" in b.render()
    # R1 does not follow references at all
    assert not [s for s in B.build("Comply with paragraph 6.1.", 2, doc, "R1").spans if s.kind == "reference"]


def test_a_referenced_section_that_is_already_a_neighbor_is_marked_there_not_repeated(B):
    b = B.build("Comply with paragraph 4.2.", 2, _doc(), "R2")  # chunk 3 is the next chunk and holds 4.2
    assert not [s for s in b.spans if s.kind == "reference"]
    nxt = [s for s in b.spans if s.kind == "next"]
    assert len(nxt) == 1 and "also the referenced section 4.2" in nxt[0].label
    assert b.render().count("due by 1 March") == 1


def test_governing_clause_candidates_come_from_the_existing_finders_and_are_marked_unverified(B):
    chunks = {1: _chunk(1, "The Director shall:\n(1) review plans.\n(2) approve budgets.", "DUTIES")}
    step_c = {1: [{"source_quote": "The Director shall:"}, {"source_quote": "(1) review plans."}, {"source_quote": "(2) approve budgets."}]}
    b = B.build("(2) approve budgets.", 1, chunks, "R1", step_c_by_chunk=step_c)
    stems = [s for s in b.spans if s.kind == "stem"]
    assert stems and stems[0].unverified and "The Director shall:" in stems[0].text
    assert "(unverified)" in b.render()


def test_neighbors_are_cut_first_and_the_candidate_heading_and_stems_are_never_cut(B):
    chunks = _doc()
    chunks[1]["raw_text"] = "x " * 2000  # a huge previous chunk
    chunks[3]["raw_text"] = "y " * 2000
    chunks[2]["raw_text"] = "z " * 3000 + "a. Provides quarterly retention reports to the Program Office. " + "w " * 3000
    q = "a. Provides quarterly retention reports to the Program Office."
    b = B.build(q, 2, chunks, "R2", fixed_tokens=1500)
    assert not b.untreatable
    assert b.chars() <= B.prompt_budget_chars(1500)
    assert b.truncated
    kept = {s.kind: s for s in b.spans}
    assert kept["candidate"].text == B.normalize(q)
    assert kept["heading"].text == "3.4 RECORDS"
    if "chunk" in kept:  # the own chunk is cut around the candidate, never from the instructions
        assert B.normalize(q)[:20] in kept["chunk"].text
    first_cut = b.truncated[0]
    assert "next" in first_cut or "previous" in first_cut  # the lowest-priority spans go first


def test_a_bundle_that_cannot_fit_is_flagged_untreatable_before_any_call(B):
    b = B.build("a. Provides reports.", 2, _doc(), "R2", fixed_tokens=6400)
    assert b.untreatable
    assert B.preflight(fixed_tokens=1500, minimum_bundle_chars=500)
    assert not B.preflight(fixed_tokens=7500, minimum_bundle_chars=500)


def test_budget_uses_the_conservative_character_estimate(B):
    assert B.estimate_tokens(250) == 100
    assert B.prompt_budget_chars(0) == int(B.BUNDLE_TOKEN_CAP * 2.5)
    assert B.prompt_budget_chars(5000) == int((B.PROMPT_TOKEN_CAP - 5000 - B.ANSWER_RESERVE_TOKENS) * 2.5)


def test_the_bundle_hash_is_stable_and_follows_the_text(B):
    a = B.build("a. Provides reports.", 2, _doc(), "R1")
    assert a.bundle_hash() == B.build("a. Provides reports.", 2, _doc(), "R1").bundle_hash()
    assert a.bundle_hash() != B.build("a. Reviews reports.", 2, _doc(), "R1").bundle_hash()
    d = a.to_dict()
    assert d["tier"] == "R1" and d["spans"][0]["id"] == "E1" and d["chars"] == a.chars()


def test_an_unknown_tier_or_missing_chunk_is_handled(B):
    with pytest.raises(ValueError):
        B.build("x", 1, _doc(), "R9")
    only_quote = B.build("x", 99, _doc(), "R2")  # a chunk id that is not in the document: the candidate alone
    assert [s.kind for s in only_quote.spans] == ["candidate"]


def test_the_first_and_last_chunks_have_only_the_neighbor_they_have(B):
    first = B.build("q", 1, _doc(), "R2")
    assert "previous" not in [s.kind for s in first.spans] and "next" in [s.kind for s in first.spans]
    last = B.build("q", 3, _doc(), "R2")
    assert "next" not in [s.kind for s in last.spans] and "previous" in [s.kind for s in last.spans]

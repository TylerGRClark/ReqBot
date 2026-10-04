"""WP-45.1(c)/(d): the pure pieces of the fair retrieval test.

The scripts run for real against the live index and Ollama; these tests pin what would silently change a reported number:
the production constants the adapter must mirror, tie-aware ranks, the variant text layout, the paired bootstrap, the
pre-registered "meaningful" rule, and the query-writing checks.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_1c"


def _load(name):
    sys.path.insert(0, str(_DIR))
    try:
        spec = importlib.util.spec_from_file_location(f"wp451c_{name}", _DIR / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(_DIR))


@pytest.fixture(scope="module")
def engine():
    return _load("engine")


@pytest.fixture(scope="module")
def variants():
    return _load("variants")


@pytest.fixture(scope="module")
def analyze():
    return _load("analyze")


@pytest.fixture(scope="module")
def qcheck():
    return _load("query_check")


@pytest.fixture(scope="module")
def groups():
    return _load("groups")


@pytest.fixture(scope="module")
def packet():
    return _load("query_packet")


# ------------------------------------------------------------------------------------------------------- adapter


def test_adapter_constants_equal_the_ones_retrieve_derives(engine):
    """retrieve(top_k=20, min_score=0.02): prefetch 100 per leg, fuse 60, filter, trim to 20 (core/ask.py)."""
    assert (engine.TOP_K, engine.MIN_SCORE) == (20, 0.02)
    assert engine.FUSION_LIMIT == max(20 * 3, 50) == 60
    assert engine.PREFETCH == max(100, 20 * 5, 60) == 100


def test_returned_takes_the_first_sixty_drops_low_scores_and_keeps_twenty(engine):
    fused = [(f"R{i}", 1.0 - i * 0.005) for i in range(100)]  # scores 1.0 .. 0.505
    assert [r for r, _ in engine.returned(fused)] == [f"R{i}" for i in range(20)]
    low = [("A", 0.5), ("B", 0.019), ("C", 0.4)]
    assert [r for r, _ in engine.returned(low)] == [
        "A",
        "C",
    ]  # B is under the 0.02 floor and is dropped, not stop-at
    deep = [(f"R{i}", 0.5) for i in range(59)] + [("late", 0.5)] * 5 + [("later", 0.5)]
    # only the first FUSION_LIMIT positions are considered at all
    assert len(engine.returned(deep + deep)) == 20


def test_rank_info_reports_ties_as_best_and_worst_case(engine):
    fused = [("A", 0.9), ("B", 0.5), ("C", 0.5), ("D", 0.5), ("E", 0.1)]
    c = engine.rank_info(fused, "C")
    assert (c["best_rank"], c["worst_rank"]) == (2, 4)
    assert (
        engine.rank_info(fused, "A")["best_rank"] == engine.rank_info(fused, "A")["worst_rank"] == 1
    )
    assert engine.rank_info(fused, "Z") == {
        "found": False,
        "best_rank": None,
        "worst_rank": None,
        "score": None,
        "survives": False,
        "in_returned": False,
    }
    below = engine.rank_info([("A", 0.9), ("T", 0.01)], "T")
    assert below["found"] and not below["survives"] and not below["in_returned"]


def test_snapshot_digest_changes_with_any_vector(engine):
    pts = {
        "R": {
            "id": "1",
            "payload": {},
            "dense": [0.1, 0.2],
            "sparse_indices": [1],
            "sparse_values": [0.5],
        }
    }
    d1 = engine.digest(pts)
    pts["R"] = {**pts["R"], "dense": [0.1, 0.3]}
    assert engine.digest(pts) != d1


# ------------------------------------------------------------------------------------------------------ variants


def test_variants_follow_the_production_layout(variants):
    payload = {
        "source_quote": "Update courses.",
        "source_ref": "2.2",
        "embedding_text": "The CIO shall:\nUpdate courses.",
    }
    assert variants.production_text(payload) == "The CIO shall:\nUpdate courses.\nRef: 2.2"
    assert variants.quote_alone_text(payload) == "Update courses.\nRef: 2.2"
    assert (
        variants.oracle_text(payload, "CCDRs will: | As appropriate,")
        == "CCDRs will: As appropriate,\nUpdate courses.\nRef: 2.2"
    )
    assert variants.has_stem(payload) and not variants.has_stem({"source_quote": "x"})
    bare = {"source_quote": "Do it.", "source_ref": ""}
    assert variants.production_text(bare) == variants.quote_alone_text(bare) == "Do it."


# ----------------------------------------------------------------------------------------------------- analysis


def _row(rid, arm, mode, best, worst=None, style="topic"):
    worst = best if worst is None else worst
    return {
        "rid": rid,
        "style": style,
        "arm": arm,
        "mode": mode,
        "best_rank": best,
        "worst_rank": worst,
    }


def test_recall_and_reciprocal_rank_use_the_chosen_tie_convention(analyze):
    row = _row("R", "production", "base", best=8, worst=12)
    assert analyze.recall_at(row, 10, "best") == 1.0 and analyze.recall_at(row, 10, "worst") == 0.0
    assert analyze.reciprocal_rank(row, "best") == pytest.approx(1 / 8)
    gone = _row("R", "production", "base", best=None)
    assert (
        analyze.recall_at(gone, 20, "best") == 0.0 and analyze.reciprocal_rank(gone, "worst") == 0.0
    )


def test_paired_difference_is_arm_minus_production_for_the_same_record(analyze):
    rows = [
        _row("A", "production", "base", 15),
        _row("A", "quote_alone", "target_only", 3),
        _row("B", "production", "base", 4),
        _row("B", "quote_alone", "target_only", 30),
        _row("C", "production", "base", 4),  # no arm row: dropped, not counted as zero
    ]
    pairs = dict(
        analyze.paired(
            rows, ["A", "B", "C"], "quote_alone", "target_only", "topic", "recall@10", "best"
        )
    )
    assert pairs == {"A": 1.0, "B": -1.0}


def test_bootstrap_interval_is_exact_for_constant_differences_and_wide_for_noise(analyze):
    mean, lo, hi = analyze.bootstrap_ci([0.5] * 20)
    assert mean == lo == hi == pytest.approx(0.5)
    mean, lo, hi = analyze.bootstrap_ci([1, -1] * 10)
    assert mean == 0 and lo < 0 < hi
    assert all(np.isnan(x) for x in analyze.bootstrap_ci([]))
    again = analyze.bootstrap_ci([1, 0, 0, 1, 0, 1, 1, 0])
    assert again == analyze.bootstrap_ci([1, 0, 0, 1, 0, 1, 1, 0])  # fixed seed: reproducible


def test_document_bootstrap_resamples_whole_documents(analyze):
    deltas = [1.0] * 5 + [-1.0] * 5
    docs = ["a"] * 5 + ["b"] * 5
    mean, lo, hi = analyze.bootstrap_ci(deltas, clusters=docs)
    # only 'a', only 'b' or both can be drawn, so the interval spans the full range even though 10 records agree-ish
    assert mean == 0 and lo == -1.0 and hi == 1.0


def test_meaningful_needs_size_and_an_interval_that_excludes_zero(analyze):
    assert analyze.meaningful(0.02, 0.30, 0.16)
    assert analyze.meaningful(-0.30, -0.02, -0.16)
    assert not analyze.meaningful(-0.05, 0.35, 0.15)  # big but the interval includes zero
    assert not analyze.meaningful(0.01, 0.07, 0.04)  # excludes zero but under 0.10
    cell = lambda m, lo, hi: {t: {"mean": m, "lo": lo, "hi": hi} for t in analyze.TIES}  # noqa: E731
    assert analyze.verdict(cell(0.2, 0.05, 0.35)) == "BETTER"
    assert analyze.verdict(cell(-0.2, -0.35, -0.05)) == "WORSE"
    split = cell(0.2, 0.05, 0.35)
    split["worst"] = {"mean": 0.2, "lo": -0.05, "hi": 0.4}
    assert (
        analyze.verdict(split) == "no demonstrated difference"
    )  # not meaningful under both tie conventions


# ----------------------------------------------------------------------------------------------- query writing


def test_longest_common_run_and_named_entities(qcheck):
    w = qcheck.words
    assert (
        qcheck.longest_common_run(w("keep the old base image safe"), w("the old base image")) == 4
    )
    assert qcheck.longest_common_run(w("a b c"), w("x y z")) == 0
    # a named entity counts as one token, so repeating the full name is not copying
    assert (
        qcheck.longest_common_run(
            w("who runs the Joint Federated Assurance Center today"),
            w("manages the Joint Federated Assurance Center in accordance"),
        )
        == 2
    )


def test_check_flags_copying_length_and_missing_question_mark(qcheck):
    cards = {
        "P001": {
            "quote": "Establish policy to assure fleet-wide interoperability of the mission area.",
            "lead_in": "AFNC3C will:",
        }
    }
    ok = {
        "pid": "P001",
        "topic": "What policy keeps every fleet system interoperable across the mission?",
        "party": "What must AFNC3C do for interoperability across the mission area?",
    }
    rows, problems = qcheck.check([ok], cards)
    assert problems == [] and len(rows) == 2
    bad = {
        "pid": "P001",
        "topic": "Establish policy to assure fleet-wide interoperability",
        "party": "Too short?",
    }
    _, problems = qcheck.check([bad], cards)
    text = " ".join(problems)
    assert "consecutive words" in text and "question mark" in text and "words (rule 3" in text
    # the party question may repeat the party's own name from the lead-in, the topic question may not
    lead_copy = {
        "pid": "P001",
        "topic": "What must the AFNC3C will do about this one thing now?",
        "party": "What must AFNC3C will do about this one thing now?",
    }
    cards2 = {"P001": {"quote": "x y z", "lead_in": "must the AFNC3C will do about"}}
    _, problems = qcheck.check([lead_copy], cards2)
    assert any("topic" in p for p in problems) and not any(
        "party" in p and "consecutive" in p for p in problems
    )


def test_parse_packet_reads_quote_and_lead_in(qcheck):
    text = "# Query-writing packet\n\n## P001\n\nDocument: d\nHeading path: h\n\nQuote (verbatim):\n> The quote.\n\nLead-in this quote needs to be complete (from the adjudication):\n> The lead-in:\n\n## P002\n\nDocument: d\n\nQuote (verbatim):\n> Another.\n"
    cards = qcheck.parse_packet(text)
    assert cards["P001"] == {"quote": "The quote.", "lead_in": "The lead-in:"}
    assert cards["P002"] == {"quote": "Another.", "lead_in": ""}


# ----------------------------------------------------------------------------------------- groups and the packet


def _key_and_labels():
    key = {
        "items": {
            "R001": {
                "document": "d",
                "requirement_id": "REQ-1",
                "chunk_id": 1,
                "stratum": "s",
                "stem": "S1",
            },
            "R002": {
                "document": "d",
                "requirement_id": "REQ-2",
                "chunk_id": 1,
                "stratum": "s",
                "stem": "S2",
            },
            "R003": {
                "document": "d",
                "requirement_id": "REQ-3",
                "chunk_id": 1,
                "stratum": "s",
                "stem": "S3",
            },
            "R004": {
                "document": "d",
                "requirement_id": "REQ-4",
                "chunk_id": 1,
                "stratum": "s",
                "stem": "",
            },
            "R005": {
                "document": "d",
                "requirement_id": "REQ-5",
                "chunk_id": 1,
                "stratum": "s",
                "stem": "",
            },
            "R006": {
                "document": "d",
                "requirement_id": "REQ-6",
                "chunk_id": 1,
                "stratum": "s",
                "stem": "",
            },
            "R007": {
                "document": "d",
                "requirement_id": "REQ-7",
                "chunk_id": 1,
                "stratum": "s",
                "stem": "S7",
            },
        }
    }
    ra = {
        "R001": ("needs_lead_in", "same_chunk", "Lead one"),
        "R002": ("needs_lead_in", "same_chunk", "Lead two"),
        "R003": ("complete", None, None),
        "R004": ("needs_lead_in", "section_heading", "Heading text"),
        "R005": ("complete", None, None),
        "R006": ("needs_lead_in", "not_shown", None),
        "R007": ("not_a_requirement", None, None),
    }
    rb = {"R001": "right", "R002": "wrong_sibling", "R003": "fragment_chain", "R007": "right"}
    return key, ra, rb


def test_groups_follow_the_final_labels_and_leave_out_non_requirements(groups):
    key, ra, rb = _key_and_labels()
    g = groups.build(key, ra, rb)
    assert g["groups"] == {
        "right": ["R001"],
        "misleading": ["R002"],
        "incomplete": ["R003"],
        "bare": ["R004", "R006"],
        "control": ["R005"],
    }
    assert g["excluded"]["not_a_requirement"] == ["R007"] and "R007" not in g["eligible"]
    assert g["oracle_set"] == [
        "R001",
        "R002",
        "R004",
    ]  # R006's lead-in was not shown: no text, no oracle
    assert g["needs_lead_in_not_shown"] == ["R006"]
    assert g["heading_located"] == ["R004"] and g["stem_on_complete_quote"] == ["R003"]


def test_groups_stop_on_a_missing_lead_in_text_at_a_shown_location(groups):
    key, ra, rb = _key_and_labels()
    ra["R001"] = ("needs_lead_in", "same_chunk", "")
    with pytest.raises(SystemExit, match="no adjudicated lead-in text"):
        groups.build(key, ra, rb)


def test_packet_ids_are_a_seeded_shuffle_that_carries_no_group(packet):
    rids = [f"R{i:03d}" for i in range(1, 31)]
    a, b = packet.shuffled_ids(rids), packet.shuffled_ids(list(reversed(rids)))
    assert a == b and sorted(a) == [f"P{i:03d}" for i in range(1, 31)]
    assert list(a.values()) != sorted(a.values())  # shuffled, not in audit order
    assert packet.shuffled_ids(rids, seed="another") != a


def test_a_card_shows_the_adjudicated_lead_in_but_never_the_stem_or_verdict(packet):
    rec = {"source_quote": "Do   the   thing.", "section_title_path": ["A", "B"]}
    group_rec = {
        "document": "doc",
        "standalone": "needs_lead_in",
        "lead_in_text": "Lead:",
        "stem": "WRONG STEM",
        "stem_verdict": "wrong_sibling",
        "group": "misleading",
    }
    text = packet.card("P001", rec, group_rec)
    assert "Do the thing." in text and "Lead:" in text and "A > B" in text
    for leak in ("WRONG STEM", "wrong_sibling", "misleading"):
        assert leak not in text
    none_shown = packet.card("P002", rec, {**group_rec, "lead_in_text": None})
    assert "not visible" in none_shown


# ----------------------------------------------------------------------------------------------- heading rule


@pytest.fixture(scope="module")
def hrule():
    return _load("heading_rule")


def test_h3_uses_the_leaf_when_it_ends_in_a_colon_or_sits_under_responsibilities(hrule):
    assert hrule.h3_applies(["ROLES AND RESPONSIBILITIES", "2.19. Supervisors shall:"])
    assert hrule.h3_applies(["3.  CCDRs will:"])  # a colon-ending leaf needs no ancestor
    assert hrule.h3_applies(["SECTION 2:  RESPONSIBILITIES", "2.2.  DIRECTOR, DISA."])
    assert hrule.h3_applies(["ROLES AND RESPONSIBILITIES", "2.17. MAJCOM/DRUs."])


def test_h3_skips_topical_procedural_and_ancestor_only_headings(hrule):
    assert not hrule.h3_applies(["3.  NM USE OF SNMP"])
    assert not hrule.h3_applies(["4. Security Recommendations for Virtualization Components", "4.1 Hypervisor Security"])
    assert not hrule.h3_applies(["SECTION 1:  GENERAL ISSUANCE INFORMATION", "1.2.  POLICY."])
    assert not hrule.h3_applies(["ROLES AND RESPONSIBILITIES", "2.1. Objectives."])  # a procedural label even under responsibilities
    assert not hrule.h3_applies(["The DoD CIO:", "2.9.  DOD COMPONENT HEADS."])  # a colon in an ANCESTOR does not count
    assert not hrule.h3_applies([])


def test_label_strips_numbering_and_punctuation(hrule):
    assert hrule.label("2.1.  POLICY.") == "policy"
    assert hrule.label("SECTION 3:  Objectives") == "objectives"
    assert hrule.label("3.7.2. Methodology.") == "methodology"
    assert hrule.leaf_heading(["a", "b"]) == "b" and hrule.leaf_heading([]) == ""


def test_heading_path_reads_lists_and_stringified_lists(hrule):
    assert hrule.heading_path({"section_title_path": ["A", " ", "B"]}) == ["A", "B"]
    assert hrule.heading_path({"section_title_path": "['A', 'B']"}) == ["A", "B"]
    assert hrule.heading_path({}) == []

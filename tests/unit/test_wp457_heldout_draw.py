"""WP-45.7: the held-out page draw, chunk selection and label-set closure (offline; the PDFs and chunk files are not needed)."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_7"
_SEG_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_1e"


@pytest.fixture(scope="module")
def draw():
    sys.path.insert(0, str(_SEG_DIR))
    try:
        spec = importlib.util.spec_from_file_location("draw_heldout", _DIR / "draw_heldout.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["draw_heldout"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(_SEG_DIR))


def _chunk(cid, start, end, text="body"):
    return {"chunk_id": cid, "page_start": start, "page_end": end, "text": text}


def test_the_three_development_documents_are_not_in_the_held_out_set(draw):
    assert not set(draw.DOC_CODES) & set(draw.DEV_DOCUMENTS)
    assert len(draw.DOC_CODES) == 11
    assert set(draw.CATALOG_DOCUMENTS) <= set(draw.DOC_CODES)
    assert len(set(draw.DOC_CODES.values())) == 11  # piece-id prefixes are unique


def test_page_selection_is_deterministic_and_follows_the_three_step_rule(draw):
    eligible = {"A": list(range(1, 21)), "B": list(range(1, 21)), "C": list(range(1, 21))}
    tables = {"A": {3, 4}, "B": {5}, "C": set()}
    first = draw.select_pages(eligible, tables)
    assert first == draw.select_pages(eligible, tables)
    reasons = [r for _, _, r in first]
    assert reasons.count("per_document") == 3
    assert reasons.count("table") == draw.TABLE_PAGES  # the pools here are large enough to fill every quota
    assert reasons.count("extra") == draw.EXTRA_PAGES
    assert {d for d, _, r in first if r == "per_document"} == {"A", "B", "C"}
    pages = [(d, p) for d, p, _ in first]
    assert len(pages) == len(set(pages))  # nothing is drawn twice
    for d, p, r in first:
        if r == "table":
            assert p in tables[d]


def test_a_different_seed_gives_a_different_draw(draw):
    eligible = {"A": list(range(1, 40)), "B": list(range(1, 40))}
    assert draw.select_pages(eligible, {}, seed="x") != draw.select_pages(eligible, {}, seed="y")


def test_a_catalog_document_gets_extra_pages_from_its_own_shuffle(draw):
    eligible = {"A": list(range(1, 21)), "CAT": list(range(1, 21))}
    chosen = draw.select_pages(eligible, {}, catalogs=("CAT",))
    cat = [p for d, p, r in chosen if d == "CAT" and r == "catalog"]
    assert len(cat) == draw.CATALOG_EXTRA_PAGES
    first = [p for d, p, r in chosen if d == "CAT" and r == "per_document"]
    assert first and first[0] not in cat
    assert all(r != "catalog" for d, _, r in chosen if d == "A")
    # a catalog document gets only its two pages: it is kept out of the table and extra pools
    assert [r for d, _, r in chosen if d == "CAT"] == ["per_document", "catalog"]


def test_a_catalog_full_of_tables_does_not_take_the_table_stratum(draw):
    eligible = {"A": list(range(1, 11)), "CAT": list(range(1, 41))}
    tables = {"A": {2, 3, 4}, "CAT": set(range(1, 41))}
    chosen = draw.select_pages(eligible, tables, catalogs=("CAT",))
    table_docs = {d for d, _, r in chosen if r == "table"}
    assert table_docs == {"A"}


def test_a_document_with_no_eligible_page_fails_loudly_not_with_an_index_error(draw):
    with pytest.raises(ValueError, match="no page with at least"):
        draw.select_pages({"A": [1, 2], "B": []}, {})


def test_fewer_table_pages_than_the_quota_does_not_fail(draw):
    eligible = {"A": [1, 2, 3, 4, 5, 6, 7, 8]}
    chosen = draw.select_pages(eligible, {"A": {2}})
    assert [r for _, _, r in chosen].count("table") == 1


def test_table_pages_come_from_chunks_with_a_markdown_table(draw):
    chunks = [_chunk(1, 2, 3, "| a | b |\n| 1 | 2 |\n| 3 | 4 |"), _chunk(2, 5, 5, "plain prose"), _chunk(3, 7, 7, "a | b")]
    assert draw.table_pages(chunks) == {2, 3}


def test_chunks_are_selected_when_their_range_touches_a_drawn_page(draw):
    chunks = [_chunk(1, 1, 1), _chunk(2, 2, 4), _chunk(3, 5, 5), _chunk(4, 4, 6)]
    assert draw.select_chunks(chunks, [4]) == [2, 4]
    assert draw.select_chunks(chunks, [9]) == []


def test_the_label_set_covers_drawn_pages_and_every_page_a_selected_chunk_touches(draw):
    chunks = [_chunk(1, 1, 1), _chunk(2, 2, 4), _chunk(3, 5, 5), _chunk(4, 4, 6)]
    selected = draw.select_chunks(chunks, [4])
    closed = draw.closed_pages(chunks, selected, [4], pages_in_pdf=10)
    assert closed == [2, 3, 4, 5, 6]
    # closure property: every selected chunk lies entirely inside labeled pages
    for c in chunks:
        if c["chunk_id"] in selected:
            assert set(range(c["page_start"], c["page_end"] + 1)) <= set(closed)


def test_a_drawn_page_that_no_chunk_covers_is_still_labeled(draw):
    chunks = [_chunk(1, 1, 2)]
    assert draw.closed_pages(chunks, [], [27], pages_in_pdf=28) == [27]


def test_closure_is_clipped_to_the_pdf(draw):
    chunks = [_chunk(1, 9, 12)]
    assert draw.closed_pages(chunks, [1], [9], pages_in_pdf=10) == [9, 10]


def test_piece_ids_are_stable_and_unique(draw):
    assert draw.piece_id("afi10-2402", 11, 3) == "AFI102-p011-003"
    assert draw.piece_id("dafman17-1305", 27, 12) == "DAFM-p027-012"


FROZEN = _DIR / "outputs" / "heldout_frozen.json"


@pytest.mark.skipif(not FROZEN.exists(), reason="the held-out draw is not frozen yet")
def test_the_frozen_draw_is_internally_consistent(draw):
    data = json.loads(FROZEN.read_text(encoding="utf-8"))
    assert data["pages_drawn_total"] == 16
    assert "CNSSI_No1253" in data["documents"]  # the control-catalog stratum is present
    drawn_total = 0
    texts = []
    for document, e in data["documents"].items():
        assert document in draw.DOC_CODES
        drawn = [x["page"] for x in e["drawn"]]
        drawn_total += len(drawn)
        assert drawn  # every document contributes at least one page
        assert set(drawn) <= set(e["closed_pages"])  # drawn pages are always labeled
        assert set(e["pages_added_by_closure"]) == set(e["closed_pages"]) - set(drawn)
        assert set(e["pieces"]) == {str(p) for p in e["closed_pages"]}  # every label page is cut into pieces
        for pg in e["pieces"].values():
            for p in pg:
                texts.append(p["id"] + "\t" + p["text"])
    assert drawn_total == data["pages_drawn_total"]
    assert len(texts) == data["pieces_total"]
    assert len(set(t.split("\t")[0] for t in texts)) == len(texts)  # piece ids are unique across documents
    digest = hashlib.sha256("\n".join(sorted(texts)).encode("utf-8")).hexdigest()
    assert digest == data["pieces_sha256"]

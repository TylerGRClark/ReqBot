"""WP-45.1(e): the page cutter and the frozen page draw (offline; no PDFs from raw_pdfs are needed)."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_1e"


def _load(name):
    sys.path.insert(0, str(_DIR))
    try:
        spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(_DIR))


@pytest.fixture(scope="module")
def seg():
    return _load("segment")


@pytest.fixture(scope="module")
def draw(seg):
    return _load("draw")


def test_sentences_split_at_real_ends_but_not_after_abbreviations_or_initials(seg):
    assert seg.split_sentences("Do this now. Then do that.") == ["Do this now.", "Then do that."]
    text = "Coordinate with the U.S. Strategic Command (USSTRATCOM) on circuits, e.g. diversity, per No. 5 and J. Smith."
    assert seg.split_sentences(text) == [text]
    assert seg.split_sentences("Version 2.4 applies. See table 3.") == [
        "Version 2.4 applies.",
        "See table 3.",
    ]
    # a question mark or a closing quote ends a sentence too
    assert seg.split_sentences('Is it done? "Yes." Then proceed.') == [
        "Is it done?",
        '"Yes."',
        "Then proceed.",
    ]


def test_a_leading_list_marker_stays_with_its_first_sentence(seg):
    out = seg.split_sentences("2.8.2.2.3. Prepare orders. Then check them.")
    assert out == ["2.8.2.2.3. Prepare orders.", "Then check them."]
    assert seg.split_sentences("(a) Maintain the roster. Report changes.") == [
        "(a) Maintain the roster.",
        "Report changes.",
    ]


def test_hyphenated_line_ends_join_only_before_a_lowercase_letter(seg):
    assert seg.join_lines(["manage-", "ment of  the", "network"]) == "management of the network"
    assert seg.join_lines(["the cross-", "Domain guide"]) == "the cross- Domain guide"


def test_list_markers_and_gaps_start_paragraphs_but_wrapped_lines_do_not(seg):
    def line(y, text):
        return (y, y + 10, 72.0, 500.0, text)

    lines = [
        line(100, "The Program Manager will:"),
        line(111, "(a) Maintain the access roster for the"),
        line(122, "facility and report changes."),
        line(133, "(b) Review the roster monthly."),
        line(160, "A separate paragraph after a gap."),
        line(171, "that wraps onto a second line."),
        line(182, "2024 data show rising use."),
    ]
    assert seg.paragraphs(lines) == [
        "The Program Manager will:",
        "(a) Maintain the access roster for the facility and report changes.",
        "(b) Review the roster monthly.",
        "A separate paragraph after a gap. that wraps onto a second line. 2024 data show rising use.",
    ]


def test_a_uppercase_acronym_in_parentheses_is_not_a_list_marker(seg):
    assert not seg.LIST_MARKER.match("(DTS), and the rest of the sentence")
    assert not seg.LIST_MARKER.match("30 days after the event")
    assert seg.LIST_MARKER.match("(aa) International Telecommunication")
    assert seg.LIST_MARKER.match("2.4.1.1 Single Server Virtualization")


def test_segmenting_a_real_page_is_deterministic_and_in_reading_order(seg):
    fitz = pytest.importorskip(
        "fitz"
    )  # PyMuPDF is not a project dependency; CI does not install it
    doc = fitz.open()
    page = doc.new_page()
    y = 80
    for text in (
        "2.1. The Director will:",
        "(a) Maintain the access roster. Report changes monthly.",
        "(b) Review logs.",
    ):
        page.insert_text((72, y), text, fontsize=11)
        y += 30
    first = seg.segment_page(page)
    assert first == seg.segment_page(page)
    assert first == [
        "2.1. The Director will:",
        "(a) Maintain the access roster.",
        "Report changes monthly.",
        "(b) Review logs.",
    ]
    assert seg.piece_id("afman17-2101", 12, 3) == "AFMAN-p012-003"


def test_shuffle_order_is_seeded_and_extending_n_keeps_the_pages_already_drawn(draw):
    pages = list(range(1, 26))
    a = draw.shuffle_order(pages, "DODI 8410.03")
    assert a == draw.shuffle_order(list(reversed(pages)), "DODI 8410.03")
    assert sorted(a) == pages and a != pages
    assert a[:4] == draw.shuffle_order(pages, "DODI 8410.03")[:4]
    assert a != draw.shuffle_order(pages, "afman17-2101")


def test_the_frozen_draw_is_internally_consistent_and_tied_to_the_segmenter(seg, draw):
    frozen = json.loads(draw.FROZEN.read_text(encoding="utf-8"))
    assert frozen["segmenter_sha256"] == hashlib.sha256(Path(seg.__file__).read_bytes()).hexdigest()
    texts, ids = [], []
    for name, e in frozen["documents"].items():
        assert e["drawn"] == e["shuffle_order"][: frozen["pages_per_document"]]
        assert sorted(e["shuffle_order"]) == sorted(set(e["shuffle_order"]))
        for page, pieces in e["pieces"].items():
            assert int(page) in e["drawn"] and pieces
            for k, p in enumerate(pieces, 1):
                assert p["id"] == seg.piece_id(name, int(page), k)
                ids.append(p["id"])
                texts.append(p["id"] + "\t" + p["text"])
    assert len(ids) == len(set(ids)) == frozen["pieces_total"]
    assert (
        frozen["pieces_sha256"]
        == hashlib.sha256("\n".join(sorted(texts)).encode("utf-8")).hexdigest()
    )


@pytest.fixture(scope="module")
def pack():
    return _load("pack")


def _checker():
    spec = importlib.util.spec_from_file_location(
        "wp451e_check", _DIR / "audit_pack/check_labels.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_pack_holds_exactly_the_frozen_pieces_and_the_manifest_matches_the_files(pack, draw):
    frozen = json.loads(draw.FROZEN.read_text(encoding="utf-8"))
    manifest = json.loads(pack.MANIFEST.read_text(encoding="utf-8"))
    ids = [p["id"] for e in frozen["documents"].values() for pg in e["pieces"].values() for p in pg]
    assert sorted(_checker().piece_ids(pack.PACK_DIR / "pack_a.md")) == sorted(ids)
    assert manifest["pieces_sha256"] == frozen["pieces_sha256"]
    assert manifest["pages_frozen_sha256"] == pack.sha256_of(draw.FROZEN)
    assert manifest["sha256"] == {n: pack.sha256_of(pack.PACK_DIR / n) for n in manifest["sha256"]}
    # nothing from the extraction pipeline is in the pack
    text = (pack.PACK_DIR / "pack_a.md").read_text(encoding="utf-8").lower()
    assert "requirement_id" not in text and "chunk" not in text


def test_the_checker_flags_missing_duplicate_invalid_and_unknown_labels(tmp_path):
    chk = _checker()
    (tmp_path / "pack_a.md").write_text(
        "## doc\n[AAA-p001-001] First piece.\n[AAA-p001-002] Second piece.\n[AAA-p001-003] Third.\n",
        encoding="utf-8",
    )
    good = [
        {"id": "AAA-p001-001", "label": "obligation", "segment_ok": True, "note": ""},
        {"id": "AAA-p001-002", "label": "lead_in", "segment_ok": True},
        {"id": "AAA-p001-003", "label": "not_obligation", "segment_ok": False, "note": "joined"},
    ]
    path = tmp_path / "labels.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in good), encoding="utf-8")
    assert chk.check(tmp_path, path) == []
    bad = [
        good[0],
        good[0],
        {"id": "AAA-p001-002", "label": "requirement", "segment_ok": "yes"},
        {"id": "AAA-p009-001", "label": "scope", "segment_ok": True},
    ]
    path.write_text("\n".join(json.dumps(r) for r in bad), encoding="utf-8")
    problems = "\n".join(chk.check(tmp_path, path))
    assert "appears more than once" in problems and "no label for AAA-p001-003" in problems
    assert "label must be one of" in problems and "segment_ok must be true or false" in problems
    assert "AAA-p009-001 is not a piece" in problems

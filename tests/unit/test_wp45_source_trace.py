"""WP-45.1(e): the loss trace, adjudication and page-level bootstrap (synthetic fixtures; no pipeline files, no Qdrant)."""

import importlib.util
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
def lt():
    _load("segment")
    return _load("loss_trace")


@pytest.fixture(scope="module")
def sc(lt):
    return _load("score")


PIECE = "2.1. The Program Manager shall maintain the access roster and report changes to the security office monthly."
CHUNK = (
    "Introduction text about the program. The Program Manager shall maintain the access roster and report "
    "changes to the security office monthly. Other text follows here."
)


def _chunks(lt, **texts):
    return {int(k[1:]): lt.tokens(v, drop_marker=False) for k, v in texts.items()}


def _rec(rid, chunk, quote):
    return {"requirement_id": rid, "chunk_id": chunk, "source_quote": quote}


def test_tokens_undo_ligatures_drop_the_list_marker_and_ignore_punctuation(lt):
    assert lt.tokens("2.8.2.2.3. Verify the ﬁrewall, now.") == ["verify", "the", "firewall", "now"]
    assert lt.tokens("(a) Keep it.") == ["keep", "it"]
    assert lt.tokens("2024 data show") == ["2024", "data", "show"]


def test_a_short_record_inside_a_long_piece_does_not_cover_it_but_a_whole_one_does(lt):
    piece = lt.tokens(PIECE)
    short = lt.tokens("access roster", drop_marker=False)
    assert len(lt.matched_indices(piece, short)) / len(piece) < 0.5  # below the 3-token run rule
    full = lt.tokens(CHUNK, drop_marker=False)
    assert len(lt.matched_indices(piece, full)) == len(piece)
    # scattered common words do not count as a match
    scattered = lt.tokens("the to monthly of maintain and access program", drop_marker=False)
    assert lt.status(len(lt.matched_indices(piece, scattered)) / len(piece)) == "none"


def test_status_thresholds(lt):
    assert [lt.status(x) for x in (1.0, 0.9, 0.89, 0.5, 0.49, 0.0)] == [
        "covered",
        "covered",
        "partial",
        "partial",
        "none",
        "none",
    ]


def test_a_piece_straddling_two_consecutive_chunks_is_still_chunked(lt):
    half_a = "The Program Manager shall maintain the access roster"
    half_b = "and report changes to the security office monthly. More."
    chunks = _chunks(lt, c1="Other text.", c2=half_a, c3=half_b, c4="Unrelated.")
    assert lt.chunk_ids_holding(lt.tokens(PIECE), chunks) == [2, 3]
    assert (
        lt.chunk_ids_holding(lt.tokens("A sentence found nowhere in this document at all."), chunks)
        == []
    )


@pytest.mark.parametrize(
    "records,survivors,indexed,loss",
    [
        ([], set(), {"a"}, "not_extracted"),
        (
            [_rec("a", 1, "The Program Manager shall maintain the access roster")],
            {"a"},
            {"a"},
            "partly_extracted",
        ),
        (
            [_rec("a", 1, CHUNK[CHUNK.index("The Program") : CHUNK.index(" Other")])],
            set(),
            {"a"},
            "rejected_step_d",
        ),
        (
            [_rec("a", 1, CHUNK[CHUNK.index("The Program") : CHUNK.index(" Other")])],
            {"a"},
            set(),
            "not_indexed",
        ),
        (
            [_rec("a", 1, CHUNK[CHUNK.index("The Program") : CHUNK.index(" Other")])],
            {"a"},
            {"a"},
            None,
        ),
    ],
)
def test_each_pipeline_step_is_named_as_the_first_loss(lt, records, survivors, indexed, loss):
    chunks = _chunks(lt, c1=CHUNK)
    t = lt.trace_piece(PIECE, chunks, records, survivors, indexed)
    assert t["first_loss"] == loss


def test_a_piece_missing_from_every_chunk_is_never_chunked(lt):
    t = lt.trace_piece(
        PIECE, _chunks(lt, c1="Entirely different words about something else."), [], set(), set()
    )
    assert t["first_loss"] == "never_chunked" and t["chunk_ids"] == []


def test_two_records_jointly_cover_a_split_piece_and_a_never_indexed_run_has_no_index_stage(lt):
    chunks = _chunks(lt, c1=CHUNK)
    recs = [
        _rec("a", 1, "The Program Manager shall maintain the access roster"),
        _rec("b", 1, "and report changes to the security office monthly."),
    ]
    t = lt.trace_piece(PIECE, chunks, recs, {"a", "b"}, None)
    assert t["first_loss"] is None and "indexed" not in t["status"] and t["covering_records"] == 2
    # only one of the two survives Step D: the loss is at Step D, and the rejected id is reported
    t = lt.trace_piece(PIECE, chunks, recs, {"a"}, None)
    assert t["first_loss"] == "rejected_step_d" and t["rejected_ids"] == ["b"]


def _labels(pairs):
    out = {"claude": {}, "codex": {}}
    for pid, (a, b) in pairs.items():
        out["claude"][pid] = {"id": pid, "label": a, "segment_ok": True, "note": ""}
        out["codex"][pid] = {"id": pid, "label": b, "segment_ok": True, "note": ""}
    return out


def test_answers_parse_and_every_disagreement_needs_a_ruling(sc):
    labels = _labels(
        {"X-p001-001": ("obligation", "obligation"), "X-p001-002": ("obligation", "scope")}
    )
    assert sc.disagreements(labels) == ["X-p001-002"]
    with pytest.raises(ValueError, match="without a ruling"):
        sc.resolve(labels, {})
    final = sc.resolve(labels, sc.parse_answers("X-p001-002: scope  # ruled\n\n"))
    assert final["X-p001-002"]["label"] == "scope" and final["X-p001-001"]["label"] == "obligation"
    with pytest.raises(ValueError):
        sc.parse_answers("X-p001-002: maybe")
    sets = sc.label_sets(labels, final)
    assert sets["adjudicated"] == {"X-p001-001"} and sets["either"] == {"X-p001-001", "X-p001-002"}
    assert sets["both_agree"] == {"X-p001-001"}


def test_spot_checks_are_seeded_and_split_between_obligations_and_non_obligations(sc):
    pairs = {f"X-p001-{i:03d}": ("obligation", "obligation") for i in range(1, 9)}
    pairs.update({f"X-p001-{i:03d}": ("not_obligation", "not_obligation") for i in range(9, 20)})
    labels = _labels(pairs)
    spot = sc.spot_checks(labels)
    assert spot == sc.spot_checks(labels) and len(spot) == 10
    assert sum(labels["claude"][i]["label"] == "obligation" for i in spot) == 5


def _trace(doc, page, **status):
    return {"document": doc, "page": page, "chunk_ids": [1], "status": status}


def test_the_bootstrap_resamples_pages_and_reports_recall_by_stage(sc):
    traces = {
        "a": _trace("D", 1, extracted="covered", survived_step_d="covered"),
        "b": _trace("D", 1, extracted="covered", survived_step_d="none"),
        "c": _trace("D", 2, extracted="partial", survived_step_d="none"),
        "d": _trace("D", 2, extracted="none", survived_step_d="none"),
    }
    r = sc.page_bootstrap(traces, False, resamples=500)
    assert r["chunked"]["primary"]["recall"] == 1.0
    assert (
        r["extracted"]["primary"]["recall"] == 0.5 and r["extracted"]["lenient"]["recall"] == 0.75
    )
    assert r["survived_step_d"]["primary"]["recall"] == 0.25
    assert r == sc.page_bootstrap(traces, False, resamples=500)
    lo, hi = r["extracted"]["primary"]["interval"]
    assert lo <= 0.5 <= hi and "indexed" not in r


def test_a_paired_difference_uses_the_same_pieces(sc):
    a = {
        "x": _trace("D", 1, extracted="covered"),
        "y": _trace("D", 2, extracted="covered"),
    }
    b = {
        "x": _trace("D", 1, extracted="covered"),
        "y": _trace("D", 2, extracted="none"),
    }
    d = sc.paired_difference(a, b, "extracted", resamples=300)
    assert d["difference"] == 0.5 and d["n"] == 2

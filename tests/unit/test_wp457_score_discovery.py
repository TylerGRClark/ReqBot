"""WP-45.7: the dev discovery scoring rules (offline; the committed 45.1(e) labels are real, the corpus files are not needed)."""

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "eval/spike_results/wp_45_7"


@pytest.fixture(scope="module")
def SD():
    pytest.importorskip("numpy")
    for p in (_DIR, _ROOT, _ROOT / "eval/spike_results/wp_45_1e", _ROOT / "eval/spike_results/wp_45_audit"):
        sys.path.insert(0, str(p))
    try:
        spec = importlib.util.spec_from_file_location("score_discovery", _DIR / "score_discovery.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["score_discovery"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for p in (_DIR, _ROOT, _ROOT / "eval/spike_results/wp_45_1e", _ROOT / "eval/spike_results/wp_45_audit"):
            sys.path.remove(str(p))


def test_the_dev_labels_load_with_the_expected_sample(SD):
    final, index, obligations, pages = SD.load_dev_labels()
    assert len(obligations) == 74 and len(pages) == 12  # 78 adjudicated, 74 with sound segmentation, over 12 sampled pages
    assert all(final[i]["label"] == "obligation" and not final[i]["flagged"] for i in obligations)
    assert {index[i]["document"] for i in index} == {"DODI 8410.03", "NIST.SP.800-125", "afman17-2101"}


def test_a_record_touches_a_piece_when_it_holds_half_the_piece_or_the_piece_holds_half_the_record(SD):
    T = sys.modules["loss_trace"]
    piece = T.tokens("The Director shall review the quarterly retention reports every year.", drop_marker=False)
    assert SD.touches(piece, T.tokens("The Director shall review the quarterly retention reports every year.", drop_marker=False))
    assert SD.touches(piece, T.tokens("shall review the quarterly retention reports", drop_marker=False))  # holds half the piece
    long_piece = T.tokens("a b c d e f g h i j The Director shall review the plan k l m n o p q r s t", drop_marker=False)
    assert SD.touches(long_piece, T.tokens("The Director shall review the plan", drop_marker=False))  # inside a long piece
    assert not SD.touches(piece, T.tokens("Hypervisors can pause guests.", drop_marker=False))
    assert not SD.touches([], T.tokens("anything", drop_marker=False))


def test_precision_classifies_true_false_and_unscored_records(SD):
    final = {"P1": {"label": "obligation"}, "P2": {"label": "not_obligation"}, "P3": {"label": "scope"}}
    index = {
        "P1": {"document": "D", "text": "Operators shall review logs every day."},
        "P2": {"document": "D", "text": "Virtualization is the practice of running several systems on one machine."},
        "P3": {"document": "D", "text": "This manual applies to all network operators in the command."},
    }
    records = [
        ("D", {"source_quote": "Operators shall review logs every day."}),  # touches the obligation
        ("D", {"source_quote": "Virtualization is the practice of running several systems"}),  # only a background piece
        ("D", {"source_quote": "This manual applies to all network operators"}),  # scope text
        ("D", {"source_quote": "Quarterly budget forms are due in March from every office"}),  # in no labeled piece
    ]
    got = SD.precision_tally(records, final, index)
    assert got == {"true_positive": 1, "false_positive": 2, "false_positive_not_obligation": 1, "false_positive_scope": 1, "unscored": 1}
    assert SD.precision_rate(got) == round(1 / 3, 3)  # unscored records are in neither side
    assert SD.precision_rate({"unscored": 4}) is None

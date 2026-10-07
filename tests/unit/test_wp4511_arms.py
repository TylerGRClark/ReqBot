"""WP-45.11: the arm runner and scorer's pure helpers (offline; no model, no scratch runs)."""

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "eval/spike_results/wp_45_11"


def _load(name):
    for p in (_DIR, _ROOT, _ROOT / "eval/spike_results/wp_45_10", _ROOT / "eval/spike_results/wp_45_6", _ROOT / "eval/spike_results/wp_45_1e",
              _ROOT / "eval/spike_results/wp_45_audit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location(f"wp4511_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wp4511_{name}"] = module
    spec.loader.exec_module(module)
    return module


RA = _load("run_arm")
SA = _load("score_arms")


def test_chunk_spec_must_be_tag_and_label():
    tag, label, path = RA.chunk_dir("d2.94.0:256")
    assert (tag, label) == ("d2.94.0", "256") and path.parts[-3:] == ("d2.94.0", "chunks", "256")
    with pytest.raises(SystemExit):
        RA.chunk_dir("256")


def test_an_arm_directory_is_never_reused(tmp_path):
    (tmp_path / "A" / "doc").mkdir(parents=True)
    (tmp_path / "A" / "doc" / "x").write_text("old")
    with pytest.raises(SystemExit):
        RA.run_doc("A", "doc", "d2.94.0:256", "m", "http://x", 1, None, scratch=tmp_path)


def test_overlap_counts_shared_and_exclusive_quotes():
    qa = {"d1": {"a", "b"}, "d2": {"c"}}
    qb = {"d1": {"b", "x"}, "d2": {"c"}}
    out = SA.overlap(qa, qb)
    assert out["per_document"]["d1"] == {"shared": 1, "only_first": 1, "only_second": 1, "jaccard": 0.333}
    assert out["overall_jaccard"] == 0.5


def test_paired_reports_each_direction_and_the_rest():
    ta = {"p1": {"status": {"extracted": "covered"}}, "p2": {"status": {"extracted": "covered"}}, "p3": {"status": {"extracted": "none"}}}
    tb = {"p1": {"status": {"extracted": "covered"}}, "p2": {"status": {"extracted": "none"}}, "p3": {"status": {"extracted": "covered"}}}
    assert SA.paired(ta, tb) == {"only_first": ["p2"], "only_second": ["p3"], "both": 1, "neither": 0}


def test_the_recall_sample_is_the_74_adjudicated_unflagged_obligations():
    index, ids = SA.obligations()
    assert len(ids) == 74 and ids <= set(index)


def test_an_incomplete_arm_is_not_scored(tmp_path):
    (tmp_path / "A" / "DODI 5200.01").mkdir(parents=True)
    with pytest.raises(SystemExit) as e:
        SA.check_complete("A", scratch=tmp_path)
    assert "not complete" in str(e.value) and "DODI 5200.01_chunks.jsonl" in str(e.value) and "CJCSI 6510.02G" in str(e.value)


def test_a_failed_pipeline_return_code_is_listed(tmp_path):
    import json as _json
    for doc in SA.common.pinned_documents():
        d = tmp_path / "A" / doc
        d.mkdir(parents=True)
        for pattern in SA.ARTIFACTS:
            (d / pattern.format(doc=doc)).write_text("{}" if pattern.endswith(".json") else "")
        (d / "arm_record.json").write_text(_json.dumps({"returncode": 0}))
    SA.check_complete("A", scratch=tmp_path)  # a complete, successful arm passes
    (tmp_path / "A" / "DODI 5200.01" / "arm_record.json").write_text(_json.dumps({"returncode": 1}))
    with pytest.raises(SystemExit) as e:
        SA.check_complete("A", scratch=tmp_path)
    assert "DODI 5200.01: the pipeline did not exit 0" in str(e.value)

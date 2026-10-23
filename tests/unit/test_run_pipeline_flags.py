"""WP-24.3 — confirm --full-extraction and pass1_only are fully removed from
pipeline/run_pipeline.py; WP-4 of the clause-labeling switch — requirement finding
is clause labeling, and the list-writing step is gone (no switch back)."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pipeline.run_pipeline as run_pipeline


def test_full_extraction_flag_removed_from_cli_help(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--help"])
    with pytest.raises(SystemExit):
        run_pipeline.main()
    assert "--full-extraction" not in capsys.readouterr().out


def test_run_pipeline_run_no_longer_accepts_pass1_only_kwarg(tmp_path):
    with pytest.raises(TypeError):
        run_pipeline.run(str(tmp_path / "doc.pdf"), str(tmp_path), pass1_only=True)


def test_the_list_writing_extraction_step_is_gone():
    """The owner's rule: replace, no opt-in mode, no legacy fallback."""
    assert importlib.util.find_spec("pipeline.llm_extract_requirements") is None
    assert importlib.util.find_spec("pipeline.anchor") is None


def test_requirement_finding_runs_the_clause_labeler_with_the_extraction_model(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    emitted = []
    with patch.object(run_pipeline, "_docling_available", return_value=True), \
         patch("pipeline.clause_labeling.run") as label, \
         patch("pipeline.parse_and_normalize.run") as normalize, \
         patch("pipeline.aggregate_and_export.run"), \
         patch("pipeline.progress.emit", side_effect=lambda step, *a: emitted.append(step)):
        run_pipeline.run(str(pdf), str(tmp_path), extraction_model="labeler:1b", ollama_url="http://ollama:11434", skip_to="requirement-finding",
                         max_chunks=3, timeout=77)
    label.assert_called_once()
    args, kwargs = label.call_args
    assert args == (str(tmp_path / "doc_chunks.jsonl"), str(tmp_path))
    assert kwargs == {"model": "labeler:1b", "ollama_url": "http://ollama:11434", "timeout": 77, "max_chunks": 3}
    assert normalize.call_args.kwargs["extraction_model"] == "labeler:1b"
    assert emitted[0] == "finding"  # the step keeps its progress name


def test_the_standalone_default_model_is_the_measured_labeler(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--help"])
    with pytest.raises(SystemExit):
        run_pipeline.main()
    assert "ornith:35b" in capsys.readouterr().out

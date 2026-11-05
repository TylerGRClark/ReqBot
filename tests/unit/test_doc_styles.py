"""Document styles (core/doc_styles.py, doc_styles/*.json): the loader, the built-in "general"
style (today's behavior), and the fact that choosing no style changes nothing a run writes except
the style's own name in stats."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import core.doc_styles as styles_mod
from core.doc_styles import DEFAULT_STYLE, default_style, list_styles, load_style, style_record
from pipeline.aggregate_and_export import run as aggregate_run


@pytest.fixture()
def style_dir(tmp_path, monkeypatch):
    """Point the loader at an empty temp folder."""
    monkeypatch.setattr(styles_mod, "_STYLES_DIR", tmp_path)
    return tmp_path


def _write(directory: Path, data: dict, name: str | None = None) -> None:
    (directory / f"{name or data.get('name', 'test')}.json").write_text(json.dumps(data), encoding="utf-8")


_VALID = {"name": "test", "version": "1", "reference_grammar": None}


def test_general_is_the_default_and_means_no_rules():
    style = default_style()
    assert style["name"] == DEFAULT_STYLE == "general"
    assert style["reference_grammar"] is None
    assert load_style() == style


def test_shipped_styles_all_load():
    assert "general" in list_styles()
    for name in list_styles():
        assert load_style(name)["name"] == name


def test_style_record_is_name_and_version_only():
    assert style_record(load_style("general")) == {"name": "general", "version": "1"}


def test_loader_returns_a_copy_each_time():
    a = load_style("general")
    a["description"] = "changed"
    assert load_style("general")["description"] != "changed"


def test_missing_style_is_a_clear_error(style_dir):
    with pytest.raises(FileNotFoundError, match="nope"):
        load_style("nope")


@pytest.mark.parametrize("bad", ["../general", "a/b", "a\\b", ".hidden", "", "   "])
def test_bad_names_are_rejected(bad):
    with pytest.raises(ValueError):
        load_style(bad)


def test_unknown_field_is_rejected(style_dir):
    _write(style_dir, {**_VALID, "colour": "red"})
    with pytest.raises(ValueError, match="Unknown"):
        load_style("test")


@pytest.mark.parametrize("missing", ["name", "version", "reference_grammar"])
def test_required_fields_must_be_present(style_dir, missing):
    data = {k: v for k, v in _VALID.items() if k != missing}
    _write(style_dir, data, name="test")
    with pytest.raises(ValueError, match="Missing"):
        load_style("test")


def test_name_must_match_the_file(style_dir):
    _write(style_dir, {**_VALID, "name": "other"}, name="test")
    with pytest.raises(ValueError, match="mismatch"):
        load_style("test")


def test_wrong_types_and_empty_values_are_rejected(style_dir):
    _write(style_dir, {**_VALID, "version": 1})
    with pytest.raises(ValueError, match="version"):
        load_style("test")
    _write(style_dir, {**_VALID, "version": "  "})
    with pytest.raises(ValueError, match="empty"):
        load_style("test")


def test_a_valid_grammar_is_accepted(style_dir):
    _write(style_dir, {**_VALID, "reference_grammar": {"gap_tolerance": 4}})
    assert load_style("test")["reference_grammar"] == {"gap_tolerance": 4}


def test_a_bad_grammar_is_an_error_not_a_silent_no_op(style_dir):
    """A typo in a grammar field must not quietly turn the rules off."""
    _write(style_dir, {**_VALID, "reference_grammar": {"gap_tolerence": 4}})
    with pytest.raises(ValueError, match="gap_tolerence"):
        load_style("test")


def test_non_object_and_broken_json_are_rejected(style_dir):
    (style_dir / "test.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        load_style("test")
    (style_dir / "test.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="valid JSON"):
        load_style("test")


# --- what a run writes -------------------------------------------------------------------------

def _stats(tmp_path, **overrides):
    reqs = tmp_path / "doc_requirements_normalized.jsonl"
    reqs.write_text(json.dumps({"requirement_id": "REQ-a", "confidence": 0.9}) + "\n", encoding="utf-8")
    kwargs = dict(requirements_jsonl=str(reqs), output_dir=str(tmp_path), source_pdf="doc.pdf")
    kwargs.update(overrides)
    return aggregate_run(**kwargs)


def test_stats_record_the_style_when_given(tmp_path):
    stats = _stats(tmp_path, doc_style={"name": "general", "version": "1"})
    assert stats["pipeline"]["doc_style"] == {"name": "general", "version": "1"}
    on_disk = json.loads(next(tmp_path.glob("*_stats.json")).read_text(encoding="utf-8"))
    assert on_disk["pipeline"]["doc_style"] == {"name": "general", "version": "1"}


def test_stats_are_otherwise_identical_with_or_without_a_style(tmp_path_factory):
    """Default behavior is unchanged: apart from the style's own entry, the stats match exactly."""
    a = _stats(tmp_path_factory.mktemp("a"))
    b = _stats(tmp_path_factory.mktemp("b"), doc_style={"name": "general", "version": "1"})
    for stats in (a, b):
        stats["pipeline"].pop("doc_style")
        stats.pop("generated_at", None)
        stats.get("pipeline", {}).pop("run_timestamp", None)
    assert a == b


def test_a_requirement_record_gets_no_style_field(tmp_path):
    """No JSONL schema change: the style lives in stats only."""
    reqs = tmp_path / "doc_requirements_normalized.jsonl"
    rec = {"requirement_id": "REQ-a", "confidence": 0.9}
    reqs.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    aggregate_run(str(reqs), str(tmp_path), doc_style={"name": "general", "version": "1"})
    assert json.loads(reqs.read_text(encoding="utf-8")) == rec


# --- the pipeline entry point and the command line ---------------------------------------------

def test_pipeline_fails_before_any_work_on_an_unknown_style(tmp_path):
    import pipeline.run_pipeline as run_pipeline

    with pytest.raises(RuntimeError, match="document style 'nope'"):
        run_pipeline.run(str(tmp_path / "doc.pdf"), str(tmp_path), doc_style_name="nope")


def test_ingest_command_defaults_to_the_general_style(monkeypatch):
    import cli.reqbot as reqbot

    parser_help = []
    monkeypatch.setattr(sys, "argv", ["reqbot", "ingest", "x.pdf", "--no-index"])
    with patch.object(reqbot, "cmd_ingest", side_effect=lambda a: parser_help.append(a) or 0):
        try:
            reqbot.main()
        except SystemExit:
            pass
    assert parser_help and parser_help[0].style == "general"

"""The access codes of the network MCP door (core/mcp_codes.py), their CLI (`reqbot mcp-code`) and the request log (mcp_server/request_log.py).

None of this needs the optional mcp extra, so it always runs, including in CI's base install."""
import argparse
import json
import os
import stat

import pytest

from core import mcp_codes
from mcp_server import request_log as rl
from mcp_server.request_log import RequestLog, summarize_arguments


@pytest.fixture(autouse=True)
def codes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_codes, "CODES_PATH", tmp_path / "mcp_codes.json")
    monkeypatch.delenv(mcp_codes.ENV_CODES, raising=False)
    return tmp_path / "mcp_codes.json"


def test_a_new_code_is_shown_once_and_only_its_hash_is_saved(codes_file):
    code = mcp_codes.add("claude-desktop-anna")
    assert code.startswith("rbmcp_") and len(code) > 40
    saved = codes_file.read_text(encoding="utf-8")
    assert code not in saved and "claude-desktop-anna" in saved  # the name is kept, the code is not
    assert stat.S_IMODE(os.stat(codes_file).st_mode) == 0o600


def test_a_presented_code_names_its_owner_and_nothing_else_does():
    a, b = mcp_codes.add("anna"), mcp_codes.add("ben")
    assert mcp_codes.verify(a) == "anna" and mcp_codes.verify(b) == "ben"
    assert mcp_codes.verify(a + "x") is None and mcp_codes.verify("") is None and mcp_codes.verify(None) is None
    assert mcp_codes.verify(" " + a + " ") == "anna"  # a stray space from a copy and paste


def test_revoking_cuts_one_tool_off_and_leaves_the_others():
    a, b = mcp_codes.add("anna"), mcp_codes.add("ben")
    assert mcp_codes.revoke("ANNA") is True  # names are matched without regard to case
    assert mcp_codes.verify(a) is None and mcp_codes.verify(b) == "ben"
    assert mcp_codes.revoke("anna") is False


def test_a_name_must_be_plain_and_unused():
    mcp_codes.add("anna")
    for bad in ("", " ", "../x", "a b", "-lead", "x" * 41, "naïve"):
        with pytest.raises(ValueError):
            mcp_codes.add(bad)
    with pytest.raises(ValueError):
        mcp_codes.add("Anna")


def test_listing_shows_names_and_sources_never_codes_or_hashes(codes_file):
    code = mcp_codes.add("anna")
    rows = mcp_codes.listing()
    assert [r["name"] for r in rows] == ["anna"] and rows[0]["source"] == "file"
    flat = json.dumps(rows)
    assert code not in flat and json.loads(codes_file.read_text())["codes"][0]["hash"] not in flat


def test_codes_from_the_environment_work_and_short_ones_are_refused(monkeypatch):
    good = "g" * 30
    monkeypatch.setenv(mcp_codes.ENV_CODES, f"proxy-a={good}, weak=short ,=nothing, bad name={good}")
    assert mcp_codes.verify(good) == "proxy-a"
    assert mcp_codes.verify("short") is None
    assert [r["name"] for r in mcp_codes.listing()] == ["proxy-a"]
    assert sorted(mcp_codes.rejected_from_environment()) == ["?", "bad name", "weak"]
    with pytest.raises(ValueError):  # it lives in the environment, so it is removed there
        mcp_codes.revoke("proxy-a")


def test_a_damaged_file_means_no_codes_not_a_crash(codes_file):
    codes_file.write_text("{not json", encoding="utf-8")
    assert mcp_codes.count() == 0 and mcp_codes.verify("anything") is None
    codes_file.write_text(json.dumps({"codes": [{"name": 5}, "x", {"name": "ok", "hash": "00"}]}), encoding="utf-8")
    assert [r["name"] for r in mcp_codes.listing()] == ["ok"]


def test_the_cli_shows_a_code_once_and_lists_names_only(capsys):
    from cli.reqbot import cmd_mcp_code

    assert cmd_mcp_code(argparse.Namespace(mcp_code_command="add", name="anna")) == 0
    out = capsys.readouterr().out
    code = next(line.strip() for line in out.splitlines() if line.strip().startswith("rbmcp_"))
    assert mcp_codes.verify(code) == "anna"
    assert cmd_mcp_code(argparse.Namespace(mcp_code_command="list")) == 0
    listed = capsys.readouterr().out
    assert "anna" in listed and code not in listed
    assert cmd_mcp_code(argparse.Namespace(mcp_code_command="add", name="anna")) == 1  # taken
    assert cmd_mcp_code(argparse.Namespace(mcp_code_command="revoke", name="anna")) == 0
    assert cmd_mcp_code(argparse.Namespace(mcp_code_command="revoke", name="anna")) == 1
    assert mcp_codes.verify(code) is None


# --- request log ---

def test_the_log_keeps_who_what_and_how_it_went_in_one_line_per_call(tmp_path):
    log = RequestLog(tmp_path / ".mcp" / "requests.jsonl")
    log.record(code="anna", tool="search_requirements", arguments={"question": "access reviews", "top_k": 5}, ok=True, ms=812)
    log.record(code="anna", tool="trace_requirement", arguments={"requirement_id": "REQ-1"}, ok=False, ms=3, error="RuntimeError: boom", reference="ab12cd34")
    lines = [json.loads(x) for x in (tmp_path / ".mcp" / "requests.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(e["code"], e["tool"], e["ok"]) for e in lines] == [("anna", "search_requirements", True), ("anna", "trace_requirement", False)]
    assert lines[0]["arguments"] == {"question": "access reviews", "top_k": 5} and lines[0]["ms"] == 812
    assert lines[1]["error"] == "RuntimeError: boom" and lines[1]["reference"] == "ab12cd34"
    assert stat.S_IMODE(os.stat(tmp_path / ".mcp" / "requests.jsonl").st_mode) == 0o600


def test_long_text_and_long_lists_are_cut_short_in_the_log():
    out = summarize_arguments({"question": "q" * 1000, "document_ids": [f"d{i}" for i in range(50)], "n": 3, "odd": object()})
    assert len(out["question"]) == rl.TEXT_LIMIT + 1 and out["question"].endswith("…")
    assert len(out["document_ids"]) == rl.LIST_LIMIT + 1 and out["document_ids"][-1] == "…"
    assert out["n"] == 3 and out["odd"] == "object"


def test_a_log_file_that_already_exists_is_made_private(tmp_path):
    path = tmp_path / "requests.jsonl"
    path.write_text("", encoding="utf-8")
    os.chmod(path, 0o644)  # REQBOT_MCP_LOG pointing at a file somebody made earlier
    RequestLog(path).record(code="anna", tool="get_status", ok=True)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["tool"] == "get_status"


def test_the_codes_file_is_private_even_over_a_leftover_temp_file(codes_file):
    leftover = codes_file.with_suffix(".tmp")
    leftover.write_text("", encoding="utf-8")
    os.chmod(leftover, 0o644)
    mcp_codes.add("anna")
    assert stat.S_IMODE(os.stat(codes_file).st_mode) == 0o600


def test_the_log_rotates_once_and_a_write_failure_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(rl, "MAX_BYTES", 200)
    path = tmp_path / "requests.jsonl"
    log = RequestLog(path)
    for i in range(10):
        log.record(code="anna", tool="get_status", arguments={"i": i}, ok=True)
    assert path.with_name("requests.jsonl.1").exists() and path.stat().st_size <= 400
    blocked = RequestLog(tmp_path / "file" / "requests.jsonl")
    (tmp_path / "file").write_text("not a folder", encoding="utf-8")
    blocked.record(code="anna", tool="get_status", ok=True)  # must not raise

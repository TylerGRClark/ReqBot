"""The network MCP door (mcp_server/network.py): `reqbot mcp --http`.

What is held here is the safety shape: only the seven read-only tools, nobody without a live access code, nothing about the server's layout in an answer or an error, no
synthesis, a slow call that does not stop others, a cap on simultaneous calls, and a log line for every call. The services are replaced by fakes, so no model or index is
touched. mcp is an optional extra (pyproject.toml): these skip cleanly where it is absent, and CI installs it so they run there.
"""
import asyncio
import inspect
import json
import time
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("mcp")

from starlette.testclient import TestClient  # noqa: E402

from core import mcp_codes  # noqa: E402
from mcp_server import network, server  # noqa: E402
from mcp_server.request_log import RequestLog  # noqa: E402

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
INTERNAL = ("192.168.30.153", "192.168.90.100", "/home/coder", "llama3.1", "ollama:11434")


@pytest.fixture(autouse=True)
def codes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_codes, "CODES_PATH", tmp_path / "mcp_codes.json")
    monkeypatch.delenv(mcp_codes.ENV_CODES, raising=False)
    monkeypatch.delenv(network.ENV_MAX_CONCURRENT, raising=False)


@pytest.fixture
def request_log(tmp_path):
    return RequestLog(tmp_path / ".mcp" / "requests.jsonl")


def _log_entries(request_log):
    if not request_log.path.exists():
        return []
    return [json.loads(line) for line in request_log.path.read_text(encoding="utf-8").splitlines()]


def _cfg():
    cfg = MagicMock()
    cfg.ollama_url, cfg.qdrant_url = "http://192.168.90.100:11434", "http://192.168.30.153:6333"
    cfg.processed_dir_path.return_value = "/home/coder/documents/processed"
    cfg.embedding_model, cfg.extraction_model, cfg.enrichment_model = "e-model", "llama3.1:8b", "en-model"
    cfg.rewrite_model, cfg.synthesis_model, cfg.min_score = "r-model", "s-model", 0.07
    cfg.synthesis_backend, cfg.remote_provider, cfg.remote_model, cfg.api_key_env = "local", "anthropic", "m", "KEY"
    return cfg


def _rpc(client, method, params=None, token=None, rid=1):
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post("/mcp", json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}, headers=headers)


def _call(client, token, name, arguments=None):
    body = _rpc(client, "tools/call", {"name": name, "arguments": arguments or {}}, token).json()["result"]
    return body.get("isError", False), body["content"][0]["text"]


@pytest.fixture
def door(request_log):
    """(client, code): a running door with one access code and the stdio server's configuration faked."""
    code = mcp_codes.add("anna")
    app = network.build_app(request_log=request_log, failed_code_delay=0.0)
    with patch("mcp_server.server._config.load", return_value=_cfg()), TestClient(app, base_url="http://127.0.0.1:8765") as client:
        yield client, code


# --- what the door is ---

def test_the_door_serves_exactly_the_seven_read_only_tools(door):
    client, code = door
    tools = _rpc(client, "tools/list", token=code).json()["result"]["tools"]
    assert {t["name"] for t in tools} == set(network.TOOL_NAMES) and len(tools) == 7
    for name in network.TOOL_NAMES:  # a read-only door: no verb that changes, starts or configures anything
        assert not any(w in name for w in ("ingest", "remove", "delete", "upload", "reindex", "question", "job", "token", "config", "write", "start", "cancel", "replace"))
    for t in tools:
        assert "ctx" not in t["inputSchema"].get("properties", {})
        assert "synthesize" not in t["inputSchema"].get("properties", {})


def test_each_tool_takes_the_arguments_of_its_stdio_twin_less_synthesize(door):
    client, code = door
    tools = {t["name"]: t for t in _rpc(client, "tools/list", token=code).json()["result"]["tools"]}
    for name in network.TOOL_NAMES:
        params = inspect.signature(getattr(server, name)).parameters
        expected = {p for p in params if p != "synthesize"}
        schema = tools[name]["inputSchema"]
        assert set(schema.get("properties", {})) == expected, name
        required = {p for p, v in params.items() if v.default is inspect.Parameter.empty and p != "synthesize"}
        assert set(schema.get("required", [])) == required, name


def test_the_stdio_server_is_untouched_and_still_offers_synthesis():
    assert "synthesize" in inspect.signature(server.map_evidence).parameters
    assert callable(server.run)


# --- who may call ---

def test_no_code_no_answer(door, request_log):
    client, code = door
    assert _rpc(client, "tools/list").status_code == 401
    assert _rpc(client, "tools/list", token="rbmcp_wrong").status_code == 401
    headers = dict(HEADERS, Authorization=f"Basic {code}")  # the right string in the wrong scheme
    assert client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=headers).status_code == 401
    refused = [e for e in _log_entries(request_log) if e["tool"] == "(sign-in)"]
    assert len(refused) == 3 and all(not e["ok"] and e["code"] == "-" for e in refused)
    assert code not in json.dumps(_log_entries(request_log))


def test_a_revoked_code_stops_on_the_next_request_without_a_restart(door):
    client, code = door
    other = mcp_codes.add("ben")
    assert _rpc(client, "tools/list", token=code).status_code == 200
    mcp_codes.revoke("anna")
    assert _rpc(client, "tools/list", token=code).status_code == 401
    assert _rpc(client, "tools/list", token=other).status_code == 200


def test_every_call_is_logged_under_the_name_of_its_code(door, request_log):
    client, code = door
    ben = mcp_codes.add("ben")
    with patch("mcp_server.server.ask_service.ask", return_value={"results": []}):
        _call(client, code, "search_requirements", {"question": "access reviews", "top_k": 3})
        _call(client, ben, "search_requirements", {"question": "incident reporting"})
    entries = [e for e in _log_entries(request_log) if e["tool"] == "search_requirements"]
    assert [(e["code"], e["ok"]) for e in entries] == [("anna", True), ("ben", True)]
    assert entries[0]["arguments"]["question"] == "access reviews" and entries[0]["arguments"]["top_k"] == 3
    assert all(e["ms"] >= 0 for e in entries)


# --- nothing about the server's layout ---

def test_status_says_what_is_reachable_not_where(door):
    client, code = door
    full = {
        "ollama_url": "http://192.168.90.100:11434", "qdrant_url": "http://192.168.30.153:6333",
        "ollama": {"reachable": True, "models": [{"name": "llama3.1:8b", "size_gb": 4.7}]},
        "qdrant": {"reachable": True, "collections": [{"name": "grc_requirements", "points": 2420}]},
        "processed_documents": [{"path": "~/documents/processed/afi17-203_x/afi17-203_requirements_normalized.jsonl", "count": 133}],
        "configured_models": {"extraction": "llama3.1:8b"},
    }
    with patch("mcp_server.server.status_service.check", return_value=full):
        failed, text = _call(client, code, "get_status")
    assert not failed
    assert json.loads(text) == {
        "ollama": {"reachable": True},
        "qdrant": {"reachable": True, "collections": [{"name": "grc_requirements", "points": 2420}]},
        "documents": {"count": 1, "requirements": 133},
    }
    assert not any(s in text for s in INTERNAL)


def test_the_document_list_leaves_out_folders_and_keeps_the_profile(door, tmp_path):
    """Run through the real document listing on a small processed folder, so the test cannot drift from the fields it really emits."""
    client, code = door
    run = tmp_path / "library" / "afi17-203_20261004_120000"
    run.mkdir(parents=True)
    rows = [{"requirement_id": f"REQ-{i}", "source_pdf": "afi17-203.pdf", "domain_profile": "cybersecurity", "source_quote": "Units will report."} for i in range(2)]
    (run / "afi17-203_requirements_normalized.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    cfg = _cfg()
    cfg.processed_dir_path.return_value = tmp_path / "library"
    with patch("mcp_server.server._config.load", return_value=cfg):
        failed, text = _call(client, code, "list_documents")
    data = json.loads(text)
    assert not failed and data["total_docs"] == 1 and data["total_reqs"] == 2
    assert data["docs"][0] == {"doc_key": "afi17-203", "source_pdf": "afi17-203.pdf", "count": 2, "mode": data["docs"][0]["mode"], "run_date": "2026-10-04", "profile": "cybersecurity"}
    assert str(tmp_path) not in text and "path" not in data["docs"][0]


def test_the_servers_model_names_are_removed_from_every_answer(door):
    client, code = door
    hit = {
        "requirement_id": "REQ-1", "source_quote": "Units will report.", "citation": "3.1", "source_pdf": "afi17-203.pdf",
        "extraction_model": "llama3.1:8b", "embedding_model": "nomic-embed-text", "embedding_dim": 768, "pipeline_version": "2026-10",
        "generation_notes": "Draft audit question written by qwen2.5:14b from the text above; check it before use.",
    }
    answer = {
        "results": [hit], "result_count": 1,
        "warnings": ["1 of 1 results were indexed with a different embedding model (nomic-embed-text) than your current config (e-model) and may be unreliable; run 'reqbot reindex' to refresh them.",
                     "Tag and type filters are off: the pipeline no longer assigns domain tags or requirement types, so the filter was ignored."],
    }
    with patch("mcp_server.server.ask_service.ask", return_value=answer):
        failed, text = _call(client, code, "search_requirements", {"question": "report"})
    data = json.loads(text)
    assert not failed
    row = data["results"][0]
    assert not {"extraction_model", "embedding_model", "embedding_dim"} & set(row)
    assert row["source_quote"] == "Units will report." and row["citation"] == "3.1" and row["pipeline_version"] == "2026-10"  # provenance stays
    assert "qwen2.5:14b" not in row["generation_notes"] and "from the text above" in row["generation_notes"]
    assert not any(n in text for n in ("llama3.1", "nomic-embed-text", "qwen2.5", "e-model"))
    assert data["warnings"][0].startswith("Some results were indexed with a different embedding model")
    assert data["warnings"][1].startswith("Tag and type filters are off")  # a warning that names no model is kept as it was


def test_scrub_leaves_a_clean_answer_exactly_as_it_was():
    answer = {"results": [{"source_quote": "Units will report.", "citation": "3.1", "page_start": 4, "tags": ["a"]}], "warnings": [], "n": 1, "ok": True, "none": None}
    assert network.scrub(answer, ["llama3.1:8b"]) == answer


def test_an_error_that_would_name_an_address_is_replaced_and_kept_in_the_log(door, request_log):
    client, code = door
    boom = RuntimeError("Could not connect to Qdrant: HTTPConnectionPool(host='192.168.30.153', port=6333): refused")
    with patch("mcp_server.server.ask_service.ask", side_effect=boom):
        failed, text = _call(client, code, "search_requirements", {"question": "x"})
    assert failed and "could not complete that request" in text and "192.168" not in text
    entry = [e for e in _log_entries(request_log) if e["tool"] == "search_requirements"][-1]
    assert not entry["ok"] and "192.168.30.153" in entry["error"]  # the operator sees all of it
    assert entry["reference"] and entry["reference"] in text  # and can find the line from the caller's reference


def test_mistakes_in_the_callers_own_input_keep_their_wording(door):
    client, code = door
    with patch("mcp_server.server.ask_service.ask", side_effect=ValueError("Unknown document_ids (no matching indexed document): nope")):
        failed, text = _call(client, code, "search_requirements", {"question": "x", "document_ids": ["nope"]})
    assert failed and "Unknown document_ids" in text and "nope" in text
    failed, text = _call(client, code, "search_requirements", {"question": "x", "top_k": 500})
    assert failed and "top_k must be between 1 and 100" in text
    missing = ValueError("No requirements JSONL found for doc_key 'nope' in /home/coder/documents/processed")
    with patch("mcp_server.server.checklist_service.generate", side_effect=missing):
        failed, text = _call(client, code, "generate_checklist", {"doc_key": "nope"})
    assert failed and "No document with the key 'nope'" in text and "/home" not in text


def test_a_search_result_carries_nothing_of_the_servers_layout(door):
    client, code = door
    hit = {"requirement_id": "REQ-1", "source_quote": "Units will report.", "source_ref": "3.1", "citation": "3.1", "source_pdf": "afi17-203.pdf"}
    with patch("mcp_server.server.ask_service.ask", return_value={"results": [hit], "result_count": 1}):
        failed, text = _call(client, code, "search_requirements", {"question": "report"})
    assert not failed and json.loads(text)["results"][0]["citation"] == "3.1"
    assert not any(s in text for s in INTERNAL)


# --- no synthesis, read only ---

def test_evidence_is_retrieval_only_even_if_the_caller_asks_for_a_summary(door):
    client, code = door
    built = MagicMock(return_value={"groups": {}, "group_order": []})
    with patch("mcp_server.server.evidence_service.build", built):
        _call(client, code, "map_evidence", {"topic": "access control"})
        _call(client, code, "map_evidence", {"topic": "access control", "synthesize": True})  # not an argument of this door
    assert built.call_count >= 1
    assert all(call.kwargs["synthesize"] is False for call in built.call_args_list)


def test_search_never_synthesizes(door):
    client, code = door
    asked = MagicMock(return_value={"results": []})
    with patch("mcp_server.server.ask_service.ask", asked):
        _call(client, code, "search_requirements", {"question": "x"})
    assert asked.call_args.kwargs["synthesize"] is False


# --- slow calls, busy server ---

class _Ctx:  # no HTTP request behind it: the caller is "unknown"
    pass


def _door(tmp_path, limit, wait=5.0):
    return network._Door(RequestLog(tmp_path / "r.jsonl"), limit, wait)


def test_a_slow_call_does_not_stop_another_caller(tmp_path):
    door = _door(tmp_path, limit=2)
    order = []

    def slow():
        time.sleep(0.4)
        order.append("slow")
        return "slow"

    def fast():
        order.append("fast")
        return "fast"

    async def both():
        return await asyncio.gather(door.call(_Ctx(), "search_requirements", slow), door.call(_Ctx(), "get_status", fast))

    started = time.monotonic()
    assert asyncio.run(both()) == ["slow", "fast"]
    assert order == ["fast", "slow"]  # the fast one finished while the slow one was still in its thread
    assert time.monotonic() - started < 0.8  # in parallel, not one after the other


def test_more_calls_than_slots_wait_and_then_are_told_the_server_is_busy(tmp_path):
    door = _door(tmp_path, limit=1, wait=0.05)

    def slow():
        time.sleep(0.4)
        return "done"

    async def two():
        first = asyncio.ensure_future(door.call(_Ctx(), "search_requirements", slow))
        await asyncio.sleep(0.05)
        try:
            await door.call(_Ctx(), "search_requirements", slow)
        except RuntimeError as exc:
            second = str(exc)
        return await first, second

    first, second = asyncio.run(two())
    assert first == "done" and second == network.BUSY_MESSAGE
    entries = [json.loads(x) for x in (tmp_path / "r.jsonl").read_text().splitlines()]
    assert [e["ok"] for e in entries] == [False, True] and "busy" in entries[0]["error"]


def test_the_cap_comes_from_the_environment_and_is_kept_in_range(monkeypatch):
    assert network._max_concurrent() == network.DEFAULT_MAX_CONCURRENT
    monkeypatch.setenv(network.ENV_MAX_CONCURRENT, "7")
    assert network._max_concurrent() == 7
    for raw, want in (("0", 1), ("999", 32), ("lots", network.DEFAULT_MAX_CONCURRENT)):
        monkeypatch.setenv(network.ENV_MAX_CONCURRENT, raw)
        assert network._max_concurrent() == want


# --- starting it ---

def test_it_refuses_to_start_with_no_access_code(caplog):
    with patch("uvicorn.run") as serve:
        assert network.run() == 1
    serve.assert_not_called()
    assert "mcp-code add" in caplog.text


def test_it_serves_the_app_on_the_given_address_once_a_code_exists(request_log):
    mcp_codes.add("anna")
    with patch("uvicorn.run") as serve, patch("mcp_server.network._default_log_path", return_value=request_log.path), patch("mcp_server.network.build_app", return_value="app") as build:
        assert network.run(host="0.0.0.0", port=9000, allowed_hosts=["mcp.example.org"]) == 0
    build.assert_called_once_with(host="0.0.0.0", port=9000, allowed_hosts=["mcp.example.org"])
    serve.assert_called_once()
    assert serve.call_args.kwargs["host"] == "0.0.0.0" and serve.call_args.kwargs["port"] == 9000


def test_the_host_allow_list_refuses_other_names(request_log):
    code = mcp_codes.add("anna")
    app = network.build_app(request_log=request_log, allowed_hosts=["mcp.example.org"], failed_code_delay=0.0)
    with patch("mcp_server.server._config.load", return_value=_cfg()), TestClient(app, base_url="http://mcp.example.org") as client:
        assert _rpc(client, "tools/list", token=code).status_code == 200
        wrong = dict(HEADERS, Authorization=f"Bearer {code}", Host="evil.example")  # a page on another name pointing at this server
        refused = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=wrong)
        assert refused.status_code in (400, 403, 421)


def test_the_cli_starts_the_door_only_with_http_and_passes_its_options():
    import argparse

    from cli.reqbot import cmd_mcp

    with patch("mcp_server.network.run", return_value=0) as run_net, patch("mcp_server.server.run") as run_stdio:
        args = argparse.Namespace(http=True, host="10.0.0.5", port=9001, allow_hosts=["mcp.example.org"])
        assert cmd_mcp(args) == 0
    run_net.assert_called_once_with(host="10.0.0.5", port=9001, allowed_hosts=["mcp.example.org"])
    run_stdio.assert_not_called()

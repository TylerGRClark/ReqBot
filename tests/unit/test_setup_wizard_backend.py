"""First-run setup checks (docs/WEB_UI_PARITY_PLAN.md, section 9a): the shared service, the two routes, and `reqbot init --check`."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

from services import setup_service as ss

LOOPBACK = TestClient(__import__("api.app", fromlist=["app"]).app, client=("127.0.0.1", 12345))
REMOTE = TestClient(__import__("api.app", fromlist=["app"]).app, client=("203.0.113.5", 12345))


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._payload


def fake_services(models=("llama3.1:8b-instruct-q4_K_M", "nomic-embed-text:latest"), collections=("grc_requirements",), ollama_up=True, qdrant_up=True):
    """A stand-in for `requests.get` that answers like Ollama and Qdrant."""
    calls = []

    def get(url, timeout=None, allow_redirects=True):
        calls.append(url)
        if url.endswith("/api/tags"):
            if not ollama_up:
                raise requests.ConnectionError("connection refused")
            return _Resp({"models": [{"name": m} for m in models]})
        if url.endswith("/collections"):
            if not qdrant_up:
                raise requests.ConnectionError("connection refused")
            return _Resp({"result": {"collections": [{"name": c} for c in collections]}})
        raise AssertionError(f"unexpected request {url}")

    get.calls = calls
    return get


VALUES = {"ollama_url": "http://ollama:11434", "qdrant_url": "http://qdrant:6333", "embedding_model": "nomic-embed-text",
          "default_model": "llama3.1:8b-instruct-q4_K_M", "extraction_model": None, "rewrite_model": None, "synthesis_model": "llama3.1:8b-instruct-q4_K_M",
          "synthesis_backend": "local"}


# -- addresses and model names ------------------------------------------------------------

@pytest.mark.parametrize("raw, clean", [("http://ollama:11434/", "http://ollama:11434"), (" https://q.example:6333 ", "https://q.example:6333")])
def test_a_plain_web_address_is_accepted_without_its_trailing_slash(raw, clean):
    assert ss.clean_url(raw) == clean


@pytest.mark.parametrize("raw", ["", "ollama:11434", "ftp://host", "http://", "file:///etc/passwd", "http://user:pw@host:1", "javascript:alert(1)"])
def test_anything_that_is_not_a_plain_web_address_is_refused(raw):
    with pytest.raises(ValueError):
        ss.clean_url(raw)


def test_a_refused_address_is_never_requested():
    get = fake_services()
    with patch.object(ss.requests, "get", get):
        ok, message, names = ss.test_ollama("file:///etc/passwd")
        ok_q, message_q = ss.test_qdrant("ftp://host")
    assert (ok, names, ok_q) == (False, [], False) and "web address" in message and "web address" in message_q
    assert get.calls == []


def test_a_configured_name_matches_its_latest_tag_and_nothing_looser():
    have = ss.installed_names(["nomic-embed-text:latest", "llama3.1:8b-instruct-q4_K_M"])
    assert ss.has_model("nomic-embed-text", have) and ss.has_model("llama3.1:8b-instruct-q4_K_M", have)
    assert not ss.has_model("nomic-embed", have) and not ss.has_model("llama3.1:8b", have) and not ss.has_model("", have)


def test_the_job_preflight_and_the_wizard_agree_on_what_installed_means():
    from services import job_service

    payload = {"models": [{"name": "nomic-embed-text:latest"}, {"name": "qwen2.5:14b"}]}
    with patch.object(job_service, "_get_json", return_value=payload):
        assert job_service.preflight({"ollama_url": "http://o", "ollama_models": ["nomic-embed-text", "qwen2.5:14b"]}) is None
        assert "llama3.1:8b" in job_service.preflight({"ollama_url": "http://o", "ollama_models": ["llama3.1:8b"]})


# -- the two services -----------------------------------------------------------------------

def test_ollama_and_qdrant_answers_are_turned_into_plain_sentences():
    with patch.object(ss.requests, "get", fake_services(models=("a", "b"))):
        assert ss.test_ollama("http://o:1") == (True, "OK (2 models found)", ["a", "b"])
        assert ss.test_qdrant("http://q:1") == (True, "OK (1 collection)")


def test_an_unreachable_service_says_so_and_returns_no_models():
    with patch.object(ss.requests, "get", fake_services(ollama_up=False, qdrant_up=False)):
        ok, message, names = ss.test_ollama("http://o:1")
        ok_q, message_q = ss.test_qdrant("http://q:1")
    assert not ok and names == [] and message.startswith("Could not reach Ollama there")
    assert not ok_q and message_q.startswith("Could not reach Qdrant there")


def test_the_text_of_an_exception_never_reaches_the_message():
    """The message goes to a browser: an exception can carry an internal host name or a path."""
    def get(url, timeout=None, allow_redirects=True):
        raise requests.ConnectionError("HTTPConnectionPool(host='10.1.2.3', port=11434): secret-internal-detail")

    def slow(url, timeout=None, allow_redirects=True):
        raise requests.Timeout("secret-internal-detail")

    for fn, kind in ((get, "refused or the address could not be found"), (slow, "did not answer within 5 seconds")):
        with patch.object(ss.requests, "get", fn):
            _, message, _ = ss.test_ollama("http://o:1")
            _, message_q = ss.test_qdrant("http://q:1")
        assert kind in message and kind in message_q
        assert "secret-internal-detail" not in message + message_q and "10.1.2.3" not in message + message_q


def test_an_error_status_or_a_reply_that_is_not_theirs_is_said_in_fixed_words():
    with patch.object(ss.requests, "get", lambda url, timeout=None, allow_redirects=True: _Resp({}, status=503)):
        assert "HTTP 503" in ss.test_ollama("http://o:1")[1] and "HTTP 503" in ss.test_qdrant("http://q:1")[1]

    class _Odd:
        status_code = 200

        def json(self):
            raise ValueError("not json: <html>secret-internal-detail</html>")

    with patch.object(ss.requests, "get", lambda url, timeout=None, allow_redirects=True: _Odd()):
        ok, message, names = ss.test_ollama("http://o:1")
        _, message_q = ss.test_qdrant("http://q:1")
    assert not ok and names == [] and "not like Ollama" in message and "not like Qdrant" in message_q
    assert "secret-internal-detail" not in message + message_q


def test_redirects_are_not_followed():
    seen = {}

    def get(url, timeout=None, allow_redirects=True):
        seen["allow_redirects"] = allow_redirects
        return _Resp({"models": []})

    with patch.object(ss.requests, "get", get):
        ss.test_ollama("http://o:1")
    assert seen["allow_redirects"] is False


# -- the folder and the roles ------------------------------------------------------------------

def test_the_folder_check_tells_existing_new_and_unwritable_apart(tmp_path):
    assert ss.check_folder(tmp_path) == {"path": str(tmp_path), "exists": True, "writable": True, "message": "OK"}
    new = ss.check_folder(tmp_path / "later" / "docs")
    assert new["exists"] is False and new["writable"] is True and "created" in new["message"]
    with patch("os.access", return_value=False):
        assert ss.check_folder(tmp_path)["writable"] is False
        assert ss.check_folder(tmp_path / "later")["writable"] is False


def test_a_role_left_unset_follows_the_default_model_and_synthesis_is_listed_only_when_local():
    roles = {r["role"]: r for r in ss.model_roles(VALUES, "qwen2.5:14b")}
    assert roles["extraction"]["name"] == roles["rewrite"]["name"] == "llama3.1:8b-instruct-q4_K_M"
    assert roles["questions"]["name"] == "qwen2.5:14b" and roles["embedding"]["required"] and roles["extraction"]["required"]
    assert not roles["questions"]["required"] and "synthesis" in roles
    assert "synthesis" not in {r["role"] for r in ss.model_roles({**VALUES, "synthesis_backend": "remote"}, "q")}
    assert "synthesis" not in {r["role"] for r in ss.model_roles({**VALUES, "synthesis_backend": "none"}, "q")}


# -- the whole check --------------------------------------------------------------------------

def test_everything_in_place_is_ready_and_a_missing_optional_model_only_costs_its_feature(tmp_path):
    with patch.object(ss.requests, "get", fake_services()):
        out = ss.run_check(VALUES, tmp_path, "qwen2.5:14b")
    assert out["ollama"]["ok"] and out["qdrant"]["ok"] and out["folder"]["writable"]
    by_role = {m["role"]: m for m in out["models"]}
    assert by_role["embedding"]["installed"] and by_role["extraction"]["installed"] and by_role["questions"]["installed"] is False
    assert out["ready"] is True


def test_a_missing_required_model_makes_the_setup_not_ready(tmp_path):
    with patch.object(ss.requests, "get", fake_services(models=("nomic-embed-text:latest",))):
        out = ss.run_check(VALUES, tmp_path, "qwen2.5:14b")
    assert {m["role"]: m["installed"] for m in out["models"]}["extraction"] is False and out["ready"] is False


def test_models_are_unknown_not_missing_while_ollama_cannot_be_asked(tmp_path):
    with patch.object(ss.requests, "get", fake_services(ollama_up=False)):
        out = ss.run_check(VALUES, tmp_path, "qwen2.5:14b")
    assert all(m["installed"] is None for m in out["models"]) and out["ready"] is False


# -- the routes -----------------------------------------------------------------------------------

@pytest.fixture
def cfg_env(tmp_path, monkeypatch):
    from core import config as core_config

    path = tmp_path / "config" / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", path)
    cfg = SimpleNamespace(**{k: v for k, v in VALUES.items()}, processed_dir_path=lambda: tmp_path / "processed")
    cfg.extraction_model, cfg.rewrite_model = VALUES["default_model"], VALUES["default_model"]  # as load() resolves them
    monkeypatch.setattr("api.routes.setup._config.load", lambda: cfg)
    return SimpleNamespace(path=path, tmp=tmp_path)


def test_setup_state_follows_whether_a_config_file_was_ever_saved(cfg_env):
    first = LOOPBACK.get("/api/setup").json()
    assert first["needs_setup"] is True and first["config_file"] is False and first["questions_model"]
    cfg_env.path.parent.mkdir(parents=True)
    cfg_env.path.write_text(json.dumps({"ollama_url": "http://x"}))
    assert REMOTE.get("/api/setup").json()["needs_setup"] is False  # public: it carries no value from the file


def test_the_check_route_is_for_the_server_machine_only(cfg_env):
    get = fake_services()
    with patch.object(ss.requests, "get", get):
        refused = REMOTE.post("/api/setup/check", json={})
    assert refused.status_code == 403 and get.calls == []


def test_the_check_route_uses_the_current_configuration_for_what_is_left_out(cfg_env):
    get = fake_services()
    with patch.object(ss.requests, "get", get):
        out = LOOPBACK.post("/api/setup/check", json={}).json()
    assert out["ollama"]["url"] == "http://ollama:11434" and out["qdrant"]["url"] == "http://qdrant:6333"
    assert get.calls == ["http://ollama:11434/api/tags", "http://qdrant:6333/collections"]
    assert not cfg_env.path.exists()  # a check writes nothing


def test_values_in_the_request_win_and_a_blank_one_does_not(cfg_env):
    get = fake_services(models=("other-model",))
    body = {"ollama_url": "http://elsewhere:11434", "default_model": "other-model", "extraction_model": "", "embedding_model": "other-model"}
    with patch.object(ss.requests, "get", get):
        out = LOOPBACK.post("/api/setup/check", json=body).json()
    assert out["ollama"]["url"] == "http://elsewhere:11434" and "http://elsewhere:11434/api/tags" in get.calls
    by_role = {m["role"]: m["name"] for m in out["models"]}
    assert by_role["embedding"] == "other-model" and by_role["extraction"] == "other-model"  # blank is "not given": it follows the default it was following


def test_a_role_that_followed_the_default_model_follows_the_new_one(cfg_env):
    with patch.object(ss.requests, "get", fake_services(models=("new-default", "nomic-embed-text"))):
        out = LOOPBACK.post("/api/setup/check", json={"default_model": "new-default"}).json()
    by_role = {m["role"]: (m["name"], m["installed"]) for m in out["models"]}
    assert by_role["extraction"] == ("new-default", True) and by_role["rewrite"] == ("new-default", True)


def test_a_role_set_apart_from_the_default_model_is_left_alone(cfg_env, monkeypatch):
    cfg = __import__("api.routes.setup", fromlist=["_config"])._config.load()
    cfg.extraction_model = "special-extractor"
    with patch.object(ss.requests, "get", fake_services(models=("new-default", "special-extractor", "nomic-embed-text"))):
        out = LOOPBACK.post("/api/setup/check", json={"default_model": "new-default"}).json()
    assert {m["role"]: m["name"] for m in out["models"]}["extraction"] == "special-extractor"


def test_the_check_route_refuses_a_bad_address_without_making_a_request_and_a_bad_backend(cfg_env):
    get = fake_services()
    with patch.object(ss.requests, "get", get):
        out = LOOPBACK.post("/api/setup/check", json={"ollama_url": "file:///etc/passwd"}).json()
        bad = LOOPBACK.post("/api/setup/check", json={"synthesis_backend": "sometimes"})
    assert out["ollama"]["ok"] is False and "web address" in out["ollama"]["message"]
    assert "file:///etc/passwd" not in " ".join(get.calls)
    assert bad.status_code == 422


# -- reqbot init --check ----------------------------------------------------------------------------

def _cli_cfg(tmp_path):
    return SimpleNamespace(**{k: v for k, v in VALUES.items()}, processed_dir_path=lambda: tmp_path)


def test_init_check_prints_the_same_picture_and_returns_ready(tmp_path, capsys):
    from cli import reqbot

    cfg = _cli_cfg(tmp_path)
    cfg.extraction_model = cfg.rewrite_model = VALUES["default_model"]
    with patch.object(reqbot, "_cfg", cfg), patch.object(ss.requests, "get", fake_services()):
        rc = reqbot.cmd_init(SimpleNamespace(check=True))
    out = capsys.readouterr().out
    assert rc == 0 and "Ready to use." in out and "OK   Ollama" in out and "Model  nomic-embed-text" in out
    assert "ollama pull qwen2.5:14b" in out  # the optional questions model is not installed: said, with the command, but not a failure


def test_init_check_fails_and_says_what_when_a_required_model_is_missing(tmp_path, capsys):
    from cli import reqbot

    cfg = _cli_cfg(tmp_path)
    cfg.extraction_model = cfg.rewrite_model = VALUES["default_model"]
    with patch.object(reqbot, "_cfg", cfg), patch.object(ss.requests, "get", fake_services(models=("nomic-embed-text:latest",))):
        rc = reqbot.cmd_init(SimpleNamespace(check=True))
    out = capsys.readouterr().out
    assert rc == 1 and "NOT INSTALLED" in out and "ollama pull llama3.1:8b-instruct-q4_K_M" in out and "Not ready yet" in out

"""Unit test for api/app.py's startup reranker warm-up ping, 2026-10-29.

A configured rerank_url gets a fire-and-forget /warm ping when the server starts,
so the reranker's model load happens in parallel with the server coming up instead
of on a user's first search. Must never block startup or raise if the reranker is
slow/unreachable.
"""
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from api.app import app


def _wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_a_configured_rerank_url_gets_a_warm_ping_on_startup():
    calls = []
    with (
        patch("core.config.load") as mock_load,
        patch("urllib.request.urlopen", side_effect=lambda url, **kw: calls.append(url)),
    ):
        mock_load.return_value.rerank_url = "http://reranker:8732"
        with TestClient(app):
            _wait_for(lambda: calls)
    assert calls == ["http://reranker:8732/warm"]


def test_no_rerank_url_configured_pings_nothing():
    with (
        patch("core.config.load") as mock_load,
        patch("urllib.request.urlopen") as mock_urlopen,
    ):
        mock_load.return_value.rerank_url = None
        with TestClient(app):
            time.sleep(0.1)  # give any (unwanted) background thread a chance to fire
    mock_urlopen.assert_not_called()


def test_a_slow_or_unreachable_reranker_does_not_block_or_crash_startup():
    with (
        patch("core.config.load") as mock_load,
        patch("urllib.request.urlopen", side_effect=OSError("connection refused")),
    ):
        mock_load.return_value.rerank_url = "http://reranker:8732"
        start = time.monotonic()
        with TestClient(app):
            pass
        assert time.monotonic() - start < 2.0  # startup itself was not slowed down


def test_warm_up_runs_on_a_background_thread_not_the_startup_thread():
    thread_names = []
    with (
        patch("core.config.load") as mock_load,
        patch("urllib.request.urlopen", side_effect=lambda *a, **kw: thread_names.append(threading.current_thread().name)),
    ):
        mock_load.return_value.rerank_url = "http://reranker:8732"
        with TestClient(app):
            _wait_for(lambda: thread_names)
    assert thread_names and thread_names[0] != threading.main_thread().name

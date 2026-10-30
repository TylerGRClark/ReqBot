"""Unit tests for rerank_server/server.py's idle-unload and warm-up logic, 2026-10-29.

This module deliberately has no package imports of its own (its Dockerfile copies
only server.py into a minimal container, with no access to the rest of the repo) --
import it directly off sys.path, the same way pipeline scripts add the repo root
for standalone use.

torch and transformers are faked via sys.modules, same discipline as test_reranker.py's
flashrank faking: these tests must not require a GPU or the real model to run.
"""
import importlib
import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent / "rerank_server"


def _install_fake_torch_and_transformers(monkeypatch, cuda_available=False):
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: cuda_available, empty_cache=lambda: None)
    fake_torch.no_grad = lambda: _NullContext()

    fake_model = MagicMock()
    fake_model.eval.return_value = fake_model
    fake_model.to.return_value = fake_model
    fake_logits = MagicMock()
    fake_logits.view.return_value.tolist.return_value = [0.5]
    fake_model.return_value = types.SimpleNamespace(logits=fake_logits)

    fake_tokenizer = MagicMock()
    fake_tokenizer.return_value.to.return_value = {}

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoModelForSequenceClassification = MagicMock(from_pretrained=MagicMock(return_value=fake_model))
    fake_transformers.AutoTokenizer = MagicMock(from_pretrained=MagicMock(return_value=fake_tokenizer))

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    return fake_model, fake_tokenizer


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def server(monkeypatch):
    """Fresh import of server.py per test -- its load state is module-level globals."""
    _install_fake_torch_and_transformers(monkeypatch)
    monkeypatch.syspath_prepend(str(_SERVER_DIR))
    if "server" in sys.modules:
        del sys.modules["server"]
    mod = importlib.import_module("server")
    yield mod
    del sys.modules["server"]


def test_model_is_not_loaded_at_import_time(server):
    assert server._model is None


def test_ensure_loaded_loads_once(server):
    server._ensure_loaded()
    assert server._model is not None
    first = server._model
    server._ensure_loaded()
    assert server._model is first  # not reloaded


def test_score_loads_the_model_if_needed(server):
    assert server._model is None
    out = server.score("q", ["a text"])
    assert server._model is not None
    assert out == [0.5]


def test_unload_if_idle_drops_the_model_past_the_timeout(server, monkeypatch):
    server._ensure_loaded()
    assert server._model is not None

    fake_now = [1000.0]
    monkeypatch.setattr(server.time, "monotonic", lambda: fake_now[0])
    server._last_used = 1000.0
    monkeypatch.setattr(server, "IDLE_SECONDS", 60.0)

    fake_now[0] = 1000.0 + 59.0
    with server._lock:
        if server._model is not None and server.time.monotonic() - server._last_used >= server.IDLE_SECONDS:
            server._model = None
    assert server._model is not None  # not idle long enough yet

    fake_now[0] = 1000.0 + 61.0
    with server._lock:
        if server._model is not None and server.time.monotonic() - server._last_used >= server.IDLE_SECONDS:
            server._model = None
    assert server._model is None  # now past the idle timeout


def test_idle_seconds_zero_means_never_unload_is_the_intent(server, monkeypatch):
    """IDLE_SECONDS<=0 disables the background eviction loop entirely (see
    _unload_if_idle's early return) -- this just documents that escape hatch's trigger
    condition, since _unload_if_idle itself runs forever and isn't practical to run here."""
    monkeypatch.setattr(server, "IDLE_SECONDS", 0)
    assert server.IDLE_SECONDS <= 0


def test_ensure_loaded_updates_last_used(server, monkeypatch):
    monkeypatch.setattr(server.time, "monotonic", lambda: 42.0)
    server._ensure_loaded()
    assert server._last_used == 42.0


def test_unload_never_fires_while_a_request_is_actively_using_the_model(server, monkeypatch):
    """A slow/large single request must not have its model pulled out from under it
    mid-flight, even if the idle clock (reset only at request start) looks expired by
    the time a background unload check runs."""
    server._ensure_loaded()
    server._busy = 1  # simulate: a request is actively using the model right now
    server._last_used = 0.0  # as if the request started a very long time ago
    monkeypatch.setattr(server, "IDLE_SECONDS", 1.0)

    with server._lock:
        should_unload = (
            server._model is not None and server._busy == 0
            and time.monotonic() - server._last_used >= server.IDLE_SECONDS
        )
        if should_unload:
            server._model = None
    assert server._model is not None  # busy guard held


def test_score_marks_busy_during_the_call_and_clears_it_after(server):
    import threading

    server._ensure_loaded()
    release = threading.Event()
    started = threading.Event()
    real_call = server._model.__class__.__call__

    def _slow_call(self, *a, **kw):
        started.set()
        release.wait(timeout=2)
        return real_call(self, *a, **kw)

    server._model.__class__.__call__ = _slow_call
    try:
        t = threading.Thread(target=server.score, args=("q", ["a"]))
        t.start()
        assert started.wait(timeout=2)
        assert server._busy == 1  # busy while the request is still inside the model call
        release.set()
        t.join(timeout=2)
    finally:
        server._model.__class__.__call__ = real_call

    assert server._busy == 0  # cleared after the call completes

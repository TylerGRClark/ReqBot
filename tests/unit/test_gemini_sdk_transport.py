"""Pinned reviewer SDK contract probes using fake HTTP; never live credentials.

Run with the separate reviewer requirements installed. Runtime-only environments
skip this module because the reviewer SDK is deliberately not a runtime dependency.
"""

import importlib.util
import json
from pathlib import Path

import pytest

genai = pytest.importorskip("google.genai")
httpx = pytest.importorskip("httpx")


@pytest.fixture
def sdk_reviewer():
    path = Path(__file__).resolve().parents[2] / ".github/scripts/gemini_review.py"
    spec = importlib.util.spec_from_file_location("gemini_sdk_review", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_transport(monkeypatch, handler):
    original_client = genai.Client

    def client(**kwargs):
        return original_client(**kwargs, http_options=genai.types.HttpOptions(
            client_args={"transport": httpx.MockTransport(handler)},
        ))

    monkeypatch.setattr(genai, "Client", client)


@pytest.mark.parametrize("model,thinking", [
    ("gemini-3.6-flash", {"thinking_level": "MEDIUM"}),
    ("gemini-3.5-flash", {"thinking_level": "MEDIUM"}),
    ("gemini-2.5-flash", {"thinking_budget": 4096}),
    ("gemini-2.5-flash-lite", {"thinking_budget": 4096}),
])
def test_actual_sdk_serializes_budget_schema_and_completion_metadata(
    sdk_reviewer, monkeypatch, model, thinking,
):
    calls = []
    raw = '{"summary":"reviewed","checked":["traced failure"],"findings":[],"limitations":[]}'

    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        config = payload["generationConfig"]
        assert config["responseMimeType"] == "application/json"
        assert config["responseJsonSchema"] == sdk_reviewer.REVIEW_SCHEMA
        assert config["maxOutputTokens"] == 16_384
        # ProtoJSON accepts original snake_case field names as well as camelCase;
        # the pinned SDK emits original names for these nested fields.
        assert config["thinkingConfig"] == thinking
        assert request.extensions["timeout"]["read"] == 5
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": raw}], "role": "model"},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 200,
                              "thoughtsTokenCount": 300},
        })

    install_transport(monkeypatch, handler)
    response = sdk_reviewer.generate_review(model, "fake-sdk-test-key", "untrusted data", 5)
    assert len(calls) == 1
    assert response == {"text": raw, "finish_reason": "STOP", "prompt_tokens": 100,
                        "output_tokens": 200, "thinking_tokens": 300}


@pytest.mark.parametrize("finish_reason", ["MAX_TOKENS", "SAFETY"])
def test_actual_sdk_preserves_incomplete_finish_reason(sdk_reviewer, monkeypatch, finish_reason):
    def handler(request):
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": '{"summary":"cut off'}]},
                            "finishReason": finish_reason}],
            "usageMetadata": {"candidatesTokenCount": 10, "thoughtsTokenCount": 16_374},
        })

    install_transport(monkeypatch, handler)
    response = sdk_reviewer.generate_review("gemini-3.6-flash", "fake-sdk-test-key", "data", 5)
    assert response["finish_reason"] == finish_reason
    assert response["thinking_tokens"] == 16_374


def test_actual_sdk_503_makes_one_http_attempt(sdk_reviewer, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"error": {"code": 503, "message": "unavailable"}})

    install_transport(monkeypatch, handler)
    with pytest.raises(genai.errors.ServerError):
        sdk_reviewer.generate_review("gemini-3.6-flash", "fake-sdk-test-key", "data", 5)
    assert len(calls) == 1


def test_actual_sdk_no_candidate_is_not_a_finished_review(sdk_reviewer, monkeypatch):
    install_transport(monkeypatch, lambda request: httpx.Response(
        200, json={"promptFeedback": {"blockReason": "SAFETY"}},
    ))
    response = sdk_reviewer.generate_review("gemini-3.6-flash", "fake-sdk-test-key", "data", 5)
    assert response["text"] is None and response["finish_reason"] is None

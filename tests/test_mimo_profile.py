"""Exercise actual LangChain request serialization without external API calls."""
import asyncio
import json
import os
from pathlib import Path
import sys

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import mimo


@pytest.fixture
def profile(monkeypatch, tmp_path):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setenv("MIMO_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("SMART_LLM", "openai:gpt-5.4")
    monkeypatch.setenv("EMBEDDING", "openai:text-embedding-3-small")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    return mimo.configure(tmp_path / "absent.env")


def test_profile_overrides_inherited_paid_providers(profile):
    from gpt_researcher.config import Config
    from fastembed import TextEmbedding

    config = Config()
    assert config.fast_llm_model == config.smart_llm_model == config.strategic_llm_model == "mimo-v2.6-flash"
    assert config.embedding_provider == "fastembed"
    assert config.retrievers == ["openalex"]
    assert os.environ["OPENAI_BASE_URL"] == mimo.BASE_URL
    assert os.environ["OPENAI_API_KEY"] == "test-only-not-a-real-key"
    assert "LLM_PROVIDER" not in os.environ
    assert config.embedding_model in {model["model"] for model in TextEmbedding.list_supported_models()}


def test_real_adapter_json_streaming_and_usage(profile, capsys):
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        assert str(request.url) == mimo.BASE_URL + "/chat/completions"
        assert request.headers["authorization"] == "Bearer test-only-not-a-real-key"
        assert body["model"] == "mimo-v2.6-flash"
        assert body["thinking"] == {"type": "disabled"}
        assert "reasoning_effort" not in body
        common = {"id": "test-response", "created": 0, "model": "mimo-v2.6-flash"}
        usage = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                 "prompt_tokens_details": {"cached_tokens": 40}}
        if body.get("stream"):
            assert body["stream_options"]["include_usage"] is True
            chunks = [
                {**common, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "OK"}, "finish_reason": None}]},
                {**common, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                {**common, "object": "chat.completion.chunk", "choices": [], "usage": usage},
            ]
            content = "".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n"
            return httpx.Response(200, text=content, headers={"content-type": "text/event-stream"})
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={**common, "object": "chat.completion", "usage": usage,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{"summary":"Lab only; no commercial evidence.","source_id":"S1"}'}}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            profile["LLM_KWARGS"]["http_async_client"] = client
            await mimo.probe(profile)

    asyncio.run(run())
    output = json.loads(capsys.readouterr().out)
    assert len(seen) == 2
    assert output["streaming"] == "OK"
    assert output["estimated_cny"] == pytest.approx([0.0001008, 0.0001008])


def test_missing_key_stops_before_api_call(profile, monkeypatch, capsys):
    monkeypatch.setattr(mimo, "configure", lambda: profile)
    monkeypatch.delenv("MIMO_API_KEY")
    monkeypatch.setattr(sys, "argv", ["mimo.py", "probe"])
    assert mimo.main() == 2
    assert "Missing MIMO_API_KEY" in capsys.readouterr().err


def test_cost_is_unknown_without_usage():
    assert mimo.estimate_cny(None) is None
    assert mimo.estimate_cny({"output_tokens": 1}) is None

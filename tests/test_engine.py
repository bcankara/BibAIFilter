import asyncio
import json

import httpx
import pytest

from bibaifilter.core import catalog
from bibaifilter.core.engine import Engine, call_order
from bibaifilter.core.export import write_excel
from bibaifilter.core.prompts import PRESETS
from bibaifilter.core.providers import make_adapter
from bibaifilter.core.providers.base import CallSettings
from bibaifilter.core.records import Record
from bibaifilter.core.runstore import RunConfig, RunStore


def _records(n=3):
    return [Record(rid=i, title=f"Title {i}", abstract=f"Abstract about schools {i}") for i in range(n)]


def _openai_reply(content, model="gpt-6-luna-2026-09-01", finish="stop"):
    return {"id": "chatcmpl-1", "model": model, "system_fingerprint": "fp_1",
            "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 5,
                      "completion_tokens_details": {"reasoning_tokens": 0}}}


async def _nosleep(_):
    return None


def _make_store(tmp_path, **kw):
    cfg = RunConfig(name="t", task="score", provider="openai", model="gpt-6-luna",
                    template=PRESETS["score-v2"].template, topic="education", repetitions=2,
                    settings=CallSettings(temperature=0.0, reasoning="none"), concurrency=1, **kw)
    return RunStore.create("run1", cfg, _records(), catalog.get("openai", "gpt-6-luna").to_dict(), root=tmp_path)


def test_call_order_is_seeded_and_complete():
    a = call_order(5, 3, True, 7)
    b = call_order(5, 3, True, 7)
    assert a == b and len(a) == 15
    for rep in (1, 2, 3):
        assert sorted(i for r, _, i in a if r == rep) == list(range(5))


def test_run_logs_everything(tmp_path):
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        seen.append(body)
        n = len(seen)
        if n == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": "rate"})
        if n == 2:
            return httpx.Response(200, json=_openai_reply('{"score": 6}'))
        if n == 3:
            return httpx.Response(200, json=_openai_reply("", finish="length"))
        if n == 4:
            return httpx.Response(200, json=_openai_reply('{"score": 2}', model="gpt-4o-2024-08-06"))
        return httpx.Response(200, json=_openai_reply('{"score": 4}'))

    store = _make_store(tmp_path)
    eng = Engine(store, "sk-test", transport=httpx.MockTransport(handler), sleep=_nosleep)
    state = asyncio.run(eng.run())
    assert state["status"] == "completed"
    calls = store.final_calls()
    assert len(calls) == 6
    statuses = [c["status"] for c in calls]
    assert statuses.count("truncated") == 1
    trunc = next(c for c in calls if c["status"] == "truncated")
    assert trunc["score"] is None  # never a default value
    first = calls[0]
    assert first["n_attempts"] == 2 and first["attempts"][0]["http_status"] == 429
    assert any(c["model_mismatch"] for c in calls)
    # parameters as actually sent
    assert seen[1]["temperature"] == 0.0 and seen[1]["reasoning_effort"] == "none"
    assert seen[1]["response_format"]["type"] == "json_schema"
    assert first["params_sent"]["temperature"] == 0.0
    # the key never reaches the log
    assert "sk-test" not in (store.dir / "calls.jsonl").read_text()
    out = write_excel(store)
    assert out.exists()


def test_rejected_parameter_is_retried_without_and_logged(tmp_path):
    def handler(request):
        body = json.loads(request.content)
        if "temperature" in body:
            return httpx.Response(400, json={"error": {"message": "Unsupported parameter: 'temperature' is not supported with this model."}})
        return httpx.Response(200, json=_openai_reply("5"))

    store = _make_store(tmp_path)
    eng = Engine(store, "k", transport=httpx.MockTransport(handler), sleep=_nosleep)
    asyncio.run(eng.run())
    c = store.final_calls()[0]
    assert c["status"] == "ok" and c["retried_without"] == ["temperature"]
    assert "rejected" in c["params_sent"]["temperature"]


def test_auth_error_stops_run(tmp_path):
    store = _make_store(tmp_path)
    eng = Engine(store, "bad", transport=httpx.MockTransport(lambda r: httpx.Response(401, json={})), sleep=_nosleep)
    state = asyncio.run(eng.run())
    assert state["status"] == "stopped" and "authentication" in state["message"]
    assert len(store.final_calls()) == 1


def test_resume_retries_only_failed_calls(tmp_path):
    store = _make_store(tmp_path)
    eng = Engine(store, "k", transport=httpx.MockTransport(lambda r: httpx.Response(500, json={})), sleep=_nosleep)
    asyncio.run(eng.run())
    assert all(c["status"] == "error" for c in store.final_calls())
    eng2 = Engine(RunStore("run1", tmp_path), "k",
                  transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_openai_reply("3"))), sleep=_nosleep)
    asyncio.run(eng2.run())
    assert all(c["status"] == "ok" for c in store.final_calls())


@pytest.mark.parametrize("provider,model,reasoning", [
    ("anthropic", "claude-haiku-5-5", "none"),
    ("anthropic", "claude-sonnet-5-5", "low"),
    ("google", "gemini-3.8-flash", "low"),
    ("deepseek", "deepseek-flash", "none"),
    ("openai", "gpt-6.1-sol", "low"),
    ("ollama", "qwen3:8b", None),
])
def test_temperature_rules(provider, model, reasoning):
    spec = catalog.get(provider, model)
    ad = make_adapter(provider, "SECRETKEY123")
    req = ad.prepare(spec, "prompt", "score", CallSettings(temperature=0.2, reasoning=reasoning))
    body = json.dumps(req.body)
    if provider == "anthropic":
        assert "temperature" not in req.body
        assert req.body["output_config"]["format"]["type"] == "json_schema"
    if provider == "google":
        assert "temperature" not in req.body.get("generationConfig", {})
        assert req.body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "low"
    if provider == "deepseek":
        assert req.body["temperature"] == 0.2 and req.body["thinking"] == {"type": "disabled"}
        assert req.body["response_format"] == {"type": "json_object"} and "JSON" in req.body["messages"][0]["content"]
    if model == "gpt-6.1-sol":
        assert "temperature" not in req.body and req.body["reasoning_effort"] == "low"
    if provider == "ollama":
        assert req.body["temperature"] == 0.2
    assert "SECRETKEY123" not in json.dumps(ad.redact(req.headers))
    assert isinstance(req.params_sent["temperature"], (float, str))
    assert body


def test_provider_response_parsing():
    import httpx as hx

    g = make_adapter("google", "k").parse({
        "candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}, {"text": '{"score": 3}'}]},
                        "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 4, "thoughtsTokenCount": 30},
        "modelVersion": "gemini-3.8-flash-001", "responseId": "abc"}, hx.Headers())
    assert g.text == '{"score": 3}' and g.reasoning_tokens == 30 and g.served_model == "gemini-3.8-flash-001"
    a = make_adapter("anthropic", "k").parse({
        "model": "claude-haiku-5-5-20261001", "stop_reason": "max_tokens",
        "content": [{"type": "text", "text": ""}],
        "usage": {"input_tokens": 10, "output_tokens": 4096, "output_tokens_details": {"thinking_tokens": 4000}}},
        hx.Headers({"request-id": "req_1"}))
    assert a.finish_reason == "length" and a.reasoning_tokens == 4000 and a.request_id == "req_1"
    assert catalog.same_model("gemini-3.8-flash", "gemini-3.8-flash-001")
    assert not catalog.same_model("gpt-6-luna", "gpt-4o-2024-08-06")

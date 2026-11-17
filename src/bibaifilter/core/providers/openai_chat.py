"""OpenAI Chat Completions protocol — OpenAI, DeepSeek, OpenRouter, Ollama, custom endpoints.

Facts used (provider docs, checked 2026-11-10): OpenAI output-token limits include
reasoning tokens and sampling parameters must be omitted when reasoning effort is
not ``none``; DeepSeek supports only ``json_object`` (the prompt must mention JSON),
thinking is on by default and is switched with ``thinking: {"type": ...}``;
OpenRouter needs ``provider.require_parameters`` so that unsupported parameters
are not dropped silently.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..parsing import DECISION_SCHEMA, SCORE_SCHEMA
from .base import Adapter, CallSettings, PreparedRequest, ProviderResult

JSON_HINT_SCORE = '\n\nRespond in JSON exactly as {"score": <integer 1-7>}.'
JSON_HINT_DECISION = '\n\nRespond in JSON exactly as {"decision": "include" | "exclude" | "uncertain", "reason": "<one sentence>"}.'

_FINISH = {"stop": "stop", "length": "length", "content_filter": "content_filter",
           "tool_calls": "stop", "function_call": "stop", "insufficient_system_resource": "error"}


class OpenAICompatibleAdapter(Adapter):
    provider = "custom"
    default_base_url = "http://localhost:8000/v1"
    path = "/chat/completions"
    token_param = "max_tokens"
    json_mode_default = "json_object"  # what structured output means on this endpoint

    def headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    # -- request ------------------------------------------------------------
    def prepare(self, model: Any, prompt: str, task: str, settings: CallSettings) -> PreparedRequest:
        sent: dict[str, Any] = {}
        mode = getattr(model, "structured", None) or self.json_mode_default
        if not settings.structured:
            mode = "none"
        text = prompt
        body: dict[str, Any] = {"model": model.id, "messages": [{"role": "user", "content": text}]}

        schema = SCORE_SCHEMA if task == "score" else DECISION_SCHEMA
        if mode == "json_schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "score" if task == "score" else "decision", "strict": True, "schema": schema}}
            sent["structured_output"] = "json_schema (strict)"
        elif mode == "json_object":
            text = prompt + (JSON_HINT_SCORE if task == "score" else JSON_HINT_DECISION)
            body["messages"][0]["content"] = text
            body["response_format"] = {"type": "json_object"}
            sent["structured_output"] = "json_object + format instruction appended"
            sent["format_instruction"] = (JSON_HINT_SCORE if task == "score" else JSON_HINT_DECISION).strip()
        else:
            sent["structured_output"] = "none (free text, strict parser)"

        self._sampling(model, settings, body, sent)
        self._reasoning(model, settings, body, sent)

        cap = settings.max_output_tokens or getattr(model, "default_max_output_tokens", None)
        if cap:
            body[self.token_param] = int(cap)
            sent[self.token_param] = int(cap)
        else:
            sent["output_token_cap"] = "not sent (provider default)"
        if settings.seed is not None and getattr(model, "seed", False):
            body["seed"] = settings.seed
            sent["seed"] = settings.seed
        return PreparedRequest(self.base_url + self.path, self.headers(), body, sent)

    def _sampling(self, model: Any, settings: CallSettings, body: dict, sent: dict) -> None:
        support = getattr(model, "temperature", "supported")
        if support == "reasoning_off_only":
            effective = settings.reasoning if settings.reasoning is not None else (getattr(model, "default_reasoning", None) or "")
            support = "supported" if str(effective).split(" ")[0] in ("none", "off", "disabled") else "reasoning_on"
        if settings.temperature is None:
            sent["temperature"] = "not sent (provider default)"
        elif support == "reasoning_on":
            sent["temperature"] = "not sent (must be omitted while reasoning/thinking is on)"
        elif support == "supported":
            body["temperature"] = settings.temperature
            sent["temperature"] = settings.temperature
        elif support == "ignored":
            body["temperature"] = settings.temperature
            sent["temperature"] = f"{settings.temperature} (sent, but the provider documents that this model ignores it)"
        else:
            sent["temperature"] = "not sent (model does not accept temperature)"

    def _reasoning(self, model: Any, settings: CallSettings, body: dict, sent: dict) -> None:
        style = getattr(model, "reasoning_style", None)
        if not style:
            return
        if settings.reasoning is None:
            sent["reasoning"] = f"not sent (provider default: {getattr(model, 'default_reasoning', None) or 'unknown'})"
            return
        if style == "openai_effort":
            body["reasoning_effort"] = settings.reasoning
            sent["reasoning_effort"] = settings.reasoning
        elif style == "deepseek_thinking":
            on = settings.reasoning not in ("none", "off", "disabled")
            body["thinking"] = {"type": "enabled" if on else "disabled"}
            sent["thinking"] = body["thinking"]["type"]
            if on:
                body["reasoning_effort"] = settings.reasoning
                sent["reasoning_effort"] = settings.reasoning
        elif style == "openrouter":
            body["reasoning"] = {"effort": settings.reasoning}
            sent["reasoning"] = body["reasoning"]

    # -- response -----------------------------------------------------------
    def parse(self, data: dict, headers: httpx.Headers) -> ProviderResult:
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        text = msg.get("content")
        if isinstance(text, list):  # some compatible servers return content parts
            text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
        if not text and msg.get("refusal"):
            return ProviderResult(text=None, served_model=data.get("model"), finish_reason="refusal")
        usage = data.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        pdetails = usage.get("prompt_tokens_details") or {}
        cached = pdetails.get("cached_tokens")
        if cached is None:
            cached = usage.get("prompt_cache_hit_tokens")  # DeepSeek
        fr = choice.get("finish_reason")
        return ProviderResult(
            text=text,
            served_model=data.get("model"),
            finish_reason=_FINISH.get(fr, fr),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            reasoning_tokens=details.get("reasoning_tokens"),
            cached_tokens=cached,
            request_id=headers.get("x-request-id") or data.get("id"),
            system_fingerprint=data.get("system_fingerprint"),
        )


class OpenAIAdapter(OpenAICompatibleAdapter):
    provider = "openai"
    default_base_url = "https://api.openai.com/v1"
    token_param = "max_completion_tokens"
    json_mode_default = "json_schema"


class DeepSeekAdapter(OpenAICompatibleAdapter):
    provider = "deepseek"
    default_base_url = "https://api.deepseek.com"
    json_mode_default = "json_object"


class OpenRouterAdapter(OpenAICompatibleAdapter):
    provider = "openrouter"
    default_base_url = "https://openrouter.ai/api/v1"
    json_mode_default = "json_schema"

    def headers(self) -> dict[str, str]:
        h = super().headers()
        h["X-Title"] = "BibAIFilter"
        h["X-OpenRouter-Metadata"] = "enabled"
        return h

    def prepare(self, model, prompt, task, settings):
        req = super().prepare(model, prompt, task, settings)
        req.body["usage"] = {"include": True}
        # Without this, upstream providers silently drop parameters they do not support.
        req.body["provider"] = {"require_parameters": True}
        req.params_sent["provider.require_parameters"] = True
        return req

    def parse(self, data, headers):
        res = super().parse(data, headers)
        meta = data.get("openrouter_metadata") or {}
        upstream = meta.get("provider") or data.get("provider")
        if upstream and res.served_model:
            res.served_model = f"{res.served_model} (via {upstream})"
        return res


class OllamaAdapter(OpenAICompatibleAdapter):
    provider = "ollama"
    default_base_url = "http://localhost:11434/v1"
    json_mode_default = "json_schema"
    needs_key = False


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)

"""Anthropic Messages API (``anthropic-version: 2023-06-01``).

Facts used (Anthropic docs, checked 2026-11-10):
* Structured output: ``output_config.format = {"type": "json_schema", "schema": ...}``
  on every current model; numeric ``enum`` is supported, ``minimum``/``maximum`` are not.
* Reasoning: ``output_config.effort`` (low | medium | high | xhigh | max). Claude 5.x
  thinks adaptively by default; only some models accept ``thinking: {"type": "disabled"}``.
* Sampling: Claude 4.7+ and 5.x reject non-default ``temperature`` (HTTP 400);
  ``temperature`` and ``top_p`` must never be sent together.
* Thinking tokens count against ``max_tokens``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..parsing import DECISION_SCHEMA, SCORE_SCHEMA
from .base import Adapter, CallSettings, PreparedRequest, ProviderResult

_FINISH = {"end_turn": "stop", "stop_sequence": "stop", "tool_use": "stop", "max_tokens": "length",
           "refusal": "refusal", "model_context_window_exceeded": "length", "pause_turn": "error"}


def _schema(task: str) -> dict:
    s = json.loads(json.dumps(SCORE_SCHEMA if task == "score" else DECISION_SCHEMA))
    return s


class AnthropicAdapter(Adapter):
    provider = "anthropic"
    default_base_url = "https://api.anthropic.com"
    key_env = "ANTHROPIC_API_KEY"
    version = "2023-06-01"

    def prepare(self, model: Any, prompt: str, task: str, settings: CallSettings) -> PreparedRequest:
        sent: dict[str, Any] = {"anthropic-version": self.version}
        headers = {"x-api-key": self.api_key or "", "anthropic-version": self.version,
                   "content-type": "application/json"}
        cap = int(settings.max_output_tokens or getattr(model, "default_max_output_tokens", None) or 4096)
        body: dict[str, Any] = {"model": model.id, "max_tokens": cap,
                                "messages": [{"role": "user", "content": prompt}]}
        sent["max_tokens"] = cap
        output_config: dict[str, Any] = {}

        style = getattr(model, "reasoning_style", None)
        thinking_on = bool(getattr(model, "thinks_by_default", False))
        if style == "anthropic_effort":
            if settings.reasoning is None:
                sent["effort"] = f"not sent (provider default: {getattr(model, 'default_reasoning', None) or 'unknown'})"
            elif settings.reasoning in ("none", "off", "disabled"):
                if "none" in (getattr(model, "reasoning_levels", None) or []):
                    body["thinking"] = {"type": "disabled"}
                    sent["thinking"] = "disabled"
                    thinking_on = False
                else:
                    sent["thinking"] = "cannot be disabled on this model; provider default kept"
            else:
                output_config["effort"] = settings.reasoning
                sent["effort"] = settings.reasoning

        support = getattr(model, "temperature", "supported")
        if settings.temperature is None:
            sent["temperature"] = "not sent (provider default)"
        elif thinking_on:
            sent["temperature"] = "not sent (not allowed while thinking is on)"
        elif support == "supported":
            body["temperature"] = settings.temperature
            sent["temperature"] = settings.temperature
        else:
            sent["temperature"] = "not sent (model rejects temperature)"

        if settings.structured:
            output_config["format"] = {"type": "json_schema", "schema": _schema(task)}
            sent["structured_output"] = "output_config.format json_schema"
        else:
            sent["structured_output"] = "none (free text, strict parser)"
        if output_config:
            body["output_config"] = output_config
        return PreparedRequest(f"{self.base_url}/v1/messages", headers, body, sent)

    def parse(self, data: dict, headers: httpx.Headers) -> ProviderResult:
        text_parts, tool_input = [], None
        for block in data.get("content") or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_input = block.get("input")
        text = json.dumps(tool_input) if tool_input is not None else "".join(text_parts)
        usage = data.get("usage") or {}
        details = usage.get("output_tokens_details") or {}
        sr = data.get("stop_reason")
        return ProviderResult(
            text=text,
            served_model=data.get("model"),
            finish_reason=_FINISH.get(sr, sr),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            reasoning_tokens=details.get("thinking_tokens"),
            cached_tokens=usage.get("cache_read_input_tokens"),
            request_id=headers.get("request-id") or data.get("id"),
        )

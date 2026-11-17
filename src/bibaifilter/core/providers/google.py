"""Google Gemini API (``models/{id}:generateContent``, REST).

Facts used (Gemini API docs, checked 2026-11-10): ``generateContent`` remains fully
supported; structured output via ``responseMimeType`` + ``responseJsonSchema``;
reasoning via ``thinkingConfig.thinkingLevel`` (``thinkingBudget`` is superseded);
``maxOutputTokens`` includes thought tokens; Gemini 3.6+/4 ignore ``temperature``
and announce that it will be rejected; the served model is ``modelVersion``.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..parsing import DECISION_SCHEMA, SCORE_SCHEMA
from .base import Adapter, CallSettings, PreparedRequest, ProviderResult

_FINISH = {"STOP": "stop", "MAX_TOKENS": "length", "SAFETY": "content_filter",
           "RECITATION": "content_filter", "PROHIBITED_CONTENT": "content_filter",
           "BLOCKLIST": "content_filter", "SPII": "content_filter", "OTHER": "error",
           "MALFORMED_FUNCTION_CALL": "error"}

THINKING_BUDGET = {"none": 0, "minimal": 128, "low": 1024, "medium": 4096, "high": 16384}


def _gemini_schema(schema: dict) -> dict:
    """JSON Schema for ``responseJsonSchema`` (enum, minimum and maximum are supported)."""
    props = {}
    for k, v in schema["properties"].items():
        props[k] = dict(v)
        if v.get("type") == "integer":
            props[k].update({"minimum": 1, "maximum": 7})
    return {"type": "object", "properties": props, "required": schema["required"]}


class GoogleAdapter(Adapter):
    provider = "google"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"
    key_env = "GEMINI_API_KEY"

    def prepare(self, model: Any, prompt: str, task: str, settings: CallSettings) -> PreparedRequest:
        sent: dict[str, Any] = {}
        gen: dict[str, Any] = {}
        support = getattr(model, "temperature", "supported")
        if settings.temperature is None:
            sent["temperature"] = "not sent (provider default)"
        elif support == "supported":
            gen["temperature"] = settings.temperature
            sent["temperature"] = settings.temperature
        elif support == "ignored":
            sent["temperature"] = "not sent (ignored by this model and deprecated by the provider)"
        else:
            sent["temperature"] = "not sent (model does not accept temperature)"

        cap = settings.max_output_tokens or getattr(model, "default_max_output_tokens", None)
        if cap:
            gen["maxOutputTokens"] = int(cap)
            sent["maxOutputTokens"] = int(cap)
        else:
            sent["output_token_cap"] = "not sent (provider default)"

        style = getattr(model, "reasoning_style", None)
        if style in ("gemini_level", "gemini_budget"):
            if settings.reasoning is None:
                sent["thinking"] = f"not sent (provider default: {getattr(model, 'default_reasoning', None) or 'dynamic'})"
            elif style == "gemini_level":
                gen["thinkingConfig"] = {"thinkingLevel": settings.reasoning}
                sent["thinkingLevel"] = settings.reasoning
            else:
                gen["thinkingConfig"] = {"thinkingBudget": THINKING_BUDGET.get(settings.reasoning, -1)}
                sent["thinkingBudget"] = gen["thinkingConfig"]["thinkingBudget"]

        if settings.structured:
            schema = SCORE_SCHEMA if task == "score" else DECISION_SCHEMA
            gen["responseMimeType"] = "application/json"
            gen["responseJsonSchema"] = _gemini_schema(schema)
            sent["structured_output"] = "responseJsonSchema"
        else:
            sent["structured_output"] = "none (free text, strict parser)"
        if settings.seed is not None and getattr(model, "seed", False):
            gen["seed"] = settings.seed
            sent["seed"] = settings.seed

        body: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if gen:
            body["generationConfig"] = gen
        headers = {"x-goog-api-key": self.api_key or "", "Content-Type": "application/json"}
        return PreparedRequest(f"{self.base_url}/models/{model.id}:generateContent", headers, body, sent)

    def parse(self, data: dict, headers: httpx.Headers) -> ProviderResult:
        cands = data.get("candidates") or []
        usage = data.get("usageMetadata") or {}
        if not cands:
            block = (data.get("promptFeedback") or {}).get("blockReason")
            return ProviderResult(text=None, served_model=data.get("modelVersion"),
                                  finish_reason="content_filter" if block else "error",
                                  input_tokens=usage.get("promptTokenCount"))
        c = cands[0]
        parts = (c.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        fr = c.get("finishReason")
        out_tokens = usage.get("candidatesTokenCount")
        thoughts = usage.get("thoughtsTokenCount")
        return ProviderResult(
            text=text,
            served_model=data.get("modelVersion"),
            finish_reason=_FINISH.get(fr, fr.lower() if isinstance(fr, str) else fr),
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=(out_tokens or 0) + (thoughts or 0) if (out_tokens is not None or thoughts is not None) else None,
            reasoning_tokens=thoughts,
            cached_tokens=usage.get("cachedContentTokenCount"),
            request_id=data.get("responseId"),
        )

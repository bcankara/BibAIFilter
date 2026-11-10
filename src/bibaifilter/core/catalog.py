"""Model catalogue: identifiers, parameter rules and list prices.

Facts were checked against the providers' official documentation on
2026-11-10 (see ``docs/provider-notes.md`` for sources). Model line-ups change
quickly: any identifier can be typed in the interface, and an unknown model
gets conservative defaults (``generic``). Prices are list prices in USD per
million tokens at that date; ``None`` means unknown and the cost is then shown
as unknown, never as zero.

Parameter rules
---------------
temperature
    ``supported`` – sent when the user sets it.
    ``reasoning_off_only`` – sent only when reasoning/thinking is off; otherwise
    the provider requires it to be omitted (OpenAI GPT-5.x/6) or ignores it (DeepSeek).
    ``ignored`` – accepted but documented as ignored; not sent (Gemini 3.6+/4).
    ``unsupported`` – rejected by the API; never sent (Claude 4.7+, 5.x).
reasoning_style
    How a reasoning level is sent: ``openai_effort`` (``reasoning_effort``),
    ``anthropic_effort`` (``output_config.effort``), ``gemini_level``
    (``thinkingConfig.thinkingLevel``), ``deepseek_thinking`` (``thinking`` +
    ``reasoning_effort``), ``openrouter`` (``reasoning.effort``) or ``None``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Optional

CATALOG_DATE = "2026-11-10"


@dataclass
class ModelSpec:
    provider: str
    id: str
    label: str
    tier: str = ""  # flagship | mid | cheap | local | legacy
    status: str = "current"  # current | preview | legacy | deprecated | retired | unknown
    temperature: str = "supported"
    reasoning_style: Optional[str] = None
    reasoning_levels: list[str] = field(default_factory=list)
    default_reasoning: Optional[str] = None
    recommended_reasoning: Optional[str] = None  # what BibAIFilter suggests for scoring
    thinks_by_default: bool = False
    structured: Optional[str] = None  # override adapter default: json_schema | json_object | none
    seed: bool = False
    default_max_output_tokens: Optional[int] = None
    price_in: Optional[float] = None
    price_out: Optional[float] = None
    price_cached_in: Optional[float] = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


_OAI_EFF = ["none", "low", "medium", "high", "xhigh", "max"]
_ANT_EFF = ["low", "medium", "high", "xhigh", "max"]

MODELS: list[ModelSpec] = [
    # ---------------- OpenAI ----------------
    ModelSpec("openai", "gpt-6-luna", "GPT-6 Luna (cheap)", "cheap", temperature="reasoning_off_only",
              reasoning_style="openai_effort", reasoning_levels=_OAI_EFF, default_reasoning="medium",
              recommended_reasoning="none", seed=True, default_max_output_tokens=4096,
              price_in=0.10, price_out=0.50),
    ModelSpec("openai", "gpt-6.1-terra", "GPT-6.1 Terra (mid)", "mid", temperature="reasoning_off_only",
              reasoning_style="openai_effort", reasoning_levels=_OAI_EFF, default_reasoning="medium",
              recommended_reasoning="none", seed=True, default_max_output_tokens=4096,
              price_in=1.0, price_out=5.0),
    ModelSpec("openai", "gpt-6.1-sol", "GPT-6.1 Sol", "mid", temperature="unsupported",
              reasoning_style="openai_effort", reasoning_levels=_OAI_EFF[1:], default_reasoning="medium",
              recommended_reasoning="low", default_max_output_tokens=16000, price_in=2.0, price_out=10.0,
              note="Reasoning cannot be switched off; sampling parameters are never accepted."),
    ModelSpec("openai", "gpt-6-astra", "GPT-6 Astra (flagship)", "flagship", temperature="unsupported",
              reasoning_style="openai_effort", reasoning_levels=_OAI_EFF[1:], default_reasoning=None,
              recommended_reasoning="low", default_max_output_tokens=16000, price_in=10.0, price_out=50.0,
              note="Reasoning cannot be switched off; sampling parameters are never accepted."),
    ModelSpec("openai", "gpt-5.5", "GPT-5.5", "legacy", "legacy", temperature="reasoning_off_only",
              reasoning_style="openai_effort", reasoning_levels=_OAI_EFF[:5], default_reasoning="medium",
              recommended_reasoning="none", seed=True, default_max_output_tokens=4096, price_in=5.0, price_out=30.0),
    ModelSpec("openai", "gpt-5.4", "GPT-5.4", "legacy", "legacy",
              temperature="reasoning_off_only", reasoning_style="openai_effort", reasoning_levels=_OAI_EFF[:5],
              default_reasoning="none", recommended_reasoning="none", seed=True,
              default_max_output_tokens=4096, price_in=2.50, price_out=15.0),
    ModelSpec("openai", "gpt-5.4-mini", "GPT-5.4 mini", "legacy", "legacy", temperature="reasoning_off_only",
              reasoning_style="openai_effort", reasoning_levels=_OAI_EFF[:5], default_reasoning="none",
              recommended_reasoning="none", seed=True, default_max_output_tokens=4096, price_in=0.75, price_out=4.50),
    ModelSpec("openai", "gpt-5.4-nano", "GPT-5.4 nano (shuts down 2027-04-01)", "legacy", "deprecated",
              temperature="reasoning_off_only", reasoning_style="openai_effort", reasoning_levels=_OAI_EFF[:5],
              default_reasoning="none", recommended_reasoning="none", seed=True, default_max_output_tokens=4096),
    ModelSpec("openai", "gpt-4.1", "GPT-4.1 (shuts down 2027-01-14)", "legacy", "deprecated",
              seed=True, default_max_output_tokens=256),
    ModelSpec("openai", "gpt-4o", "GPT-4o (snapshots shut down 2027-01-14)", "legacy", "deprecated",
              seed=True, default_max_output_tokens=256),
    # ---------------- Anthropic ----------------
    ModelSpec("anthropic", "claude-haiku-5-5", "Claude Haiku 5.5 (cheap)", "cheap", temperature="unsupported",
              reasoning_style="anthropic_effort", reasoning_levels=["none", "low", "medium", "high"],
              default_reasoning="medium (adaptive thinking on)", recommended_reasoning="none",
              thinks_by_default=True, default_max_output_tokens=4096, price_in=0.10, price_out=0.50,
              note="Thinking can be disabled at effort high or lower."),
    ModelSpec("anthropic", "claude-sonnet-5-5", "Claude Sonnet 5.5 (mid)", "mid", temperature="unsupported",
              reasoning_style="anthropic_effort", reasoning_levels=_ANT_EFF, default_reasoning="high (adaptive thinking on)",
              recommended_reasoning="low", thinks_by_default=True, default_max_output_tokens=16000,
              price_in=2.0, price_out=10.0, note="Thinking cannot be disabled; set a low effort."),
    ModelSpec("anthropic", "claude-opus-5-5", "Claude Opus 5.5 (flagship)", "flagship", temperature="unsupported",
              reasoning_style="anthropic_effort", reasoning_levels=_ANT_EFF, default_reasoning="medium (adaptive thinking on)",
              recommended_reasoning="low", thinks_by_default=True, default_max_output_tokens=16000,
              price_in=4.0, price_out=20.0, note="Thinking cannot be disabled; set a low effort."),
    ModelSpec("anthropic", "claude-opus-4-7", "Claude Opus 4.7", "legacy", "legacy",
              temperature="unsupported", default_max_output_tokens=1024),
    ModelSpec("anthropic", "claude-sonnet-4-6", "Claude Sonnet 4.6", "legacy", "legacy",
              default_max_output_tokens=1024, price_in=3.0, price_out=15.0),
    ModelSpec("anthropic", "claude-haiku-4-5-20251001", "Claude Haiku 4.5", "legacy", "legacy",
              default_max_output_tokens=1024, price_in=1.0, price_out=5.0),
    # ---------------- Google ----------------
    ModelSpec("google", "gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite (cheap)", "cheap", temperature="ignored",
              reasoning_style="gemini_level", reasoning_levels=["minimal", "low", "medium", "high"],
              default_reasoning="minimal", recommended_reasoning="minimal", default_max_output_tokens=4096,
              price_in=0.30, price_out=2.50),
    ModelSpec("google", "gemini-3.8-flash", "Gemini 3.8 Flash (mid)", "mid", temperature="ignored",
              reasoning_style="gemini_level", reasoning_levels=["low", "medium", "high"], default_reasoning="medium",
              recommended_reasoning="low", default_max_output_tokens=8192, price_in=0.75, price_out=3.75,
              note="Introductory price until 2026-12-31 (then 1.50/7.50)."),
    ModelSpec("google", "gemini-4-carbon", "Gemini 4 Carbon (flagship)", "flagship", temperature="ignored",
              reasoning_style="gemini_level", reasoning_levels=["low", "medium", "high"], default_reasoning="medium",
              recommended_reasoning="low", default_max_output_tokens=16000, price_in=2.0, price_out=10.0,
              note="Introductory price until 2026-11-30 (then 4/20)."),
    ModelSpec("google", "gemini-4-argon", "Gemini 4 Argon (flagship)", "flagship", temperature="ignored",
              reasoning_style="gemini_level", reasoning_levels=["low", "medium", "high"], default_reasoning="medium",
              recommended_reasoning="low", default_max_output_tokens=16000, price_in=2.0, price_out=10.0,
              note="Introductory price until 2026-11-30 (then 4/20)."),
    ModelSpec("google", "gemini-3.1-pro-preview", "Gemini 3.1 Pro preview", "legacy", "preview",
              reasoning_style="gemini_level", reasoning_levels=["low", "high"], default_reasoning="high",
              recommended_reasoning="low", default_max_output_tokens=16000, price_in=2.0, price_out=12.0),
    ModelSpec("google", "gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite", "legacy",
              "legacy", reasoning_style="gemini_level", reasoning_levels=["minimal", "low", "medium", "high"],
              default_max_output_tokens=4096),
    # ---------------- DeepSeek ----------------
    ModelSpec("deepseek", "deepseek-flash", "DeepSeek V4.1 Flash", "cheap", temperature="reasoning_off_only",
              reasoning_style="deepseek_thinking", reasoning_levels=["none", "low", "high", "max"],
              default_reasoning="high (thinking on)", recommended_reasoning="none", thinks_by_default=True,
              default_max_output_tokens=8192, price_in=0.30, price_out=1.20,
              note="Peak-hour list price; off-peak 0.15/0.60. Structured output: json_object only."),
    ModelSpec("deepseek", "deepseek-v4-pro", "DeepSeek V4 Pro", "flagship", temperature="reasoning_off_only",
              reasoning_style="deepseek_thinking", reasoning_levels=["none", "low", "high", "max"],
              default_reasoning="high (thinking on)", recommended_reasoning="none", thinks_by_default=True,
              default_max_output_tokens=8192, price_in=1.32, price_out=3.96,
              note="Peak-hour list price; off-peak 0.66/1.98."),
    # ---------------- Local / routers (examples; any id can be typed) ----------------
    ModelSpec("ollama", "qwen3:8b", "Qwen3 8B (local, Ollama)", "local", seed=True, default_max_output_tokens=2048,
              price_in=0.0, price_out=0.0, note="Open weights; pin the exact digest shown by `ollama list`."),
    ModelSpec("ollama", "llama3.1:8b", "Llama 3.1 8B (local, Ollama)", "local", seed=True,
              default_max_output_tokens=2048, price_in=0.0, price_out=0.0),
    ModelSpec("ollama", "gemma3:12b", "Gemma 3 12B (local, Ollama)", "local", seed=True,
              default_max_output_tokens=2048, price_in=0.0, price_out=0.0),
    ModelSpec("ollama", "gpt-oss:20b", "gpt-oss 20B (local, Ollama)", "local", seed=True,
              default_max_output_tokens=4096, price_in=0.0, price_out=0.0),
]

_INDEX = {(m.provider, m.id): m for m in MODELS}


def models(provider: Optional[str] = None) -> list[ModelSpec]:
    return [m for m in MODELS if provider is None or m.provider == provider]


def get(provider: str, model_id: str) -> ModelSpec:
    """Catalogue entry, or a conservative generic spec for an unknown identifier."""
    m = _INDEX.get((provider, model_id))
    if m:
        return m
    return ModelSpec(provider, model_id, model_id, tier="", status="unknown",
                     temperature="supported", default_max_output_tokens=4096,
                     note="Not in the catalogue: parameters are sent as set; check the provider documentation.")


def cost_usd(model: ModelSpec, input_tokens: Optional[int], output_tokens: Optional[int],
             cached_tokens: Optional[int] = None) -> Optional[float]:
    if model.price_in is None or model.price_out is None or input_tokens is None or output_tokens is None:
        return None
    cached = cached_tokens or 0
    price_cached = model.price_cached_in if model.price_cached_in is not None else model.price_in
    fresh = max(0, input_tokens - cached)
    return round((fresh * model.price_in + cached * price_cached + output_tokens * model.price_out) / 1e6, 8)


def _norm(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"\s*\(via .*\)$", "", s)
    s = s.split("/", 1)[1] if s.startswith("models/") else s
    return s


def same_model(requested: str, served: str) -> bool:
    """True if ``served`` is the requested model or a dated/versioned snapshot of it."""
    a, b = _norm(requested), _norm(served)
    if a == b:
        return True
    if "/" in a and not "/" in b:  # OpenRouter slug vs. bare upstream name
        a = a.split("/", 1)[1]
    return b.startswith(a + "-") or b.startswith(a + ":") or a.startswith(b + "-") or b.endswith("/" + a)


def apply_defaults(spec: ModelSpec, settings) -> None:
    """Fill unset settings with the most deterministic, cheapest choice the model allows.

    Temperature 0 is requested (the adapter does not send it where the model rejects
    or ignores it, and logs that). Reasoning is set to the lowest level recommended for
    scoring, so that answers are not truncated by reasoning and costs stay low.
    """
    if settings.reasoning is None and spec.recommended_reasoning:
        settings.reasoning = spec.recommended_reasoning

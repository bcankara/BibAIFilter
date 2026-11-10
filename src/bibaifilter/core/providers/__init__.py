"""Provider adapters (one per wire protocol) and their registry."""

from __future__ import annotations

from typing import Optional

from .anthropic import AnthropicAdapter
from .base import Adapter
from .google import GoogleAdapter
from .openai_chat import DeepSeekAdapter, OllamaAdapter, OpenAICompatibleAdapter, OpenAIAdapter, OpenRouterAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "google": GoogleAdapter,
    "deepseek": DeepSeekAdapter,
    "openrouter": OpenRouterAdapter,
    "ollama": OllamaAdapter,
    "custom": OpenAICompatibleAdapter,
}

PROVIDER_INFO = {
    "openai": {"label": "OpenAI", "key_env": "OPENAI_API_KEY", "key_url": "https://platform.openai.com/api-keys"},
    "anthropic": {"label": "Anthropic", "key_env": "ANTHROPIC_API_KEY", "key_url": "https://console.anthropic.com/settings/keys"},
    "google": {"label": "Google Gemini", "key_env": "GEMINI_API_KEY", "key_url": "https://aistudio.google.com/apikey"},
    "deepseek": {"label": "DeepSeek", "key_env": "DEEPSEEK_API_KEY", "key_url": "https://platform.deepseek.com/api_keys"},
    "openrouter": {"label": "OpenRouter", "key_env": "OPENROUTER_API_KEY", "key_url": "https://openrouter.ai/keys"},
    "ollama": {"label": "Ollama (local, no data leaves the machine)", "key_env": "", "key_url": "https://ollama.com/download"},
    "custom": {"label": "Custom OpenAI-compatible endpoint", "key_env": "CUSTOM_LLM_API_KEY", "key_url": ""},
}


def make_adapter(provider: str, api_key: Optional[str], base_url: Optional[str] = None) -> Adapter:
    try:
        cls = ADAPTERS[provider]
    except KeyError as exc:
        raise ValueError(f"unknown provider: {provider}") from exc
    return cls(api_key, base_url)

"""Configuração explícita de provedor; não imprime credenciais."""
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str = field(repr=False)
    base_url: str | None = None


def settings_from_env(env: Mapping[str, str]) -> LLMSettings:
    provider = env.get("LLM_PROVIDER", "openrouter").strip().lower()
    if provider == "openrouter":
        return LLMSettings(provider, env.get("OPENROUTER_MODEL", "google/gemini-2.5-flash").strip(),
                           env.get("OPENROUTER_API_KEY", "").strip(), "https://openrouter.ai/api/v1")
    if provider == "openai":
        return LLMSettings(provider, env.get("OPENAI_MODEL", "").strip(), env.get("OPENAI_API_KEY", "").strip())
    raise ValueError("LLM_PROVIDER deve ser openrouter ou openai")

from functools import lru_cache

from omnidoc.core.config import get_settings
from omnidoc.providers.llm.base import LLMError, LLMProvider
from omnidoc.providers.llm.fallback import FallbackLLM
from omnidoc.providers.llm.openai_compat import SPECS, OpenAICompatProvider


def configured_providers() -> list[str]:
    """Providers that have an API key in .env. This is the list the user picks from at the start."""
    s = get_settings()
    return [name for name in SPECS if getattr(s, f"{name}_api_key")]


def provider_label(name: str) -> str:
    return SPECS[name].label


@lru_cache
def get_llm(name: str) -> LLMProvider:
    return OpenAICompatProvider(name)


def get_llm_for_user_choice(primary: str) -> LLMProvider:
    """The provider the user chose, plus (only if LLM_FALLBACK_ORDER is set) backups behind it."""
    configured = configured_providers()
    if primary not in configured:
        raise LLMError(primary, "not configured (no API key in .env)")
    wanted = [n.strip() for n in get_settings().llm_fallback_order.split(",")]
    backups = [n for n in wanted if n in configured and n != primary]
    return FallbackLLM([get_llm(primary)] + [get_llm(n) for n in backups]) if backups else get_llm(primary)

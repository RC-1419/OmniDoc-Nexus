import json
from dataclasses import dataclass

import openai
from openai import OpenAI

from omnidoc.core.config import get_settings
from omnidoc.providers.llm.base import LLMError, LLMProvider, LLMResponse, ToolCall


@dataclass(frozen=True)
class ProviderSpec:
    label: str
    base_url: str


# Groq, Mistral, Gemini and OpenRouter all speak the OpenAI chat format, so one adapter covers them.
# To add another: add a line here and the three settings fields <name>_api_key / <name>_model.
SPECS = {
    "groq": ProviderSpec("Groq", "https://api.groq.com/openai/v1"),
    "mistral": ProviderSpec("Mistral AI", "https://api.mistral.ai/v1"),
    "gemini": ProviderSpec("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    "openrouter": ProviderSpec("OpenRouter", "https://openrouter.ai/api/v1"),
}


def _loads(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


class OpenAICompatProvider(LLMProvider):
    def __init__(self, name: str, api_key: str | None = None, model: str | None = None):
        if name not in SPECS:
            raise ValueError(f"Unknown LLM provider: {name}")
        s = get_settings()
        key = api_key or getattr(s, f"{name}_api_key")
        if not key:
            raise LLMError(name, f"{name.upper()}_API_KEY is not set in .env")
        self.name = name
        self.label = SPECS[name].label
        self.model = model or getattr(s, f"{name}_model")
        self.client = OpenAI(base_url=SPECS[name].base_url, api_key=key,
                             timeout=s.llm_timeout_seconds, max_retries=1)

    def chat(self, messages, tools=None, json_mode=False):
        kwargs = {}
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        elif json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            r = self.client.chat.completions.create(model=self.model, messages=messages,
                                                    temperature=0, **kwargs)
        except openai.OpenAIError as e:
            status = getattr(e, "status_code", None)
            raise LLMError(self.name, f"{type(e).__name__}" +
                           (f" (HTTP {status})" if status else "")) from None
        msg = r.choices[0].message
        raw_calls = msg.tool_calls or []
        calls = [ToolCall(tc.id or f"call_{i}", tc.function.name, _loads(tc.function.arguments))
                 for i, tc in enumerate(raw_calls)]
        message = {"role": "assistant", "content": msg.content}
        if raw_calls:
            message["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name, "arguments": raw.function.arguments or "{}"}}
                for c, raw in zip(calls, raw_calls)]
        return LLMResponse(msg.content, calls, message, self.name)

    def list_models(self) -> list[str]:
        try:
            return sorted(m.id for m in self.client.models.list())
        except openai.OpenAIError as e:
            raise LLMError(self.name, type(e).__name__) from None

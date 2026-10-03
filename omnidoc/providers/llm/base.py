from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMError(Exception):
    """Any provider failure (rate limit, outage, bad key...), described without prompts or keys."""

    def __init__(self, provider: str, detail: str):
        super().__init__(f"{provider}: {detail}")
        self.provider = provider
        self.detail = detail


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall]
    message: dict   # the assistant message, ready to append to the conversation history
    provider: str   # which provider actually answered


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             json_mode: bool = False) -> LLMResponse:
        """messages and tools use the OpenAI chat format."""

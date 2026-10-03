from omnidoc.providers.llm.base import LLMError, LLMProvider, LLMResponse


class FallbackLLM(LLMProvider):
    """Tries providers in order. Only used when the owner has opted in, because every provider
    in the list will see the text that is sent."""

    def __init__(self, providers: list[LLMProvider]):
        if not providers:
            raise ValueError("FallbackLLM needs at least one provider")
        self.providers = providers
        self.name = providers[0].name

    def chat(self, messages, tools=None, json_mode=False) -> LLMResponse:
        errors = []
        for provider in self.providers:
            try:
                return provider.chat(messages, tools=tools, json_mode=json_mode)
            except LLMError as e:
                errors.append(str(e))
        raise LLMError("all providers", "; ".join(errors))

class LLMError(RuntimeError):
    """LLM call or response parsing failed (no silent fallback)."""


OllamaLLMError = LLMError

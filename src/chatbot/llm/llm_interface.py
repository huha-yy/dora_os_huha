import abc
import asyncio
from typing import AsyncIterator, Iterable, List, Optional


class LLMInterface(metaclass=abc.ABCMeta):
    """Common interface for LLM chat engines.

    Implementations should be cheap to instantiate (no network calls in
    __init__) and safe to share across WebSocket clients. Per-client
    conversation state is managed outside the engine.
    """

    @abc.abstractmethod
    async def async_chat(
        self,
        messages: List[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Run a single non-streaming chat completion.

        Args:
            messages: OpenAI-style list of {"role": ..., "content": ...} dicts.
                The caller is responsible for prepending the system prompt and
                trimming history to fit the context window.
            temperature: Optional override for sampling temperature.
            max_tokens: Optional override for max output tokens.

        Returns:
            The assistant's reply as a single string. Empty string on failure.
        """
        raise NotImplementedError

    async def async_chat_stream(
        self,
        messages: List[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Optional streaming variant. Default falls back to non-streaming."""
        full = await self.async_chat(
            messages, temperature=temperature, max_tokens=max_tokens
        )

        async def _single() -> AsyncIterator[str]:
            if full:
                yield full

        return _single()

    @staticmethod
    def build_messages(
        user_text: str,
        history: Iterable[dict] = (),
        system_prompt: Optional[str] = None,
    ) -> List[dict]:
        """Helper to assemble a messages list with optional system prompt."""
        msgs: List[dict] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(history)
        msgs.append({"role": "user", "content": user_text})
        return msgs

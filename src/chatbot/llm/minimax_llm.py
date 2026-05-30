"""MiniMax LLM client.

MiniMax exposes an OpenAI-compatible `/v1/chat/completions` endpoint, so we
just point the `openai` async SDK at it.

Endpoints (per https://platform.minimax.io/docs/api-reference/text-openai-api):
    - International:  https://api.minimax.io/v1
    - China:          https://api.minimaxi.com/v1

API key resolution order:
    1. explicit `api_key` kwarg
    2. ${MINIMAX_API_KEY} environment variable

Reasoning models (M2.7, etc.) emit a chain-of-thought into `content` by
default; passing ``extra_body={"reasoning_split": True}`` moves the thinking
into a separate ``reasoning_details`` field so the visible reply (which we
hand to TTS) is the final answer only. As a belt-and-suspenders measure we
also strip ``<think>...</think>`` blocks from the returned content.
"""

import os
import re
from typing import List, Optional

from loguru import logger
from openai import AsyncOpenAI

from .llm_interface import LLMInterface


DEFAULT_BASE_URL = "https://api.minimaxi.com/v1"
DEFAULT_MODEL = "MiniMax-M2.7"

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Remove any leaked <think>...</think> blocks and trim whitespace."""
    return _THINK_BLOCK_RE.sub("", text).strip()


class LLMEngine(LLMInterface):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: float = 30.0,
        reasoning_split: bool = True,
        **_: object,
    ) -> None:
        resolved_key = api_key or os.environ.get("MINIMAX_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "MiniMax API key not provided. Set MINIMAX_API_KEY env var "
                "or pass api_key in config.json."
            )

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_split = reasoning_split
        self._client = AsyncOpenAI(
            api_key=resolved_key,
            base_url=base_url,
            timeout=timeout,
        )

        logger.info(
            f"MiniMax LLM ready: base_url={base_url}, model={model}, "
            f"temperature={temperature}, max_tokens={max_tokens}, "
            f"reasoning_split={reasoning_split}"
        )

    async def async_chat(
        self,
        messages: List[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        extra_body = {"reasoning_split": True} if self.reasoning_split else None

        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                stream=False,
                extra_body=extra_body,
            )
        except Exception as e:
            logger.error(f"MiniMax chat completion failed: {e}")
            return ""

        if not resp.choices:
            logger.warning("MiniMax returned no choices")
            return ""

        raw = resp.choices[0].message.content or ""
        content = _strip_thinking(raw)
        if not content:
            logger.warning(
                f"MiniMax returned empty content after stripping thinking "
                f"(raw was {len(raw)} chars)"
            )
        else:
            logger.debug(
                f"MiniMax reply ({len(content)} chars, model={self.model}): "
                f"{content[:120]}{'...' if len(content) > 120 else ''}"
            )
        return content

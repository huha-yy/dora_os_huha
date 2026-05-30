from typing import Type

from .llm_interface import LLMInterface


class LLMFactory:
    @staticmethod
    def get_llm_engine(engine_type: str, **kwargs) -> Type[LLMInterface]:
        if engine_type == "minimax":
            from .minimax_llm import LLMEngine as MiniMaxLLMEngine

            return MiniMaxLLMEngine(**kwargs)
        else:
            raise ValueError(f"Unknown LLM engine: {engine_type}")

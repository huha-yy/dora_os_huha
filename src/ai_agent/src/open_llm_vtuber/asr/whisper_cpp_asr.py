from pywhispercpp.model import Model

import numpy as np
from loguru import logger
from .asr_interface import ASRInterface


class VoiceRecognition(ASRInterface):
    def __init__(
        self,
        model_name: str = "base",
        model_dir="asr/models",
        language: str = "en",
        print_realtime=False,
        print_progress=False,
        prompt: str = None,
    ) -> None:
        # Resolve model_dir relative to AI_AGENT_DIR if it's a relative path
        from ..config_manager.utils import resolve_model_path
        resolved_model_dir = resolve_model_path(model_dir)
        
        self.model = Model(
            model=model_name,
            models_dir=resolved_model_dir,
            language=language,
            print_realtime=print_realtime,
            print_progress=print_progress,
        )
        self.prompt = prompt

    def transcribe_np(self, audio: np.ndarray) -> str:
        if self.prompt is not None:
            segments = self.model.transcribe(
                audio, new_segment_callback=logger.info, initial_prompt=self.prompt
            )
        else:
            segments = self.model.transcribe(audio, new_segment_callback=logger.info)
        full_text = ""
        for segment in segments:
            full_text += segment.text
        return full_text

import json
from pathlib import Path
from typing import Any, Dict, Optional
from asr.asr_interface import ASRInterface
from tts.tts_interface import TTSInterface
from vad.vad_interface import VADInterface
from llm.llm_interface import LLMInterface
from datetime import datetime

from asr.asr_factory import ASRFactory
from tts.tts_factory import TTSFactory
from vad.vad_factory import VADFactory
from llm.llm_factory import LLMFactory

from loguru import logger


class ServiceContext:
    """Service context for the chatbot"""

    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.asr_engine: ASRInterface = None
        self.tts_engine: TTSInterface = None
        self.vad_engine: VADInterface = None
        self.llm_engine: Optional[LLMInterface] = None
        self.system_prompt: str = ""
        self.max_history_turns: int = 8

    def update_activity_time(self):
        """Update the last activity time to current time."""
        self.last_activity_time = datetime.now()

    def __str__(self):
        return (
            f"ServiceContext:\n"
            f"  ASR Engine: {type(self.asr_engine).__name__ if self.asr_engine else 'Not Loaded'}\n"
            f"  TTS Engine: {type(self.tts_engine).__name__ if self.tts_engine else 'Not Loaded'}\n"
            f"  VAD Engine: {type(self.vad_engine).__name__ if self.vad_engine else 'Not Loaded'}\n"
            f"  LLM Engine: {type(self.llm_engine).__name__ if self.llm_engine else 'Not Loaded'}\n"
        )

    def load_from_config(self, config: Dict[str, Any]):
        """Load the service context from a configuration dictionary"""
        self.config = config
        if config.get("asr_engine"):
            self.asr_engine = self.init_asr(config["asr_engine"])
        if config.get("tts_engine"):
            self.tts_engine = self.init_tts(config["tts_engine"])
        if config.get("vad_engine"):
            self.vad_engine = self.init_vad(config["vad_engine"])
        if config.get("llm_engine"):
            self.llm_engine = self.init_llm(config["llm_engine"])
            self.system_prompt = config["llm_engine"].get("system_prompt", "")
            self.max_history_turns = int(
                config["llm_engine"].get("max_history_turns", 8)
            )

    def init_asr(self, asr_config: Dict[str, Any]) -> ASRInterface:
        """Initialize the ASR engine"""
        asr_model = asr_config.get("asr_model")
        if not asr_model:
            logger.warning("No ASR model specified")
            return None
        
        # Get the model-specific config
        model_config = asr_config.get(asr_model, {})
        logger.info(f"Initializing ASR engine: {asr_model}")
        
        return ASRFactory.get_asr_system(asr_model, **model_config)

    def init_tts(self, tts_config: Dict[str, Any]) -> TTSInterface:
        """Initialize the TTS engine"""
        tts_model = tts_config.get("tts_model")
        if not tts_model:
            logger.warning("No TTS model specified")
            return None
        
        # Get the model-specific config
        model_config = tts_config.get(tts_model, {})
        logger.info(f"Initializing TTS engine: {tts_model}")
        
        return TTSFactory.get_tts_engine(tts_model, **model_config)

    def init_vad(self, vad_config: Dict[str, Any]) -> VADInterface:
        """Initialize the VAD engine"""
        vad_model = vad_config.get("vad_model")
        if not vad_model:
            logger.warning("No VAD model specified")
            return None
        
        # Get the model-specific config
        model_config = vad_config.get(vad_model, {})
        logger.info(f"Initializing VAD engine: {vad_model}")
        
        return VADFactory.get_vad_engine(vad_model, **model_config)

    def init_llm(self, llm_config: Dict[str, Any]) -> Optional[LLMInterface]:
        """Initialize the LLM engine"""
        llm_model = llm_config.get("llm_model")
        if not llm_model:
            logger.warning("No LLM model specified")
            return None

        model_config = llm_config.get(llm_model, {})
        logger.info(f"Initializing LLM engine: {llm_model}")

        try:
            return LLMFactory.get_llm_engine(llm_model, **model_config)
        except Exception as e:
            logger.error(f"Failed to initialize LLM engine '{llm_model}': {e}")
            return None


def default_context() -> ServiceContext:
    """Get the default service context"""
    with open(Path(__file__).parent / "config.json", "r") as f:
        default_config = json.load(f)
    sc = ServiceContext()
    sc.load_from_config(default_config)
    return sc

default_service_context = default_context()

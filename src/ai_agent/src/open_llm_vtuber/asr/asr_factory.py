from typing import Type
from .asr_interface import ASRInterface
from ..config_manager.utils import resolve_model_path


class ASRFactory:
    @staticmethod
    def get_asr_system(system_name: str, **kwargs) -> Type[ASRInterface]:
        if system_name == "faster_whisper":
            from .faster_whisper_asr import VoiceRecognition as FasterWhisperASR

            return FasterWhisperASR(
                model_path=kwargs.get("model_path"),  # Can be model name, not always a path
                download_root=resolve_model_path(kwargs.get("download_root") or "") if kwargs.get("download_root") else None,
                language=kwargs.get("language"),
                device=kwargs.get("device"),
                compute_type=kwargs.get("compute_type"),
                prompt=kwargs.get("prompt", None),
            )
        elif system_name == "whisper_cpp":
            from .whisper_cpp_asr import VoiceRecognition as WhisperCPPASR
            # Resolve model_dir if present
            if "model_dir" in kwargs and kwargs["model_dir"]:
                kwargs = kwargs.copy()
                kwargs["model_dir"] = resolve_model_path(kwargs["model_dir"])

            return WhisperCPPASR(**kwargs)
        elif system_name == "whisper":
            from .openai_whisper_asr import VoiceRecognition as WhisperASR
            # Resolve download_root if present
            if "download_root" in kwargs and kwargs["download_root"]:
                kwargs = kwargs.copy()
                kwargs["download_root"] = resolve_model_path(kwargs["download_root"])

            return WhisperASR(**kwargs)
        elif system_name == "fun_asr":
            from .fun_asr import VoiceRecognition as FunASR

            return FunASR(
                model_name=kwargs.get("model_name"),
                vad_model=kwargs.get("vad_model"),
                punc_model=kwargs.get("punc_model"),
                ncpu=kwargs.get("ncpu"),
                hub=kwargs.get("hub"),
                device=kwargs.get("device"),
                language=kwargs.get("language"),
                use_itn=kwargs.get("use_itn"),
                # sample_rate=kwargs.get("sample_rate"),
            )
        elif system_name == "azure_asr":
            from .azure_asr import VoiceRecognition as AzureASR

            return AzureASR(
                subscription_key=kwargs.get("api_key"),
                region=kwargs.get("region"),
                languages=kwargs.get("languages", ["en-US", "zh-CN"]),
            )
        elif system_name == "groq_whisper_asr":
            from .groq_whisper_asr import VoiceRecognition as GroqWhisperASR

            return GroqWhisperASR(
                api_key=kwargs.get("api_key"),
                model=kwargs.get("model"),
                lang=kwargs.get("lang"),
            )
        elif system_name == "sherpa_onnx_asr":
            from .sherpa_onnx_asr import VoiceRecognition as SherpaOnnxASR
            # Resolve all path parameters
            path_params = ["encoder", "decoder", "joiner", "paraformer", "nemo_ctc", 
                          "wenet_ctc", "tdnn_model", "whisper_encoder", "whisper_decoder",
                          "sense_voice", "tokens", "hotwords_file", "bpe_vocab"]
            kwargs = kwargs.copy()
            for param in path_params:
                if param in kwargs and kwargs[param]:
                    kwargs[param] = resolve_model_path(kwargs[param])
            return SherpaOnnxASR(**kwargs)
        else:
            raise ValueError(f"Unknown ASR system: {system_name}")

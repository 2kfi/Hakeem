import os
import logging
import yaml
from pathlib import Path
from typing import Optional, List, Tuple


class Config:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._config = self._load_config()

        self.preset = self._config.get("preset", "default")

        models_config = self._config.get("models", {})
        self.models_storage_path = models_config.get("storage_path", "./models")
        self.models_download_on_startup = models_config.get(
            "download_on_startup", False
        )

        stt_config = self._config.get("stt", {})
        self.stt_model_path = stt_config.get("model_path")
        self.stt_device = stt_config.get("device", "auto")
        self.stt_compute_type = stt_config.get("compute_type", "int8")
        self.stt_beam_size = stt_config.get("beam_size", 5)
        self.stt_vad_filter = stt_config.get("vad_filter", True)
        self.stt_vad_threshold = stt_config.get("vad_threshold", 0.5)
        self.stt_vad_min_speech_ms = stt_config.get("vad_min_speech_ms", 250)
        self.stt_vad_min_silence_ms = stt_config.get("vad_min_silence_ms", 200)

        tts_config = self._config.get("tts", {})
        tts_en = tts_config.get("en", {})
        self.tts_en_model_path = tts_en.get("model_path")
        self.tts_en_config_path = tts_en.get("config_path")
        tts_ar = tts_config.get("ar", {})
        self.tts_ar_model_path = tts_ar.get("model_path")
        self.tts_ar_config_path = tts_ar.get("config_path")
        tts_settings = tts_config.get("settings", {})
        self.tts_volume = tts_settings.get("volume", 0.5)
        self.tts_length_scale = tts_settings.get("length_scale", 1.0)
        self.tts_noise_scale = tts_settings.get("noise_scale", 1.0)
        self.tts_noise_w_scale = tts_settings.get("noise_w_scale", 1.0)
        self.tts_normalize_audio = tts_settings.get("normalize_audio", False)
        self.tts_nchannels = tts_settings.get("nchannels", 1)
        self.tts_sampwidth = tts_settings.get("sampwidth", 2)
        self.tts_framerate = tts_settings.get("framerate", 24000)

        llm_config = self._config.get("llm", {})
        self.llm_api_url = llm_config.get("api_url", "http://localhost:2312/v1")
        self.llm_api_key = llm_config.get("api_key", "sk-no-key-required")
        self.llm_model = llm_config.get("model", "local-model")

        mcp_config = self._config.get("mcp", {})
        self.mcp_servers = mcp_config.get("servers", [])
        self.mcp_max_retries = mcp_config.get("max_retries", 2)

        app_config = self._config.get("app", {})
        self.app_host = app_config.get("host", "0.0.0.0")
        self.app_port = app_config.get("port", 8003)

    def _load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f) or {}

    def get_final_stt_path(self) -> str:
        if self.stt_model_path:
            return self.stt_model_path
        return os.path.join(self.models_storage_path, "whisper-medium")

    def get_stt_urls(self) -> List[Tuple[str, str]]:
        base = "https://huggingface.co/Systran/faster-whisper-medium/resolve/main"
        model_path = self.get_final_stt_path()
        files = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]
        urls = []
        for f in files:
            urls.append((f"{base}/{f}", f"{model_path}/{f}"))
        return urls

    def get_final_tts_en_paths(self) -> Tuple[str, str]:
        model = self.tts_en_model_path or os.path.join(
            self.models_storage_path, "TTS-CORI-EN/en_GB-cori-high.onnx"
        )
        config = self.tts_en_config_path or os.path.join(
            self.models_storage_path, "TTS-CORI-EN/en_GB-cori-high.onnx.json"
        )
        return model, config

    def get_tts_en_urls(self) -> List[Tuple[str, str]]:
        return []

    def get_final_tts_ar_paths(self) -> Tuple[str, str]:
        model = self.tts_ar_model_path or os.path.join(
            self.models_storage_path, "TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx"
        )
        config = self.tts_ar_config_path or os.path.join(
            self.models_storage_path, "TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx.json"
        )
        return model, config

    def get_tts_ar_urls(self) -> List[Tuple[str, str]]:
        return []


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

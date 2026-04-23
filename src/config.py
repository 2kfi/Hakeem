"""Configuration management for LLMSIMT pipeline"""

import os
import logging
import yaml
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .shared import find_onnx_files, is_local_path

try:
    from huggingface_hub import list_repo_files

    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False


@dataclass
class TTSLanguageConfig:
    repo: Optional[str] = None
    voice: Optional[str] = None
    local_path: Optional[str] = None


@dataclass
class Config:
    config_path: str = "config.yaml"

    models_storage_path: str = "/app/models"
    models_download_on_startup: bool = False

    app_host: str = "0.0.0.0"
    app_port: int = 8003
    app_log_level: str = "INFO"

    stt_model: str = "Systran/faster-whisper-medium"
    stt_device: str = "auto"
    stt_compute_type: str = "int8"
    stt_beam_size: int = 5
    stt_vad_filter: bool = True
    stt_vad_threshold: float = 0.5
    stt_vad_min_speech_ms: int = 250
    stt_vad_min_silence_ms: int = 200

    tts: dict = field(default_factory=dict)

    tts_volume: float = 0.5
    tts_length_scale: float = 1.0
    tts_noise_scale: float = 1.0
    tts_noise_w_scale: float = 1.0
    tts_normalize_audio: bool = False
    tts_nchannels: int = 1
    tts_sampwidth: int = 2
    tts_framerate: int = 24000

    llm_api_url: str = "http://localhost:2312/v1"
    llm_api_key: str = "sk-no-key-required"
    llm_model: str = "local-model"

    mcp_servers: List[str] = field(default_factory=list)
    mcp_max_retries: int = 2

    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "Config":
        if not os.path.exists(path):
            return cls(config_path=path)

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        models_cfg = data.get("models", {})
        app_cfg = data.get("app", {})
        stt_cfg = data.get("stt", {})
        tts_data = data.get("tts", {})
        settings = data.get("settings", {})
        llm_cfg = data.get("llm", {})
        mcp_cfg = data.get("mcp", {})

        tts_dict = {}
        for lang, cfg in tts_data.items():
            if isinstance(cfg, dict):
                tts_dict[lang] = TTSLanguageConfig(
                    repo=cfg.get("repo"),
                    voice=cfg.get("voice"),
                    local_path=cfg.get("local_path"),
                )
            elif isinstance(cfg, str):
                if is_local_path(cfg):
                    tts_dict[lang] = TTSLanguageConfig(local_path=cfg)
                else:
                    parts = cfg.split("/")
                    tts_dict[lang] = TTSLanguageConfig(
                        repo=parts[0] if len(parts) > 1 else cfg,
                        voice="/".join(parts[1:]) if len(parts) > 1 else "",
                    )

        return cls(
            config_path=path,
            models_storage_path=models_cfg.get("storage_path", "/app/models"),
            models_download_on_startup=models_cfg.get("download_on_startup", False),
            app_host=app_cfg.get("host", "0.0.0.0"),
            app_port=app_cfg.get("port", 8003),
            app_log_level=app_cfg.get("log_level", "INFO"),
            stt_model=stt_cfg.get("model", "Systran/faster-whisper-medium"),
            stt_device=stt_cfg.get("device", "auto"),
            stt_compute_type=stt_cfg.get("compute_type", "int8"),
            stt_beam_size=stt_cfg.get("beam_size", 5),
            stt_vad_filter=stt_cfg.get("vad_filter", True),
            stt_vad_threshold=stt_cfg.get("vad_threshold", 0.5),
            stt_vad_min_speech_ms=stt_cfg.get("vad_min_speech_ms", 250),
            stt_vad_min_silence_ms=stt_cfg.get("vad_min_silence_ms", 200),
            tts=tts_dict,
            tts_volume=settings.get("volume", 0.5),
            tts_length_scale=settings.get("length_scale", 1.0),
            tts_noise_scale=settings.get("noise_scale", 1.0),
            tts_noise_w_scale=settings.get("noise_w_scale", 1.0),
            tts_normalize_audio=settings.get("normalize_audio", False),
            tts_nchannels=settings.get("nchannels", 1),
            tts_sampwidth=settings.get("sampwidth", 2),
            tts_framerate=settings.get("framerate", 24000),
            llm_api_url=llm_cfg.get("api_url", "http://localhost:2312/v1"),
            llm_api_key=llm_cfg.get("api_key", "sk-no-key-required"),
            llm_model=llm_cfg.get("model", "local-model"),
            mcp_servers=mcp_cfg.get("servers", []),
            mcp_max_retries=mcp_cfg.get("max_retries", 2),
        )

    def get_stt_path(self) -> str:
        if is_local_path(self.stt_model):
            if os.path.exists(self.stt_model):
                return self.stt_model
            folder = os.path.join(
                self.models_storage_path, self.stt_model.split("/")[-1]
            )
            if os.path.exists(folder):
                return folder
            return self.stt_model
        return self.stt_model

    def get_stt_is_local(self) -> bool:
        if not self.stt_model:
            return False
        return is_local_path(self.stt_model)

    def get_tts_paths(self, lang: str) -> Tuple[Optional[str], Optional[str]]:
        tts_cfg = self.tts.get(lang)
        if not tts_cfg:
            return None, None

        if tts_cfg.local_path and os.path.exists(tts_cfg.local_path):
            return find_onnx_files(tts_cfg.local_path)

        if tts_cfg.repo and tts_cfg.voice:
            hf_path = f"{tts_cfg.repo}/{tts_cfg.voice}"
            folder = os.path.join(self.models_storage_path, hf_path.replace("/", "-"))
            if os.path.exists(folder):
                return find_onnx_files(folder)
            return hf_path, None

        return None, None

    def get_tts_urls(self, lang: str) -> List[Tuple[str, str]]:
        tts_cfg = self.tts.get(lang)
        if not tts_cfg:
            return []

        if tts_cfg.local_path and os.path.exists(tts_cfg.local_path):
            return []

        if not HF_AVAILABLE or not tts_cfg.repo or not tts_cfg.voice:
            return []

        try:
            repo = f"{tts_cfg.repo}/{tts_cfg.voice}"
            files = list_repo_files(repo)
            model_path = os.path.join(self.models_storage_path, repo.replace("/", "-"))
            urls = []
            for f in files:
                if f.endswith((".onnx", ".json")):
                    urls.append(
                        (
                            f"https://huggingface.co/{repo}/resolve/main/{f}",
                            f"{model_path}/{f}",
                        )
                    )
            return urls
        except Exception:
            return []

    def get_stt_urls(self) -> List[Tuple[str, str]]:
        if is_local_path(self.stt_model):
            return []

        base = f"https://huggingface.co/{self.stt_model}/resolve/main"
        model_path = os.path.join(
            self.models_storage_path, self.stt_model.split("/")[-1]
        )
        files = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]
        return [(f"{base}/{f}", f"{model_path}/{f}") for f in files]


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_yaml()
    return _config


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

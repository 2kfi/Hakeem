import os
import sys
import logging
from pathlib import Path
from typing import Optional, List, Any, Dict
import yaml

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def _detect_gpu() -> str:
    has_cuda = os.system("nvidia-smi > /dev/null 2>&1") == 0
    if has_cuda:
        return "cuda"

    has_rocm = os.system("rocm-smi > /dev/null 2>&1") == 0
    if has_rocm:
        return "rocm"

    return "cpu"


def _load_yaml() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        print(f"[ERROR] config.yaml not found at {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


class Config:
    def __init__(self, yaml_config: Dict[str, Any]):
        self._yaml = yaml_config
        self._apply_env_overrides()
        self._detect_device()

    def _apply_env_overrides(self):
        overrides = {
            "app": {
                "host": "APP_HOST",
                "port": "APP_PORT",
                "log_level": "APP_LOG_LEVEL",
            },
            "stt": {
                "model_path": "STT_MODEL_PATH",
                "variant": "STT_VARIANT",
                "device": "STT_DEVICE",
                "compute_type": "STT_COMPUTE_TYPE",
                "beam_size": "STT_BEAM_SIZE",
                "vad_filter": "STT_VAD_FILTER",
            },
            "tts": {
                "en": {
                    "model": "TTS_EN_MODEL",
                    "config": "TTS_EN_CONFIG",
                },
                "ar": {
                    "model": "TTS_AR_MODEL",
                    "config": "TTS_AR_CONFIG",
                },
                "settings": {
                    "volume": "TTS_VOLUME",
                    "length_scale": "TTS_LENGTH_SCALE",
                    "noise_scale": "TTS_NOISE_SCALE",
                    "noise_w_scale": "TTS_NOISE_W_SCALE",
                    "normalize_audio": "TTS_NORMALIZE_AUDIO",
                    "nchannels": "TTS_NCHANNELS",
                    "sampwidth": "TTS_SAMPWIDTH",
                    "framerate": "TTS_FRAMERATE",
                },
            },
            "llm": {
                "api_url": "LLM_API_URL",
                "api_key": "LLM_API_KEY",
            },
            "mcp": {
                "servers": "MCP_SERVER_URLS",
                "max_retries": "MCP_MAX_RETRIES",
            },
            "models": {
                "storage_path": "MODELS_STORAGE_PATH",
                "download_on_startup": "MODELS_DOWNLOAD_ON_STARTUP",
            },
        }

        self._apply_nested_overrides(self._yaml, overrides)

    def _apply_nested_overrides(self, config: Dict, overrides: Dict, prefix: str = ""):
        for key, env_key in overrides.items():
            if isinstance(env_key, dict):
                if key not in config:
                    config[key] = {}
                self._apply_nested_overrides(config[key], env_key, f"{prefix}{key}_")
            else:
                env_value = os.environ.get(env_key)
                if env_value is not None:
                    if key in [
                        "port",
                        "beam_size",
                        "framerate",
                        "nchannels",
                        "sampwidth",
                        "max_retries",
                    ]:
                        config[key] = int(env_value)
                    elif key in [
                        "vad_filter",
                        "normalize_audio",
                        "download_on_startup",
                    ]:
                        config[key] = env_value.lower() in ("true", "1", "yes")
                    else:
                        config[key] = env_value

    def _detect_device(self):
        if self._yaml.get("stt", {}).get("device", "auto") == "auto":
            detected = _detect_gpu()
            self._yaml["stt"]["device"] = detected
            print(f"[CONFIG] Auto-detected GPU device: {detected}")

    @property
    def app_host(self) -> str:
        return self._yaml.get("app", {}).get("host", "0.0.0.0")

    @property
    def app_port(self) -> int:
        return self._yaml.get("app", {}).get("port", 8003)

    @property
    def app_log_level(self) -> str:
        return self._yaml.get("app", {}).get("log_level", "INFO")

    @property
    def stt_model_path(self) -> str:
        return self._yaml.get("stt", {}).get("model_path", "models/whisper-medium")

    @property
    def stt_variant(self) -> str:
        return self._yaml.get("stt", {}).get("variant", "medium")

    @property
    def stt_device(self) -> str:
        return self._yaml.get("stt", {}).get("device", "cpu")

    @property
    def stt_compute_type(self) -> str:
        return self._yaml.get("stt", {}).get("compute_type", "int8")

    @property
    def stt_beam_size(self) -> int:
        return self._yaml.get("stt", {}).get("beam_size", 5)

    @property
    def stt_vad_filter(self) -> bool:
        return self._yaml.get("stt", {}).get("vad_filter", True)

    @property
    def tts_en_model(self) -> str:
        return self._yaml.get("tts", {}).get("en", {}).get("model", "")

    @property
    def tts_en_config(self) -> str:
        return self._yaml.get("tts", {}).get("en", {}).get("config", "")

    @property
    def tts_ar_model(self) -> str:
        return self._yaml.get("tts", {}).get("ar", {}).get("model", "")

    @property
    def tts_ar_config(self) -> str:
        return self._yaml.get("tts", {}).get("ar", {}).get("config", "")

    @property
    def tts_volume(self) -> float:
        return self._yaml.get("tts", {}).get("settings", {}).get("volume", 0.5)

    @property
    def tts_length_scale(self) -> float:
        return self._yaml.get("tts", {}).get("settings", {}).get("length_scale", 1.0)

    @property
    def tts_noise_scale(self) -> float:
        return self._yaml.get("tts", {}).get("settings", {}).get("noise_scale", 1.0)

    @property
    def tts_noise_w_scale(self) -> float:
        return self._yaml.get("tts", {}).get("settings", {}).get("noise_w_scale", 1.0)

    @property
    def tts_normalize_audio(self) -> bool:
        return (
            self._yaml.get("tts", {}).get("settings", {}).get("normalize_audio", False)
        )

    @property
    def tts_nchannels(self) -> int:
        return self._yaml.get("tts", {}).get("settings", {}).get("nchannels", 1)

    @property
    def tts_sampwidth(self) -> int:
        return self._yaml.get("tts", {}).get("settings", {}).get("sampwidth", 2)

    @property
    def tts_framerate(self) -> int:
        return self._yaml.get("tts", {}).get("settings", {}).get("framerate", 24000)

    @property
    def llm_api_url(self) -> str:
        return self._yaml.get("llm", {}).get("api_url", "")

    @property
    def llm_api_key(self) -> str:
        return self._yaml.get("llm", {}).get("api_key", "sk-no-key-required")

    @property
    def mcp_servers(self) -> List[str]:
        servers = self._yaml.get("mcp", {}).get("servers", [])
        if isinstance(servers, str):
            return [s for s in servers.split(",") if s.strip()]
        return servers

    @property
    def mcp_max_retries(self) -> int:
        return self._yaml.get("mcp", {}).get("max_retries", 2)

    @property
    def models_storage_path(self) -> str:
        return self._yaml.get("models", {}).get("storage_path", "./models")

    @property
    def models_download_on_startup(self) -> bool:
        return self._yaml.get("models", {}).get("download_on_startup", True)

    @property
    def model_urls(self) -> Dict[str, Any]:
        return self._yaml.get("models", {}).get("urls", {})

    def get_whisper_urls(self) -> List[tuple]:
        urls_config = self.model_urls.get("whisper", {})
        base = urls_config.get("base", "").format(variant=self.stt_variant)
        files = urls_config.get("files", [])
        return [(f"{base}/{f}", f"{self.stt_model_path}/{f}") for f in files]

    def get_tts_en_urls(self) -> List[tuple]:
        urls_config = self.model_urls.get("tts_en", {})
        base = urls_config.get("base", "")
        files = urls_config.get("files", [])
        return [
            (
                f"{base}/{f}",
                f"{self.tts_en_model.replace(self.tts_en_model.split('/')[-1], '')}{f}",
            )
            for f in files
        ]

    def get_tts_ar_urls(self) -> List[tuple]:
        urls_config = self.model_urls.get("tts_ar", {})
        base = urls_config.get("base", "")
        files = urls_config.get("files", [])
        return [
            (
                f"{base}/{f}",
                f"{self.tts_ar_model.replace(self.tts_ar_model.split('/')[-1], '')}{f}",
            )
            for f in files
        ]

    def get_medgemma_urls(self) -> List[tuple]:
        urls_config = self.model_urls.get("medgemma", {})
        base = urls_config.get("base", "")
        files = urls_config.get("files", [])
        return [
            (f"{base}/{f}", f"{self.models_storage_path}/MedGemma/{f}") for f in files
        ]


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config(_load_yaml())
    return _config


def setup_logging():
    config = get_config()
    level = getattr(logging, config.app_log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

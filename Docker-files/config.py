import os
import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import yaml

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "config.yaml"

PRESETS = {
    "default": {
        "stt": {"model": "medium"},
        "tts": {
            "en": {"voice": "en_GB/cori/high"},
            "ar": {"voice": "ar_JO/kareem/medium"},
        },
        "compute_type": "int8",
    },
    "lightweight": {
        "stt": {"model": "small"},
        "tts": {"en": {"voice": "en_GB/cori/high"}},
        "compute_type": "int8",
    },
    "heavy": {
        "stt": {"model": "large-v3"},
        "tts": {
            "en": {"voice": "en_GB/cori/high"},
            "ar": {"voice": "ar_JO/kareem/medium"},
        },
        "compute_type": "float16",
    },
}

STT_FILES = ["model.bin", "config.json", "vocabulary.txt", "tokenizer.json"]

TTS_FILE_MAP = {
    "en_GB/cori/high": ["en_GB-cori-high.onnx", "en_GB-cori-high.onnx.json"],
    "en_GB/southern_english_female/high": [
        "en_GB-southern_english_female-high.onnx",
        "en_GB-southern_english_female-high.onnx.json",
    ],
    "ar_JO/kareem/medium": [
        "ar_JO-kareem-medium.onnx",
        "ar_JO-kareem-medium.onnx.json",
    ],
}


def _detect_gpu() -> str:
    has_cuda = os.system("nvidia-smi > /dev/null 2>&1") == 0
    if has_cuda:
        return "cuda"

    has_rocm = os.system("rocm-smi > /dev/null 2>&1") == 0
    if has_rocm:
        return "rocm"

    return "cpu"


def _resolve_tts_files(voice: str) -> List[str]:
    if voice in TTS_FILE_MAP:
        return TTS_FILE_MAP[voice]
    voice_name = voice.split("/")[-1].replace("/", "-")
    return [f"{voice_name}.onnx", f"{voice_name}.onnx.json"]


def _load_yaml() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        print(f"[ERROR] config.yaml not found at {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {}


class Config:
    def __init__(self, yaml_config: Dict[str, Any]):
        self._yaml = yaml_config
        preset_from_env = os.environ.get("PRESET")
        self._preset = preset_from_env or self._yaml.get("preset", "default")
        self._apply_preset()
        self._apply_env_overrides()
        self._detect_device()

    def _apply_preset(self):
        preset = PRESETS.get(self._preset, PRESETS["default"])

        if "stt" not in self._yaml:
            self._yaml["stt"] = {}
        if "tts" not in self._yaml:
            self._yaml["tts"] = {}
        if "en" not in self._yaml["tts"]:
            self._yaml["tts"]["en"] = {}
        if "ar" not in self._yaml["tts"]:
            self._yaml["tts"]["ar"] = {}

        stt_user_keys = set(self._yaml["stt"].keys())
        for key, value in preset.get("stt", {}).items():
            if key not in stt_user_keys:
                self._yaml["stt"][key] = value

        for lang in ["en", "ar"]:
            tts_user_keys = set(self._yaml["tts"].get(lang, {}).keys())
            preset_tts = preset.get("tts", {}).get(lang, {})
            for key, value in preset_tts.items():
                if key not in tts_user_keys:
                    self._yaml["tts"][lang][key] = value

        if "compute_type" not in self._yaml.get("stt", {}):
            self._yaml["stt"]["compute_type"] = preset.get("compute_type", "int8")
        elif self._yaml["stt"].get("compute_type") is None:
            self._yaml["stt"]["compute_type"] = preset.get("compute_type", "int8")

    def _apply_env_overrides(self):
        overrides = {
            "app": {
                "host": "APP_HOST",
                "port": "APP_PORT",
                "log_level": "APP_LOG_LEVEL",
            },
            "stt": {
                "repo": "STT_REPO",
                "model": "STT_MODEL",
                "model_path": "STT_MODEL_PATH",
                "device": "STT_DEVICE",
                "compute_type": "STT_COMPUTE_TYPE",
                "beam_size": "STT_BEAM_SIZE",
                "vad_filter": "STT_VAD_FILTER",
            },
            "tts": {
                "en": {
                    "repo": "TTS_EN_REPO",
                    "voice": "TTS_EN_VOICE",
                    "model_path": "TTS_EN_MODEL_PATH",
                    "config_path": "TTS_EN_CONFIG_PATH",
                },
                "ar": {
                    "repo": "TTS_AR_REPO",
                    "voice": "TTS_AR_VOICE",
                    "model_path": "TTS_AR_MODEL_PATH",
                    "config_path": "TTS_AR_CONFIG_PATH",
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

    def _apply_nested_overrides(self, config: Dict, overrides: Dict):
        for key, env_key in overrides.items():
            if isinstance(env_key, dict):
                if key not in config:
                    config[key] = {}
                self._apply_nested_overrides(config[key], env_key)
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
    def preset(self) -> str:
        return self._preset

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
    def stt_repo(self) -> str:
        return self._yaml.get("stt", {}).get("repo", "Systran/faster-whisper")

    @property
    def stt_model(self) -> str:
        return self._yaml.get("stt", {}).get("model", "medium")

    @property
    def stt_model_path(self) -> Optional[str]:
        return self._yaml.get("stt", {}).get("model_path")

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
    def tts_en_repo(self) -> Optional[str]:
        return self._yaml.get("tts", {}).get("en", {}).get("repo")

    @property
    def tts_en_voice(self) -> Optional[str]:
        return self._yaml.get("tts", {}).get("en", {}).get("voice")

    @property
    def tts_en_model_path(self) -> Optional[str]:
        return self._yaml.get("tts", {}).get("en", {}).get("model_path")

    @property
    def tts_en_config_path(self) -> Optional[str]:
        return self._yaml.get("tts", {}).get("en", {}).get("config_path")

    @property
    def tts_ar_repo(self) -> Optional[str]:
        return self._yaml.get("tts", {}).get("ar", {}).get("repo")

    @property
    def tts_ar_voice(self) -> Optional[str]:
        return self._yaml.get("tts", {}).get("ar", {}).get("voice")

    @property
    def tts_ar_model_path(self) -> Optional[str]:
        return self._yaml.get("tts", {}).get("ar", {}).get("model_path")

    @property
    def tts_ar_config_path(self) -> Optional[str]:
        return self._yaml.get("tts", {}).get("ar", {}).get("config_path")

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

    def get_stt_urls(self) -> List[Tuple[str, str]]:
        if self.stt_model_path:
            return []

        repo = self.stt_repo
        model = self.stt_model
        base_url = f"https://huggingface.co/{repo}/resolve/main"
        storage = self.models_storage_path

        files = STT_FILES
        return [(f"{base_url}/{f}", f"{storage}/whisper-{model}/{f}") for f in files]

    def get_tts_en_urls(self) -> List[Tuple[str, str]]:
        if self.tts_en_model_path:
            return []

        repo = self.tts_en_repo
        voice = self.tts_en_voice
        if not repo or not voice:
            return []

        base_url = f"https://huggingface.co/{repo}/resolve/main/{voice}"
        storage = self.models_storage_path

        files = _resolve_tts_files(voice)
        voice_folder = voice.replace("/", "-")
        return [
            (f"{base_url}/{f}", f"{storage}/TTS-EN-{voice_folder}/{f}") for f in files
        ]

    def get_tts_ar_urls(self) -> List[Tuple[str, str]]:
        if self.tts_ar_model_path:
            return []

        repo = self.tts_ar_repo
        voice = self.tts_ar_voice
        if not repo or not voice:
            return []

        base_url = f"https://huggingface.co/{repo}/resolve/main/{voice}"
        storage = self.models_storage_path

        files = _resolve_tts_files(voice)
        voice_folder = voice.replace("/", "-")
        return [
            (f"{base_url}/{f}", f"{storage}/TTS-AR-{voice_folder}/{f}") for f in files
        ]

    def get_final_stt_path(self) -> str:
        if self.stt_model_path:
            return self.stt_model_path
        return f"{self.models_storage_path}/whisper-{self.stt_model}"

    def get_final_tts_en_paths(self) -> Tuple[str, str]:
        if self.tts_en_model_path and self.tts_en_config_path:
            return self.tts_en_model_path, self.tts_en_config_path

        voice = self.tts_en_voice
        if not voice:
            return "", ""
        voice_folder = voice.replace("/", "-")
        base = f"{self.models_storage_path}/TTS-EN-{voice_folder}"
        return f"{base}/{voice_folder}.onnx", f"{base}/{voice_folder}.onnx.json"

    def get_final_tts_ar_paths(self) -> Tuple[str, str]:
        if self.tts_ar_model_path and self.tts_ar_config_path:
            return self.tts_ar_model_path, self.tts_ar_config_path

        voice = self.tts_ar_voice
        if not voice:
            return "", ""
        voice_folder = voice.replace("/", "-")
        base = f"{self.models_storage_path}/TTS-AR-{voice_folder}"
        return f"{base}/{voice_folder}.onnx", f"{base}/{voice_folder}.onnx.json"


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

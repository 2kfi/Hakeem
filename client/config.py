import logging
import os
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger("hakeem-cli")

REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_WS_PATH = "/api/v1/connect"


def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return bool(val)


class ClientConfig:
    backend_host: str = "localhost"
    backend_port: int = 8080
    backend_tls: bool = False
    ws_path: str = _DEFAULT_WS_PATH

    jwt_secret: str = ""
    jwt_token: str = ""
    jwt_permissions: list[str] = None
    device_id: str = "hakeem-cli"
    user_id: str = "cli-user"

    inference_framework: str = "onnx"
    wake_models: list[str] = []
    chunk_size: int = 1280
    sample_rate: int = 16000

    record_timeout: float = 2.0
    max_record_seconds: int = 10
    silence_threshold: float = 0.01
    min_audio_chunks: int = 20

    wakeword_threshold: float = 0.5
    wakeword_cooldown: float = 3.0
    input_device: Optional[int] = None
    response_timeout: float = 120.0
    wakeword_timeout: float = 60.0

    @classmethod
    def load(cls, path: Optional[str] = None) -> "ClientConfig":
        cfg = cls()

        paths_to_try = []
        if path:
            paths_to_try.append(Path(path))
        paths_to_try.append(REPO_ROOT / "client" / "config.yaml")
        paths_to_try.append(REPO_ROOT / "config.yaml")

        loaded = {}
        for p in paths_to_try:
            if p.exists():
                try:
                    if yaml is None and p.suffix in (".yaml", ".yml"):
                        logger.warning(
                            "PyYAML not installed, cannot load %s. "
                            "Install with: pip install pyyaml", p
                        )
                        continue
                    raw = p.read_text()
                    if yaml:
                        loaded = yaml.safe_load(raw) or {}
                    else:
                        import json
                        loaded = json.loads(raw)
                    logger.debug("Loaded config from %s", p)
                    break
                except Exception as exc:
                    logger.warning("Failed to parse config %s: %s", p, exc)
                    continue

        client_cfg = loaded.get("client", {})

        cfg.backend_host = client_cfg.get("backend_host", os.getenv("BACKEND_HOST", cfg.backend_host))
        cfg.backend_port = int(client_cfg.get("backend_port", os.getenv("BACKEND_PORT", cfg.backend_port)))
        raw_tls = client_cfg.get("backend_tls", os.getenv("BACKEND_TLS", "false"))
        cfg.backend_tls = _parse_bool(raw_tls)
        cfg.ws_path = client_cfg.get("ws_path", os.getenv("WS_PATH", cfg.ws_path))

        cfg.jwt_secret = client_cfg.get("jwt_secret", os.getenv("JWT_SECRET", cfg.jwt_secret))
        cfg.jwt_token = client_cfg.get("jwt_token", os.getenv("JWT_TOKEN", cfg.jwt_token))
        cfg.device_id = client_cfg.get("device_id", os.getenv("DEVICE_ID", cfg.device_id))
        cfg.user_id = client_cfg.get("user_id", os.getenv("USER_ID", cfg.user_id))
        cfg.jwt_permissions = client_cfg.get("jwt_permissions", ["admin"])

        cfg.inference_framework = client_cfg.get("inference_framework", cfg.inference_framework)
        cfg.wake_models = client_cfg.get("wake_models", cfg.wake_models)
        cfg.chunk_size = int(client_cfg.get("chunk_size", cfg.chunk_size))
        cfg.sample_rate = int(client_cfg.get("sample_rate", cfg.sample_rate))

        cfg.record_timeout = float(client_cfg.get("record_timeout", cfg.record_timeout))
        cfg.max_record_seconds = int(client_cfg.get("max_record_seconds", cfg.max_record_seconds))
        cfg.silence_threshold = float(client_cfg.get("silence_threshold", cfg.silence_threshold))
        cfg.min_audio_chunks = int(client_cfg.get("min_audio_chunks", cfg.min_audio_chunks))

        cfg.wakeword_threshold = float(client_cfg.get("wakeword_threshold", cfg.wakeword_threshold))
        cfg.wakeword_cooldown = float(client_cfg.get("wakeword_cooldown", cfg.wakeword_cooldown))
        raw_input_dev = client_cfg.get("input_device")
        if raw_input_dev is not None:
            cfg.input_device = int(raw_input_dev)

        cfg.response_timeout = float(client_cfg.get("response_timeout", cfg.response_timeout))

        return cfg

    @property
    def backend_url(self) -> str:
        scheme = "wss" if self.backend_tls else "ws"
        return f"{scheme}://{self.backend_host}:{self.backend_port}{self.ws_path}"

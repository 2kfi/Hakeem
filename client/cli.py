#!/usr/bin/env python3
"""
Hakeem CLI Client — Wake-word triggered voice assistant.

Listens for a wake word (Hakeem / يا ستر), streams audio to the
Hakeem backend, and plays back the TTS response.

Usage:
  python client/cli.py
  python client/cli.py --config client/config.yaml
  python client/cli.py --framework tflite
  python client/cli.py --list-models
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from client.config import ClientConfig
from client.wakeword import WakeWordDetector
from client.audio import (
    MicrophoneStream,
    AudioPlayer,
    record_until_silence,
    pcm_to_wav,
    wav_to_base64,
)
from client.backend import HakeemBackendClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hakeem-cli")


def resolve_model_paths(config: ClientConfig, repo_root: Path) -> list[str]:
    paths = []
    for name in config.wake_models:
        p = Path(name)
        if not p.is_absolute():
            p = repo_root / p
        if p.exists():
            paths.append(str(p))
        else:
            logger.warning("Wake model not found: %s (skipping)", p)
    return paths


def resolve_default_models(repo_root: Path, framework: str) -> list[str]:
    ext = ".tflite" if framework == "tflite" else ".onnx"
    candidates = [
        repo_root / "models" / "Hakeem" / f"Hakeem{ext}",
        repo_root / "models" / "WW-EYE-STRA" / f"EYE-STRA{ext}",
    ]
    return [str(p) for p in candidates if p.exists()]


def list_available_models(repo_root: Path):
    print("Available wake word models:")
    for ext in [".onnx", ".tflite"]:
        framework = "tflite" if ext == ".tflite" else "onnx"
        for path in sorted(repo_root.rglob(f"*{ext}")):
            if "Hakeem" in path.parts or "WW-EYE-STRA" in path.parts:
                rel = path.relative_to(repo_root)
                print(f"  {framework:6s}  {rel}")
    print()
    print("Use --framework onnx or --framework tflite to select.")


def generate_jwt(config: ClientConfig) -> str:
    if config.jwt_token:
        return config.jwt_token
    if not config.jwt_secret:
        logger.error(
            "No JWT token or JWT_SECRET configured. "
            "Set jwt_token or jwt_secret in client/config.yaml, "
            "or run: python scripts/generate_secrets.py"
        )
        sys.exit(1)
    try:
        from jose import jwt
        import time
        token = jwt.encode(
            {
                "user_id": config.user_id,
                "device_id": config.device_id,
                "permissions": ["admin"],
                "iat": time.time(),
                "exp": time.time() + 86400,
            },
            config.jwt_secret,
            algorithm="HS256",
        )
        return token
    except ImportError:
        logger.error("python-jose not installed. Set jwt_token in config, or install jose.")
        sys.exit(1)


async def run_session(
    config: ClientConfig,
    mic: MicrophoneStream,
    player: AudioPlayer,
    audio_b64: str,
    language: str = "",
):
    token = generate_jwt(config)
    backend = HakeemBackendClient(
        url=config.backend_url,
        token=token,
        device_id=config.device_id,
        user_id=config.user_id,
    )

    try:
        ok = await backend.connect()
        if not ok:
            logger.error("Could not connect to backend at %s", config.backend_url)
            return

        await backend.send_audio(audio_b64, language=language)
        text, audio_b64_resp = await backend.handle_messages(audio_player=player)

        if text:
            logger.info("Assistant: %s", text)
    except Exception as e:
        logger.error("Session error: %s", e)
    finally:
        await backend.close()


async def main_loop(config: ClientConfig):
    repo_root = REPO_ROOT
    logger.info("Hakeem CLI Client — listening for wake word")
    logger.info("Backend: %s", config.backend_url)
    logger.info("Framework: %s", config.inference_framework)
    logger.info("Threshold: %.2f", config.wakeword_threshold)

    model_paths = resolve_model_paths(config, repo_root)
    if not model_paths:
        model_paths = resolve_default_models(repo_root, config.inference_framework)
    if not model_paths:
        logger.warning("No wake word models found — using openwakeword defaults")

    detector = WakeWordDetector(
        model_paths=model_paths,
        framework=config.inference_framework,
        chunk_size=config.chunk_size,
        threshold=config.wakeword_threshold,
    )

    mic = MicrophoneStream(
        sample_rate=config.sample_rate,
        chunk_size=config.chunk_size,
    )

    player = AudioPlayer()

    try:
        while True:
            logger.info("🎤 Listening for wake word...")

            audio_pcm = record_until_silence(
                mic,
                wakeword_detector=detector,
                silence_threshold=config.silence_threshold,
                min_chunks=config.min_audio_chunks,
                max_seconds=config.max_record_seconds,
            )

            if len(audio_pcm) < config.min_audio_chunks * config.chunk_size * 2:
                continue

            wav_bytes = pcm_to_wav(audio_pcm, sample_rate=config.sample_rate)
            audio_b64 = wav_to_base64(wav_bytes)
            duration = len(audio_pcm) / (config.sample_rate * 2)
            logger.info("🎤 Recorded %.1fs — sending to backend", duration)

            await run_session(config, mic, player, audio_b64)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        mic.close()
        player.close()


def main():
    parser = argparse.ArgumentParser(description="Hakeem CLI Voice Assistant")
    parser.add_argument("--config", "-c", default=None, help="Path to config YAML")
    parser.add_argument("--framework", "-f", choices=["onnx", "tflite"],
                        default=None, help="Inference framework")
    parser.add_argument("--backend-host", default=None, help="Backend host")
    parser.add_argument("--backend-port", type=int, default=None, help="Backend port")
    parser.add_argument("--jwt-secret", default=None, help="JWT secret for token generation")
    parser.add_argument("--jwt-token", default=None, help="Pre-generated JWT token")
    parser.add_argument("--list-models", action="store_true", help="List available wake models")
    parser.add_argument("--once", action="store_true", help="Single wake-record-send cycle")
    parser.add_argument("--threshold", type=float, default=None, help="Wake word threshold")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--language", default="", help="Language hint (en, ar)")
    args = parser.parse_args()

    config = ClientConfig.load(args.config)

    if args.framework:
        config.inference_framework = args.framework
    if args.backend_host:
        config.backend_host = args.backend_host
    if args.backend_port:
        config.backend_port = args.backend_port
    if args.jwt_secret:
        config.jwt_secret = args.jwt_secret
    if args.jwt_token:
        config.jwt_token = args.jwt_token
    if args.threshold is not None:
        config.wakeword_threshold = args.threshold
    if args.debug:
        logging.getLogger("hakeem-cli").setLevel(logging.DEBUG)

    if args.list_models:
        list_available_models(REPO_ROOT)
        return

    if args.once:
        asyncio.run(run_once(config, args.language))
    else:
        asyncio.run(main_loop(config))


async def run_once(config: ClientConfig, language: str = ""):
    repo_root = REPO_ROOT
    model_paths = resolve_default_models(repo_root, config.inference_framework)
    detector = WakeWordDetector(
        model_paths=model_paths,
        framework=config.inference_framework,
        chunk_size=config.chunk_size,
        threshold=config.wakeword_threshold,
    )
    mic = MicrophoneStream(sample_rate=config.sample_rate, chunk_size=config.chunk_size)
    player = AudioPlayer()

    try:
        print("🎤 Listening (one-shot)...")
        audio_pcm = record_until_silence(
            mic, wakeword_detector=detector,
            silence_threshold=config.silence_threshold,
            min_chunks=config.min_audio_chunks,
            max_seconds=config.max_record_seconds,
        )
        if len(audio_pcm) < config.min_audio_chunks * config.chunk_size * 2:
            print("No audio detected")
            return

        wav_bytes = pcm_to_wav(audio_pcm, sample_rate=config.sample_rate)
        audio_b64 = wav_to_base64(wav_bytes)
        await run_session(config, mic, player, audio_b64, language=language)
    finally:
        mic.close()
        player.close()


if __name__ == "__main__":
    main()

import asyncio
import base64
import logging
from typing import Optional

from core.config import get_settings
from core.redis_manager import RedisManager
from pipeline.tts_queue import TTSQueue

logger = logging.getLogger(__name__)

_tts_queue: Optional[TTSQueue] = None

ARABIC_RANGE = range(0x0600, 0x06FF + 1)


def _detect_language_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    arabic_chars = sum(1 for c in text if ord(c) in ARABIC_RANGE)
    total = len(text.strip())
    if total == 0:
        return None
    arabic_ratio = arabic_chars / total
    if arabic_ratio > 0.3:
        return "ar"
    return "en"


async def get_tts_queue(redis: RedisManager) -> TTSQueue:
    global _tts_queue
    if _tts_queue is None:
        _tts_queue = TTSQueue(redis)
    return _tts_queue


async def tts_handler(data: dict) -> dict:
    redis = await RedisManager.get_instance()
    tts = await get_tts_queue(redis)

    device_id = data.get("device_id", "")
    session_id = data.get("session_id", device_id)
    response_text = data.get("response", "")
    language = data.get("language")

    if not response_text:
        logger.warning(f"TTS [{device_id}]: empty response text, skipping synthesis")
        return {"device_id": device_id, "session_id": session_id, "audio": "", "text": ""}

    skip_tts = data.get("skip_tts", "false")
    if isinstance(skip_tts, str):
        skip_tts = skip_tts.lower() in ("true", "1", "yes")
    else:
        skip_tts = bool(skip_tts)
    if skip_tts:
        logger.info(f"TTS [{device_id}]: skip_tts=true, returning text-only response")
        return {"device_id": device_id, "session_id": session_id, "audio": "", "text": response_text, "text_only": "true"}

    detected_lang = _detect_language_from_text(response_text)
    if detected_lang and language != detected_lang:
        logger.info(
            f"TTS [{device_id}]: language mismatch — upstream said '{language}' but text "
            f"detected as '{detected_lang}', overriding"
        )
        language = detected_lang

    logger.info(f"TTS [{device_id}]: synthesizing {len(response_text)} chars for language={language}")
    audio_b64 = await tts.synthesize_and_b64(response_text, language=language)
    logger.info(f"TTS [{device_id}]: synthesized {len(audio_b64)} bytes of audio")

    return {
        "device_id": device_id,
        "session_id": session_id,
        "audio": audio_b64,
        "text": response_text,
    }


async def process_tts_jobs(redis: RedisManager, consumer: str):
    from pipeline.workers.base import BaseWorker

    settings = get_settings()
    worker = BaseWorker(
        redis=redis,
        stream=settings.pipeline.tts_stream,
        group=settings.pipeline.consumer_group,
        consumer=consumer,
        handler=tts_handler,
        poll_timeout=settings.pipeline.poll_timeout_ms,
        max_retries=settings.pipeline.tts_max_retries,
        target_stream=settings.pipeline.response_stream,
    )
    await worker.start()
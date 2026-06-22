import asyncio
import base64
import logging
import os
import tempfile
import traceback

from faster_whisper.audio import decode_audio

from core.app_state import get_app_state
from core.config import get_settings
from core.redis_manager import RedisManager

logger = logging.getLogger(__name__)




def _detect_best_language(
    audio_array,
    whisper_model,
    supported_languages: set[str],
    default_language: str,
) -> str:
    _, _, all_lang_probs = whisper_model.detect_language(
        audio_array, vad_filter=False,
    )
    logger.debug("Language detection top-5: %s", [(l, f"{p:.4f}") for l, p in all_lang_probs[:5]])
    supported = [(lang, prob) for lang, prob in all_lang_probs if lang in supported_languages]
    if supported:
        best = max(supported, key=lambda x: x[1])
        logger.info("Detected language: %s (prob=%.4f)", best[0], best[1])
        return best[0]
    logger.warning(
        "No supported language detected (supported=%s, candidates=%s), falling back to %s",
        supported_languages,
        [(lang, f"{prob:.4f}") for lang, prob in all_lang_probs[:5]],
        default_language,
    )
    return default_language


def _transcribe_with_lock(state, audio_array, settings, language, stt_task):
    with state.whisper_lock:
        segments, info = state.whisper_model.transcribe(
            audio_array,
            beam_size=settings.stt.beam_size,
            language=language,
            task=stt_task,
            without_timestamps=True,
            condition_on_previous_text=False,
        )
    return segments, info


async def stt_handler(data: dict) -> dict:
    settings = get_settings()
    state = get_app_state()

    audio_b64 = data.get("audio_data", "")
    if not audio_b64:
        raise ValueError("No audio_data in job")

    audio = base64.b64decode(audio_b64)
    device_id = data.get("device_id", "")
    language = data.get("language")
    stt_task = data.get("task") or "transcribe"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio)
        temp_path = f.name

    try:
        audio_array = decode_audio(temp_path)

        if not language:
            language = _detect_best_language(
                audio_array,
                state.whisper_model,
                supported_languages=set(settings.tts.voices.keys()),
                default_language=settings.tts.default_voice,
            )

        try:
            segments, info = await asyncio.to_thread(
                lambda: _transcribe_with_lock(state, audio_array, settings, language, stt_task)
            )
        except Exception as e:
            logger.error(f"STT transcription failed for {device_id}: {e}", exc_info=True)
            raise

        text = "".join(segment.text for segment in segments).strip()
        logger.info(
            f"STT [{device_id}]: lang={info.language} "
            f"(confidence={info.language_probability:.3f}) text={text[:80]}"
        )
        return {
            "device_id": device_id,
            "session_id": data.get("session_id", device_id),
            "text": text,
            "language": info.language,
            "probability": info.language_probability,
        }
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


async def process_stt_jobs(redis: RedisManager, consumer: str):
    from pipeline.workers.base import BaseWorker

    settings = get_settings()
    worker = BaseWorker(
        redis=redis,
        stream=settings.pipeline.stt_stream,
        group=settings.pipeline.consumer_group,
        consumer=consumer,
        handler=stt_handler,
        poll_timeout=settings.pipeline.poll_timeout_ms,
        max_retries=settings.pipeline.stt_max_retries,
        target_stream=settings.pipeline.llm_stream,
    )
    await worker.start()
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.config import get_config, setup_logging
from src.shared import validate_audio_format, detect_language

import downloader

import asyncio
import io
import json
import logging
import uuid
import wave
import uvicorn
from contextlib import asynccontextmanager
from typing import Optional, Tuple
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from faster_whisper import WhisperModel
from piper import PiperVoice
from piper.config import SynthesisConfig

from src.mcp import MCPWrapper

config = get_config()
setup_logging()
logger = logging.getLogger("Pipeline")

models_info = {}

stt_resolved, stt_exists = config.get_stt_path()
models_info["stt"] = {"path": stt_resolved, "local": stt_exists}

tts_en_paths = config.get_tts_paths("en")
tts_ar_paths = config.get_tts_paths("ar")
models_info["tts_en"] = {
    "path": tts_en_paths[0],
    "local": config._path_exists(tts_en_paths[0]),
}
models_info["tts_ar"] = {
    "path": tts_ar_paths[0],
    "local": config._path_exists(tts_ar_paths[0]),
}

print(
    f"[CONFIG] STT model: {stt_resolved} {'(local)' if stt_exists else '(will download)'}"
)
print(
    f"[CONFIG] TTS EN: {tts_en_paths[0] or 'not configured'} {'(local)' if models_info['tts_en']['local'] else '(will download)'}"
)
print(
    f"[CONFIG] TTS AR: {tts_ar_paths[0] or 'not configured'} {'(local)' if models_info['tts_ar']['local'] else '(will download)'}"
)
print(f"[CONFIG] LLM API: {config.llm_api_url}")
print(f"[CONFIG] MCP servers: {config.mcp_servers}")

if config.models_download_on_startup:
    print("\n[CONFIG] download_on_startup=True — checking for missing models...")
    downloader.main()

SYN_config = SynthesisConfig(
    volume=config.tts_volume,
    length_scale=config.tts_length_scale,
    noise_scale=config.tts_noise_scale,
    noise_w_scale=config.tts_noise_w_scale,
    normalize_audio=config.tts_normalize_audio,
)

TTS_NCHANNELS = config.tts_nchannels
TTS_SAMPWIDTH = config.tts_sampwidth
TTS_FRAMERATE = config.tts_framerate

WHISPER_DEVICE = config.stt_device
WHISPER_COMPUTE_TYPE = config.stt_compute_type
WHISPER_BEAM_SIZE = config.stt_beam_size
WHISPER_VAD_FILTER = config.stt_vad_filter
WHISPER_VAD_PARAMS = {
    "threshold": config.stt_vad_threshold,
    "min_speech_duration_ms": config.stt_vad_min_speech_duration_ms,
    "min_silence_duration_ms": config.stt_vad_min_silence_duration_ms,
}
WHISPER_LOCAL_ONLY = config.get_stt_is_local()

MCP_SERVER_URLS = config.mcp_servers

whisper_model: Optional[WhisperModel] = None
voice_EN: Optional[PiperVoice] = None
voice_AR: Optional[PiperVoice] = None

_model_load_lock = asyncio.Lock()


def _load_whisper() -> WhisperModel:
    global whisper_model
    if whisper_model is not None:
        return whisper_model

    path, exists = config.get_stt_path()
    if exists and os.path.isabs(path):
        path = os.path.relpath(path)
    logger.info(f"Loading Whisper model from: {path}")
    model = WhisperModel(
        path,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
        local_files_only=exists,
    )
    whisper_model = model
    logger.info(f"Loaded Whisper model: {path}")
    return model


def _load_voice(
    model_path: str, config_path: Optional[str], lang: str
) -> Optional[PiperVoice]:
    logger.info(f"Loading {lang} voice from: {model_path}")
    try:
        voice = PiperVoice.load(model_path, config_path=config_path)
        logger.info(f"Loaded {lang} voice: {model_path}")
        return voice
    except Exception as e:
        logger.error(f"Failed to load {lang} voice: {e}")
        return None


def _get_voice_EN() -> Optional[PiperVoice]:
    global voice_EN
    if voice_EN is not None:
        return voice_EN
    model_path, config_path = config.get_tts_paths("en")
    if model_path and config_path:
        voice_EN = _load_voice(model_path, config_path, "English")
    return voice_EN


def _get_voice_AR() -> Optional[PiperVoice]:
    global voice_AR
    if voice_AR is not None:
        return voice_AR
    model_path, config_path = config.get_tts_paths("ar")
    if model_path and config_path:
        voice_AR = _load_voice(model_path, config_path, "Arabic")
    return voice_AR


mcp_wrapper = MCPWrapper(
    llama_base_url=config.llm_api_url,
    llama_model=config.llm_model,
    mcp_urls=MCP_SERVER_URLS,
    api_key=config.llm_api_key,
    timeout=config.llm_timeout,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading models at startup...")

    try:
        await asyncio.to_thread(_load_whisper)
    except Exception as e:
        logger.warning(f"STT model failed to load: {e}. Will load on first request.")

    try:
        en_path, en_cfg = config.get_tts_paths("en")
        if en_path:
            global voice_EN
            voice_EN = _load_voice(en_path, en_cfg, "English")
    except Exception as e:
        logger.warning(f"English TTS failed to load: {e}. Will load on first request.")

    try:
        ar_path, ar_cfg = config.get_tts_paths("ar")
        if ar_path:
            global voice_AR
            voice_AR = _load_voice(ar_path, ar_cfg, "Arabic")
    except Exception as e:
        logger.warning(f"Arabic TTS failed to load: {e}. Will load on first request.")

    await mcp_wrapper.initialize_servers()
    yield
    await mcp_wrapper.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "device": config.stt_device,
        "models": models_info,
    }


def stt_transcribe(audio_file) -> Tuple[str, str]:
    model = _load_whisper()
    segments, info = model.transcribe(
        audio_file,
        vad_filter=WHISPER_VAD_FILTER,
        vad_parameters=WHISPER_VAD_PARAMS,
        beam_size=WHISPER_BEAM_SIZE,
    )
    stt_output = " ".join(segment.text for segment in segments).strip()
    logger.info(f"STT Language: {info.language} ({info.language_probability:.2f})")
    return stt_output, info.language


async def llm_process(llm_input: str) -> str:
    if not mcp_wrapper._initialized:
        await mcp_wrapper.initialize_servers()
    return await mcp_wrapper.run_query(llm_input)


async def tts_synthesize(text: Optional[str], lang: str) -> io.BytesIO:
    use_ar = False
    if lang:
        use_ar = str(lang).lower().startswith("ar")
    voice = (
        _get_voice_AR() if (use_ar and _get_voice_AR() is not None) else _get_voice_EN()
    )

    if voice is None:
        raise RuntimeError("No TTS voice available")

    t = (text or "").strip() or " "

    wav_buffer = io.BytesIO()

    try:

        def _synth():
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(TTS_NCHANNELS)
                wav_file.setsampwidth(TTS_SAMPWIDTH)
                wav_file.setframerate(TTS_FRAMERATE)
                voice.synthesize_wav(t, wav_file, syn_config=SYN_config)

        await asyncio.to_thread(_synth)

        wav_buffer.seek(0)

        if wav_buffer.getbuffer().nbytes == 0:
            raise RuntimeError("TTS produced empty audio.")

        return wav_buffer

    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        raise RuntimeError(f"TTS synthesis failed: {e}") from e


MAX_AUDIO_SIZE = 50 * 1024 * 1024
MIN_AUDIO_SIZE = 100


def _validate_audio(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content_type = file.content_type or ""
    if not validate_audio_format(file.filename, content_type):
        raise HTTPException(
            status_code=400,
            detail="Invalid audio format. Allowed: wav, wave, ogg, flac, mp3",
        )


@app.post("/process-audio")
async def process_audio(file: UploadFile = File(...)):
    request_id = uuid.uuid4().hex
    logger.info(f"Processing request {request_id}")

    _validate_audio(file)

    audio_data = None
    try:
        audio_data = await file.read()
        audio_size = len(audio_data)

        if audio_size > MAX_AUDIO_SIZE:
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")
        if audio_size < MIN_AUDIO_SIZE:
            raise HTTPException(status_code=400, detail="Audio file too small")

        audio_file = io.BytesIO(audio_data)
        llm_input, stt_lang = await asyncio.to_thread(stt_transcribe, audio_file)
        logger.info(f"[{request_id}] STT: {llm_input}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{request_id}] STT failed: {e}")
        raise HTTPException(status_code=400, detail=f"STT failed: {str(e)}")

    if not llm_input or not llm_input.strip():
        raise HTTPException(status_code=400, detail="No speech detected")

    try:
        tts_text = await llm_process(llm_input)
        logger.info(f"[{request_id}] LLM Response: {tts_text}")
    except Exception as e:
        logger.error(f"[{request_id}] LLM failed: {e}")
        raise HTTPException(status_code=502, detail=f"LLM failed: {str(e)}")

    if not tts_text or not tts_text.strip():
        raise HTTPException(status_code=502, detail="LLM returned empty response")

    response_lang = detect_language(tts_text)
    logger.info(f"[{request_id}] Detected response language: {response_lang}")

    try:
        audio_buffer = await tts_synthesize(tts_text, response_lang)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS failed: {str(e)}",
        )

    audio_buffer.seek(0)
    return StreamingResponse(audio_buffer, media_type="audio/wav")


if __name__ == "__main__":
    uvicorn.run(app, host=config.app_host, port=config.app_port)

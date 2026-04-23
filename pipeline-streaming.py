import downloader

downloader.main()

import asyncio
import io
import logging
import os
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

from src.config import get_config, setup_logging
from src.mcp import MCPWrapper
from src.shared import validate_audio_format, detect_language

config = get_config()
setup_logging()

has_cuda = os.system("nvidia-smi > /dev/null 2>&1") == 0
device = (
    "cuda"
    if has_cuda
    else ("auto" if config.stt_device == "auto" else config.stt_device)
)
print(f"[CONFIG] Will use {device} for faster-whisper")

WHISPER_MODEL = config.get_stt_path()
WHISPER_DEVICE = device
WHISPER_COMPUTE_TYPE = config.stt_compute_type

TTS_MODEL_EN, TTS_CONFIG_EN = config.get_tts_paths("en")
TTS_MODEL_AR, TTS_CONFIG_AR = config.get_tts_paths("ar")

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

logger = logging.getLogger("Pipeline")

try:
    model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type="int8")
    logger.info("Loaded Whisper model.")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    raise

voice_EN = None
voice_AR = None

try:
    voice_EN = PiperVoice.load(TTS_MODEL_EN, config_path=TTS_CONFIG_EN)
    logger.info("Loaded English voice.")
except Exception as e:
    logger.error(f"Failed to load English voice: {e}")
    raise

try:
    voice_AR = PiperVoice.load(TTS_MODEL_AR, config_path=TTS_CONFIG_AR)
    logger.info("Loaded Arabic voice.")
except Exception:
    voice_AR = None
    logger.warning("Arabic voice not available; will fallback to English voice.")


mcp_wrapper = MCPWrapper(
    llama_base_url=config.llm_api_url,
    llama_model=config.llm_model,
    mcp_urls=config.mcp_servers,
    api_key=config.llm_api_key,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_wrapper.initialize_servers()
    yield
    await mcp_wrapper.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "device": WHISPER_DEVICE,
        "models_loaded": {
            "stt": model is not None,
            "tts_en": voice_EN is not None,
            "tts_ar": voice_AR is not None,
        },
    }


def stt_transcribe(audio_file) -> Tuple[str, str]:
    segments, info = model.transcribe(
        audio_file,
        vad_filter=True,
        beam_size=5,
    )
    stt_output = " ".join(segment.text for segment in segments).strip()
    lang = getattr(info, "language", "en")
    logger.info(f"STT Language: {lang}")
    return stt_output, lang


async def llm_process(llm_input: str) -> str:
    if not mcp_wrapper._initialized:
        await mcp_wrapper.initialize_servers()
    return await mcp_wrapper.run_query(llm_input)


async def tts_synthesize(text: Optional[str], lang: str) -> io.BytesIO:
    use_ar = str(lang).lower().startswith("ar")
    voice = voice_AR if (use_ar and voice_AR is not None) else voice_EN

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

    try:
        llm_input, stt_lang = await asyncio.to_thread(stt_transcribe, file.file)
        logger.info(f"[{request_id}] STT: {llm_input}")
    except Exception as e:
        logger.error(f"[{request_id}] STT failed: {e}")
        llm_input, stt_lang = (" ", "en")

    try:
        tts_text = await llm_process(llm_input)
        logger.info(f"[{request_id}] LLM Response: {tts_text}")
    except Exception as e:
        logger.error(f"[{request_id}] LLM failed: {e}")
        tts_text = llm_input or " "

    response_lang = detect_language(tts_text)

    try:
        audio_buffer = await tts_synthesize(tts_text, response_lang)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS failed: {e}",
        )

    audio_buffer.seek(0)
    return StreamingResponse(audio_buffer, media_type="audio/wav")


@app.post("/process-audio-stream")
async def process_audio_stream(file: UploadFile = File(...)):
    request_id = uuid.uuid4().hex
    logger.info(f"Processing stream request {request_id}")

    _validate_audio(file)

    try:
        llm_input, stt_lang = await asyncio.to_thread(stt_transcribe, file.file)
        logger.info(f"[{request_id}] STT: {llm_input}")
    except Exception as e:
        logger.error(f"[{request_id}] STT failed: {e}")
        llm_input, stt_lang = (" ", "en")

    try:
        tts_text = await llm_process(llm_input)
        logger.info(f"[{request_id}] LLM Response: {tts_text}")
    except Exception as e:
        logger.error(f"[{request_id}] LLM failed: {e}")
        tts_text = llm_input or " "

    async def audio_stream_generator():
        use_ar = str(stt_lang).lower().startswith("ar")
        voice = voice_AR if (use_ar and voice_AR is not None) else voice_EN
        t = (tts_text or "").strip() or " "

        read_fd, write_fd = os.pipe()
        loop = asyncio.get_running_loop()

        def _synth_thread():
            try:
                with os.fdopen(write_fd, "wb") as write_pipe:
                    with wave.open(write_pipe, "wb") as wav_file:
                        wav_file.setnchannels(TTS_NCHANNELS)
                        wav_file.setsampwidth(TTS_SAMPWIDTH)
                        wav_file.setframerate(TTS_FRAMERATE)
                        voice.synthesize_wav(t, wav_file, syn_config=SYN_config)
            except Exception as e:
                logger.error(f"TTS synthesis thread failed: {e}")

        synth_task = loop.run_in_executor(None, _synth_thread)

        try:
            with os.fdopen(read_fd, "rb") as read_pipe:
                while True:
                    chunk = await loop.run_in_executor(None, read_pipe.read, 4096)
                    if not chunk:
                        break
                    yield chunk
        finally:
            await synth_task
            logger.info(f"[{request_id}] Audio stream finished.")

    return StreamingResponse(audio_stream_generator(), media_type="audio/wav")


if __name__ == "__main__":
    uvicorn.run(app, host=config.app_host, port=config.app_port)

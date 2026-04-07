import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get_config, setup_logging

import downloader

if get_config().models_download_on_startup:
    downloader.main()

import asyncio
import io
import json
import logging
import uuid
import wave
import uvicorn
from contextlib import asynccontextmanager, AsyncExitStack
from typing import Dict, List, Optional, Any, Tuple
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from faster_whisper import WhisperModel
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AsyncOpenAI
from piper import PiperVoice
from piper.config import SynthesisConfig

try:
    from langdetect import detect

    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

config = get_config()
setup_logging()
logger = logging.getLogger("Pipeline")

print(f"[CONFIG] Using device: {config.stt_device} for STT")
print(f"[CONFIG] STT model: {config.get_final_stt_path()}")
tts_en_paths = config.get_final_tts_en_paths()
tts_ar_paths = config.get_final_tts_ar_paths()
print(f"[CONFIG] TTS EN: {tts_en_paths[0]}")
print(f"[CONFIG] TTS AR: {tts_ar_paths[0]}")
print(f"[CONFIG] LLM API: {config.llm_api_url}")
print(f"[CONFIG] MCP servers: {config.mcp_servers}")

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

WHISPER_MODEL = config.get_final_stt_path()
WHISPER_DEVICE = config.stt_device
WHISPER_COMPUTE_TYPE = config.stt_compute_type
WHISPER_BEAM_SIZE = config.stt_beam_size
WHISPER_VAD_FILTER = config.stt_vad_filter
WHISPER_VAD_PARAMS = {
    "threshold": config.stt_vad_threshold,
    "min_speech_duration_ms": config.stt_vad_min_speech_ms,
    "min_silence_ms": config.stt_vad_min_silence_ms,
}
WHISPER_LOCAL_ONLY = config.stt_model_path is not None

TTS_MODEL_EN, TTS_CONFIG_EN = config.get_final_tts_en_paths()
TTS_MODEL_AR, TTS_CONFIG_AR = config.get_final_tts_ar_paths()

LLAMA_API_URL = config.llm_api_url
LLAMA_API_KEY = config.llm_api_key
LLAMA_MODEL = config.llm_model
MCP_SERVER_URLS = config.mcp_servers

whisper_model = None
voice_EN = None
voice_AR = None

try:
    whisper_model = WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
        local_files_only=WHISPER_LOCAL_ONLY,
    )
    logger.info("Loaded Whisper model.")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    raise

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


class MCPSessionManager:
    def __init__(self, url: str):
        self.url = url
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.tools: List[Any] = []
        self.lock = asyncio.Lock()
        self.connected = False

    async def connect(self):
        async with self.lock:
            if self.connected:
                return
            try:
                logger.info(f"Connecting to MCP server: {self.url}")
                transport_ctx = sse_client(self.url)
                read, write = await self.exit_stack.enter_async_context(transport_ctx)
                self.session = await self.exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
                await self.session.initialize()

                resp = await self.session.list_tools()
                self.tools = resp.tools
                self.connected = True
                logger.info(f"Connected to {self.url} - Found {len(self.tools)} tools.")
            except Exception as e:
                logger.error(f"Failed to connect to {self.url}: {e}")
                await self.close()
                raise

    async def close(self):
        self.connected = False
        self.session = None
        self.tools = []
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"Error closing session for {self.url}: {e}")

    async def call_tool(self, name: str, arguments: dict) -> Any:
        if not self.connected or not self.session:
            await self.connect()
        return await self.session.call_tool(name, arguments=arguments)


class MCPWrapper:
    def __init__(self, llama_base_url: str, llama_model: str, mcp_urls: list[str]):
        self.llama = AsyncOpenAI(
            base_url=llama_base_url,
            api_key=LLAMA_API_KEY,
            timeout=60.0,
            max_retries=0,
        )
        self.llama_model = llama_model
        self.mcp_managers: List[MCPSessionManager] = [
            MCPSessionManager(url) for url in mcp_urls
        ]
        self.tool_map: Dict[str, MCPSessionManager] = {}
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._tools_schema_cache: Optional[List[Dict]] = None

    async def initialize_servers(self):
        async with self._init_lock:
            if self._initialized:
                return

            results = await asyncio.gather(
                *(mgr.connect() for mgr in self.mcp_managers), return_exceptions=True
            )

            self.tool_map.clear()
            for mgr, res in zip(self.mcp_managers, results):
                if isinstance(res, Exception):
                    logger.error(f"Startup connection failed for {mgr.url}: {res}")
                    continue
                for tool in mgr.tools:
                    self.tool_map[tool.name] = mgr

            self._initialized = True
            self._rebuild_tools_schema_cache()
            logger.info("MCPWrapper initialization complete.")

    def _rebuild_tools_schema_cache(self):
        schema = []
        for mgr in self.mcp_managers:
            if not mgr.connected:
                continue
            for tool in mgr.tools:
                schema.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "No description",
                            "parameters": tool.inputSchema,
                        },
                    }
                )
        self._tools_schema_cache = schema

    @property
    def openai_tools_schema(self):
        if self._tools_schema_cache is not None:
            return self._tools_schema_cache
        return []

    async def _execute_tool(self, tool_call) -> dict:
        name = tool_call.function.name
        try:
            args_dict = json.loads(tool_call.function.arguments)
        except Exception:
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": "Error: Invalid JSON arguments.",
            }

        logger.info(f"AI requested tool: {name}({args_dict})")

        manager = self.tool_map.get(name)
        if not manager:
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": f"Error: Tool '{name}' not found.",
            }

        try:
            result = await manager.call_tool(name, args_dict)
            content = str(result.content)
        except Exception as e:
            logger.warning(f"Tool call '{name}' failed: {e}. Attempting reconnect...")
            try:
                await manager.close()
                await manager.connect()
                result = await manager.call_tool(name, args_dict)
                content = str(result.content)
            except Exception as e2:
                logger.error(f"Tool retry '{name}' failed: {e2}")
                content = f"Error executing tool '{name}': {e2}"

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": name,
            "content": content,
        }

    async def run_query(self, stt_input: str) -> str:
        messages = [
            {
                "role": "system",
                "content": "You are a concise voice assistant. Give short, natural answers. "
                "Avoid bold text, markdown lists, or long explanations unless asked.",
            },
            {"role": "user", "content": stt_input},
        ]

        max_tool_loops = 5
        for i in range(max_tool_loops):
            try:
                response = await self.llama.chat.completions.create(
                    model=self.llama_model,
                    messages=messages,
                    tools=self.openai_tools_schema
                    if self.openai_tools_schema
                    else None,
                    tool_choice="auto" if self.openai_tools_schema else None,
                )
            except Exception as e:
                logger.error(f"LLM call failed at step {i}: {e}")
                raise RuntimeError(f"LLM API call failed: {e}")

            message = response.choices[0].message
            messages.append(message)

            if not message.tool_calls:
                return message.content or ""

            tool_results = await asyncio.gather(
                *(self._execute_tool(tc) for tc in message.tool_calls)
            )
            messages.extend(tool_results)

        logger.warning(f"Tool loop exceeded {max_tool_loops} iterations")
        return messages[-1].content or ""

    async def close(self):
        await asyncio.gather(*(mgr.close() for mgr in self.mcp_managers))


mcp_wrapper = MCPWrapper(LLAMA_API_URL, LLAMA_MODEL, MCP_SERVER_URLS)


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
        "device": config.stt_device,
        "models_loaded": {
            "stt": whisper_model is not None,
            "tts_en": voice_EN is not None,
            "tts_ar": voice_AR is not None,
        },
    }


def stt_transcribe(audio_file) -> Tuple[str, str]:
    segments, info = whisper_model.transcribe(
        audio_file,
        vad_filter=WHISPER_VAD_FILTER,
        vad_parameters=WHISPER_VAD_PARAMS,
        beam_size=WHISPER_BEAM_SIZE,
    )
    stt_output = " ".join(segment.text for segment in segments).strip()
    logger.info(
        f"STT Language: {getattr(info, 'language', 'unknown')} ({getattr(info, 'language_probability', 0.0):.2f})"
    )
    return stt_output, getattr(info, "language", "en")


async def llm_process(llm_input: str) -> str:
    if not mcp_wrapper._initialized:
        await mcp_wrapper.initialize_servers()
    return await mcp_wrapper.run_query(llm_input)


async def tts_synthesize(text: Optional[str], lang: str) -> io.BytesIO:
    use_ar = False
    if lang:
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


@app.post("/process-audio")
async def process_audio(file: UploadFile = File(...)):
    request_id = uuid.uuid4().hex
    logger.info(f"Processing request {request_id}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    audio_data = None
    llm_input = ""
    stt_lang = "en"

    try:
        audio_data = await file.read()
        if len(audio_data) < 100:
            raise ValueError("Audio file too small")
        import io as io_module

        audio_file = io_module.BytesIO(audio_data)
        llm_input, stt_lang = await asyncio.to_thread(stt_transcribe, audio_file)
        logger.info(f"[{request_id}] STT: {llm_input}")
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

    response_lang = _detect_language(tts_text)
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


def _detect_language(text: str) -> str:
    if not text or not text.strip():
        return "en"

    if not LANGDETECT_AVAILABLE:
        return "en"

    try:
        detected = detect(text[:200])
        return detected if detected else "en"
    except Exception:
        return "en"


if __name__ == "__main__":
    uvicorn.run(app, host=config.app_host, port=config.app_port)

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

config = get_config()
setup_logging()
logger = logging.getLogger("Pipeline")

print(f"[CONFIG] Using device: {config.stt_device} for STT")
print(f"[CONFIG] STT model: {config.stt_model_path}")
print(f"[CONFIG] TTS EN: {config.tts_en_model}")
print(f"[CONFIG] TTS AR: {config.tts_ar_model}")
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

WHISPER_MODEL = config.stt_model_path
WHISPER_DEVICE = config.stt_device
WHISPER_COMPUTE_TYPE = config.stt_compute_type
WHISPER_BEAM_SIZE = config.stt_beam_size
WHISPER_VAD_FILTER = config.stt_vad_filter

TTS_MODEL_EN = config.tts_en_model
TTS_CONFIG_EN = config.tts_en_config
TTS_MODEL_AR = config.tts_ar_model
TTS_CONFIG_AR = config.tts_ar_config

LLAMA_API_URL = config.llm_api_url
LLAMA_API_KEY = config.llm_api_key
MCP_SERVER_URLS = config.mcp_servers

whisper_model = None
voice_EN = None
voice_AR = None

try:
    whisper_model = WhisperModel(
        WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
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
    def __init__(self, llama_base_url: str, mcp_urls: list[str]):
        self.llama = AsyncOpenAI(base_url=llama_base_url, api_key=LLAMA_API_KEY)
        self.mcp_managers: List[MCPSessionManager] = [
            MCPSessionManager(url) for url in mcp_urls
        ]
        self.tool_map: Dict[str, MCPSessionManager] = {}
        self._init_lock = asyncio.Lock()
        self._initialized = False

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
            logger.info("MCPWrapper initialization complete.")

    @property
    def openai_tools_schema(self):
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
        return schema

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

        for i in range(5):
            try:
                response = await self.llama.chat.completions.create(
                    model="local-model",
                    messages=messages,
                    tools=self.openai_tools_schema,
                    tool_choice="auto",
                )
            except Exception as e:
                logger.error(f"LLM call failed at step {i}: {e}")
                return stt_input

            message = response.choices[0].message
            messages.append(message)

            if not message.tool_calls:
                return message.content or ""

            tool_results = await asyncio.gather(
                *(self._execute_tool(tc) for tc in message.tool_calls)
            )
            messages.extend(tool_results)

        return messages[-1].content or stt_input

    async def close(self):
        await asyncio.gather(*(mgr.close() for mgr in self.mcp_managers))


mcp_wrapper = MCPWrapper(LLAMA_API_URL, MCP_SERVER_URLS)


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


@app.post("/prosess-audio")
async def prosess_audio(file: UploadFile = File(...)):
    request_id = uuid.uuid4().hex
    logger.info(f"Processing request {request_id}")

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

    try:
        audio_buffer = await tts_synthesize(tts_text, stt_lang)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"TTS failed: {e}"
        )

    audio_buffer.seek(0)
    return StreamingResponse(audio_buffer, media_type="audio/wav")


if __name__ == "__main__":
    uvicorn.run(app, host=config.app_host, port=config.app_port)

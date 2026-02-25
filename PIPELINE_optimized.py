import asyncio
import io
import json
import logging
import uuid
import wave
from contextlib import AsyncExitStack
from typing import Dict, List, Optional, Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from faster_whisper import WhisperModel
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AsyncOpenAI
from piper import PiperVoice
from piper.config import SynthesisConfig

# --- CONFIG ---
LLAMA_API_URL = "http://10.200.71.180:2312/v1"
LLAMA_API_KEY = "sk-no-key-required"
MCP_SERVER_URLS = [
    "http://10.200.71.180:2527/sse",
    "http://10.200.71.180:2528/sse",
]

WHISPER_MODEL = "/run/media/2kfi/DATA/Work-files/Projects/new-voice-asstant/models/whisper-medium"

TTS_MODEL_EN = "/run/media/2kfi/DATA/Work-files/Projects/new-voice-asstant/models/TTS-CORI-EN/en_GB-cori-high.onnx"
TTS_CONFIG_EN = "/run/media/2kfi/DATA/Work-files/Projects/new-voice-asstant/models/TTS-CORI-EN/en_GB-cori-high.onnx.json"
TTS_MODEL_AR = "/run/media/2kfi/DATA/Work-files/Projects/new-voice-asstant/models/TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx"
TTS_CONFIG_AR = "/run/media/2kfi/DATA/Work-files/Projects/new-voice-asstant/models/TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx.json"

SYN_config = SynthesisConfig(
    volume=0.5,
    length_scale=1.0,
    noise_scale=1.0,
    noise_w_scale=1.0,
    normalize_audio=False,
)

# Wave defaults
TTS_NCHANNELS = 1
TTS_SAMPWIDTH = 2
TTS_FRAMERATE = 24000

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Pipeline")

# --- Load models ---
try:
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
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


# --- MCP Session Manager ---
class MCPSessionManager:
    """Manages a single MCP server connection with auto-reconnect capability."""
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
                self.session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                await self.session.initialize()
                
                # Fetch tools
                resp = await self.session.list_tools()
                self.tools = resp.tools
                self.connected = True
                logger.info(f"Connected to {self.url} - Found {len(self.tools)} tools.")
            except Exception as e:
                logger.error(f"Failed to connect to {self.url}: {e}")
                await self.close() # Ensure cleanup on failure
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


# --- MCPWrapper ---
class MCPWrapper:
    """
    Persistent MCP + LLM wrapper.
    """
    def __init__(self, llama_base_url: str, mcp_urls: list[str]):
        self.llama = AsyncOpenAI(base_url=llama_base_url, api_key=LLAMA_API_KEY)
        self.mcp_managers: List[MCPSessionManager] = [MCPSessionManager(url) for url in mcp_urls]
        self.tool_map: Dict[str, MCPSessionManager] = {} # Maps tool_name -> Manager
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def initialize_servers(self):
        async with self._init_lock:
            if self._initialized:
                return
            
            # Parallel connection
            results = await asyncio.gather(
                *(mgr.connect() for mgr in self.mcp_managers), 
                return_exceptions=True
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
            if not mgr.connected: continue
            for tool in mgr.tools:
                schema.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "No description",
                        "parameters": tool.inputSchema
                    }
                })
        return schema

    async def _execute_tool(self, tool_call) -> dict:
        """Executes a single tool call with retry logic."""
        name = tool_call.function.name
        try:
            args_dict = json.loads(tool_call.function.arguments)
        except Exception:
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": "Error: Invalid JSON arguments."
            }

        logger.info(f"AI requested tool: {name}({args_dict})")
        
        manager = self.tool_map.get(name)
        if not manager:
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": f"Error: Tool '{name}' not found."
            }

        try:
            # Attempt 1
            result = await manager.call_tool(name, args_dict)
            content = str(result.content)
        except Exception as e:
            logger.warning(f"Tool call '{name}' failed: {e}. Attempting reconnect...")
            try:
                # Attempt 2: Reconnect and retry
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
            "content": content
        }

    async def run_query(self, stt_input: str) -> str:
        messages = [
            {
                "role": "system",
                "content": "You are a concise voice assistant. Give short, natural answers. "
                           "Avoid bold text, markdown lists, or long explanations unless asked."
            },
            {"role": "user", "content": stt_input}
        ]
        
        for i in range(5):  # Maximum 5 reasoning steps
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

            # Execute all requested tools in parallel
            tool_results = await asyncio.gather(
                *(self._execute_tool(tc) for tc in message.tool_calls)
            )
            messages.extend(tool_results)
            
        return messages[-1].content or stt_input

    async def close(self):
        await asyncio.gather(*(mgr.close() for mgr in self.mcp_managers))


mcp_wrapper = MCPWrapper(LLAMA_API_URL, MCP_SERVER_URLS)

# --- FastAPI ---
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await mcp_wrapper.initialize_servers()

@app.on_event("shutdown")
async def on_shutdown():
    await mcp_wrapper.close()

# --- Core Functions (Memory Optimized) ---

def STT_Pros(audio_file) -> (str, str):
    """
    Accepts a file-like object (binary).
    """
    segments, info = model.transcribe(
        audio_file,
        vad_filter=True,
        beam_size=5,
    )
    stt_output = " ".join(segment.text for segment in segments).strip()
    logger.info(f"STT Language: {getattr(info, 'language', 'unknown')} ({getattr(info, 'language_probability', 0.0):.2f})")
    return stt_output, getattr(info, "language", "en")

async def LLM_pros(llm_input: str) -> str:
    if not mcp_wrapper._initialized:
        await mcp_wrapper.initialize_servers()
    return await mcp_wrapper.run_query(llm_input)

async def TTS_pros(text: Optional[str], lang: str) -> io.BytesIO:
    """
    Returns audio as in-memory bytes.
    """
    use_ar = False
    if lang:
        use_ar = str(lang).lower().startswith("ar")
    voice = voice_AR if (use_ar and voice_AR is not None) else voice_EN

    t = (text or "").strip() or " "
    
    # In-memory buffer
    wav_buffer = io.BytesIO()
    
    try:
        def _synth():
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(TTS_NCHANNELS)
                wav_file.setsampwidth(TTS_SAMPWIDTH)
                wav_file.setframerate(TTS_FRAMERATE)
                voice.synthesize_wav(t, wav_file, syn_config=SYN_config)

        await asyncio.to_thread(_synth)
        
        # Rewind buffer for reading
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

    # STT (Direct from UploadFile stream, offloaded to thread)
    try:
        llm_input, stt_lang = await asyncio.to_thread(STT_Pros, file.file)
        logger.info(f"[{request_id}] STT: {llm_input}")
    except Exception as e:
        logger.error(f"[{request_id}] STT failed: {e}")
        llm_input, stt_lang = (" ", "en")

    # LLM
    try:
        tts_text = await LLM_pros(llm_input)
        logger.info(f"[{request_id}] LLM Response: {tts_text}")
    except Exception as e:
        logger.error(f"[{request_id}] LLM failed: {e}")
        tts_text = llm_input or " "

    # TTS
    try:
        audio_buffer = await TTS_pros(tts_text, stt_lang)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"TTS failed: {e}")

    # StreamingResponse for potential performance gain and idiomatic output
    audio_buffer.seek(0)
    return StreamingResponse(audio_buffer, media_type="audio/wav")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)

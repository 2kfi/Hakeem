# Developer Guide

## English

### About AIOL

> **AIOL** (Artificial Intelligence Open Lab) - Project developed for JOYS T323 competition.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [System Components](#system-components)
3. [API Reference](#api-reference)
4. [Pipeline Flow](#pipeline-flow)
5. [MCP Server & Tools](#mcp-server--tools)
6. [Wake Word Detection](#wake-word-detection)
7. [Configuration Reference](#configuration-reference)
8. [Running the System](#running-the-system)
9. [Testing](#testing)
10. [Related Documentation](#related-documentation)

---

## Architecture Overview

The Hakeem voice assistant pipeline follows a sequential STT → LLM → TTS architecture:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Audio      │───▶│     STT      │───▶│     LLM      │───▶│     TTS      │
│   Input      │    │   Whisper    │    │  MedGemma    │    │    Piper     │
│  (Wake Word) │    │  (faster-    │    │  (MCP Tools) │    │  (EN + AR)   │
│              │    │   whisper)   │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                           │                    │                    │
                           └────────────────────┴────────────────────┘
                                                 │
                                          ┌──────┴──────┐
                                          │  FastAPI   │
                                          │   :8003    │
                                          └────────────┘
```

### Component Breakdown

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Wake Word** | openWakeWord (custom "Hakeem" model) | Listen for activation phrase |
| **STT** | Faster-Whisper | Convert speech to text |
| **LLM** | MedGemma (medical fine-tuned) via llama.cpp | Process queries with medical knowledge |
| **MCP** | Model Context Protocol + ZIM files | Access offline Wikipedia encyclopedia |
| **TTS** | Piper (English + Arabic) | Convert text response to speech |

---

## System Components

### 1. Wake Word Client (`wake_word_client.py`)

Listens for "Hakeem" wake word using ONNX models:

- Uses `openwakeword` library for inference
- WebRTC VAD for silence detection
- Records user speech until silence detected
- Sends audio to pipeline API
- Plays back TTS response via PyAudio

```python
# Key parameters
python wake_word_client.py \
    --api-url http://localhost:8003/process-audio \
    --model-path models/Hakeem/Hakeem.onnx \
    --threshold 0.5
```

### 2. Pipeline Server (`pipeline.py`)

FastAPI server handling the STT → LLM → TTS flow:

- **Non-streaming**: `/process-audio` - Returns complete audio file
- **Streaming**: `/process-audio-stream` - Streams TTS output

### 3. MCP Server (`MCP-servers/Open-zim/`)

Provides offline knowledge base using ZIM files (Wikipedia dumps):

- Runs as separate FastMCP server
- Tools: `search`, `get_article`, `list_articles`, `get_suggestions`
- Connects to main pipeline via SSE (Server-Sent Events)

---

## API Reference

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check - returns model status |
| `/process-audio` | POST | Process audio → audio response (non-streaming) |
| `/process-audio-stream` | POST | Process audio → streaming audio response |

### GET /health

**Response:**
```json
{
  "status": "healthy",
  "device": "cpu",
  "models_loaded": {
    "stt": true,
    "tts_en": true,
    "tts_ar": true
  }
}
```

### POST /process-audio

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - Audio file (wav, mp3, ogg, flac)

**Response:**
- Content-Type: `audio/wav`
- Body: Audio file

**Example:**
```bash
curl -X POST http://localhost:8003/process-audio \
  -F "file=@audio.wav" \
  --output response.wav
```

### POST /process-audio-stream

Same as above but streams TTS audio in real-time.

---

## Pipeline Flow

### Step 1: Speech-to-Text (STT)

```python
# Using faster-whisper
from faster_whisper import WhisperModel

whisper_model = WhisperModel("medium", device="auto", compute_type="int8")
segments, info = whisper_model.transcribe(
    audio_file,
    vad_filter=True,
    vad_parameters={"threshold": 0.5, "min_speech_duration_ms": 250}
)
text = " ".join(segment.text for segment in segments)
```

**Key features:**
- Voice Activity Detection (VAD) filters non-speech
- Language detection included
- Beam size: 5 for accuracy

### Step 2: LLM Processing with MCP

```python
# MCP wrapper connects to LLM server + MCP tools
from src.mcp import MCPWrapper

mcp = MCPWrapper(
    llama_base_url="http://localhost:2312/v1",
    llama_model="medgemma",
    mcp_urls=["http://localhost:2527/sse"]
)
response = await mcp.run_query(user_text)
```

**Primary LLM: MedGemma**
- Medical-domain fine-tuned model from Google
- Optimized for healthcare question answering
- Runs locally via llama.cpp (quantized for efficiency)

**Benchmark Results:**
| Model | Accuracy | Avg Time |
|-------|----------|----------|
| **MedGemma** | Target model | - |
| Qwen3-4B | 25% | 1.4s MCQ / 10.6s generative |

**LLM System Prompt:**
> "You are a concise voice assistant. Give short, natural answers. Avoid bold text, markdown lists, or long explanations unless asked."

**Tool Loop:** LLM can call MCP tools up to 5 times per query.

### Step 3: Text-to-Speech (TTS)

```python
from piper import PiperVoice

voice = PiperVoice.load("en_GB-cori-high.onnx")
wav_buffer = voice.synthesize_wav(text)
```

**Language Detection:** Automatically detects Arabic vs English and selects appropriate voice.

---

## MCP Server & Tools

### Available Tools

The MCP server provides these tools to the LLM:

| Tool | Description |
|------|-------------|
| `search` | Full-text search in ZIM file |
| `get_article` | Read article by path |
| `list_articles` | List all entries |
| `get_metadata` | Get ZIM file metadata |
| `get_suggestions` | Search suggestions |
| `list_zim_files` | List available ZIM files |

### Tool Schema Example

```json
{
  "type": "function",
  "function": {
    "name": "search",
    "description": "Search for content in a ZIM file using full-text search.",
    "parameters": {
      "type": "object",
      "properties": {
        "zim_file": {"type": "string"},
        "query": {"type": "string"},
        "limit": {"type": "integer"}
      },
      "required": ["zim_file", "query"]
    }
  }
}
```

### Running MCP Server

```bash
cd MCP-servers/Open-zim
docker-compose up --build

# Or directly:
python -m zim_mcp.server
```

---

## Wake Word Detection

### Custom Wake Word Model

The "Hakeem" wake word model was trained using openWakeWord:

1. **Audio Collection**: Record multiple samples of "Hakeem" pronunciation
2. **Training**: Use openwakeword training pipeline
3. **Export**: ONNX format for efficient inference

### Model Location

```
models/
└── Hakeem/
    └── Hakeem.onnx    # Custom wake word model
```

### Configuration

```python
# In wake_word_client.py
client = WakeWordClient(
    model_path="models/Hakeem/Hakeem.onnx",
    oww_threshold=0.5,      # Detection sensitivity (0-1)
    silence_threshold_ms=1500,  # Stop recording after silence
)
```

---

## Configuration Reference

### Presets

```yaml
preset: "default"  # or "lightweight" or "heavy"
```

| Preset | STT Model | Voices | Compute | Best For |
|--------|-----------|--------|---------|----------|
| `default` | whisper-medium | EN + AR | int8 | Good CPU/GPU |
| `lightweight` | whisper-small | EN only | int8 | Weak CPU |
| `heavy` | whisper-large-v3 | EN + AR | float16 | Powerful GPU |

### Full Configuration

```yaml
# config.yaml
app:
  host: "0.0.0.0"
  port: 8003

stt:
  model: "Systran/faster-whisper-medium"
  device: "auto"      # auto/cuda/rocm/cpu
  compute_type: "int8"
  beam_size: 5

tts:
  en:
    repo: "rhasspy/piper-voices"
    voice: "en_GB/cori/high"
  ar:
    repo: "speaches-ai/piper-ar_JO-kareem-medium"

llm:
  api_url: "http://localhost:2312/v1"
  api_key: "sk-no-key-required"
  model: "medgemma-4b-it"

mcp:
  servers:
    - "http://localhost:2527/sse"
```

---

## Running the System

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/2kfi/Hakeem.git
cd Hakeem

# 2. Copy environment file
cp .env.example .env

# 3. Build and run
docker-compose up --build

# 4. Test health endpoint
curl http://localhost:8003/health
```

### Option 2: Bare Metal

```bash
# Install dependencies
pip install -r backend-requirements.txt

# Run pipeline
python pipeline.py

# In another terminal - run wake word client
python wake_word_client.py
```

### Option 3: LLM Server (MedGemma)

```bash
# Using llama.cpp server
./server -m models/medgemma-4b-it-q4_k_m.gguf \
    -c 4096 \
    --port 2312
```

---

## Testing

### Health Check

```bash
curl http://localhost:8003/health
```

### Process Audio

```bash
curl -X POST http://localhost:8003/process-audio \
  -F "file=@test_audio.wav" \
  --output response.wav
```

### Test Wake Word

```bash
python wake_word_client.py --debug
```

---

## Related Documentation

- [Developer Guide (Arabic)](./DEVELOPER_AR.md) - دليل المطور
- [User Guide](./USER.md) - End-user documentation
- [User Guide (Arabic)](./USER_AR.md) - دليل المستخدم
- [Judges Report](./JUDGES.md) - Technical report for competition
- [Judges Report (Arabic)](./JUDGES_AR.md) - تقرير الحكام
- [API Reference](./API.md) - Detailed API documentation
- [Configuration](./CONFIG.md) - Configuration options

---

## License

See project root for license information.
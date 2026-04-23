# LLMSIMT Voice Pipeline (Hakeem)

> **AIOL** - A Docker-ready voice processing pipeline with STT, LLM, and TTS capabilities for medical AI assistance.

## Documentation

| Guide | Audience | Description |
|-------|----------|-------------|
| **[User Guide](docs/USER.md)** | End Users | Features, usage, hardware requirements, disclaimers |
| **[Developer Guide](docs/DEVELOPER.md)** | Developers | API, architecture, config, MCP tools, wake word |
| **[Judges Report](docs/JUDGES.md)** | Judges | Technical report for JOYS T323 competition |

### Quick Links
- [Configuration](docs/CONFIG.md)
- [API Reference](docs/API.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

---

## Architecture

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Audio │───▶│   STT   │───▶│   LLM  │───▶│   TTS   │
│ Input  │    │ Whisper │    │ (MCP)  │    │  Piper  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
                    │              │              │
                    └──────────────┴──────────────┘
                                  │
                            ┌─────┴─────┐
                            │ FastAPI   │
                            │  :8003    │
                            └───────────┘
```

## Quick Start

### Docker Compose (Recommended)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env with your settings
nano .env

# 3. Build and run
docker-compose up --build

# 4. Test the health endpoint
curl http://localhost:8003/health
```

### Docker Only

```bash
# Build
docker build -t llmsimt-pipeline .

# Run with model volume
docker run -p 8003:8003 \
  -v $(pwd)/models:/app/models:ro \
  -e MODELS_DOWNLOAD_ON_STARTUP=false \
  llmsimt-pipeline
```

### Bare Metal

```bash
cd Docker-files

# Option 1: Auto-download models (internet required)
python pipeline.py

# Option 2: Use existing models from parent directory
# Copy the baremetal config example:
cp config.baremetal.example config.yaml
python pipeline.py
```

## Configuration

### Presets (Recommended)

The easiest way to configure - just choose a preset:

```yaml
# config.yaml
preset: "default"  # or "lightweight" or "heavy"
```

| Preset | STT Model | Voices | Compute | Best For |
|--------|-----------|--------|---------|----------|
| `default` | whisper-medium | EN + AR | int8 | Good CPU/GPU |
| `lightweight` | whisper-small | EN only | int8 | Weak CPU |
| `heavy` | whisper-large-v3 | EN + AR | float16 | Powerful GPU |

### Override Specific Settings

```yaml
preset: "default"

# Override STT
stt:
  repo: "Systran/faster-whisper"
  model: "small"       # tiny/small/medium/large-v3
  device: "auto"        # auto/cuda/rocm/cpu
  compute_type: "int8"  # int8/float16/float32

# Override TTS - use custom voice from HuggingFace
tts:
  en:
    repo: "rhasspy/piper-voices"
    voice: "en_GB/cori/high"

# Or use local model (overrides repo)
tts:
  en:
    model_path: "models/my-voice.onnx"
    config_path: "models/my-voice.onnx.json"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check - returns model status |
| `/process-audio` | POST | Process audio, returns audio (non-streaming) |
| `/process-audio-stream` | POST | Process audio, returns audio (streaming TTS) |

### Health Check Response

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

### Process Audio (Non-Streaming)

```bash
curl -X POST http://localhost:8003/process-audio \
  -F "file=@audio.wav" \
  --output response.wav
```

### Process Audio (Streaming TTS)

```bash
curl -X POST http://localhost:8003/process-audio-stream \
  -F "file=@audio.wav" \
  --output stream_response.wav
```

## Models

### Auto-Download (Recommended)

Set `MODELS_DOWNLOAD_ON_STARTUP=true` in config.yaml to auto-download models from HuggingFace on first run.

### Model Structure (After Download)

With presets, models download to:

```
models/
├── whisper-medium/          # STT - from preset
│   ├── model.bin
│   ├── config.json
│   ├── vocabulary.txt
│   └── tokenizer.json
├── TTS-EN-en_GB-cori-high/  # TTS - English
│   ├── en_GB-cori-high.onnx
│   └── en_GB-cori-high.onnx.json
└── TTS-AR-ar_JO-kareem-medium/  # TTS - Arabic
    ├── ar_JO-kareem-medium.onnx
    └── ar_JO-kareem-medium.onnx.json
```

### Using Custom Models

#### Option 1: HuggingFace Repository

```yaml
preset: "default"
stt:
  repo: "your-username/whisper-model"
  model: "small"

tts:
  en:
    repo: "your-username/piper-voices"
    voice: "en_US/your-voice/low"
```

#### Option 2: Local Model (Already Downloaded)

```yaml
preset: "default"
stt:
  model_path: "models/my-whisper"  # folder with model files

tts:
  en:
    model_path: "models/my-voice.onnx"
    config_path: "models/my-voice.onnx.json"
```

#### Option 3: Environment Variables

```bash
# Use lightweight preset via env
PRESET=lightweight

# Or override specific settings
STT_MODEL=small
TTS_EN_VOICE=en_GB/cori/high
STT_DEVICE=cuda
```

## GPU Support

### NVIDIA GPU

```bash
# Install nvidia-docker
# Then run with:
docker-compose up --build
# GPU is auto-detected via STT_DEVICE=auto
```

### AMD ROCm

```bash
# Set device manually
STT_DEVICE=rocm docker-compose up
```

## Docker Compose with External Services

If you have LLM and MCP servers running on the host:

```yaml
# In .env
LLM_API_URL=http://host.docker.internal:2312/v1
MCP_SERVER_URLS=http://host.docker.internal:2527/sse,http://host.docker.internal:2528/sse
```

## File Structure

```
Docker-files/
├── config.yaml              # Main configuration
├── config.py                # Config loader with env overrides
├── downloader.py            # Model download script
├── pipeline.py              # Main FastAPI application (non-streaming)
├── pipeline-streaming.py   # Streaming version with TTS streaming
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker Compose deployment
├── .env.example             # Environment variables template
├── .env                     # Your environment settings (gitignored)
└── requirements.txt          # Python dependencies
```

## Two Pipeline Versions

### pipeline.py (Default)
- Standard processing: STT → LLM → TTS
- Returns complete audio file after TTS synthesis
- Endpoint: `/process-audio`

### pipeline-streaming.py
- Same as pipeline.py but with streaming TTS
- Audio streams in real-time during synthesis
- Endpoints: `/process-audio` + `/process-audio-stream`

```bash
# Run pipeline.py (default)
python pipeline.py

# Run streaming version
python pipeline-streaming.py
```

## Troubleshooting

### Models not found

```bash
# Check model paths
ls -la models/
```

### GPU not detected

```bash
# Test manually
nvidia-smi  # for NVIDIA
rocm-smi    # for AMD

# Or set explicitly
STT_DEVICE=cuda docker run ...
```

### MCP connection failed

```bash
# Check MCP server is running
curl http://your-mcp-server:2527/sse
```

### Health check fails

```bash
# Check logs
docker-compose logs pipeline

# Or test manually
docker exec -it llmsimt-pipeline curl localhost:8003/health
```

## Development

### Running without Docker

```bash
cd Docker-files

# Option 1: Let it auto-download models
python pipeline.py

# Option 2: Use existing models (skip download)
# Edit config.yaml:
# models:
#   download_on_startup: false

# Run
python pipeline.py
```

### Quick Config Changes

```bash
# Want lighter model for weak CPU?
# Just change preset in config.yaml:
preset: "lightweight"

# Want to use your custom voice?
# Edit config.yaml:
preset: "default"
tts:
  en:
    model_path: "models/my-voice.onnx"
    config_path: "models/my-voice.onnx.json"

# Or via environment:
TTS_EN_MODEL_PATH=models/my-voice.onnx
TTS_EN_CONFIG_PATH=models/my-voice.onnx.json
```

### Rebuilding

```bash
# Rebuild container
docker-compose build --no-cache

# Or rebuild and start fresh
docker-compose down -v
docker-compose up --build
```

## License

See project root for license information.

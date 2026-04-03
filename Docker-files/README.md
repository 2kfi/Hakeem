# LLMSIMT Voice Pipeline

A Docker-ready voice processing pipeline with STT (Speech-to-Text), LLM (Language Model), and TTS (Text-to-Speech) capabilities.

## Architecture

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Audio  │───▶│   STT   │───▶│   LLM   │───▶│   TTS   │
│ Input   │    │ Whisper │    │ (MCP)   │    │  Piper  │
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
# Install dependencies
pip install -r requirements.txt

# Run
python pipeline.py
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_HOST` | `0.0.0.0` | Server host |
| `APP_PORT` | `8003` | Server port |
| `APP_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `STT_MODEL_PATH` | `models/whisper-medium` | Whisper model path |
| `STT_VARIANT` | `medium` | Whisper variant (tiny, small, medium, large) |
| `STT_DEVICE` | `auto` | Device (auto, cpu, cuda, rocm) |
| `STT_COMPUTE_TYPE` | `int8` | Compute type (int8, float16) |
| `TTS_EN_MODEL` | `models/TTS-CORI-EN/...` | English TTS model |
| `TTS_AR_MODEL` | `models/TTS-KAREEM-ARABIC/...` | Arabic TTS model |
| `LLM_API_URL` | `http://10.200.71.180:2312/v1` | LLM API URL |
| `LLM_API_KEY` | `sk-no-key-required` | LLM API key |
| `MCP_SERVER_URLS` | `http://10.200.71.180:2527/sse,...` | MCP server URLs (comma-separated) |
| `MODELS_DOWNLOAD_ON_STARTUP` | `false` | Download models on startup |

### Using config.yaml

All settings can also be configured in `config.yaml`. Environment variables take precedence over config.yaml values.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check - returns model status |
| `/prosess-audio` | POST | Process audio, returns audio (non-streaming) |
| `/prosess-audio-stream` | POST | Process audio, returns audio (streaming TTS) |

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
curl -X POST http://localhost:8003/prosess-audio \
  -F "file=@audio.wav" \
  --output response.wav
```

### Process Audio (Streaming TTS)

```bash
curl -X POST http://localhost:8003/prosess-audio-stream \
  -F "file=@audio.wav" \
  --output stream_response.wav
```

## Models

### Required Models

Place models in a `models/` directory with this structure:

```
models/
├── whisper-medium/          # STT - Whisper
│   ├── model.bin
│   ├── config.json
│   ├── vocabulary.txt
│   └── tokenizer.json
├── TTS-CORI-EN/            # TTS - English
│   ├── en_GB-cori-high.onnx
│   └── en_GB-cori-high.onnx.json
├── TTS-KAREEM-ARABIC/      # TTS - Arabic
│   ├── ar_JO-kareem-medium.onnx
│   └── ar_JO-kareem-medium.onnx.json
├── MedGemma/               # LLM (optional)
│   ├── MedGemma-3b-it-Q4_K_M.gguf
│   └── MedGemma-mmproj.gguf
└── Hakeem/                 # Wakeword (frontend, not used by pipeline)
    └── Hakeem.tflite
```

### Model Download

Set `MODELS_DOWNLOAD_ON_STARTUP=true` to auto-download models from HuggingFace on first run.

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
- Endpoint: `/prosess-audio`

### pipeline-streaming.py
- Same as pipeline.py but with streaming TTS
- Audio streams in real-time during synthesis
- Endpoints: `/prosess-audio` + `/prosess-audio-stream`

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

# Create models symlink to parent
ln -s ../models models

# Set environment
export MODELS_DOWNLOAD_ON_STARTUP=false
export STT_MODEL_PATH=models/whisper-medium
export TTS_EN_MODEL=models/TTS-CORI-EN/en_GB-cori-high.onnx
export TTS_EN_CONFIG=models/TTS-CORI-EN/en_GB-cori-high.onnx.json
export TTS_AR_MODEL=models/TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx
export TTS_AR_CONFIG=models/TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx.json
export MODELS_STORAGE_PATH=./models

# Run
python pipeline.py
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

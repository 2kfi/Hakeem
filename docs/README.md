# LLMSIMT-Hakeem

Voice AI Pipeline with STT → LLM → TTS

## Quick Start

### Docker (Recommended)

```bash
# 1. Copy example config
cp examples/config.docker.yaml.example config.yaml

# 2. Build and run
docker-compose up --build

# 3. Test
curl http://localhost:8003/health
```

### Bare Metal

```bash
# 1. Copy example config
cp examples/config.local.yaml.example config.yaml

# 2. Install dependencies
pip install -r backend-requirements.txt

# 3. Run
python pipeline.py
```

## Architecture

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Audio  │───▶│   STT   │───▶│   LLM   │───▶│   TTS   │
│  Input  │    │ Whisper │    │ (MCP)   │    │  Piper  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
                     │              │              │
                     └──────────────┴──────────────┘
                                   │
                             ┌─────┴─────┐
                             │  FastAPI  │
                             │   :8003   │
                             └───────────┘
```

## File Structure

```
├── config.yaml          # Your configuration
├── pipeline.py         # Main application
├── pipeline-streaming.py # Streaming TTS version
├── examples/           # Example configs
├── docs/               # Documentation
└── models/             # Local models (if used)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/process-audio` | POST | Process audio → audio |
| `/process-audio-stream` | POST | Process audio → streaming audio |

## More Info

- [Configuration](CONFIG.md)
- [API Reference](API.md)
- [Troubleshooting](TROUBLESHOOTING.md)
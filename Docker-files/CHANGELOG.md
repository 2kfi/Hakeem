# Changelog

All notable changes to this project will be documented in this file.

## [Alpha v.3] - 2026-04-03

### Added
- **Config system**: Centralized `config.yaml` for all configuration
- **Environment variable overrides**: All config values can be overridden via env vars
- **GPU auto-detection**: Automatic detection of CUDA/ROCm/CPU via `config.py`
- **Health endpoint**: `GET /health` returns model status
- **Streaming TTS support**: New `/prosess-audio-stream` endpoint in `pipeline-streaming.py`
- **Docker Compose**: Full deployment stack with all environment variables
- **.env.example**: Template file with all configurable variables
- **Documentation**: Comprehensive README.md with usage examples

### Changed
- **pipeline.py**: Refactored to use config system instead of hardcoded values
- **pipeline-streaming.py**: Refactored to use config system + lifespan API
- **downloader.py**: Now reads model URLs/paths from config
- **Dockerfile**: Production-ready with non-root user, health check
- **FastAPI lifespan**: Migrated from deprecated `@app.on_event` to lifespan API

### Fixed
- **Hardcoded values removed**: All model paths, URLs, and settings now configurable
- **MCP server list**: Comma-separated env var now properly converted to list
- **Dependencies**: Added missing `tqdm` to requirements.txt

### Removed
- **Hardcoded IP addresses**: LLM and MCP server URLs now configurable
- **Hardcoded model paths**: All paths now via config.yaml or env vars

---

## Migration from v.2

### Before (Hardcoded)
```python
LLAMA_API_URL = "http://10.200.71.180:2312/v1"
WHISPER_MODEL = "models/whisper-medium"
TTS_MODEL_EN = "models/TTS-CORI-EN/en_GB-cori-high.onnx"
```

### After (Configurable)
```bash
# Via environment variables
export LLM_API_URL=http://your-llm:2312/v1
export STT_MODEL_PATH=models/whisper-small
export TTS_EN_MODEL=models/custom-tts/en.onnx

# Or via config.yaml
```

---

## File Changes

| File | Action |
|------|--------|
| `config.yaml` | Added |
| `config.py` | Added |
| `downloader.py` | Modified |
| `pipeline.py` | Modified |
| `pipeline-streaming.py` | Modified |
| `Dockerfile` | Modified |
| `docker-compose.yml` | Added |
| `.env.example` | Added |
| `README.md` | Added |
| `requirements.txt` | Modified |

---

## Known Issues

- None at this time

---

## Upcoming (v.4)

- [ ] Kubernetes manifests
- [ ] Prometheus metrics endpoint
- [ ] Structured JSON logging option
- [ ] Audio preprocessing configuration
- [ ] Batch processing endpoint

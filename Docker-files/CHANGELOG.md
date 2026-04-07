# Changelog

All notable changes to this project will be documented in this file.

## [Alpha v.4] - 2026-04-06

### Added
- **Preset system**: Simple `preset` config option with 3 presets
  - `default` - whisper-medium, EN+AR voices, int8
  - `lightweight` - whisper-small, EN only (for weak CPU)
  - `heavy` - whisper-large-v3, EN+AR, float16 (for powerful GPU)
- **HuggingFace repo-based config**: Specify models via repo name instead of full URLs
  - `stt.repo` + `stt.model` → auto-resolves to HF download URLs
  - `tts.en.repo` + `tts.en.voice` → auto-resolves to HF download URLs
- **Local model override**: Use `model_path` and `config_path` to override repo-based downloads
- **GPU priority detection**: CUDA → ROCm → CPU (in that order)
- **Environment variable preset override**: `PRESET=lightweight` via env var

### Changed
- **config.yaml**: Simplified to use presets with optional overrides
- **config.py**: Complete rewrite with preset system, HF repo resolution, local override support
- **downloader.py**: Uses new repo-based URL resolution
- **.env.example**: Simplified with commented examples for common overrides
- **pipeline.py**: Updated to use new config methods
- **README.md**: Updated with new preset-based configuration documentation

### Migration from v.3

#### Before (complex config)
```yaml
stt:
  model_path: "models/whisper-medium"
  variant: "medium"
  device: "auto"
  compute_type: "int8"
```

#### After (preset + override)
```yaml
# Option 1: Just use preset (auto-selects medium + EN+AR)
preset: "default"

# Option 2: Override specific settings
preset: "default"
stt:
  model: "small"  # change model size
  device: "cuda"   # force CUDA
```

---

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

## Upcoming (v.5)

- [ ] Kubernetes manifests
- [ ] Prometheus metrics endpoint
- [ ] Structured JSON logging option
- [ ] Audio preprocessing configuration
- [ ] Batch processing endpoint

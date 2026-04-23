# Configuration Reference

## Full Config Structure

```yaml
# Models settings
models:
  storage_path: "/app/models"      # Where models are stored
  download_on_startup: false     # Auto-download from HuggingFace

# App settings
app:
  host: "0.0.0.0"              # Listen address
  port: 8003                    # Listen port
  log_level: "INFO"             # DEBUG/INFO/WARNING/ERROR

# Speech-to-Text (Whisper)
stt:
  model: "Systran/faster-whisper-medium"  # Model name or path
  device: "auto"                # auto/cuda/rocm/cpu
  compute_type: "int8"         # int8/float16/float32
  beam_size: 5                  # Beam size for decoding
  vad_filter: true             # Enable voice activity detection
  vad_threshold: 0.5           # VAD threshold (0-1)
  vad_min_speech_ms: 250        # Min speech duration
  vad_min_silence_ms: 200       # Min silence between speech

# Text-to-Speech (Piper)
tts:
  en:
    repo: "rhasspy/piper-voices"       # HuggingFace repo
    voice: "en_GB/cori/high"         # Voice path in repo
    local_path: "/app/models/EN"     # Optional: use local files instead
  ar:
    repo: "speaches-ai/piper-ar_JO-kareem-medium"
    local_path: null

# TTS audio settings
settings:
  volume: 0.5              # Output volume (0-1)
  length_scale: 1.0        # Speech length modifier
  noise_scale: 1.0           # Noise/warmth modifier
  noise_w_scale: 1.0          # Noise width modifier
  normalize_audio: false      # Normalize output
  nchannels: 1              # Output channels
  sampwidth: 2               # Sample width (bytes)
  framerate: 24000          # Sample rate

# Language Model
llm:
  api_url: "http://localhost:2312/v1"
  api_key: "sk-no-key-required"
  model: "local-model"

# MCP Servers (knowledge base)
mcp:
  servers:
    - "http://localhost:2527/sse"
  max_retries: 2
```

## TTS Language Configuration

Each language under `tts:` supports three formats:

### 1. HuggingFace (default)
```yaml
tts:
  en:
    repo: "rhasspy/piper-voices"
    voice: "en_GB/cori/high"
    local_path: null
```

### 2. Local Override
```yaml
tts:
  en:
    repo: null
    voice: null
    local_path: "/app/models/my-voice"
```

### 3. Hybrid (keep HF reference but use local)
```yaml
tts:
  en:
    repo: "rhasspy/piper-voices"
    voice: "en_GB/cori/high"
    local_path: "/app/models/EN"  # This takes priority if exists
```

## Load Priority

1. Check `local_path` - if exists, use local files
2. Use `repo` + `voice` - download from HuggingFace or use cached

## Adding New Languages

```yaml
tts:
  en:
    repo: "rhasspy/piper-voices"
    voice: "en_GB/cori/high"
  fr:
    repo: "rhasspy/piper-voices"
    voice: "fr_FR/upmc/high"
  de:
    local_path: "/app/models/DE"
```

## Example Files

See `examples/` folder:
- `config.yaml.example` - Full example
- `config.docker.yaml.example` - Docker deployment
- `config.local.yaml.example` - Bare metal
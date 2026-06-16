<!-- Arkan Fakoseh -  @2kfi on github -->

# 🎙️ CLI Client

A wake-word-triggered voice assistant that runs on your Linux desktop. Listens for **"Hakeem"** (or **"يا ستر"**), records your voice, sends it to the backend, and plays back the spoken response — all hands-free.

```
🎤 Wake word detected  →  Record until silence  →  WebSocket to backend
                                                           │
                                                    STT → LLM → TTS
                                                           │
🔊 Play response audio  ←  Audio + text  ←────────────────┘
```

---

## Quick start

```bash
# 1. Install deps (pick ONNX or TFLite)
pip install -r client/requirements-onnx.txt

# 2. Make sure the backend is running (see getting_started.md)
#    curl http://localhost:8080/health  →  "ok"

# 3. List available wake word models
python client/cli.py --list-models

# 4. Start listening
python client/cli.py
```

Say **"Hakeem"** into your mic. The CLI will record your query, send it to the backend, and play back the answer.

---

## Installation

### Prerequisites

- Python 3.11+
- PortAudio (`libportaudio2` for PyAudio)
- A working microphone and speakers

```bash
# Debian / Ubuntu
sudo apt install portaudio19-dev python3-pyaudio

# Fedora
sudo dnf install portaudio-devel
```

### Dependencies

Two requirement files — pick one:

| File | Backend | Notes |
|------|---------|-------|
| `client/requirements-onnx.txt` | ONNX Runtime | Faster on CPU, recommended for Linux |
| `client/requirements-tflite.txt` | TensorFlow Lite | Alternative runtime |

```bash
pip install -r client/requirements-onnx.txt
```

---

## Usage

### Wake word loop (default)

```bash
python client/cli.py
```

The client continuously listens for a wake word. When detected, it records until you stop speaking (~0.8s of silence), sends the audio to the backend, plays the response, and returns to listening. Press **Ctrl+C** to quit.

### One-shot mode

```bash
python client/cli.py --once
```

Records once (with wake word detection), sends to backend, plays response, then exits.

### All options

```
python client/cli.py [OPTIONS]

Options:
  -c, --config PATH       Path to config YAML (default: client/config.yaml)
  -f, --framework {onnx,tflite}  Inference framework
  --backend-host HOST     Backend host (default: localhost)
  --backend-port PORT     Backend port (default: 8080)
  --jwt-secret SECRET     JWT secret for auto-generating tokens
  --jwt-token TOKEN       Pre-generated JWT token (skips signing)
  --threshold FLOAT       Wake word threshold 0.0–1.0 (default: 0.5)
  --language LANG         Language hint: "en" or "ar"
  --list-models           List available wake word models
  --once                  Single capture cycle, then exit
  --debug                 Verbose logging
```

### Examples

```bash
# Connect to a remote backend
python client/cli.py --backend-host 10.0.0.5 --jwt-secret "your-secret"

# Use TFLite runtime with lower sensitivity
python client/cli.py --framework tflite --threshold 0.7

# One-shot with Arabic language hint
python client/cli.py --once --language ar

# Custom config file
python client/cli.py -c my-config.yaml
```

---

## Configuration

Copy `client/config.yaml.example` to `client/config.yaml` and edit:

```yaml
client:
  # ── Backend ─────────────────────────────────────
  backend_host: "localhost"
  backend_port: 8080
  backend_tls: false

  # ── Authentication ──────────────────────────────
  jwt_secret: "CHANGE_ME_JWT_SECRET"

  # ── Wake word models ────────────────────────────
  # Leave empty to auto-discover models/ directory:
  inference_framework: "onnx"

  # ── Recording ──────────────────────────────────
  silence_threshold: 0.01       # lower = more sensitive to silence
  max_record_seconds: 10        # max recording length
  wakeword_threshold: 0.5       # lower = wakes up easier
```

All fields can be overridden via CLI flags.

---

## Wake word models

The client uses **openwakeword** with models stored in `models/`:

| Model | File | Wake word |
|-------|------|-----------|
| `models/Hakeem/Hakeem.onnx` | 206 KB | **"Hakeem"** |
| `models/WW-EYE-STRA/EYE-STRA.onnx` | 206 KB | **"يا ستر"** (Arabic) |

Both `.onnx` and `.tflite` variants are available. Use `--list-models` to see all files.

**Threshold tuning:**

| Threshold | Behavior |
|-----------|----------|
| `0.3` | Very sensitive — may false-trigger on background noise |
| `0.5` | Balanced — recommended starting point |
| `0.7` | Conservative — requires clear, loud wake word |
| `0.9` | Very strict — almost never false-triggers |

---

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Client                              │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ WakeWord │    │ Silence  │    │ WebSocket│    │ Audio    │  │
│  │ Detector │───▶│ Detector │───▶│ Client   │───▶│ Player   │  │
│  │(openwake │    │(energy   │    │(send WAV,│    │(play TTS)│  │
│  │ word)    │    │ threshold)│   │ receive  │    │          │  │
│  └──────────┘    └──────────┘    │ response)│    └──────────┘  │
│                                  └────┬─────┘                  │
│                                       │                        │
└───────────────────────────────────────┼────────────────────────┘
                                        │
                               WebSocket │
                                        │
                         ┌──────────────▼──────────────┐
                         │     Hakeem Backend          │
                         │  STT → LLM → TTS Pipeline   │
                         └─────────────────────────────┘
```

### Message flow

| Step | Message | Direction |
|------|---------|-----------|
| 1 | `{"type": "connect", "capabilities": ["cli-client"]}` | 📱→☁️ |
| 2 | `{"type": "connected", "device_id": "...", "node_id": "..."}` | ☁️→📱 |
| 3 | `{"type": "audio", "audio_data": "<base64 WAV>"}` | 📱→☁️ |
| 4 | `{"type": "accepted", "message": "Processing started"}` | ☁️→📱 |
| 5 | `{"type": "processing", "text": "..."}` | ☁️→📱 |
| 6 | `{"type": "audio_chunk", "audio_data": "<base64 WAV>", "text": "..."}` | ☁️→📱 |
| 7 | *(loop back to step 3 for next query)* | |

Heartbeat messages are exchanged every 30s to keep the connection alive.

---

## File layout

```
client/
├── __init__.py                  # Package marker
├── cli.py                       # Entry point + argument parsing
├── config.py                    # Config loader (YAML + env vars)
├── wakeword.py                  # OpenWakeWord wrapper
├── audio.py                     # Microphone, playback, WAV encode
├── backend.py                   # WebSocket client
├── config.yaml.example          # Example config template
├── requirements-onnx.txt        # ONNX runtime deps
└── requirements-tflite.txt      # TFLite runtime deps
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `OSError: No Default Input Device` | No mic detected | Check `pactl list sources short` |
| `ModuleNotFoundError: openwakeword` | Missing deps | `pip install -r client/requirements-onnx.txt` |
| Wake word never triggers | Threshold too high | Lower `--threshold 0.3` |
| Wake word triggers constantly | Threshold too low | Raise `--threshold 0.7` |
| "Failed to connect" | Backend not running | `curl http://localhost:8080/health` |
| "Invalid token" | Wrong JWT secret | Set `jwt_secret` matching backend's `JWT_SECRET` |
| No audio after response | Speaker not detected | Check `pactl list sinks short` |
| Arabic wake word not working | Wrong model used | Verify `EYE-STRA.onnx` is in model paths |

---

## See also

- [`websocket.md`](websocket.md) — Full WebSocket protocol specification
- [`getting_started.md`](getting_started.md) — How to start the backend
- [`authentication.md`](authentication.md) — JWT token generation
- [`config.md`](config.md) — Backend configuration reference

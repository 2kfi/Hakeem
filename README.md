<!-- Arkan Fakoseh -  @2kfi on github -->

<p align="center">
  <img src="https://img.shields.io/badge/version-3.0.0-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/license-open%20source-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/status-alpha-orange?style=flat-square" alt="Alpha">
</p>

<h1 align="center">🎙️ Hakeem Backend</h1>
<p align="center"><strong>Multi-tenant, distributed voice assistant for Intel Atom clusters.</strong><br>
Android App → STT → LLM → Tool Calls → TTS. All state in Redis. Crash-proof by design.</p>

---

## ✨ What is Hakeem?

Hakeem turns an Android phone into a **voice assistant client** that connects to a cluster of stateless backend nodes. Speak → the phone streams audio → Whisper transcribes → an LLM thinks (with RAG and tools) → Piper speaks back. Every stage writes to a Redis stream checkpoint, so if any node dies mid-request, a sibling picks up exactly where it left off. Zero state in local memory. **Shared-nothing architecture.**

---

## 🏗️ Architecture

```
                          ┌─────────────┐
                          │  Load       │
                          │  Balancer   │  (nginx / haproxy / caddy)
                          └──────┬──────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
    ┌─────▼──────┐        ┌─────▼──────┐        ┌─────▼──────┐
    │  Node 1    │        │  Node 2    │        │  Node 3    │
    │  (FastAPI) │        │  (FastAPI) │        │  (FastAPI) │
    └─────┬──────┘        └─────┬──────┘        └─────┬──────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                        ┌───────▼────────┐
                        │     Redis      │
                        │  ────────────  │
                        │  Sessions      │
                        │  Conversations │
                        │  Tool Bridge   │
                        │  Pub/Sub       │
                        │  Checkpoints   │
                        └────────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
              ┌─────▼────┐ ┌───▼───┐ ┌─────▼────┐
              │  Qdrant  │ │ Neo4j │ │  Models  │
              │ (vector) │ │ (graph)│ │STT/TTS/LLM│
              └──────────┘ └───────┘ └──────────┘
```

### Data flow at a glance

```
📱 Phone ──audio──▶ WS Receive ──▶ [stt_jobs] ──▶ STT (Whisper)
                                                        │
                                            [llm_jobs] ◀─┘
                                                    │
                                              ┌─────┴─────┐
                                              │    LLM     │
                                              │  (Groq /   │
                                              │  OpenAI)   │
                                              └─────┬─────┘
                                          ┌─────────┼─────────┐
                                          │         │         │
                                     RAG Docs  Tool Router  Phone Tools
                                          │         │         │
                                          └─────────┼─────────┘
                                                    │
                                            [tts_jobs] ──▶ TTS (Piper)
                                                              │
                                              [responses] ◀──┘
                                                    │
📱 Phone ◀──audio── WS Sender ◀────────────────────┘
```

> Every arrow is a **Redis stream**. If a worker crashes, another picks up the pending job. No lost data. No duplicate work.

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/2kfi/hakeem-backend
cd hakeem-backend

# 2. Generate secure secrets (JWT secret + DB password)
python scripts/generate_secrets.py --random

# 3. Set your LLM API key (Groq / OpenAI / compatible)
echo 'LLM_API_KEY=gsk_your_real_key' >> .env

# 4. Fire it up
docker compose up -d

# 5. Verify
curl http://localhost:8080/health
```

The `generate_secrets.py` script writes a single `DB_PASSWORD` that's shared across **Redis**, **Neo4j**, and **Qdrant** — and updates `config.yaml`, `.env`, and `docker-compose.infra.yml` automatically. One command, everything consistent.

---

## 🧪 Interactive or Random?

```bash
# 👤 Interactive — prompts with cryptographically secure defaults
python scripts/generate_secrets.py

# 🤖 Random — generates everything, writes files, prints summary
python scripts/generate_secrets.py --random

# 📤 Pipe output wherever you want
python scripts/generate_secrets.py --random --stdout
python scripts/generate_secrets.py --random --format=yaml
```

---

## 🔧 Deployment Options

| Scenario | Command |
|----------|---------|
| **Single node** (default) | `docker compose up -d` |
| **3-node cluster** | `docker compose -f docker-compose.cluster.yml up -d` |
| **Infra only** (Redis + Neo4j + Qdrant) | `docker compose -f docker-compose.infra.yml up -d` |
| **App only** (connect to existing infra) | `docker compose -f docker-compose.app.yml up -d` |
| **Standalone** (your own Redis) | `docker compose -f docker-compose.standalone.yml up -d` |

```bash
# Cluster access
#   Node 1: http://localhost:8081
#   Node 2: http://localhost:8082
#   Node 3: http://localhost:8083
```

---

## 🧠 What makes Hakeem different?

| Feature | How |
|---------|-----|
| **💥 Crash recovery** | Every stage writes to a Redis stream with consumer groups. Dead worker? Another claims the pending job. |
| **🔗 Stateless nodes** | No `local` state. Any node can serve any request. Scale horizontally by adding instances. |
| **📱 Phone = tool server** | The Android app registers capabilities at connect time — GPS, file index, HTTP server, whatever — and the LLM calls them like remote functions. |
| **🏥 Medical RAG** | Domain-isolated multi-hop retrieval with Qdrant (vectors) + Neo4j (knowledge graph) + ONNX reranker + hallucination guard. |
| **🔌 MCP + OpenAPI** | Ingest tools from any MCP server or OpenAPI spec. The LLM discovers and calls them dynamically. |
| **🌐 Bilingual** | English and Arabic TTS out of the box. Language auto-detection on input. |

---

## 🔐 Security model

```
Internet
    │
    ▼
┌────────────┐
│  Firewall  │  Port 443 only
├────────────┤
│  TLS/SSL   │  Reverse proxy terminates HTTPS/WSS
├────────────┤
│  JWT Auth  │  HS256 tokens with device_id, user_id, permissions
├────────────┤
│  Rate Lim  │  60 req/min per IP (configurable)
├────────────┤
│  Perms     │  Per-device tool permissions (default-deny)
└────────────┘
```

- **All secrets are gitignored** — `config.yaml` and `.env` in `.gitignore`. Run `generate_secrets.py` to create them.
- **Behind a reverse proxy** — set `proxy.enabled: true` in `config.yaml` (or `PROXY_ENABLED=true` env var) to enable forwarded-IP headers.
- **JWT or die** — `AUTH_JWT_ONLY=true` (default) rejects anything without a valid token.

---

## 📡 WebSocket API

```
ws://localhost:8080/api/v1/connect?token=<JWT>
```

| Direction | Type | What it does |
|-----------|------|-------------|
| 📱→☁️ | `connect` | Handshake + register device capabilities |
| 📱→☁️ | `audio` | Base64 WAV chunk for transcription |
| 📱→☁️ | `tool_response` | Reply to a remote tool request |
| 📱→☁️ | `heartbeat` | Keepalive every 30s |
| ☁️→📱 | `response` | Final TTS audio + transcribed text |
| ☁️→📱 | `tool_request` | "Run this function on your device" |
| ☁️→📱 | `processing` | "I'm thinking..." interim status |

> Full protocol details in [`docs/websocket.md`](docs/websocket.md)

---

## 📋 REST API

| Method | Path | Auth | What |
|--------|------|------|------|
| `GET` | `/health` | ❌ | Node health + connected devices |
| `GET` | `/ready` | ❌ | Readiness check |
| `GET` | `/live` | ❌ | Liveness check |
| `GET` | `/metrics` | ✅ | Prometheus metrics |
| `POST` | `/api/v1/sessions` | ✅ | Create session |
| `GET` | `/api/v1/sessions` | ✅ | List sessions |
| `GET` | `/api/v1/sessions/{id}` | ✅ | Get session |
| `DELETE` | `/api/v1/sessions/{id}` | ✅ | Delete session |
| `PATCH` | `/api/v1/sessions/{id}/config` | ✅ | Update config |
| `GET` | `/api/v1/conversations/{id}` | ✅ | Conversation history |
| `GET` | `/api/v1/devices` | ✅ | List connected devices |
| `GET` | `/api/v1/devices/{id}` | ✅ | Device info |
| `GET` | `/api/v1/permissions/{id}` | ✅ | Device permissions |
| `PUT` | `/api/v1/permissions/{id}/{tool}` | ✅ | Set tool permission |
| `GET` | `/api/v1/rag/documents` | ✅ | List RAG documents |
| `POST` | `/api/v1/rag/documents/upload` | ✅ | Upload + index doc |
| `DELETE` | `/api/v1/rag/documents/{id}` | ✅ | Remove doc |
| `GET` | `/api/v1/rag/documents/search` | ✅ | Search docs |
| `POST` | `/api/v1/rag/documents/reindex` | ✅ | Re-index source dirs |

---

## 📖 Documentation

The `docs/` directory has 18 markdown files covering every corner of the system:

| Document | What you'll find |
|----------|-----------------|
| [`overview.md`](docs/overview.md) | One-paragraph intro to the whole system |
| [`getting_started.md`](docs/getting_started.md) | Step-by-step deploy guide with nginx/Caddy/HAProxy configs |
| [`architecture.md`](docs/architecture.md) | Deep dive into every component and data flow |
| [`understand.md`](docs/understand.md) | **The big tutorial** — 2800+ lines, 24 sections, diagrams, code traces |
| [`config.md`](docs/config.md) | Every config field, env var, default, and type |
| [`authentication.md`](docs/authentication.md) | JWT, API keys, permissions, security layers |
| [`websocket.md`](docs/websocket.md) | Full protocol spec with all message types |
| [`pipeline.md`](docs/pipeline.md) | STT/LLM/TTS worker internals and crash recovery |
| [`cluster.md`](docs/cluster.md) | Multi-node setup, load balancing, Pub/Sub |
| [`deployment.md`](docs/deployment.md) | Docker Compose files, volumes, troubleshooting |
| [`sessions.md`](docs/sessions.md) | Session/conversation/device state in Redis |
| [`tools.md`](docs/tools.md) | Internal tools, remote tool bridge, permissions |
| [`mcp.md`](docs/mcp.md) | MCP servers, OpenAPI ingestion, tool registry |
| [`redis.md`](docs/redis.md) | All Redis data structures with key patterns |
| [`benchmark.md`](docs/benchmark.md) | Running medical USMLE benchmarks |
| [`faq.md`](docs/faq.md) | 16 common questions with answers |
| [`glossary.md`](docs/glossary.md) | 44 terms defined |

> Start with [`getting_started.md`](docs/getting_started.md) if you want to deploy.
> Read [`understand.md`](docs/understand.md) if you want to understand everything.

---

## 🧩 Environment Variables

### Required
| Variable | What | How to generate |
|----------|------|----------------|
| `JWT_SECRET` | HS256 signing key | `python scripts/generate_secrets.py --random` |
| `LLM_API_KEY` | Groq / OpenAI API key | Get from [groq.com](https://groq.com) |

### Common overrides
| Variable | Default | What |
|----------|---------|------|
| `REDIS_URL` | — | Full Redis URL (`redis://:pass@host:6379/0`) |
| `REDIS_PASSWORD` | `hakeem_pass` | Redis password |
| `NEO4J_PASSWORD` | `changeMe` | Neo4j password |
| `CLUSTER_NODE_ID` | hostname | Unique node name for multi-node |
| `STT_DEVICE` | `auto` | `cpu`, `cuda`, or `auto` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model name |
| `LLM_API_BASE_URL` | `https://api.groq.com/openai/v1` | API endpoint |
| `TTS_DEFAULT_VOICE` | `en` | `en` or `ar` |
| `AUTH_JWT_ONLY` | `true` | `false` to allow legacy API keys |
| `PROXY_ENABLED` | `false` | Enable reverse proxy headers |
| `DEBUG` | `false` | Print admin JWT on startup |

> Full reference: [`docs/config.md`](docs/config.md)

---

## 📁 Model files

```
models/
├── whisper-medium/            # STT model (faster-whisper)
├── TTS-CORI-EN/               # English TTS voice (Piper)
├── TTS-KAREEM-ARABIC/         # Arabic TTS voice (Piper)
└── chroma/onnx/               # RAG embedding model (all-MiniLM-L6-v2)
```

```bash
# One-shot download:
python scripts/downloader.py

# Or let Docker do it:
MODEL_DOWNLOAD=true docker compose up -d
```

---

## 🧪 Testing without a phone

### CLI client (wake word + voice)

```bash
# Install deps (pick ONNX or TFLite):
pip install -r client/requirements-onnx.txt

# Learn what models are available:
python client/cli.py --list-models

# Start listening for "Hakeem" or "يا ستر":
python client/cli.py
```

The CLI client:
1. Listens for a wake word using openwakeword (models in `models/Hakeem/` and `models/WW-EYE-STRA/`)
2. Records audio until silence
3. Sends it to the backend via WebSocket
4. Plays back the TTS response through your speakers

Configure via `client/config.yaml.example` → `client/config.yaml`, or CLI flags: `--framework tflite`, `--backend-host 10.0.0.5`, `--threshold 0.3`.

### Raw WebSocket (wscat)

```bash
npm install -g wscat
python scripts/generate_secrets.py --random

python -c "
from core.jwt_auth import get_jwt_manager
print(get_jwt_manager().create_token('admin', 'test-phone', ['admin']))
"

wscat -c "ws://localhost:8080/api/v1/connect?token=<JWT>"

{"type": "connect", "capabilities": ["test"]}
{"type": "audio", "audio_data": "<base64 WAV>"}
```

---

## 📄 License

Open source. Built by [Arkan Fakoseh (@2kfi)](https://github.com/2kfi).

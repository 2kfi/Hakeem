<!-- Arkan Fakoseh -  @2kfi on github -->
# Deployment

## Prerequisites

- Docker and Docker Compose
- At least 4GB RAM per node (for Whisper + Piper models)
- Redis 7+ (provided by Docker)

## First-time setup

```bash
# Generate secure secrets (JWT + DB password for Redis/Neo4j/Qdrant):
python scripts/generate_secrets.py --random

# Set your LLM API key:
echo 'LLM_API_KEY="gsk_your_key"' >> .env
```

> This writes `.env` and `config.yaml` with cryptographically random secrets. Both are gitignored.

## Docker Compose Files

| File | What It Starts | Best For |
|------|---------------|----------|
| `docker-compose.yml` | Redis + Qdrant + Neo4j + Hakeem app | Single-node with all services |
| `docker-compose.infra.yml` | Redis + Qdrant + Neo4j only | Shared infra for multi-node |
| `docker-compose.app.yml` | Hakeem app only (connects to infra) | Scalable app behind infra |
| `docker-compose.cluster.yml` | Redis + Qdrant + Neo4j + 3 app nodes | 3-node cluster on 1 machine |
| `docker-compose.standalone.yml` | Hakeem app only (you bring Redis) | External Redis setups |

## Quick Start (Single Node, All Services)

```bash
docker compose up -d
```

This starts Redis + Qdrant + Neo4j + the app. Available at `http://localhost:8080`.

If using MedRAG, set `NEO4J_PASSWORD`:
```bash
NEO4J_PASSWORD=my-secret docker compose up -d
```

## Infra + App (Two-File Decomposition)

For multi-node deployments or when you want infra on dedicated hardware:

### Step 1 — Start infrastructure

```bash
docker compose -f docker-compose.infra.yml up -d
```

Starts:
- `redis` — Redis 7 on `:6379`
- `qdrant` — Qdrant vector DB on `:6333` (gRPC) and `:6334` (HTTP)
- `neo4j` — Neo4j graph DB on `:7474` (browser) and `:7687` (bolt)

### Step 2 — Start apps (can scale)

```bash
docker compose -f docker-compose.app.yml up -d
docker compose -f docker-compose.app.yml up -d --scale hakeem=3
```

Each app node shares the same infra services. Available on the host's network.

### Combined on one machine

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d
```

## Cluster (3 Nodes)

```bash
docker compose -f docker-compose.cluster.yml up -d
```

Starts:
- `redis` — Redis 7 on `:6379`
- `qdrant` — Qdrant vector DB on `:6333`
- `neo4j` — Neo4j graph DB on `:7474` / `:7687`
- `hakeem-node-1` — app on `:8081`
- `hakeem-node-2` — app on `:8082`
- `hakeem-node-3` — app on `:8083`

Put a load balancer (nginx/haproxy) in front of `:8081-:8083`.

## Standalone (External Redis)

```bash
docker compose -f docker-compose.standalone.yml up -d
```

Set `REDIS_URL` to your Redis:
```bash
REDIS_URL="redis://:password@my-redis:6379" docker compose -f docker-compose.standalone.yml up -d
```

For MedRAG, also provide Qdrant and Neo4j hosts:
```bash
MEDRAG_ENABLED=true \
  MEDRAG_QDRANT_HOST="10.1.1.50" \
  MEDRAG_NEO4J_URI="bolt://10.1.1.51:7687" \
  NEO4J_PASSWORD="my-secret" \
  docker compose -f docker-compose.standalone.yml up -d
```

## MedRAG Infrastructure

MedRAG needs Qdrant (vector DB) and Neo4j (knowledge graph) running.

### Qdrant

Ports: `6333` (gRPC), `6334` (HTTP API)
Data: persisted to `qdrant-data` volume at `/qdrant/storage`

### Neo4j

Ports: `7474` (browser UI), `7687` (bolt protocol)
Data: persisted to `neo4j-data` volume at `/data`
Auth: `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-changeMe}`

Access the Neo4j browser at `http://localhost:7474` (username: `neo4j`).

### Monitoring Qdrant

```bash
# REST API health check
curl http://localhost:6333/healthz

# List collections
curl http://localhost:6333/collections

# Collection info
curl http://localhost:6333/collections/hakeem_hepatology
```

### Monitoring Neo4j

```bash
# Cypher shell in container
docker exec -it hakeem-neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD

# Count entities
MATCH (n) RETURN labels(n), count(*) ORDER BY count(*) DESC
```

## Required Environment Variables

### For basic operation (no MedRAG)

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | **YES** | Long random string (`openssl rand -hex 32`) |
| `LLM_API_KEY` | **YES** | Groq API key (or your LLM provider's key) |

### For MedRAG (additional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEO4J_PASSWORD` | **YES when MedRAG enabled** | `changeMe` | Neo4j admin password |
| `MEDRAG_ENABLED` | No | `false` | Set to `true` to activate |
| `MEDRAG_QDRANT_HOST` | No | `qdrant` (container) / `localhost` | Qdrant server host |
| `MEDRAG_QDRANT_PORT` | No | `6333` | Qdrant gRPC port |
| `MEDRAG_NEO4J_URI` | No | `bolt://neo4j:7687` | Neo4j bolt URI |
| `MEDRAG_LLM_API_BASE` | No | varies by compose file | LLM for decomposition + CRAG |
| `MEDRAG_LLM_API_KEY` | No | same as `LLM_API_KEY` | LLM API key for RAG |
| `MEDRAG_LLM_MODEL` | No | varies by compose file | Model name for RAG |

### Full Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8080` | HTTP port |
| `API_DEBUG` | `false` | Enable debug mode |
| `API_CORS_ORIGINS` | `*` | CORS origins (comma-separated) |
| `API_RATE_LIMIT` | `60/minute` | Global rate limit |
| `REDIS_URL` | `redis://:password@redis:6379/0` | Redis connection string |
| `REDIS_TLS` | `false` | Enable TLS for Redis |
| `REDIS_POOL_SIZE` | `20` | Connection pool size |
| `REDIS_PASSWORD` | `hakeem_pass` | Redis password (for compose-managed Redis) |
| `JWT_SECRET` | `change-me-in-production` | JWT signing key |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRY_MINUTES` | `1440` | Token lifetime |
| `CLUSTER_NODE_ID` | hostname | Unique node identifier |
| `CLUSTER_NODE_ROLE` | `worker` | Node role |
| `AUTH_JWT_ONLY` | `true` | Disable API key fallback |
| `SESSION_TTL` | `86400` | Session TTL in seconds |
| `SESSION_MAX_HISTORY` | `100` | Max conversation messages |
| `SESSION_HEARTBEAT_INTERVAL` | `30` | Heartbeat interval in seconds |
| `TOOL_REMOTE_TIMEOUT` | `30.0` | Remote tool timeout |
| `TOOL_INTERNAL_TIMEOUT` | `10.0` | Internal tool timeout |
| `TOOL_MAX_RETRIES` | `2` | Max tool retries |
| `STT_MODEL_NAME` | `medium` | Whisper model size |
| `STT_MODEL_DIR` | `./models` | Model storage path |
| `STT_DEVICE` | `auto` | Compute device (`cpu`/`cuda`/`auto`) |
| `STT_COMPUTE_TYPE` | `int8` | Compute precision |
| `TTS_MODEL_DIR` | `./models` | TTS model path |
| `TTS_DEFAULT_VOICE` | `en` | Default TTS voice |
| `TTS_VOLUME` | `0.75` | TTS output volume |
| `TTS_LENGTH_SCALE` | `1.0` | Speech speed |
| `TTS_NOISE_SCALE` | `0.75` | Voice variance |
| `TTS_NOISE_W_SCALE` | `0.5` | Voice variance (width) |
| `LLM_API_BASE_URL` | `https://api.groq.com/openai/v1` | LLM API endpoint |
| `LLM_API_KEY` | `gsk_...` | LLM API key |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | LLM model name |
| `LLM_TIMEOUT` | `60.0` | LLM request timeout |
| `MEDRAG_ENABLED` | `false` | Enable medical RAG pipeline |
| `MEDRAG_QDRANT_HOST` | `localhost` | Qdrant vector DB host |
| `MEDRAG_QDRANT_PORT` | `6333` | Qdrant gRPC port |
| `MEDRAG_NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `MEDRAG_NEO4J_USER` | `neo4j` | Neo4j username |
| `MEDRAG_NEO4J_PASSWORD` | `` | Neo4j password |
| `MEDRAG_LLM_API_BASE` | `http://10.1.1.180:2312/v1` | LLM API for decomposition + CRAG |
| `MEDRAG_LLM_API_KEY` | `` | LLM API key for RAG |
| `MEDRAG_LLM_MODEL` | `unsloth/gemma-4-E2B` | LLM model for RAG |
| `MEDRAG_ROUTER_MODEL_PATH` | `./models/medical_router` | MedBERT ONNX domain classifier |
| `MEDRAG_RERANKER_MODEL_PATH` | `./models/bge_reranker` | bge-reranker-v2-m3 ONNX |
| `NEO4J_PASSWORD` | `changeMe` | Neo4j admin password (shared across compose files) |

## Model Files

Models are loaded from `./models/` (mounted as a volume in all compose files).

### Download Behavior

All models download on startup when `MODEL_DOWNLOAD=true` (or `models.download_on_startup: true` in config.yaml):

| Model | Directory | Type |
|-------|-----------|------|
| Whisper | `./models/whisper-medium/` | STT |
| Piper (English) | `./models/TTS-CORI-EN/` | TTS |
| Piper (Arabic) | `./models/TTS-KAREEM-ARABIC/` | TTS |
| Embedding (all-MiniLM-L6-v2) | `./models/chroma/onnx/` | RAG embeddings |
| MedBERT Router | `./models/medical_router/` | MedRAG domain routing |
| bge-reranker-v2-m3 | `./models/bge_reranker/` | MedRAG cross-encoder |

### Manual Download

```bash
python scripts/downloader.py
```

## Persisted Data

| Volume | Container Path | Content | Compose Files |
|--------|---------------|---------|---------------|
| `redis-data` | `/data` | Redis RDB snapshots | All |
| `qdrant-data` | `/qdrant/storage` | Qdrant vector indexes | infra, cluster, main |
| `qdrant-snapshots` | `/qdrant/snapshots` | Qdrant snapshots | infra |
| `neo4j-data` | `/data` | Neo4j graph database | infra, cluster, main |
| `neo4j-logs` | `/logs` | Neo4j debug logs | infra |

Host mounts:
- `./models:/app/models` — model files (shared across nodes)
- `./data:/app/data` — app data (uploads, config)
- `./docs:/app/docs` — document sources for indexing (app.yml only)

## Testing

### Health Check

```bash
curl http://localhost:8080/health
# → {"status":"healthy","redis":"ok","models":"ok","uptime_seconds":123}
```

### WebSocket

```bash
# Get an admin JWT from the server (set DEBUG=true in docker-compose.yml):
docker compose run -e DEBUG=true -e JWT_SECRET=$JWT_SECRET hakeem
# → [hakeem] Admin JWT: eyJhbGciOi...

# Connect
wscat -c "ws://localhost:8080/api/v1/connect?token=<ADMIN_JWT>"
```

### MedRAG Search

```bash
# Search indexed documents
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/rag/documents/search?q=What+treats+cirrhosis%3F"

# List documents in a domain
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/rag/documents?domain=hepatology"

# Upload a document
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@guidelines.md" \
  "http://localhost:8080/api/v1/rag/documents/upload?domain=hepatology"

# Reindex source directories
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/rag/documents/reindex"
```

### Send Audio

```python
import base64, json, asyncio, websockets

async def test():
    async with websockets.connect(f"ws://localhost:8080/api/v1/connect?token={TOKEN}") as ws:
        await ws.send(json.dumps({"type": "connect", "capabilities": ["gps"]}))
        
        with open("test.wav", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        
        await ws.send(json.dumps({
            "type": "audio", "data": b64,
            "mime_type": "audio/wav",
            "chunk_index": 0, "total_chunks": 1
        }))
        
        async for msg in ws:
            print(msg)

asyncio.run(test())
```

## Troubleshooting

### Neo4j won't start

Check password complexity — Neo4j 5 requires a non-trivial password:
```
NEO4J_PASSWORD=my-secret docker compose up -d
```

### Qdrant connection refused

Ensure Qdrant is running and reachable. The app connects on port `6333` (gRPC):
```bash
curl http://localhost:6333/healthz
```

### MedRAG engine fails to initialize

Check logs for Neo4j/Qdrant connectivity:
```bash
docker logs hakeem-node-1 | grep -i "rag\|neo4j\|qdrant"
```

## Verified Config

Reference `config.yaml` contains every section with defaults. See the `config/` directory or `understand.md` Section 22 Q16 for the complete annotated config.

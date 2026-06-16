<!-- Arkan Fakoseh -  @2kfi on github -->
# Configuration Reference

Settings are loaded from `config.yaml`. Every value can be overridden via environment variables.

> 🔐 **Quick setup:** Run `python scripts/generate_secrets.py --random` to generate a secure `config.yaml` and `.env` with cryptographically random secrets (JWT key, DB password for Redis/Neo4j/Qdrant).

**Priority (highest to lowest):** CLI args > env vars > `config.yaml` > code defaults

**Env var naming:**
- Flat keys: `API_HOST`, `API_PORT`, `DEBUG`
- Nested keys use prefixes: `RAG_ENABLED`, `LLM_API_KEY`, `STT_MODEL_NAME`, `JWT_SECRET`
- The env prefix for each section is listed in the tables below

---

## `api` — Server settings (prefix: `API_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `host` | `API_HOST` | string | `"0.0.0.0"` | Bind address (`0.0.0.0` = all interfaces) |
| `port` | `API_PORT` | int | `8080` | HTTP port |
| `debug` | `API_DEBUG` | bool | `false` | Enable debug logging + hot reload |
| `cors_origins` | — | list | `["*"]` | Allowed CORS origins; set to your frontend URL in production |
| `rate_limit` | `API_RATE_LIMIT` | string | `"60/minute"` | Max requests per minute per IP |
| `max_audio_size_mb` | `API_MAX_AUDIO_SIZE_MB` | int | `10` | Reject audio uploads larger than this (MB) |
| `allowed_audio_types` | — | list | `["audio/wav", "audio/mpeg", "audio/ogg"]` | Accepted Content-Type values for audio |

---

## `proxy` — Reverse proxy support (prefix: `PROXY_`)

Enable when running behind nginx, haproxy, caddy, or similar.

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `enabled` | `PROXY_ENABLED` | bool | `false` | Enable proxy mode (forwarded-IP headers) |
| `trusted_proxies` | `PROXY_TRUSTED_PROXIES` | list | `["127.0.0.1"]` | IPs trusted to send `X-Forwarded-For` |
| `forwarded_allow_ips` | `PROXY_FORWARDED_ALLOW_IPS` | list | `["127.0.0.1"]` | Passed to uvicorn `--forwarded-allow-ips` |
| `num_proxies` | `PROXY_NUM_PROXIES` | int | `1` | Number of proxy layers |

When `enabled: true`, uvicorn runs with `proxy-headers` and `forwarded-allow-ips`, so rate limiting and logging see real client IPs instead of the proxy's IP.

---

## `redis` — Shared state, pub/sub, job queues (prefix: `REDIS_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `url` | `REDIS_URL` | string | — | Redis URL (`redis://:password@host:6379/0`). Overrides host/port/password |
| `host` | `REDIS_HOST` | string | `"localhost"` | Redis host (used if url is not set) |
| `port` | `REDIS_PORT` | int | `6379` | Redis port |
| `password` | `REDIS_PASSWORD` | string | `""` | Redis password |
| `tls` | `REDIS_TLS` | bool | `false` | Enable TLS for Redis connection |
| `pool_size` | `REDIS_POOL_SIZE` | int | `20` | Connection pool size (increase for multi-node) |
| `socket_keepalive` | `REDIS_SOCKET_KEEPALIVE` | bool | `true` | TCP keepalive on Redis socket |
| `socket_connect_timeout` | `REDIS_SOCKET_CONNECT_TIMEOUT` | int | `5` | Connection timeout (seconds) |
| `health_check_interval` | `REDIS_HEALTH_CHECK_INTERVAL` | int | `30` | Health check interval (seconds) |

---

## `jwt` — Authentication tokens (prefix: `JWT_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `secret` | `JWT_SECRET` | string | `""` | Signing key. Generate with `openssl rand -hex 32` |
| `algorithm` | `JWT_ALGORITHM` | string | `"HS256"` | Signing algorithm |
| `expiry_minutes` | `JWT_EXPIRY_MINUTES` | int | `1440` | Token TTL (1440 = 24 hours) |

---

## `cluster` — Node identity (prefix: `CLUSTER_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `node_id` | `CLUSTER_NODE_ID` | string | hostname | Unique per node |
| `node_role` | `CLUSTER_NODE_ROLE` | string | `"worker"` | Reserved for future role-based scheduling |
| `pubsub_channel` | `CLUSTER_PUBSUB_CHANNEL` | string | `"hakeem:events"` | Redis pub/sub channel for cluster-wide events |

---

## `auth` — Access control (prefix: `AUTH_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `jwt_only` | `AUTH_JWT_ONLY` | bool | `true` | `true` = reject requests without valid JWT |
| `api_keys` | — | dict | `{}` | Fallback API keys when `jwt_only: false`. Format: `key: {name, rate_limit}` |

---

## `session` — Conversation history (prefix: `SESSION_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `ttl_seconds` | `SESSION_TTL_SECONDS` | int | `86400` | Session data TTL in Redis (86400 = 24h) |
| `max_history` | `SESSION_MAX_HISTORY` | int | `100` | Max messages kept per conversation |
| `heartbeat_interval` | `SESSION_HEARTBEAT_INTERVAL` | int | `30` | Seconds between client heartbeats |
| `summarize_after` | `SESSION_SUMMARIZE_AFTER` | int | `10` | Auto-summarize after N user messages (`0` = disabled) |
| `summarize_keep_last` | `SESSION_SUMMARIZE_KEEP_LAST` | int | `5` | Keep last N user messages after summarization |

---

## `tool` — Tool call settings (prefix: `TOOL_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `remote_timeout` | `TOOL_REMOTE_TIMEOUT` | float | `30.0` | Seconds to wait for a phone-side tool response |
| `internal_timeout` | `TOOL_INTERNAL_TIMEOUT` | float | `10.0` | Seconds to wait for an internal tool |
| `max_retries` | `TOOL_MAX_RETRIES` | int | `2` | Max retries for tool calls |

---

## `stt` — Speech-to-Text / Whisper (prefix: `STT_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `model_name` | `STT_MODEL_NAME` | string | `"medium"` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `model_dir` | `STT_MODEL_DIR` | string | `"./models"` | Where Whisper model weights are stored |
| `hf_repo` | `STT_HF_REPO` | string | `"Systran/faster-whisper-medium"` | HuggingFace repo for auto-download |
| `device` | `STT_DEVICE` | string | `"auto"` | `"auto"`, `"cpu"`, `"cuda"`, or `"mps"` |
| `compute_type` | `STT_COMPUTE_TYPE` | string | `"int8"` | Precision: `int8_float16`, `int8`, `float16`, `float32` |
| `beam_size` | `STT_BEAM_SIZE` | int | `5` | Beam search width (higher = better but slower) |
| `vad_filter` | `STT_VAD_FILTER` | bool | `true` | Skip silent segments before transcription |
| `language` | `STT_LANGUAGE` | string | — | Force a language (`"en"`, `"ar"`) or leave empty for auto-detect |

---

## `tts` — Text-to-Speech / Piper (prefix: `TTS_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `model_dir` | `TTS_MODEL_DIR` | string | `"./models"` | Root dir containing voice subdirectories with `.onnx` + `.json` |
| `voices` | — | dict | `{en, ar}` | Voice profiles per language code |
| `voices.*.local_path` | — | string | — | Subdirectory under `model_dir` |
| `voices.*.hf_repo` | — | string | — | HuggingFace repo for auto-download |
| `voices.*.voice` | — | string | — | Piper voice name |
| `voices.*.use_cuda` | — | bool | `false` | Load voice on GPU (requires `piper-tts` with CUDA) |
| `default_voice` | `TTS_DEFAULT_VOICE` | string | `"en"` | Fallback language if none specified |
| `max_length` | `TTS_MAX_LENGTH` | int | `500` | Max text chars per TTS call (longer is truncated) |

### `synthesis` sub-section (prefix: `TTS_SYNTH_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `volume` | `TTS_SYNTH_VOLUME` | float | `0.75` | Volume (0.0–1.0) |
| `length_scale` | `TTS_SYNTH_LENGTH_SCALE` | float | `1.0` | Speed: lower = faster |
| `noise_scale` | `TTS_SYNTH_NOISE_SCALE` | float | `0.75` | Emotional range: higher = more expressive |
| `noise_w_scale` | `TTS_SYNTH_NOISE_W_SCALE` | float | `0.5` | Variation |
| `normalize_audio` | `TTS_SYNTH_NORMALIZE_AUDIO` | bool | `true` | Normalize output volume |
| `nchannels` | `TTS_SYNTH_NCHANNELS` | int | `1` | `1` = mono |
| `sampwidth` | `TTS_SYNTH_SAMPWIDTH` | int | `2` | Bytes per sample: `2` = 16-bit PCM |
| `framerate` | `TTS_SYNTH_FRAMERATE` | int | `22050` | Sample rate |

---

## `llm` — Large Language Model (prefix: `LLM_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `api_base_url` | `LLM_API_BASE_URL` | string | `"https://api.groq.com/openai/v1"` | OpenAI-compatible API endpoint |
| `api_key` | `LLM_API_KEY` | string | `""` | API key |
| `model` | `LLM_MODEL` | string | `"llama-3.3-70b-versatile"` | Model name |
| `timeout` | `LLM_TIMEOUT` | float | `60.0` | Request timeout (seconds) |
| `max_retries` | `LLM_MAX_RETRIES` | int | `2` | Retries on transient API errors |
| `system_prompt` | — | string | `""` | System prompt sent before every query. Use YAML `\|` for multiline |

---

## `mcp` — External tool servers (prefix: `MCP_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `servers` | — | list | `[]` | List of MCP server URLs or config dicts |
| `sse_read_timeout` | `MCP_SSE_READ_TIMEOUT` | float | `300.0` | SSE stream read timeout |
| `tool_timeout` | `MCP_TOOL_TIMEOUT` | float | `30.0` | Per-tool execution timeout |
| `max_retries` | `MCP_MAX_RETRIES` | int | `2` | Retries on tool failure |
| `max_tool_loops` | `MCP_MAX_TOOL_LOOPS` | int | `5` | Max LLM tool-call iterations before forcing a final answer |

---

## `rag` — Retrieval-Augmented Generation (prefix: `RAG_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `enabled` | `RAG_ENABLED` | bool | `false` | Master switch |
| `chunk_size` | `RAG_CHUNK_SIZE` | int | `512` | Characters per document chunk |
| `chunk_overlap` | `RAG_CHUNK_OVERLAP` | int | `64` | Overlap between chunks |
| `embedding_model` | `RAG_EMBEDDING_MODEL` | string | `"all-MiniLM-L6-v2"` | ONNX embedding model name |
| `model_dir` | `RAG_MODEL_DIR` | string | `"./models/chroma"` | Dir containing `onnx/` subdirectory |
| `vector_store_path` | `RAG_VECTOR_STORE_PATH` | string | `"./data/vector_store"` | ChromaDB persistence path |
| `top_k` | `RAG_TOP_K` | int | `3` | Top-K chunks to retrieve per query |
| `min_score` | `RAG_MIN_SCORE` | float | `0.4` | Minimum cosine similarity (0.0–1.0) |
| `auto_index_on_start` | `RAG_AUTO_INDEX_ON_START` | bool | `true` | Run file change detection on startup |
| `source_directories` | — | list | `[]` | Directories to scan for documents |
| `download_url` | `RAG_DOWNLOAD_URL` | string | `""` | Custom S3 download URL (empty = use `embedding_model` name) |
| `hf_repo` | `RAG_HF_REPO` | string | `""` | HuggingFace repo for ONNX model download |
| `hf_filename` | `RAG_HF_FILENAME` | string | `"onnx.tar.gz"` | Filename in HF repo or S3 URL |
| `device` | `RAG_DEVICE` | string | `"auto"` | ONNX runtime device: `"auto"`, `"cpu"`, or `"cuda"` |
| `indexing_batch_size` | `RAG_INDEXING_BATCH_SIZE` | int | `32` | Chunks per ONNX inference call (lower = less RAM) |
| `indexing_delay_ms` | `RAG_INDEXING_DELAY_MS` | int | `100` | Pause between indexing each file (lower = faster, higher = kinder to CPU) |
| `evaluate_hallucinations` | `RAG_EVALUATE_HALLUCINATIONS` | bool | `false` | B→C guard: retry once then abstain on unfaithful responses |
| `evaluation_max_retries` | `RAG_EVALUATION_MAX_RETRIES` | int | `1` | Max re-query attempts before abstaining (0 = only abstain) |

### Device settings explained

| Value | Behavior |
|-------|----------|
| `"auto"` | Use whatever ONNX Runtime finds (CUDA if available, otherwise CPU) |
| `"cpu"` | Force CPU only — strips CUDA/TensorRT providers. Saves VRAM |
| `"cuda"` | Prefer CUDA — puts `CUDAExecutionProvider` first. ONNX falls back to CPU if GPU fails |

---

## `medrag` — Medical RAG Pipeline (prefix: `MEDRAG_`)

The new Hakeem MedRAG pipeline replaces the old ChromaDB-based RAG for medical domains. It adds domain isolation, parent-document retrieval, Neo4j Knowledge Graph, multi-hop query decomposition, hybrid dense+sparse search, cross-encoder reranking, and corrective RAG.

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `enabled` | `MEDRAG_ENABLED` | bool | `false` | Master switch |
| `qdrant_host` | `MEDRAG_QDRANT_HOST` | string | `"localhost"` | Qdrant vector DB host |
| `qdrant_port` | `MEDRAG_QDRANT_PORT` | int | `6333` | Qdrant gRPC port |
| `qdrant_api_key` | `MEDRAG_QDRANT_API_KEY` | string | `""` | Qdrant API key |
| `collection_name_prefix` | `MEDRAG_COLLECTION_NAME_PREFIX` | string | `"hakeem"` | Prefix for Qdrant collections |
| `vector_size` | `MEDRAG_VECTOR_SIZE` | int | `384` | Embedding dimension |
| `domains` | — | list | `["hepatology", "nephrology", "neurology"]` | Isolated medical domains |
| `domain_source_dirs` | — | dict | `{}` | `{domain: /path/to/source}` mapping |
| `router_model_path` | `MEDRAG_ROUTER_MODEL_PATH` | string | `"./models/medical_router"` | MedBERT ONNX domain classifier path |
| `router_threshold` | `MEDRAG_ROUTER_THRESHOLD` | float | `0.6` | Confidence threshold for routing |
| `child_chunk_size` | `MEDRAG_CHILD_CHUNK_SIZE` | int | `128` | Word tokens per child chunk |
| `child_chunk_overlap` | `MEDRAG_CHILD_CHUNK_OVERLAP` | int | `16` | Overlap between child chunks |
| `parent_chunk_size` | `MEDRAG_PARENT_CHUNK_SIZE` | int | `1024` | Word tokens per parent chunk |
| `parent_chunk_overlap` | `MEDRAG_PARENT_CHUNK_OVERLAP` | int | `64` | Overlap between parent chunks |
| `hybrid_top_k` | `MEDRAG_HYBRID_TOP_K` | int | `30` | Raw results before reranking |
| `reranker_top_k` | `MEDRAG_RERANKER_TOP_K` | int | `5` | Results after cross-encoder reranking |
| `rrf_k` | `MEDRAG_RRF_K` | int | `60` | RRF fusion constant |
| `reranker_model_path` | `MEDRAG_RERANKER_MODEL_PATH` | string | `"./models/bge_reranker"` | bge-reranker-v2-m3 ONNX path |
| `reranker_device` | `MEDRAG_RERANKER_DEVICE` | string | `"auto"` | Reranker compute device |
| `decomposer_enabled` | `MEDRAG_DECOMPOSER_ENABLED` | bool | `true` | Enable multi-hop query decomposition |
| `decomposer_num_queries` | `MEDRAG_DECOMPOSER_NUM_QUERIES` | int | `3` | Number of sub-queries to generate |
| `neo4j_uri` | `MEDRAG_NEO4J_URI` | string | `"bolt://localhost:7687"` | Neo4j connection URI |
| `neo4j_user` | `MEDRAG_NEO4J_USER` | string | `"neo4j"` | Neo4j username |
| `neo4j_password` | `MEDRAG_NEO4J_PASSWORD` | string | `""` | Neo4j password |
| `graph_traversal_depth` | `MEDRAG_GRAPH_TRAVERSAL_DEPTH` | int | `2` | BFS depth for KG traversal |
| `crag_enabled` | `MEDRAG_CRAG_ENABLED` | bool | `true` | Enable corrective RAG verification |
| `llm_api_base` | `MEDRAG_LLM_API_BASE` | string | `"http://10.1.1.180:2312/v1"` | LLM API for decomposition + CRAG |
| `llm_api_key` | `MEDRAG_LLM_API_KEY` | string | `""` | LLM API key |
| `llm_model` | `MEDRAG_LLM_MODEL` | string | `"unsloth/gemma-4-E2B"` | LLM model for decomposition + CRAG |
| `model_dir` | `MEDRAG_MODEL_DIR` | string | `"./models/chroma"` | Embedding ONNX model directory |
| `device` | `MEDRAG_DEVICE` | string | `"auto"` | Embedding compute device |
| `indexing_batch_size` | `MEDRAG_INDEXING_BATCH_SIZE` | int | `16` | Chunks per ONNX call during indexing |
| `indexing_delay_ms` | `MEDRAG_INDEXING_DELAY_MS` | int | `100` | Pause between file indexes |

### Architecture

```
User Query → Semantic Router (MedBERT) → Domain(s) + Entities
                                                 │
                    ┌────────────────────────────┤
                    ▼                            ▼
          Query Decomposer              Knowledge Graph (Neo4j)
          (MedGemma, 3 sub-queries)      BFS traversal, entity paths
                    │                            │
                    ▼                            │
          Hybrid Retriever (Qdrant)              │
          dense + BM25 per sub-query             │
          RRF fusion                             │
                    │                            │
                    ▼                            │
          Parent Resolver                        │
          child→parent chunk mapping             │
                    │                            │
                    ▼                            │
          Cross-Encoder Reranker                 │
          (bge-reranker-v2-m3 ONNX)              │
                    │                            │
                    ▼                            ▼
          Corrective RAG (CRAG) ←─── GraphRAG Paths
          LLM verifies sufficiency
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    Sufficient            Insufficient
         │                     │
         ▼                     ▼
    CitationFormatter      Abstention Message
    [Doc_ID:filename]      "Insufficient clinical
    + GraphRAG paths       data in internal DB"
```

### Required Services

- **Qdrant** — vector database (run as shared server, not embedded)
- **Neo4j** — knowledge graph (hard fail if unavailable)

Start with:
```bash
docker compose -f docker-compose.infra.yml up -d qdrant neo4j
```

Or as part of the full stack:
```bash
docker compose up -d
```

### Pipeline Flow

```
1. Semantic Router classifies query into domain(s), extracts entities
2. Query Decomposer splits complex queries into 3 sub-questions (via MedGemma)
3. Hybrid Retriever searches Qdrant per domain × sub-query (dense + BM25), RRF fusion
4. Parent Resolver maps child chunks → parent chunks (word-overlap matching)
5. Cross-Encoder Reranker re-scores top-30, keeps top-5
6. Knowledge Graph traverses entity relationships (BFS)
7. Corrective RAG verifies context sufficiency via LLM
8. Citation Formatter enforces [Doc_ID:filename] citations
   → Abstains if insufficient: "Insufficient clinical data in internal database"
```

---

## `models` — Auto-downloader (no env prefix)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `storage_path` | — | string | `"./models"` | Root directory for downloaded model files |
| `download_on_startup` | — | bool | `true` | Download missing models at startup |

---

## `pipeline` — Worker queues and concurrency (prefix: `PIPELINE_`)

| Field | Env Var | Type | Default | Description |
|-------|---------|------|---------|-------------|
| `stt_stream` | `PIPELINE_STT_STREAM` | string | `"stt_jobs"` | Redis stream name for STT jobs |
| `llm_stream` | `PIPELINE_LLM_STREAM` | string | `"llm_jobs"` | Redis stream name for LLM jobs |
| `tts_stream` | `PIPELINE_TTS_STREAM` | string | `"tts_jobs"` | Redis stream name for TTS jobs |
| `response_stream` | `PIPELINE_RESPONSE_STREAM` | string | `"responses"` | Redis stream name for final responses |
| `consumer_group` | `PIPELINE_CONSUMER_GROUP` | string | `"hakeem_workers"` | Redis consumer group (shared across all nodes in a cluster) |
| `consumer_prefix` | `PIPELINE_CONSUMER_PREFIX` | string | `"worker"` | Prefix for individual consumer IDs |
| `stt_max_retries` | `PIPELINE_STT_MAX_RETRIES` | int | `3` | Max delivery attempts for STT jobs |
| `llm_max_retries` | `PIPELINE_LLM_MAX_RETRIES` | int | `2` | Max delivery attempts for LLM jobs |
| `tts_max_retries` | `PIPELINE_TTS_MAX_RETRIES` | int | `3` | Max delivery attempts for TTS jobs |
| `poll_timeout_ms` | `PIPELINE_POLL_TIMEOUT_MS` | int | `5000` | Redis XREADGROUP block timeout (ms) |
| `stt_workers` | `PIPELINE_STT_WORKERS` | int | `1` | Number of concurrent STT workers (Whisper is CPU/GPU-heavy) |
| `llm_workers` | `PIPELINE_LLM_WORKERS` | int | `1` | Number of concurrent LLM workers (API-bound, not CPU) |
| `tts_workers` | `PIPELINE_TTS_WORKERS` | int | `2` | Number of concurrent TTS workers (Piper is moderate CPU) |
| `ws_workers` | `PIPELINE_WS_WORKERS` | int | `1` | Number of WS response senders (I/O only, 1 is enough) |

### Worker sizing guide

| Worker type | Bottleneck | Recommendation |
|------------|------------|---------------|
| `stt_workers` | CPU/GPU | `1` on CPU, `2` on GPU with CUDA |
| `llm_workers` | Network (API) | Match expected concurrent users, but session state is not locked — be careful with >1 |
| `tts_workers` | CPU | `2` is plenty on most hardware |
| `ws_workers` | I/O | `1` — XREADGROUP delivers each message to exactly one consumer |

<!-- Arkan Fakoseh -  @2kfi on github -->
# Getting Started

Two scenarios:

- **Single node**: one machine runs everything (Redis + Qdrant + Neo4j + the app)
- **Cluster**: 3+ nodes behind a load balancer, sharing Redis + Qdrant + Neo4j

---

## 1. Single Node

### 1.1 Prerequisites

```bash
git clone <repo> hakeem
cd hakeem
```

### 1.2 Generate secrets

```bash
# Auto-generate JWT secret + DB password (Redis/Neo4j/Qdrant share one password):
python scripts/generate_secrets.py --random

# Or go interactive:
python scripts/generate_secrets.py

# Then set your LLM API key:
echo 'LLM_API_KEY="gsk_your-groq-key-here"' >> .env
```

This writes a `.env` file and `config.yaml` with consistent, cryptographically secure secrets. Both files are in `.gitignore` and won't be committed.

Optional — enable MedRAG with Neo4j:

```bash
export NEO4J_PASSWORD="my-secret"
export MEDRAG_ENABLED=true
export MEDRAG_LLM_API_BASE="http://10.1.1.180:2312/v1"
```

### 1.3 Create source document directories (if using MedRAG)

```bash
mkdir -p data/med_docs/hepatology
mkdir -p data/med_docs/nephrology
mkdir -p data/med_docs/neurology
```

Drop `.md`, `.pdf`, `.txt`, or `.docx` files into each domain folder.

### 1.4 Start everything

```bash
docker compose up -d
```

This starts:
| Container | Port | Purpose |
|-----------|------|---------|
| `hakeem-redis` | `:6379` | Session state, pipeline queues |
| `hakeem-qdrant` | `:6333` | Vector DB (MedRAG) |
| `hakeem-neo4j` | `:7474` (UI), `:7687` (bolt) | Knowledge graph (MedRAG) |
| `hakeem-node-1` | `:8080` | The app |

### 1.5 Verify it's running

```bash
# Health check
curl http://localhost:8080/health

# Watch startup logs
docker logs -f hakeem-node-1
```

Look for these log lines to confirm MedRAG initialized:

```
INFO: Embedding model loaded
INFO: Qdrant store initialized
INFO: Semantic router initialized
INFO: Knowledge graph connected to bolt://neo4j:7687
INFO: HakeemRAGEngine fully initialized: 3 domains, vector_size=384
```

### 1.6 Get an admin JWT

```bash
docker compose run -e DEBUG=true -e JWT_SECRET=$JWT_SECRET hakeem
```

Copy the token, then:

```bash
export TOKEN="eyJhbGciOiJ..."
```

### 1.7 Index documents

```bash
# Auto-index source directories
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/rag/documents/reindex

# Or upload a specific file
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@my_notes.md" \
  "http://localhost:8080/api/v1/rag/documents/upload?domain=hepatology"

# List what's indexed
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/rag/documents
```

### 1.8 Search

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/rag/documents/search?q=What+treats+cirrhosis%3F"
```

Response includes `sufficient`, `verification`, `citations`, and ranked results.

### 1.9 Connect via WebSocket

```bash
wscat -c "ws://localhost:8080/api/v1/connect?token=$TOKEN"
```

Send audio to test STT → RAG → LLM → TTS pipeline.

---

## 2. Cluster Behind a Load Balancer

Three app nodes share one Redis, Qdrant, and Neo4j. The load balancer distributes WebSocket connections across them.

### Architecture

```
                         ┌─────────────┐
                         │  Load       │
                         │  Balancer   │
                         │  :443       │
                         └──────┬──────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
         ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
         │ node-1  │      │ node-2  │      │ node-3  │
         │ :8081   │      │ :8082   │      │ :8083   │
         └────┬────┘      └────┬────┘      └────┬────┘
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │  Shared Services      │
                    │  Redis :6379          │
                    │  Qdrant :6333         │
                    │  Neo4j :7687          │
                    └───────────────────────┘
```

### 2.1 Set env vars (same on all nodes)

Create `.env` or export:

```bash
export JWT_SECRET="$(openssl rand -hex 32)"
export LLM_API_KEY="gsk_your-groq-key-here"
export NEO4J_PASSWORD="my-secret"
export MEDRAG_ENABLED=true
export MEDRAG_LLM_API_BASE="http://10.1.1.180:2312/v1"
```

### 2.2 Start shared infrastructure

On the infra node (or first node):

```bash
docker compose -f docker-compose.infra.yml up -d
```

This starts Redis `:6379`, Qdrant `:6333`, and Neo4j `:7687` on the host network.

### 2.3 Start app nodes

On each node (or all on one machine with different ports):

```bash
# Node 1
CLUSTER_NODE_ID=1 API_PORT=8081 \
  docker compose -f docker-compose.app.yml up -d

# Node 2
CLUSTER_NODE_ID=2 API_PORT=8082 \
  docker compose -f docker-compose.app.yml up -d

# Node 3
CLUSTER_NODE_ID=3 API_PORT=8083 \
  docker compose -f docker-compose.app.yml up -d
```

Or scale on a single machine:

```bash
docker compose -f docker-compose.app.yml up -d --scale hakeem=3
```

Each node auto-discovers Redis/Qdrant/Neo4j via the compose network. All share the same vector store and graph database.

### 2.4 Load balancer

#### Option A — Caddy (recommended, auto HTTPS)

Create `Caddyfile`:

```
your-domain.com {
    reverse_proxy 10.1.1.1:8081 10.1.1.2:8082 10.1.1.3:8083 {
        lb_policy round_robin
    }
}
```

```bash
docker run -d -p 80:80 -p 443:443 \
  -v $PWD/Caddyfile:/etc/caddy/Caddyfile \
  -v caddy-data:/data \
  caddy:latest
```

#### Option B — nginx

Create `nginx.conf`:

```nginx
upstream hakeem_backend {
    least_conn;
    server 10.1.1.1:8081;
    server 10.1.1.2:8082;
    server 10.1.1.3:8083;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://hakeem_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }
}
```

```bash
docker run -d -p 80:80 \
  -v $PWD/nginx.conf:/etc/nginx/conf.d/default.conf \
  nginx:alpine
```

#### Option C — HAProxy

Create `haproxy.cfg`:

```haproxy
global
    daemon

defaults
    mode http
    timeout connect 5s
    timeout client 86400s
    timeout server 86400s

frontend hakeem_front
    bind *:80
    default_backend hakeem_nodes

backend hakeem_nodes
    balance leastconn
    server node-1 10.1.1.1:8081 check
    server node-2 10.1.1.2:8082 check
    server node-3 10.1.1.3:8083 check
```

```bash
docker run -d -p 80:80 \
  -v $PWD/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg \
  haproxy:latest
```

### 2.5 Verify

```bash
# Hit the load balancer (not individual nodes)
curl http://your-domain.com/health

# Should see healthy — any node can respond
```

### 2.6 Index documents (once — persists across nodes)

```bash
# Get token from any node
docker compose -f docker-compose.app.yml run -e DEBUG=true -e JWT_SECRET=$JWT_SECRET hakeem

# Index on any single node (all nodes share Qdrant + Neo4j)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://your-domain.com/api/v1/rag/documents/reindex
```

### 2.7 Test failover

```bash
# Kill one node
docker rm -f hakeem-node-1

# Requests still work — load balancer sends to remaining nodes
curl http://your-domain.com/health

# If a phone was connected to node-1, it reconnects and lands on
# node-2 or node-3. Session data in Redis is picked up seamlessly.
```

### 2.8 Simulating the full cluster on one machine

```bash
# Start everything (infra + 3 app nodes) with one command:
docker compose -f docker-compose.cluster.yml up -d

# Node 1: http://localhost:8081
# Node 2: http://localhost:8082
# Node 3: http://localhost:8083
```

Then put nginx/Caddy/HAProxy in front of `:8081-:8083`.

---

## 3. Production Checklist

| Item | Single Node | Cluster |
|------|-------------|---------|
| JWT_SECRET | Random hex string | Same across all nodes |
| LLM_API_KEY | Your Groq key | Same across all nodes |
| NEO4J_PASSWORD | Non-trivial password | Same across all nodes (used by all containers) |
| Redis password | Default `hakeem_pass` | Change via `REDIS_PASSWORD` |
| Model download | Auto on startup | Each node downloads independently |
| Qdrant data | Local volume | Shared via network (Qdrant is the single source of truth) |
| Neo4j data | Local volume | Shared via network (single Neo4j instance) |
| Load balancer | Not needed | Required for WS distribution + failover |
| TLS/HTTPS | Optional | Strongly recommended (via Caddy) |

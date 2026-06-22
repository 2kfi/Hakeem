# Arkan Fakoseh -  @2kfi on github
"""
Najim Backend - Multi-Tenant Distributed Voice Assistant
"""
import asyncio
import logging
import logging.handlers
import json
import os
import time
import uuid

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core.config import get_settings, Settings
from core.redis_manager import RedisManager, get_redis
from core.app_state import get_app_state, AppState
from core.jwt_auth import get_jwt_manager, verify_jwt
from api.chat import router as chat_router
from api.websocket import router as ws_router, _start_ws_listener, _active_connections
from api.sessions import router as sessions_router
from api.health import router as health_router
from rag.api import router as rag_router
from pipeline.orchestrator import WorkerManager
from rag.engine import init_rag_engine, get_rag_engine
from scripts.mcp import MCPWrapper, openapi_spec_to_tools

logger = logging.getLogger("najim")

settings = get_settings()
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(levelname)s: %(name)s: %(message)s",
)

os.makedirs("logs", exist_ok=True)
_handler = logging.handlers.RotatingFileHandler(
    "logs/app.log", maxBytes=10_000_000, backupCount=3
)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))
logging.getLogger().addHandler(_handler)

limiter = Limiter(key_func=get_remote_address)

_uptime_start = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Starting Najim cluster node: {settings.cluster.node_id}")

    # ═══════════════════════════════════════════════════════════════════
    # Phase 1: Redis
    # ═══════════════════════════════════════════════════════════════════
    logger.info("═══════════ Phase 1: Redis ═══════════")
    redis = await get_redis()

    if not await redis.ping():
        raise RuntimeError("Redis connection failed")
    else:
        logger.info("Redis connected")

    # ═══════════════════════════════════════════════════════════════════
    # Phase 2: RAG (file change detection)
    # ═══════════════════════════════════════════════════════════════════
    logger.info("═══════════ Phase 2: RAG ═══════════")
    if settings.medrag.enabled:
        engine = await init_rag_engine(settings.medrag)
        if engine and settings.medrag.auto_index_on_start:
            dirs = settings.medrag.domain_source_dirs
            if dirs:
                logger.info(f"RAG: checking {len(dirs)} domain dirs for changes...")
                n = await engine.index_if_changed(dirs)
                if n:
                    logger.info(f"RAG: indexed {n} new/changed chunks")

    # ═══════════════════════════════════════════════════════════════════
    # Phase 3: Models (TTS + Whisper + LLM)
    # ═══════════════════════════════════════════════════════════════════
    logger.info("═══════════ Phase 3: Models ═══════════")
    await AppState.initialize()

    # ═══════════════════════════════════════════════════════════════════
    # Phase 4: Workers
    # ═══════════════════════════════════════════════════════════════════
    logger.info("═══════════ Phase 4: Workers ═══════════")
    worker_mgr = WorkerManager(redis)
    started_ok = False
    try:
        await worker_mgr.start_all()
        started_ok = True
    except Exception as e:
        logger.error(f"Failed to start workers: {e}", exc_info=True)
        await worker_mgr.stop_all()
        raise

    ws_listener_task = asyncio.create_task(_start_ws_listener(settings.cluster.node_id, redis))

    # ── External MCP servers ──────────────────────────────────────────
    # Connect to configured MCP servers and register their tools in the
    # ToolRegistry so the pipeline LLM can call them.
    mcp_wrapper = None
    if settings.mcp.servers:
        try:
            mcp_wrapper = MCPWrapper(
                llama_base_url=settings.llm.api_base_url,
                llama_model=settings.llm.model,
                mcp_servers=settings.mcp.servers,
                api_key=settings.llm.api_key,
                timeout=settings.llm.timeout,
                max_tool_loops=settings.mcp.max_tool_loops,
                max_retries=settings.mcp.max_retries,
            )
            await mcp_wrapper.initialize_servers()
            n = await mcp_wrapper.register_all_in_registry()
            logger.info("Registered %d external MCP tools in ToolRegistry", n)
        except Exception as e:
            logger.error("Failed to initialize MCP servers: %s", e)
        app.state.mcp_wrapper = mcp_wrapper

    # ── OpenAPI → MCP tools ────────────────────────────────────────────
    # Load OpenAPI specs and register each endpoint as an MCP tool.
    openapi_specs = os.environ.get("MCP_OPENAPI_SPECS", "").strip()
    if openapi_specs:
        for spec_path in openapi_specs.split(","):
            spec_path = spec_path.strip()
            if not spec_path:
                continue
            try:
                n = await openapi_spec_to_tools(spec_path)
                logger.info("Registered %d OpenAPI tools from %s", n, spec_path)
            except Exception as e:
                logger.error("Failed to load OpenAPI spec %s: %s", spec_path, e)

    logger.info("Application initialized successfully")
    yield

    logger.info("Shutting down...")
    ws_listener_task.cancel()
    try:
        await ws_listener_task
    except asyncio.CancelledError:
        pass
    if started_ok:
        await worker_mgr.stop_all()
    if mcp_wrapper is not None:
        try:
            await mcp_wrapper.close()
        except Exception:
            pass
    await AppState.shutdown()
    await redis.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Najim Backend",
    version="3.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False if "*" in settings.cors_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "error_code": "RATE_LIMITED"}
    )


@app.middleware("http")
async def api_key_fallback(request: Request, call_next):
    if get_settings().auth.disabled:
        return await call_next(request)
    if request.url.path in ["/health", "/ready", "/live", "/metrics", "/openapi.json", "/docs", "/redoc"]:
        return await call_next(request)
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    auth = request.headers.get("authorization", "")
    settings = get_settings()

    if auth.startswith("Bearer "):
        token = auth.replace("Bearer ", "").strip()
        try:
            jwt_mgr = get_jwt_manager()
            jwt_mgr.verify_token(token)
            return await call_next(request)
        except Exception:
            if settings.auth.jwt_only:
                return JSONResponse({"error": "Invalid JWT token"}, status_code=401)

    if not settings.auth.jwt_only:
        if settings.auth.api_keys:
            if auth.startswith("Bearer "):
                key = auth.replace("Bearer ", "").strip()
                if not key:
                    return JSONResponse({"error": "Missing or invalid API key"}, status_code=401)
                if key in settings.auth.api_keys:
                    return await call_next(request)
            return JSONResponse({"error": "Invalid API key"}, status_code=401)
        return JSONResponse({"error": "Authentication not configured (set JWT_SECRET or AUTH_API_KEYS)"}, status_code=401)

    return JSONResponse({"error": "Missing or invalid Authorization header"}, status_code=401)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(ws_router)
app.include_router(sessions_router)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(rag_router)


@app.get("/")
@limiter.limit("60/minute")
async def root(request: Request):
    return {
        "service": "najim-backend",
        "version": "3.0.0",
        "node_id": settings.cluster.node_id,
        "status": "running",
        "uptime_seconds": time.time() - _uptime_start,
    }


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "error_code": "NOT_FOUND", "path": request.url.path}
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Najim/Hakeem backend")
    parser.add_argument("--no-auth", action="store_true", help="Disable all auth (JWT + API keys)")
    args, _ = parser.parse_known_args()
    if args.no_auth:
        get_settings().auth.disabled = True
        logger.warning("Auth is DISABLED (--no-auth)")

    import uvicorn

    uvicorn_kwargs = {
        "host": settings.api_host,
        "port": settings.api_port,
        "log_level": "debug" if settings.debug else "info",
        "ws_ping_interval": 25,
        "ws_max_size": settings.ws_max_size,
    }

    if settings.proxy.enabled:
        uvicorn_kwargs["proxy_headers"] = True
        uvicorn_kwargs["forwarded_allow_ips"] = ",".join(settings.proxy.forwarded_allow_ips)

    uvicorn.run(app, **uvicorn_kwargs)
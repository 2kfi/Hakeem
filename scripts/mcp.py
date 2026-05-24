"""MCP client wrapper for connecting to MCP servers.

Supports connecting to external MCP servers over SSE and HTTP transports,
and registering their tools in the Hakeem ToolRegistry.
"""

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
import yaml

from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AsyncOpenAI

from core.schemas import ToolDefinition
from tools.registry import get_tool_registry

logger = logging.getLogger(__name__)


# ── Proxy factory ──────────────────────────────────────────────────────────


def _make_mcp_proxy(manager: "MCPSessionManager", tool_name: str) -> Callable[..., Any]:
    """Create an async handler that proxies calls through an MCPSessionManager."""
    async def proxy(**kwargs: Any) -> str:
        result = await manager.call_tool(tool_name, kwargs)
        return str(result.content)
    proxy.__name__ = f"mcp_{tool_name}"
    proxy.__qualname__ = f"mcp_{tool_name}"
    return proxy


# ── MCP server session manager (SSE + HTTP) ───────────────────────────────


class MCPSessionManager:
    """Manages a single MCP server connection with auto-reconnect capability.

    Transport is auto-detected from the URL:
    - ``sse://`` or any HTTP URL  → SSE transport (HTTP-based, standard MCP)
    """

    def __init__(
        self,
        url: str,
        api_key: str = "",
        sse_read_timeout: float = 300.0,
        connect_timeout: float = 30.0,
        tool_timeout: float = 60.0,
        transport: str = "sse",
    ):
        self.url = url
        self.api_key = api_key or "sk-no-key-required"
        self.sse_read_timeout = sse_read_timeout
        self.connect_timeout = connect_timeout
        self.tool_timeout = tool_timeout
        self.transport = transport
        self.session: Optional[ClientSession] = None
        self.exit_stack: Optional[AsyncExitStack] = None
        self.tools: List[Any] = []
        self.lock = asyncio.Lock()
        self.connected = False

    async def connect(self):
        """Connect to MCP server using the configured transport."""
        async with self.lock:
            if self.connected:
                return
            try:
                logger.info(f"Connecting to MCP server: {self.url} (transport={self.transport})")

                if self.transport == "sse":
                    await self._connect_sse()
                else:
                    await self._connect_http()

                resp = await self.session.list_tools()
                self.tools = resp.tools
                self.connected = True
                logger.info(f"Connected to {self.url} - Found {len(self.tools)} tools.")
            except Exception as e:
                logger.error(f"Failed to connect to {self.url}: {e}", exc_info=True)
                await self.close()
                raise

    async def _connect_sse(self):
        """Connect using SSE transport (HTTP-based, standard MCP)."""
        transport_ctx = sse_client(
            self.url,
            timeout=self.connect_timeout,
            sse_read_timeout=self.sse_read_timeout,
        )
        self.exit_stack = AsyncExitStack()
        read, write = await self.exit_stack.enter_async_context(transport_ctx)
        self.session = ClientSession(read, write)
        await self.session.initialize()

    async def _connect_http(self):
        """Connect using raw HTTP transport.

        Uses POST to the URL for client→server messages and SSE for
        server→client streaming responses.
        """
        transport_ctx = sse_client(
            self.url,
            timeout=self.connect_timeout,
            sse_read_timeout=self.sse_read_timeout,
        )
        self.exit_stack = AsyncExitStack()
        read, write = await self.exit_stack.enter_async_context(transport_ctx)
        self.session = ClientSession(read, write)
        await self.session.initialize()

    async def close(self):
        """Close MCP connection."""
        self.connected = False
        self.session = None
        self.tools = []
        try:
            if self.exit_stack:
                await self.exit_stack.aclose()
        except OSError as e:
            logger.error(f"Error closing session for {self.url}: {e}")

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call a tool on the MCP server."""
        if not self.connected or not self.session:
            await self.connect()
        return await asyncio.wait_for(
            self.session.call_tool(name, arguments=arguments), timeout=self.tool_timeout
        )

    # ── ToolRegistry integration ──────────────────────────────────────────

    async def register_in_registry(self) -> int:
        """Register this server's tools in the Hakeem ToolRegistry.

        Each tool is prefixed with ``mcp_`` to avoid name collisions.
        Returns the number of tools registered.
        """
        registry = await get_tool_registry()
        count = 0
        for tool in self.tools:
            name = f"mcp_{tool.name}"
            tdef = ToolDefinition(
                name=name,
                description=tool.description or f"MCP tool from {self.url}",
                input_schema=tool.inputSchema or {"type": "object", "properties": {}},
                is_internal=False,
            )
            handler = _make_mcp_proxy(self, tool.name)
            await registry.register_mcp_tool(name, tdef, handler)
            count += 1
        return count

    async def unregister_from_registry(self) -> int:
        """Remove this server's tools from the ToolRegistry."""
        registry = await get_tool_registry()
        count = 0
        for tool in self.tools:
            name = f"mcp_{tool.name}"
            if await registry.remove_mcp_tool(name):
                count += 1
        return count


# ── OpenAPI → MCP tools ────────────────────────────────────────────────────


async def openapi_spec_to_tools(
    spec_path: str,
    prefix: str = "openapi_",
) -> int:
    """Parse an OpenAPI 3.x spec and register each endpoint as an MCP tool.

    Supports local file paths and remote URLs. Each endpoint becomes a tool
    that executes the corresponding HTTP request via ``httpx``.

    Args:
        spec_path: Path or URL to an OpenAPI 3.x spec (JSON or YAML).
        prefix: Prefix for tool names (default ``openapi_``).

    Returns:
        Number of tools registered.
    """
    if spec_path.startswith(("http://", "https://")):
        resp = httpx.get(spec_path, timeout=30)
        resp.raise_for_status()
        raw = resp.text
    else:
        path = Path(spec_path)
        if not path.exists():
            raise FileNotFoundError(f"OpenAPI spec not found: {spec_path}")
        raw = path.read_text(encoding="utf-8")

    if spec_path.endswith((".yaml", ".yml")) or raw.strip().startswith(("openapi:", "swagger:")):
        spec = yaml.safe_load(raw)
    else:
        spec = json.loads(raw)

    servers = spec.get("servers", [])
    base_url = servers[0].get("url", "") if servers else ""
    info = spec.get("info", {})
    logger.info(
        "Loading OpenAPI spec: %s v%s (%s)",
        info.get("title", ""),
        info.get("version", ""),
        spec_path,
    )

    registry = await get_tool_registry()
    count = 0

    for path, path_item in spec.get("paths", {}).items():
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            operation = path_item.get(method)
            if not operation:
                continue

            operation_id = operation.get("operationId") or f"{method}_{path}".replace("/", "_").replace("{", "").replace("}", "")
            name = f"{prefix}{operation_id}"
            description = operation.get("description") or operation.get("summary") or ""

            params = operation.get("parameters", [])
            path_params = [p for p in params if p.get("in") == "path"]
            query_params = [p for p in params if p.get("in") == "query"]
            request_body = operation.get("requestBody")

            properties: dict = {}
            required: list = []
            for p in path_params + query_params:
                ps = p.get("schema", {"type": "string"})
                properties[p["name"]] = {
                    "type": ps.get("type", "string"),
                    "description": p.get("description", ""),
                }
                if p.get("required", False):
                    required.append(p["name"])
            if request_body:
                for mt, body in request_body.get("content", {}).items():
                    bs = body.get("schema", {})
                    if bs.get("type") == "object":
                        for fn, fs in bs.get("properties", {}).items():
                            if fn not in properties:
                                properties[fn] = fs
                        for r in bs.get("required", []):
                            if r not in required:
                                required.append(r)

            tdef = ToolDefinition(
                name=name,
                description=description,
                input_schema={"type": "object", "properties": properties, "required": required},
                is_internal=True,
            )

            handler = _make_openapi_handler(method, path, base_url)
            handler.__name__ = name
            handler.__qualname__ = name

            await registry.register_mcp_tool(name, tdef, handler)
            count += 1

    logger.info("Registered %d OpenAPI endpoints as MCP tools from %s", count, spec_path)
    return count


def _make_openapi_handler(method: str, path: str, base_url: str) -> Callable[..., Any]:
    """Create an async handler that executes an OpenAPI endpoint call."""
    async def handler(**kwargs: Any) -> str:
        url = base_url.rstrip("/") + "/" + path.lstrip("/")
        path_params = {k: v for k, v in kwargs.items() if f"{{{k}}}" in path}
        query_params = {k: v for k, v in kwargs.items() if k not in path_params}
        body_args = {k: v for k, v in kwargs.items()}
        for key, val in path_params.items():
            path = path.replace(f"{{{key}}}", str(val))
        url = base_url.rstrip("/") + "/" + path.lstrip("/")

        extra: dict = {}
        if method in ("post", "put", "patch"):
            extra["json"] = body_args
        elif query_params:
            extra["params"] = query_params

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(method, url, **extra)
            resp.raise_for_status()
            return resp.text
    return handler


# ── Multi-server orchestrator ──────────────────────────────────────────────


class MCPWrapper:
    """Orchestrates multiple MCP server connections with LLM integration.

    This is the legacy orchestrator that runs its own LLM loop. For new
    code, use ``MCPSessionManager.register_in_registry()`` directly to
    register tools in the Hakeem ToolRegistry.
    """

    def __init__(
        self,
        llama_base_url: str,
        llama_model: str,
        mcp_servers: list[dict],
        api_key: str = "sk-no-key-required",
        timeout: float = 60.0,
        max_tool_loops: int = 5,
        max_retries: int = 2,
        mcp_defaults: dict = None,
    ):
        self.llama = AsyncOpenAI(
            base_url=llama_base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=0,
        )
        self.llama_model = llama_model
        self.api_key = api_key
        self.max_tool_loops = max_tool_loops
        self.max_retries = max_retries

        defaults = mcp_defaults or {"api_key": "", "sse_read_timeout": 300.0, "connect_timeout": 30.0, "tool_timeout": 60.0, "max_retries": 2}
        self.mcp_managers: List[MCPSessionManager] = [
            MCPSessionManager(
                url=srv.get("url", srv) if isinstance(srv, str) else srv.get("url", ""),
                api_key=srv.get("api_key", "") if isinstance(srv, dict) else "",
                sse_read_timeout=srv.get("sse_read_timeout", defaults["sse_read_timeout"]) if isinstance(srv, dict) else defaults["sse_read_timeout"],
                connect_timeout=srv.get("connect_timeout", defaults["connect_timeout"]) if isinstance(srv, dict) else defaults["connect_timeout"],
                tool_timeout=srv.get("tool_timeout", defaults["tool_timeout"]) if isinstance(srv, dict) else defaults["tool_timeout"],
            )
            for srv in (mcp_servers or [])
        ]
        self.tool_map: Dict[str, MCPSessionManager] = {}
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._tools_schema_cache: Optional[List[Dict]] = None

    async def initialize_servers(self):
        """Initialize all MCP server connections."""
        async with self._init_lock:
            if self._initialized:
                return

            results = await asyncio.gather(
                *(mgr.connect() for mgr in self.mcp_managers), return_exceptions=True
            )

            self.tool_map.clear()
            for mgr, res in zip(self.mcp_managers, results):
                if isinstance(res, Exception):
                    logger.error(f"Startup connection failed for {mgr.url}: {res}")
                    continue
                for tool in mgr.tools:
                    self.tool_map[tool.name] = mgr

            self._initialized = True
            self._rebuild_tools_schema_cache()
            logger.info("MCPWrapper initialization complete.")

    def _rebuild_tools_schema_cache(self):
        """Rebuild the tools schema cache."""
        schema = []
        for mgr in self.mcp_managers:
            if not mgr.connected:
                continue
            for tool in mgr.tools:
                schema.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "No description",
                            "parameters": tool.inputSchema,
                        },
                    }
                )
        self._tools_schema_cache = schema

    @property
    def openai_tools_schema(self) -> List[Dict]:
        """Get OpenAI-compatible tools schema."""
        if self._tools_schema_cache is not None and self._initialized:
            return self._tools_schema_cache
        return []

    async def _execute_tool(self, tool_call) -> dict:
        """Execute a tool call from LLM."""
        name = tool_call.function.name
        try:
            args_dict = json.loads(tool_call.function.arguments)
        except (json.JSONDecodeError, ValueError):
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": "Error: Invalid JSON arguments.",
            }

        logger.info(f"AI requested tool: {name}({args_dict})")

        manager = self.tool_map.get(name)
        if not manager:
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": f"Error: Tool '{name}' not found.",
            }

        content = None
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await manager.call_tool(name, args_dict)
                content = str(result.content)
                break
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    logger.warning(f"Tool call '{name}' failed (attempt {attempt + 1}): {e}. Reconnecting...")
                    try:
                        await manager.close()
                        await manager.connect()
                    except Exception as reconnect_err:
                        logger.warning(f"Reconnect failed: {reconnect_err}")

        if content is None:
            logger.error(f"Tool call '{name}' failed after {self.max_retries + 1} attempts: {last_error}")
            content = f"Error executing tool '{name}' after {self.max_retries + 1} attempts: {last_error}"

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": name,
            "content": content,
        }

    async def run_query(self, stt_input: str) -> str:
        """Run a query through the LLM with MCP tools."""
        system_msg = {
            "role": "system",
            "content": (
                "You are a concise voice assistant. Give short, natural answers. "
                "Avoid bold text, markdown lists, or long explanations unless asked."
            ),
        }
        user_msg = {"role": "user", "content": stt_input}
        messages = [system_msg, user_msg]

        for i in range(self.max_tool_loops):
            try:
                tools_schema = self.openai_tools_schema
                response = await self.llama.chat.completions.create(
                    model=self.llama_model,
                    messages=messages,
                    tools=tools_schema if tools_schema else None,
                    tool_choice="auto" if tools_schema else None,
                )
            except (OSError, TimeoutError) as e:
                logger.error(f"LLM call failed at step {i}: {e}")
                raise RuntimeError(f"LLM API call failed: {e}")

            message = response.choices[0].message

            msg_dict: Dict[str, Any] = {
                "role": message.role,
                "content": message.content or "",
            }
            if message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            messages.append(msg_dict)

            if not message.tool_calls:
                return message.content or ""

            tool_results = await asyncio.gather(
                *(self._execute_tool(tc) for tc in message.tool_calls)
            )
            messages.extend(tool_results)

        logger.warning(f"Tool loop exceeded {self.max_tool_loops} iterations")
        final_msg = messages[-1]
        return final_msg.get("content", "") if isinstance(final_msg, dict) else ""

    async def register_all_in_registry(self) -> int:
        """Register all discovered MCP server tools in the Hakeem ToolRegistry."""
        total = 0
        for mgr in self.mcp_managers:
            if mgr.connected:
                count = await mgr.register_in_registry()
                total += count
                logger.info("Registered %d tools from %s in ToolRegistry", count, mgr.url)
        return total

    async def unregister_all_from_registry(self) -> int:
        """Remove all MCP server tools from the ToolRegistry."""
        total = 0
        for mgr in self.mcp_managers:
            count = await mgr.unregister_from_registry()
            total += count
        return total

    async def close(self):
        """Close all MCP connections."""
        await self.unregister_all_from_registry()
        await asyncio.gather(*(mgr.close() for mgr in self.mcp_managers))

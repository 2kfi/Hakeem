"""MCP client for connecting to MCP servers"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AsyncOpenAI

logger = logging.getLogger("MCP")


class MCPSessionManager:
    """Manages a single MCP server connection with auto-reconnect capability."""

    def __init__(
        self, url: str, timeout: float = 30.0, api_key: str = "sk-no-key-required"
    ):
        self.url = url
        self.timeout = timeout
        self.api_key = api_key
        self.session: Optional[ClientSession] = None
        self.exit_stack: Optional[asyncio.AsyncExitStack] = None
        self.tools: List[Any] = []
        self.lock = asyncio.Lock()
        self.connected = False

    async def connect(self):
        """Connect to MCP server."""
        async with self.lock:
            if self.connected:
                return
            try:
                logger.info(f"Connecting to MCP server: {self.url}")
                transport_ctx = sse_client(self.url)
                read, write = await transport_ctx.__aenter__()
                self.exit_stack = asyncio.AsyncExitStack()
                read, write = await self.exit_stack.enter_async_context(
                    (read, write) if isinstance(transport_ctx, tuple) else (read, write)
                )
                self.session = ClientSession(read, write)
                await self.session.initialize()

                resp = await self.session.list_tools()
                self.tools = resp.tools
                self.connected = True
                logger.info(f"Connected to {self.url} - Found {len(self.tools)} tools.")
            except Exception as e:
                logger.error(f"Failed to connect to {self.url}: {e}")
                await self.close()
                raise

    async def close(self):
        """Close MCP connection."""
        self.connected = False
        self.session = None
        self.tools = []
        try:
            if self.exit_stack:
                await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"Error closing session for {self.url}: {e}")

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call a tool on the MCP server."""
        if not self.connected or not self.session:
            await self.connect()
        return await asyncio.wait_for(
            self.session.call_tool(name, arguments=arguments), timeout=self.timeout
        )


class MCPWrapper:
    """Wrapper for multiple MCP servers with LLM integration."""

    def __init__(
        self,
        llama_base_url: str,
        llama_model: str,
        mcp_urls: list[str],
        api_key: str = "sk-no-key-required",
        timeout: float = 60.0,
    ):
        self.llama = AsyncOpenAI(
            base_url=llama_base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=0,
        )
        self.llama_model = llama_model
        self.api_key = api_key
        self.mcp_managers: List[MCPSessionManager] = [
            MCPSessionManager(url, api_key=api_key) for url in mcp_urls
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
        if self._tools_schema_cache is not None:
            return self._tools_schema_cache
        return []

    async def _execute_tool(self, tool_call) -> dict:
        """Execute a tool call from LLM."""
        name = tool_call.function.name
        try:
            args_dict = json.loads(tool_call.function.arguments)
        except Exception:
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

        try:
            result = await manager.call_tool(name, args_dict)
            content = str(result.content)
        except Exception as e:
            logger.warning(f"Tool call '{name}' failed: {e}. Attempting reconnect...")
            try:
                await manager.close()
                await manager.connect()
                result = await manager.call_tool(name, args_dict)
                content = str(result.content)
            except Exception as e2:
                logger.error(f"Tool retry '{name}' failed: {e2}")
                content = f"Error executing tool '{name}': {e2}"

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

        max_tool_loops = 5
        for i in range(max_tool_loops):
            try:
                tools_schema = self.openai_tools_schema
                response = await self.llama.chat.completions.create(
                    model=self.llama_model,
                    messages=messages,
                    tools=tools_schema if tools_schema else None,
                    tool_choice="auto" if tools_schema else None,
                )
            except Exception as e:
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

        logger.warning(f"Tool loop exceeded {max_tool_loops} iterations")
        final_msg = messages[-1]
        return final_msg.get("content", "") if isinstance(final_msg, dict) else ""

    async def close(self):
        """Close all MCP connections."""
        await asyncio.gather(*(mgr.close() for mgr in self.mcp_managers))

<!-- Arkan Fakoseh -  @2kfi on github -->
# MCP (Model Context Protocol)

The server can **ingest** tools from external sources via the Model Context Protocol
and make them available to the pipeline LLM through the existing `ToolRegistry`.

Three sources are supported:

| Source | Protocol | Registers as |
|--------|----------|-------------|
| MCP over SSE | SSE transport (HTTP-based) | `mcp_{name}` |
| MCP over HTTP | Same as SSE — SSE runs on HTTP | `mcp_{name}` |
| OpenAPI spec | REST → MCP bridge | `openapi_{operationId}` |

All ingested tools are routed through `route_tool_call()` alongside internal and
remote phone tools. The LLM sees a unified tool list.

---

## MCP Servers (SSE / HTTP)

Configure external MCP servers in `config.yaml` under `mcp.servers`:

```yaml
mcp:
  servers:
    - url: "http://192.168.1.50:8080/sse"   # SSE endpoint of remote MCP server
      api_key: "sk-..."                      # optional
    - url: "http://10.0.0.5:2527/sse"
  sse_read_timeout: 300.0
  connect_timeout: 30.0
  tool_timeout: 60.0
  max_retries: 2
  max_tool_loops: 5
```

At startup, the server connects to each URL, discovers tools via
`client.list_tools()`, and registers each one as `mcp_{name}` in the
`ToolRegistry`. The MCP Python SDK's SSE transport uses HTTP for client→server
messages and SSE for server→client streaming — no additional config needed.

**Example:** If an MCP server at `http://10.0.0.5:2527/sse` exposes a tool
called `search_docs`, it becomes available as `mcp_search_docs`.

---

## OpenAPI → MCP Bridge

Any REST API with an OpenAPI 3.x spec (JSON or YAML) can be imported as MCP
tools. Set the `MCP_OPENAPI_SPECS` environment variable:

```bash
# Single spec
MCP_OPENAPI_SPECS="https://api.example.com/openapi.json"

# Multiple specs (comma-separated)
MCP_OPENAPI_SPECS="/path/to/spec.yaml,https://api.example.com/openapi.json"
```

Each endpoint becomes a tool named `openapi_{operationId}` (or
`openapi_{method}_{path}` if no `operationId`). Calling the tool executes the
corresponding HTTP request via `httpx`.

**Example:** Given this OpenAPI spec:

```json
{
  "openapi": "3.1.0",
  "info": { "title": "Weather API", "version": "1.0.0" },
  "servers": [{ "url": "https://api.weather.com" }],
  "paths": {
    "/forecast": {
      "get": {
        "operationId": "getForecast",
        "parameters": [
          { "name": "city", "in": "query", "required": true, "schema": { "type": "string" } }
        ]
      }
    }
  }
}
```

Registers `openapi_getForecast(city: string)` — calling it does
`GET https://api.weather.com/forecast?city=...`.

---

## How It All Fits Together

```
                       ┌──────────────────────┐
                       │    Pipeline LLM       │
                       │  (LLMRunner / Worker) │
                       └────────┬─────────────┘
                                │
                       ┌────────▼────────┐
                       │  route_tool_call │
                       └──┬────┬────┬────┘
                          │    │    │
          ┌───────────────┘    │    └───────────────┐
          ▼                    ▼                    ▼
   Internal tools      Remote phone tools     MCP tools
   (get_time, etc.)    (get_gps, etc.)        (mcp_*, openapi_*)
                                                  │
                                    ┌─────────────┴─────────────┐
                                    │                           │
                           ┌────────▼────────┐       ┌─────────▼─────────┐
                           │ MCPSessionMgr   │       │ OpenAPI bridge    │
                           │ (SSE / HTTP)    │       │ (httpx HTTP call) │
                           └────────┬────────┘       └───────────────────┘
                                    │
                           ┌────────▼────────┐
                           │ External MCP    │
                           │ Server          │
                           └─────────────────┘
```

1. The LLM (in `llm_runner.py` or `MCPWrapper`) asks the `ToolRegistry` for
   available tools.
2. When it calls an MCP tool, `route_tool_call()` finds it in the `_mcp` dict,
   retrieves the registered handler, and executes it.
3. For `mcp_*` tools, the handler proxies through `MCPSessionManager.call_tool()`
   to the external MCP server.
4. For `openapi_*` tools, the handler makes an HTTP request using `httpx`.

---

## Adding a New MCP Source Programmatically

```python
from scripts.mcp import MCPSessionManager, openapi_spec_to_tools

# Connect to an MCP server and register its tools
manager = MCPSessionManager(url="http://10.0.0.5:2527/sse")
await manager.connect()
count = await manager.register_in_registry()  # → ToolRegistry
print(f"Registered {count} tools from MCP server")

# Import an OpenAPI spec as MCP tools
count = await openapi_spec_to_tools("https://api.example.com/openapi.json")
print(f"Registered {count} tools from OpenAPI spec")
```

---

## Removing Tools

When an MCP server disconnects, tools can be removed:

```python
manager.unregister_from_registry()  # removes all mcp_{name} from this server
```

This is called automatically in `MCPWrapper.close()`.

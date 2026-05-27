#!/usr/bin/env python3
# Arkan Fakoseh -  @2kfi on github
"""Example: Ingest MCP tools from external sources.

Run from the project root:
    python examples/mcp_ingest.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.mcp import MCPSessionManager, openapi_spec_to_tools
from tools.registry import get_tool_registry


async def main():
    registry = await get_tool_registry()

    print("=" * 60)
    print("Example 1: Ingest tools from an external MCP server (SSE)")
    print("=" * 60)
    print()

    # Connect to an MCP server and register its tools
    try:
        manager = MCPSessionManager(
            url="http://localhost:2527/sse",
            sse_read_timeout=10.0,
            connect_timeout=5.0,
            tool_timeout=10.0,
        )
        await manager.connect()
        count = await manager.register_in_registry()
        print(f"  Registered {count} tools from MCP server")

        all_tools = registry.get_all()
        for name, tdef in all_tools.items():
            if name.startswith("mcp_"):
                print(f"    - {name}: {tdef.description}")
    except Exception as e:
        print(f"  Could not connect to MCP server (this is expected if none running): {e}")

    print()
    print("=" * 60)
    print("Example 2: Ingest tools from an OpenAPI spec")
    print("=" * 60)
    print()

    # Use the FastAPI auto-generated OpenAPI spec of this very server
    try:
        count = await openapi_spec_to_tools("http://localhost:8080/openapi.json", prefix="api_")
        print(f"  Registered {count} tools from OpenAPI spec")
        all_tools = registry.get_all()
        for name, tdef in list(all_tools.items())[:10]:
            if name.startswith("api_"):
                print(f"    - {name}: {tdef.description}")
    except Exception as e:
        print(f"  Could not load OpenAPI spec (start the server first): {e}")

    print()
    print("=" * 60)
    print("Example 3: Ingest from a local OpenAPI file")
    print("=" * 60)
    print()

    # Create a minimal inline spec and write it to a temp file
    import json, tempfile, os

    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Useful APIs", "version": "1.0.0"},
        "servers": [{"url": "https://api.example.com"}],
        "paths": {
            "/greet": {
                "get": {
                    "operationId": "greetUser",
                    "summary": "Greet a user",
                    "parameters": [
                        {"name": "name", "in": "query", "required": True, "schema": {"type": "string"}},
                    ],
                }
            },
            "/echo": {
                "post": {
                    "operationId": "echoMessage",
                    "summary": "Echo a message back",
                    "requestBody": {
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                            "required": ["message"],
                        }}}
                    },
                }
            },
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(spec, f)
        tmp = f.name

    try:
        count = await openapi_spec_to_tools(tmp)
        print(f"  Registered {count} tools from local OpenAPI file")
        for name in registry.get_all():
            if name.startswith("openapi_"):
                tdef = registry.get_all()[name]
                print(f"    - {name}: {tdef.description}")
    finally:
        os.unlink(tmp)

    print()
    print("=" * 60)
    print("All tools currently in ToolRegistry:")
    print("=" * 60)
    all_tools = registry.get_all()
    for name, tdef in all_tools.items():
        source = "internal" if name in registry._internal else "remote" if name in registry._remote else "mcp"
        print(f"  [{source:>8}] {name}")


if __name__ == "__main__":
    asyncio.run(main())

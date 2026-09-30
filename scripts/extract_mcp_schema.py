#!/usr/bin/env python3
"""Generate a generic-mock-mcp-server schema.json from a live MCP server.

Connects to a real MCP server (over Streamable HTTP or stdio), calls the
standard `initialize` and `tools/list` methods, and writes out a schema.json
in the format this mock server expects.

The MCP protocol's tools/list only carries `name`, `description` and
`inputSchema` (plus, for servers that declare it, `outputSchema`). It has no
concept of an example response, so `outputExample` is always emitted empty
and must be filled in by hand — see SCHEMA.md.

Usage:
    # Streamable HTTP transport
    python scripts/extract_mcp_schema.py --url http://127.0.0.1:8080/mcp --output schema.json

    # stdio transport
    python scripts/extract_mcp_schema.py --command ./kubernetes-mcp-server --output schema.json
    python scripts/extract_mcp_schema.py --command "npx -y some-mcp-server" --output schema.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Tool


def tool_to_schema_entry(tool: Tool) -> dict[str, Any]:
    dumped = tool.model_dump(by_alias=True, exclude_none=True, mode="json")
    return {
        "name": dumped["name"],
        "description": dumped.get("description", ""),
        "inputSchema": dumped.get("inputSchema", {"type": "object", "properties": {}}),
        "outputSchema": dumped.get("outputSchema", {}),
        "outputExample": {},
    }


async def extract_via_session(session: ClientSession) -> dict[str, Any]:
    init_result = await session.initialize()
    server_info = init_result.server_info
    tools_result = await session.list_tools()

    return {
        "name": server_info.name if server_info else "unknown-mcp-server",
        "version": server_info.version if server_info and server_info.version else "0.0.0",
        "tools": [tool_to_schema_entry(tool) for tool in tools_result.tools],
    }


async def extract_via_http(url: str) -> dict[str, Any]:
    async with streamable_http_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            return await extract_via_session(session)


async def extract_via_stdio(command: str) -> dict[str, Any]:
    parts = shlex.split(command)
    server_params = StdioServerParameters(command=parts[0], args=parts[1:])
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            return await extract_via_session(session)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Streamable HTTP MCP endpoint, e.g. http://127.0.0.1:8080/mcp")
    source.add_argument("--command", help="Command (with args) that starts the MCP server over stdio")
    parser.add_argument("--output", "-o", default="schema.json", help="Path to write schema.json (default: schema.json)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.url:
        schema = asyncio.run(extract_via_http(args.url))
    else:
        schema = asyncio.run(extract_via_stdio(args.command))

    output_path = Path(args.output)
    output_path.write_text(json.dumps(schema, indent=2) + "\n")

    empty_output_schemas = sum(1 for t in schema["tools"] if not t["outputSchema"])
    print(f"Wrote {len(schema['tools'])} tools to {output_path}", file=sys.stderr)
    if empty_output_schemas:
        print(
            f"{empty_output_schemas} tool(s) have no outputSchema/outputExample "
            "(not provided by the MCP server) — fill these in by hand, see SCHEMA.md.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

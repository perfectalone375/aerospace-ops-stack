"""
Native Model Context Protocol (MCP) JSON-RPC 2.0 Server for Aerospace Operations Stack.
Supports both `stdio` transport (`aero-ops-mcp`) and HTTP JSON-RPC (`POST /mcp`).
"""

from __future__ import annotations

import json
import sys
from typing import Any

from ..db import DatabaseManager
from ..handshake import HANDSHAKE_TASKS
from .portal import MCPPortal

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "aerospace-ops-stack", "version": "0.2.0"}

MCP_RESOURCES = [
    {
        "uri": "aeroops://handshake/tasks",
        "name": "Handshake AI Benchmark Registry",
        "description": "Catalog of 8 physical simulation SWE-bench coding challenges (AERO-001 to AERO-008).",
        "mimeType": "application/json",
    },
    {
        "uri": "aeroops://db/runs",
        "name": "Recent Simulation Telemetry Runs",
        "description": "Recent aerospace simulation runs persisted in SQLite WAL storage.",
        "mimeType": "application/json",
    },
    {
        "uri": "aeroops://db/leaderboard",
        "name": "Handshake AI Leaderboard",
        "description": "SQL-aggregated model pass rates and execution latencies.",
        "mimeType": "application/json",
    },
]


def _read_resource(uri: str, db: DatabaseManager | None = None) -> str:
    if uri == "aeroops://handshake/tasks":
        return json.dumps({"tasks": HANDSHAKE_TASKS}, indent=2)
    manager = db if db is not None else DatabaseManager(":memory:")
    if uri == "aeroops://db/runs":
        return json.dumps({"runs": manager.list_simulation_runs(limit=25)}, indent=2)
    if uri == "aeroops://db/leaderboard":
        return json.dumps({"leaderboard": manager.get_evaluation_leaderboard()}, indent=2)
    raise ValueError(f"Resource URI not found: {uri}")


def handle_jsonrpc_request(
    request: dict[str, Any],
    db: DatabaseManager | None = None,
) -> dict[str, Any] | None:
    """Process a single JSON-RPC 2.0 MCP message and return response (or None for notifications)."""
    req_id = request.get("id")
    method = str(request.get("method", ""))
    params = request.get("params") or {}

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCPPortal.list_tools()},
        }

    if method == "tools/call":
        tool_name = str(params.get("name", ""))
        args = params.get("arguments") or {}
        try:
            output = MCPPortal.invoke_tool(tool_name, args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(output, indent=2)}],
                    "isError": False,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            }

    if method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": MCP_RESOURCES},
        }

    if method == "resources/read":
        uri = str(params.get("uri", ""))
        try:
            payload = _read_resource(uri, db=db)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [{"uri": uri, "mimeType": "application/json", "text": payload}]
                },
            }
        except ValueError as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": str(exc)},
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    """Run Model Context Protocol server over standard input/output (stdio)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    db = DatabaseManager(":memory:")
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_jsonrpc_request(req, db=db)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

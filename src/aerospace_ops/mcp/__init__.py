"""
Model Context Protocol (MCP) Central Portal and JSON-RPC 2.0 Server for Aerospace Microservices.
"""

from .portal import MCP_PORTAL_TOOLS, MCPPortal
from .server import MCP_RESOURCES, handle_jsonrpc_request

__all__ = ["MCP_PORTAL_TOOLS", "MCP_RESOURCES", "MCPPortal", "handle_jsonrpc_request"]

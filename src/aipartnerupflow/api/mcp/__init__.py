"""
MCP (Model Context Protocol) Server for aipartnerupflow

This module provides MCP server implementation that exposes aipartnerupflow's
task orchestration capabilities as MCP tools and resources.
"""

from aipartnerupflow.api.mcp.server import McpServer

__all__ = ["McpServer"]


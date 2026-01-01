"""
MCP (Model Context Protocol) Server for apflow

This module provides MCP server implementation that exposes apflow's
task orchestration capabilities as MCP tools and resources.
"""

from apflow.api.mcp.server import McpServer

__all__ = ["McpServer"]


"""
MCP (Model Context Protocol) Executor Extension

This extension provides executors for interacting with MCP servers,
enabling AI applications to access external tools and data sources
through the standardized MCP protocol.
"""

from apflow.extensions.mcp.mcp_executor import McpExecutor

__all__ = ["McpExecutor"]


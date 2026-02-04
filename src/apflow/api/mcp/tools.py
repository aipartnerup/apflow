"""
MCP Tools Definition

Generates MCP tools from the unified capabilities registry and routes
tool calls to the appropriate TaskRoutes adapter methods.
"""

import json
from typing import Any, Dict, List, Optional

from apflow.api.capabilities import get_all_operations
from apflow.api.mcp.adapter import TaskRoutesAdapter
from apflow.logger import get_logger

logger = get_logger(__name__)


class McpTool:
    """Represents an MCP tool"""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_mcp_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool definition format"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class McpToolsRegistry:
    """Registry of MCP tools, auto-generated from capabilities registry"""

    def __init__(self, adapter: TaskRoutesAdapter):
        self.adapter = adapter
        self._tools: Dict[str, McpTool] = {}
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all MCP tools from capabilities registry."""
        for op in get_all_operations():
            tool_name = op.get_mcp_tool_name()
            self._tools[tool_name] = McpTool(
                name=tool_name,
                description=op.description,
                input_schema=op.input_schema,
            )
        logger.info(f"Registered {len(self._tools)} MCP tools from capabilities registry")

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools in MCP format"""
        return [tool.to_mcp_dict() for tool in self._tools.values()]

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        request: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Call a tool by name, routing to the appropriate adapter method.

        Args:
            name: Tool name
            arguments: Tool arguments
            request: Optional request object (for HTTP mode)

        Returns:
            Tool execution result in MCP content format

        Raises:
            ValueError: If tool not found
        """
        if name not in self._tools:
            raise ValueError(f"Tool not found: {name}")

        try:
            result = await self.adapter.call_by_tool_name(name, arguments, request)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": self._format_result(result),
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}", exc_info=True)
            raise

    def _format_result(self, result: Any) -> str:
        """Format result as text for MCP response"""
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2, ensure_ascii=False)
        return str(result)

"""
MCP Tools Definition

Defines MCP tools that expose apflow task orchestration capabilities.
"""

from typing import Dict, Any, List, Optional
from apflow.api.mcp.adapter import TaskRoutesAdapter
from apflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class McpTool:
    """Represents an MCP tool"""
    
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any]
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
    
    def to_mcp_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool definition format"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }


class McpToolsRegistry:
    """Registry of MCP tools"""
    
    def __init__(self, adapter: TaskRoutesAdapter):
        self.adapter = adapter
        self._tools: Dict[str, McpTool] = {}
        self._register_tools()
    
    def _register_tools(self):
        """Register all MCP tools"""
        # Execute task tool
        self._tools["execute_task"] = McpTool(
            name="execute_task",
            description="Execute a task or task tree. Supports executing by task_id or by providing tasks array directly.",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to execute (optional if tasks is provided)"
                    },
                    "tasks": {
                        "type": "array",
                        "description": "Array of task dictionaries to execute (optional if task_id is provided)"
                    },
                    "use_streaming": {
                        "type": "boolean",
                        "description": "Enable streaming mode for real-time updates (default: false)"
                    },
                    "copy_execution": {
                        "type": "boolean",
                        "description": "Copy task before execution to preserve original (default: false)"
                    },
                    "webhook_config": {
                        "type": "object",
                        "description": "Webhook configuration for push notifications",
                        "properties": {
                            "url": {"type": "string"},
                            "headers": {"type": "object"},
                            "method": {"type": "string"},
                            "timeout": {"type": "number"},
                            "max_retries": {"type": "integer"}
                        }
                    }
                }
            }
        )
        
        # Create task tool
        self._tools["create_task"] = McpTool(
            name="create_task",
            description="Create a new task or task tree. Can create single task or multiple tasks.",
            input_schema={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "Array of task dictionaries to create (can be single task in array)",
                        "items": {
                            "type": "object",
                            "description": "Task definition with name, description, executor, inputs, etc."
                        }
                    }
                },
                "required": ["tasks"]
            }
        )
        
        # Get task tool
        self._tools["get_task"] = McpTool(
            name="get_task",
            description="Get a task by ID",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to retrieve"
                    }
                },
                "required": ["task_id"]
            }
        )
        
        # Update task tool
        self._tools["update_task"] = McpTool(
            name="update_task",
            description="Update an existing task",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to update"
                    },
                    "name": {"type": "string", "description": "Task name"},
                    "description": {"type": "string", "description": "Task description"},
                    "status": {"type": "string", "description": "Task status"},
                    "inputs": {"type": "object", "description": "Task inputs"},
                    "schemas": {"type": "object", "description": "Task schemas"}
                },
                "required": ["task_id"]
            }
        )
        
        # Delete task tool
        self._tools["delete_task"] = McpTool(
            name="delete_task",
            description="Delete a task and its children (if all are pending)",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to delete"
                    }
                },
                "required": ["task_id"]
            }
        )
        
        # List tasks tool
        self._tools["list_tasks"] = McpTool(
            name="list_tasks",
            description="List tasks with optional filtering",
            input_schema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status (pending, running, completed, failed, cancelled)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination"
                    }
                }
            }
        )
        
        # Get task status tool
        self._tools["get_task_status"] = McpTool(
            name="get_task_status",
            description="Get status of a running task",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to get status for"
                    }
                },
                "required": ["task_id"]
            }
        )
        
        # Cancel task tool
        self._tools["cancel_task"] = McpTool(
            name="cancel_task",
            description="Cancel a running task",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to cancel"
                    }
                },
                "required": ["task_id"]
            }
        )
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools in MCP format"""
        return [tool.to_mcp_dict() for tool in self._tools.values()]
    
    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        request: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Call a tool by name
        
        Args:
            name: Tool name
            arguments: Tool arguments
            request: Optional request object (for HTTP mode)
        
        Returns:
            Tool execution result
        
        Raises:
            ValueError: If tool not found
        """
        if name not in self._tools:
            raise ValueError(f"Tool not found: {name}")
        
        try:
            # Route to appropriate adapter method
            if name == "execute_task":
                result = await self.adapter.execute_task(arguments, request)
            elif name == "create_task":
                result = await self.adapter.create_task(arguments, request)
            elif name == "get_task":
                result = await self.adapter.get_task(arguments, request)
            elif name == "update_task":
                result = await self.adapter.update_task(arguments, request)
            elif name == "delete_task":
                result = await self.adapter.delete_task(arguments, request)
            elif name == "list_tasks":
                result = await self.adapter.list_tasks(arguments, request)
            elif name == "get_task_status":
                result = await self.adapter.get_task_status(arguments, request)
            elif name == "cancel_task":
                result = await self.adapter.cancel_task(arguments, request)
            else:
                raise ValueError(f"Unknown tool: {name}")
            
            # Format result for MCP
            return {
                "content": [
                    {
                        "type": "text",
                        "text": self._format_result(result)
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}", exc_info=True)
            raise
    
    def _format_result(self, result: Any) -> str:
        """Format result as text for MCP response"""
        import json
        if isinstance(result, dict):
            return json.dumps(result, indent=2, ensure_ascii=False)
        elif isinstance(result, list):
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            return str(result)


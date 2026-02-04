"""
Adapter for TaskRoutes to MCP interface

This adapter bridges TaskRoutes (protocol-agnostic task handlers) with MCP protocol.
Routing is driven by the capabilities registry.
"""

from typing import Any, Dict, Optional, Type

from starlette.requests import Request

from apflow.api.capabilities import get_mcp_tool_name_to_operation
from apflow.api.routes.tasks import TaskRoutes
from apflow.logger import get_logger

logger = get_logger(__name__)


class TaskRoutesAdapter:
    """
    Adapter to convert MCP tool calls to TaskRoutes method calls.

    Uses capabilities registry for routing: each MCP tool name maps to
    a handler method on TaskRoutes via OperationDef.get_handler_method().
    """

    def __init__(self, task_routes_class: Optional[Type[TaskRoutes]] = None):
        """
        Initialize adapter with TaskRoutes instance

        Args:
            task_routes_class: Optional custom TaskRoutes class to use instead of default TaskRoutes.
        """
        from apflow.core.config import get_task_model_class

        task_routes_cls = task_routes_class or TaskRoutes
        self.task_routes = task_routes_cls(
            task_model_class=get_task_model_class(),
            verify_token_func=None,
            verify_permission_func=None,
        )

    def _get_request_or_none(self, request: Optional[Request]) -> Optional[Request]:
        """Get request object or None (stdio mode has no request)."""
        return request

    async def call_by_tool_name(
        self,
        tool_name: str,
        params: Dict[str, Any],
        request: Optional[Request] = None,
    ) -> Any:
        """
        Route an MCP tool call to the appropriate TaskRoutes handler.

        Uses the capabilities registry to find the handler method for the tool name.
        Falls back to legacy routing for backward compatibility.

        Args:
            tool_name: MCP tool name (e.g. "execute_task", "create_task")
            params: Tool arguments
            request: Optional Starlette Request object

        Returns:
            Handler result
        """
        tool_map = get_mcp_tool_name_to_operation()
        op = tool_map.get(tool_name)
        if not op:
            raise ValueError(f"Unknown MCP tool: {tool_name}")

        handler_name = op.get_handler_method()
        request_id = str(params.pop("request_id", ""))
        req = self._get_request_or_none(request)

        # Special handling for create_task: support both single and array format
        if handler_name == "handle_task_create":
            return await self._handle_create(params, req, request_id)

        # Special handling for execute: may return StreamingResponse
        if handler_name == "handle_task_execute":
            return await self._handle_execute(params, req, request_id)

        handler = getattr(self.task_routes, handler_name, None)
        if handler is None:
            raise ValueError(
                f"TaskRoutes has no handler method: {handler_name} "
                f"(mapped from MCP tool: {tool_name})"
            )

        return await handler(params, req, request_id)

    async def _handle_create(
        self,
        params: Dict[str, Any],
        request: Optional[Request],
        request_id: str,
    ) -> Any:
        """Handle create_task with both single-task and array formats."""
        if "tasks" in params:
            tasks = params["tasks"]
        else:
            tasks = [params]
        return await self.task_routes.handle_task_create(tasks, request, request_id)

    async def _handle_execute(
        self,
        params: Dict[str, Any],
        request: Optional[Request],
        request_id: str,
    ) -> Any:
        """Handle execute_task, converting StreamingResponse if needed."""
        result = await self.task_routes.handle_task_execute(params, request, request_id)
        # StreamingResponse cannot be serialized for MCP; return as-is and let caller handle
        if hasattr(result, "status_code"):
            return result
        return result

    # ── Legacy direct methods (kept for backward compatibility) ─────

    async def execute_task(self, params: Dict[str, Any], request: Optional[Request] = None) -> Any:
        """Execute a task via TaskRoutes"""
        return await self.call_by_tool_name("execute_task", dict(params), request)

    async def create_task(self, params: Dict[str, Any], request: Optional[Request] = None) -> Any:
        """Create a task via TaskRoutes"""
        return await self.call_by_tool_name("create_task", dict(params), request)

    async def get_task(self, params: Dict[str, Any], request: Optional[Request] = None) -> Any:
        """Get a task by ID via TaskRoutes"""
        return await self.call_by_tool_name("get_task", dict(params), request)

    async def update_task(self, params: Dict[str, Any], request: Optional[Request] = None) -> Any:
        """Update a task via TaskRoutes"""
        return await self.call_by_tool_name("update_task", dict(params), request)

    async def delete_task(self, params: Dict[str, Any], request: Optional[Request] = None) -> Any:
        """Delete a task via TaskRoutes"""
        return await self.call_by_tool_name("delete_task", dict(params), request)

    async def list_tasks(self, params: Dict[str, Any], request: Optional[Request] = None) -> Any:
        """List tasks via TaskRoutes"""
        return await self.call_by_tool_name("list_tasks", dict(params), request)

    async def get_task_status(
        self, params: Dict[str, Any], request: Optional[Request] = None
    ) -> Any:
        """Get task status via TaskRoutes"""
        return await self.call_by_tool_name("get_task_status", dict(params), request)

    async def cancel_task(self, params: Dict[str, Any], request: Optional[Request] = None) -> Any:
        """Cancel a task via TaskRoutes"""
        return await self.call_by_tool_name("cancel_task", dict(params), request)

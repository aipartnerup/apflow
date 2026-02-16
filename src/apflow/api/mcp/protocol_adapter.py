"""MCP Protocol Adapter implementing ProtocolAdapter interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from apflow.logger import get_logger

if TYPE_CHECKING:
    from apflow.api.protocol_types import ProtocolAdapterConfig

logger = get_logger(__name__)


class MCPProtocolAdapter:
    """Adapter wrapping the existing MCP server as a ProtocolAdapter.

    Delegates to McpServer and FastAPI creation for all real work,
    preserving existing behavior while conforming to the unified interface.
    """

    def __init__(self) -> None:
        self._config: ProtocolAdapterConfig | None = None

    @property
    def protocol_name(self) -> str:
        return "mcp"

    @property
    def supported_operations(self) -> list[str]:
        from apflow.api.capabilities import get_all_operations

        return [op.id for op in get_all_operations()]

    def create_app(self, config: ProtocolAdapterConfig) -> Any:
        """Create MCP FastAPI application using existing McpServer."""
        from fastapi import FastAPI

        from apflow import __version__
        from apflow.api.mcp.server import McpServer

        self._config = config

        logger.info(
            "MCPProtocolAdapter creating app: System routes=%s, Docs=%s",
            config.enable_system_routes,
            config.enable_docs,
        )

        app = FastAPI(
            title="apflow MCP Server",
            description="Model Context Protocol server for task orchestration",
            version=__version__,
        )

        mcp_server = McpServer(task_routes_class=config.task_routes_class)
        for route in mcp_server.get_http_routes():
            app.routes.append(route)

        if config.enable_system_routes:
            from starlette.routing import Route

            from apflow.api.routes.system import SystemRoutes
            from apflow.core.config import get_task_model_class

            system_routes_instance = SystemRoutes(task_model_class=get_task_model_class())  # type: ignore[arg-type]

            async def system_handler(request: Any) -> Any:
                return await system_routes_instance.handle_system_requests(request)

            app.routes.append(Route("/system", system_handler, methods=["POST"]))

        if config.enable_docs:
            try:
                from apflow.api.docs.swagger_ui import setup_swagger_ui  # type: ignore[attr-defined]

                setup_swagger_ui(app)
            except ImportError:
                logger.debug("Swagger UI setup not available for MCP server")

        return app

    async def handle_request(self, operation_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Delegate request to TaskRoutes handler by operation_id."""
        from apflow.api.capabilities import dispatch_operation

        return await dispatch_operation(
            operation_id,
            params,
            verify_token_func=self._config.verify_token_func if self._config else None,
            verify_permission_func=self._config.verify_permission_func if self._config else None,
        )

    async def handle_streaming_request(
        self, operation_id: str, params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """MCP does not natively support streaming; yields single result."""
        result = await self.handle_request(operation_id, params)
        yield result

    def get_discovery_info(self) -> dict[str, Any]:
        """Return discovery info for this adapter."""
        from apflow.api.capabilities import get_all_operations

        return {
            "protocol": "mcp",
            "status": "active",
            "operations": [op.id for op in get_all_operations()],
            "description": "MCP (Model Context Protocol) Server",
        }

"""
Application creation for apflow

This module provides functions to create API applications based on different protocols.
"""

from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

from apflow import __version__
from apflow.api.protocols import (
    check_protocol_dependency,
    get_protocol_dependency_info,
    get_protocol_from_env,
)
from apflow.core.utils.helpers import get_url_with_host_and_port
from apflow.logger import get_logger

if TYPE_CHECKING:
    from apflow.api.protocol_types import ProtocolAdapterConfig
    from apflow.api.routes.tasks import TaskRoutes

logger = get_logger(__name__)


def create_a2a_server(
    jwt_secret_key: str | None,
    jwt_algorithm: str,
    base_url: str,
    enable_system_routes: bool,
    enable_docs: bool = True,
    task_routes_class: type[TaskRoutes] | None = None,
    custom_routes: list[Any] | None = None,
    custom_middleware: list[Any] | None = None,
    verify_token_func: Any | None = None,
    verify_permission_func: Any | None = None,
) -> Any:
    """Create A2A Protocol Server."""
    from apflow.api.a2a.server import create_a2a_server

    from apflow.core.config import get_task_model_class

    task_model_class = get_task_model_class()

    logger.info(
        "A2A Protocol Server configuration: "
        "JWT enabled=%s, System routes=%s, Docs=%s, TaskModel=%s",
        bool(jwt_secret_key or verify_token_func),
        enable_system_routes,
        enable_docs,
        task_model_class.__name__,
    )

    a2a_server_instance = create_a2a_server(
        verify_token_func=verify_token_func,
        verify_token_secret_key=jwt_secret_key,
        verify_token_algorithm=jwt_algorithm,
        base_url=base_url,
        enable_system_routes=enable_system_routes,
        enable_docs=enable_docs,
        task_routes_class=task_routes_class,
        custom_routes=custom_routes,
        custom_middleware=custom_middleware,
        verify_permission_func=verify_permission_func,
    )

    return a2a_server_instance.build()


def create_mcp_server(
    base_url: str,
    enable_system_routes: bool,
    enable_docs: bool = True,
    task_routes_class: type[TaskRoutes] | None = None,
) -> Any:
    """Create MCP (Model Context Protocol) Server."""
    from fastapi import FastAPI

    from apflow.api.mcp.server import McpServer

    logger.info(
        "MCP Server configuration: System routes=%s, Docs=%s",
        enable_system_routes,
        enable_docs,
    )

    app = FastAPI(
        title="apflow MCP Server",
        description="Model Context Protocol server for task orchestration",
        version=__version__,
    )

    mcp_server = McpServer(task_routes_class=task_routes_class)

    mcp_routes = mcp_server.get_http_routes()
    for route in mcp_routes:
        app.routes.append(route)

    if enable_system_routes:
        from starlette.routing import Route

        from apflow.api.routes.system import SystemRoutes
        from apflow.core.config import get_task_model_class

        system_routes = SystemRoutes(task_model_class=get_task_model_class())  # type: ignore[arg-type]

        async def system_handler(request: Any) -> Any:
            return await system_routes.handle_system_requests(request)

        app.routes.append(Route("/system", system_handler, methods=["POST"]))

    if enable_docs:
        try:
            from apflow.api.docs.swagger_ui import setup_swagger_ui  # type: ignore[attr-defined]

            setup_swagger_ui(app)
        except ImportError:
            logger.debug("Swagger UI setup not available for MCP server")

    return app


def create_rest_server() -> Any:
    """Create REST API Server (future implementation)."""
    raise NotImplementedError(
        "REST API server is not yet implemented. "
        "Please use A2A Protocol Server (set APFLOW_API_PROTOCOL=a2a or leave unset)."
    )


def _resolve_protocol(protocol: str | None) -> str:
    """Resolve and validate the protocol name."""
    if protocol is None:
        resolved = get_protocol_from_env()
    else:
        resolved = protocol.lower()

    check_protocol_dependency(resolved)

    _, _, description = get_protocol_dependency_info(resolved)
    logger.info("Creating %s application", description)
    return resolved


def _load_env_config(
    task_routes_class: type[TaskRoutes] | None,
    custom_routes: list[Any] | None,
    custom_middleware: list[Any] | None,
    verify_token_func: Any | None,
    verify_permission_func: Any | None,
) -> ProtocolAdapterConfig:
    """Load protocol adapter configuration from environment variables."""
    from apflow.api.protocol_types import ProtocolAdapterConfig

    jwt_secret_key = os.getenv("APFLOW_JWT_SECRET")
    jwt_algorithm = os.getenv("APFLOW_JWT_ALGORITHM", "HS256")

    if jwt_secret_key:
        logger.info("JWT secret key found (length: %d)", len(jwt_secret_key))
    else:
        logger.info("JWT secret key not set - authentication disabled")

    enable_system_routes = os.getenv("APFLOW_ENABLE_SYSTEM_ROUTES", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    enable_docs = os.getenv("APFLOW_ENABLE_DOCS", "true").lower() in ("true", "1", "yes")
    host = os.getenv("APFLOW_API_HOST", os.getenv("API_HOST", "0.0.0.0"))
    port = int(os.getenv("APFLOW_API_PORT", os.getenv("API_PORT", "8000")))
    base_url = os.getenv("APFLOW_BASE_URL", get_url_with_host_and_port(host, port))

    return ProtocolAdapterConfig(
        base_url=base_url,
        enable_system_routes=enable_system_routes,
        enable_docs=enable_docs,
        jwt_secret_key=jwt_secret_key,
        jwt_algorithm=jwt_algorithm,
        task_routes_class=task_routes_class,
        custom_routes=custom_routes,
        custom_middleware=custom_middleware,
        verify_token_func=verify_token_func,
        verify_permission_func=verify_permission_func,
    )


def create_app_by_protocol(
    protocol: str | None = None,
    task_routes_class: type[TaskRoutes] | None = None,
    custom_routes: list[Any] | None = None,
    custom_middleware: list[Any] | None = None,
    verify_token_func: Any | None = None,
    verify_permission_func: Any | None = None,
) -> Any:
    """Create application based on protocol type.

    This is the main entry point for creating API applications.
    Delegates to the protocol registry to find the appropriate adapter.
    """
    from apflow.api.protocols import get_protocol_registry

    resolved = _resolve_protocol(protocol)
    config = _load_env_config(
        task_routes_class=task_routes_class,
        custom_routes=custom_routes,
        custom_middleware=custom_middleware,
        verify_token_func=verify_token_func,
        verify_permission_func=verify_permission_func,
    )
    adapter = get_protocol_registry().get_adapter(resolved)
    return adapter.create_app(config)

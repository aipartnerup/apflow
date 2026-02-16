"""A2A Protocol Adapter implementing ProtocolAdapter interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from apflow.logger import get_logger

if TYPE_CHECKING:
    from apflow.api.protocol_types import ProtocolAdapterConfig

logger = get_logger(__name__)


class A2AProtocolAdapter:
    """Adapter wrapping the existing A2A server as a ProtocolAdapter.

    Delegates to create_a2a_server() for app creation, preserving all
    existing behavior while conforming to the unified interface.
    """

    def __init__(self) -> None:
        self._config: ProtocolAdapterConfig | None = None

    @property
    def protocol_name(self) -> str:
        return "a2a"

    @property
    def supported_operations(self) -> list[str]:
        from apflow.api.capabilities import get_all_operations

        return [op.id for op in get_all_operations()]

    def create_app(self, config: ProtocolAdapterConfig) -> Any:
        """Create A2A ASGI application using existing create_a2a_server()."""
        from apflow.api.a2a.server import create_a2a_server

        self._config = config

        logger.info(
            "A2AProtocolAdapter creating app: " "JWT enabled=%s, System routes=%s, Docs=%s",
            bool(config.jwt_secret_key or config.verify_token_func),
            config.enable_system_routes,
            config.enable_docs,
        )

        server_instance = create_a2a_server(
            verify_token_func=config.verify_token_func,
            verify_token_secret_key=config.jwt_secret_key,
            verify_token_algorithm=config.jwt_algorithm,
            base_url=config.base_url,
            enable_system_routes=config.enable_system_routes,
            enable_docs=config.enable_docs,
            task_routes_class=config.task_routes_class,
            custom_routes=config.custom_routes,
            custom_middleware=config.custom_middleware,
            verify_permission_func=config.verify_permission_func,
        )
        return server_instance.build()

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
        """Delegate streaming request. Yields single result."""
        result = await self.handle_request(operation_id, params)
        yield result

    def get_discovery_info(self) -> dict[str, Any]:
        """Return discovery info for this adapter."""
        from apflow.api.capabilities import get_agent_action_operations

        return {
            "protocol": "a2a",
            "status": "active",
            "operations": [op.id for op in get_agent_action_operations()],
            "description": "A2A Protocol Server (Agent-to-Agent)",
        }

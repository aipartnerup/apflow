"""GraphQL Protocol Adapter for apflow."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from apflow.logger import get_logger

if TYPE_CHECKING:
    from apflow.api.protocol_types import ProtocolAdapterConfig

logger = get_logger(__name__)


class GraphQLProtocolAdapter:
    """Protocol adapter that exposes apflow via a GraphQL endpoint.

    Implements the ProtocolAdapter interface using structural subtyping.
    Creates a Strawberry ASGI application mounted inside a Starlette app,
    with optional system routes.
    """

    def __init__(self) -> None:
        self._config: ProtocolAdapterConfig | None = None

    @property
    def protocol_name(self) -> str:
        return "graphql"

    @property
    def supported_operations(self) -> list[str]:
        from apflow.api.capabilities import get_all_operations

        return [op.id for op in get_all_operations()]

    def create_app(self, config: ProtocolAdapterConfig) -> Any:
        """Create a Starlette ASGI application with the GraphQL endpoint."""
        from starlette.applications import Starlette
        from starlette.routing import Mount
        from strawberry.asgi import GraphQL

        from apflow.api.graphql.schema import schema
        from apflow.api.routes.tasks import TaskRoutes
        from apflow.core.config import get_task_model_class

        self._config = config

        logger.info(
            "GraphQLProtocolAdapter creating app: " "System routes=%s, Docs=%s",
            config.enable_system_routes,
            config.enable_docs,
        )

        task_routes_cls = config.task_routes_class or TaskRoutes
        task_routes = task_routes_cls(
            task_model_class=get_task_model_class(),  # type: ignore[arg-type]
            verify_token_func=config.verify_token_func,
            verify_permission_func=config.verify_permission_func,
        )

        class _ApflowGraphQL(GraphQL):  # type: ignore[type-arg]
            """Subclass to inject task_routes into context."""

            async def get_context(  # type: ignore[override]
                self, request: Any, response: Any
            ) -> dict[str, Any]:
                return {
                    "request": request,
                    "response": response,
                    "task_routes": task_routes,
                }

        graphql_app = _ApflowGraphQL(
            schema,
            graphiql=config.enable_docs,
        )

        routes: list[Any] = [Mount("/graphql", app=graphql_app)]

        if config.enable_system_routes:
            from starlette.routing import Route

            from apflow.api.routes.system import SystemRoutes

            system_routes = SystemRoutes(
                task_model_class=get_task_model_class(),  # type: ignore[arg-type]
            )

            async def system_handler(request: Any) -> Any:
                return await system_routes.handle_system_requests(request)

            routes.append(Route("/system", system_handler, methods=["POST"]))

        return Starlette(routes=routes)

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
        """Yield single result from handle_request."""
        result = await self.handle_request(operation_id, params)
        yield result

    def get_discovery_info(self) -> dict[str, Any]:
        """Return metadata for the protocol discovery endpoint."""
        return {
            "protocol": "graphql",
            "status": "active",
            "endpoint": "/graphql",
            "subscription_protocols": ["graphql-transport-ws"],
            "operations": self.supported_operations,
            "description": "GraphQL Protocol Server",
        }

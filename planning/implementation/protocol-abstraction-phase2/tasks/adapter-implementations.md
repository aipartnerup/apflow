# T2: Implement A2AProtocolAdapter and MCPProtocolAdapter

## Goal

Create concrete adapter classes that implement the `ProtocolAdapter` interface by wrapping the existing A2A and MCP server creation logic. Each adapter delegates to the existing server modules, preserving all current behavior while conforming to the unified protocol interface.

## Files Involved

| Action | File |
|--------|------|
| Create | `src/apflow/api/a2a/protocol_adapter.py` |
| Create | `src/apflow/api/mcp/protocol_adapter.py` |
| Create | `tests/api/a2a/test_a2a_protocol_adapter.py` |
| Create | `tests/api/mcp/test_mcp_protocol_adapter.py` |

## Steps

### 1. Write A2A adapter tests first (`tests/api/a2a/test_a2a_protocol_adapter.py`)

```python
"""Tests for A2AProtocolAdapter."""

import pytest
from unittest.mock import patch, MagicMock
from apflow.api.protocols import ProtocolAdapter, ProtocolAdapterConfig


class TestA2AProtocolAdapter:
    """Test A2AProtocolAdapter conformance and behavior."""

    @pytest.fixture
    def adapter(self):
        from apflow.api.a2a.protocol_adapter import A2AProtocolAdapter
        return A2AProtocolAdapter()

    def test_satisfies_protocol_adapter_interface(self, adapter):
        """A2AProtocolAdapter passes isinstance(obj, ProtocolAdapter)."""
        assert isinstance(adapter, ProtocolAdapter)

    def test_protocol_name_returns_a2a(self, adapter):
        """protocol_name property returns 'a2a'."""
        assert adapter.protocol_name == "a2a"

    def test_supported_operations_returns_agent_action_ids(self, adapter):
        """supported_operations includes agent action operation IDs."""
        ops = adapter.supported_operations
        assert isinstance(ops, list)
        assert len(ops) > 0
        # Agent actions from capabilities registry
        assert "tasks.execute" in ops
        assert "tasks.generate" in ops
        assert "tasks.cancel" in ops

    def test_get_discovery_info_returns_correct_structure(self, adapter):
        """get_discovery_info returns dict with protocol, status, operations."""
        info = adapter.get_discovery_info()
        assert info["protocol"] == "a2a"
        assert "status" in info
        assert "operations" in info
        assert isinstance(info["operations"], list)

    def test_create_app_produces_asgi_app(self, adapter):
        """create_app returns an ASGI-compatible application."""
        config = ProtocolAdapterConfig(
            base_url="http://localhost:8000",
            enable_system_routes=True,
            enable_docs=True,
            jwt_secret_key=None,
            jwt_algorithm="HS256",
            task_routes_class=None,
            custom_routes=None,
            custom_middleware=None,
            verify_token_func=None,
            verify_permission_func=None,
        )
        app = adapter.create_app(config)
        assert app is not None
        # Starlette/ASGI apps are callable
        assert callable(app)
```

### 2. Write MCP adapter tests first (`tests/api/mcp/test_mcp_protocol_adapter.py`)

```python
"""Tests for MCPProtocolAdapter."""

import pytest
from unittest.mock import patch, MagicMock
from apflow.api.protocols import ProtocolAdapter, ProtocolAdapterConfig


class TestMCPProtocolAdapter:
    """Test MCPProtocolAdapter conformance and behavior."""

    @pytest.fixture
    def adapter(self):
        from apflow.api.mcp.protocol_adapter import MCPProtocolAdapter
        return MCPProtocolAdapter()

    def test_satisfies_protocol_adapter_interface(self, adapter):
        """MCPProtocolAdapter passes isinstance(obj, ProtocolAdapter)."""
        assert isinstance(adapter, ProtocolAdapter)

    def test_protocol_name_returns_mcp(self, adapter):
        """protocol_name property returns 'mcp'."""
        assert adapter.protocol_name == "mcp"

    def test_supported_operations_returns_all_operations(self, adapter):
        """supported_operations includes all operation IDs."""
        ops = adapter.supported_operations
        assert isinstance(ops, list)
        assert len(ops) > 0
        # MCP exposes all operations (CRUD, query, monitoring, agent actions)
        assert "tasks.create" in ops
        assert "tasks.list" in ops
        assert "tasks.execute" in ops

    def test_get_discovery_info_returns_correct_structure(self, adapter):
        """get_discovery_info returns dict with protocol, status, operations."""
        info = adapter.get_discovery_info()
        assert info["protocol"] == "mcp"
        assert "status" in info
        assert "operations" in info
        assert isinstance(info["operations"], list)

    def test_create_app_produces_fastapi_app(self, adapter):
        """create_app returns a FastAPI application."""
        config = ProtocolAdapterConfig(
            base_url="http://localhost:8000",
            enable_system_routes=True,
            enable_docs=True,
            jwt_secret_key=None,
            jwt_algorithm="HS256",
            task_routes_class=None,
            custom_routes=None,
            custom_middleware=None,
            verify_token_func=None,
            verify_permission_func=None,
        )
        app = adapter.create_app(config)
        assert app is not None
```

### 3. Run tests (should fail -- no implementation yet)

```bash
pytest tests/api/a2a/test_a2a_protocol_adapter.py tests/api/mcp/test_mcp_protocol_adapter.py -v
```

### 4. Implement `A2AProtocolAdapter` (`src/apflow/api/a2a/protocol_adapter.py`)

Key design decisions:
- Wraps the existing `create_a2a_server()` function inside `create_app()`.
- Uses lazy imports to avoid triggering `ImportError` when `a2a-sdk` is not installed.
- Reports agent action operations from the capabilities registry.
- `handle_request()` delegates to the existing agent executor dispatch via `TaskRoutes`.

```python
"""A2A Protocol Adapter implementing ProtocolAdapter interface."""

from typing import Any, AsyncIterator

from apflow.api.protocols import ProtocolAdapterConfig
from apflow.logger import get_logger

logger = get_logger(__name__)


class A2AProtocolAdapter:
    """Adapter that wraps the existing A2A server as a ProtocolAdapter.

    Delegates to create_a2a_server() and agent executor for all real work,
    preserving existing behavior while conforming to the unified interface.
    """

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
        from apflow.core.config import get_task_model_class

        task_model_class = get_task_model_class()
        logger.info(
            f"A2AProtocolAdapter creating app: "
            f"JWT enabled={bool(config.jwt_secret_key or config.verify_token_func)}, "
            f"System routes={config.enable_system_routes}, "
            f"Docs={config.enable_docs}, "
            f"TaskModel={task_model_class.__name__}"
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

    async def handle_request(self, operation_id: str, params: dict) -> dict:
        """Delegate request to TaskRoutes handler by operation_id."""
        from apflow.api.capabilities import get_operation_by_id
        from apflow.api.routes.tasks import TaskRoutes

        op = get_operation_by_id(operation_id)
        if not op:
            raise ValueError(f"Unknown operation: {operation_id}")

        handler_name = op.get_handler_method()
        task_routes = TaskRoutes()
        handler = getattr(task_routes, handler_name, None)
        if handler is None:
            raise ValueError(f"No handler for operation: {operation_id}")

        return await handler(params, None, "")

    async def handle_streaming_request(
        self, operation_id: str, params: dict
    ) -> AsyncIterator[dict]:
        """Delegate streaming request. Only tasks.execute supports streaming."""
        result = await self.handle_request(operation_id, params)
        yield result

    def get_discovery_info(self) -> dict:
        """Return discovery info for this adapter."""
        from apflow.api.capabilities import get_agent_action_operations
        return {
            "protocol": "a2a",
            "status": "active",
            "operations": [op.id for op in get_agent_action_operations()],
            "description": "A2A Protocol Server (Agent-to-Agent)",
        }
```

### 5. Implement `MCPProtocolAdapter` (`src/apflow/api/mcp/protocol_adapter.py`)

Key design decisions:
- Wraps the existing `McpServer` + FastAPI creation logic inside `create_app()`.
- Delegates `handle_request()` to `McpServer.handle_request()`.
- Reports all operations from the capabilities registry (MCP exposes full CRUD/query/monitoring).

```python
"""MCP Protocol Adapter implementing ProtocolAdapter interface."""

from typing import Any, AsyncIterator

from apflow.api.protocols import ProtocolAdapterConfig
from apflow.logger import get_logger

logger = get_logger(__name__)


class MCPProtocolAdapter:
    """Adapter that wraps the existing MCP server as a ProtocolAdapter.

    Delegates to McpServer and FastAPI creation for all real work,
    preserving existing behavior while conforming to the unified interface.
    """

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
        from apflow.api.mcp.server import McpServer
        from apflow import __version__

        logger.info(
            f"MCPProtocolAdapter creating app: "
            f"System routes={config.enable_system_routes}, "
            f"Docs={config.enable_docs}"
        )

        app = FastAPI(
            title="apflow MCP Server",
            description="Model Context Protocol server for task orchestration",
            version=__version__,
        )

        mcp_server = McpServer(task_routes_class=config.task_routes_class)
        mcp_routes = mcp_server.get_http_routes()
        for route in mcp_routes:
            app.routes.append(route)

        if config.enable_system_routes:
            from starlette.routing import Route
            from apflow.api.routes.system import SystemRoutes

            system_routes_instance = SystemRoutes()

            async def system_handler(request):
                return await system_routes_instance.handle_system_requests(request)

            app.routes.append(Route("/system", system_handler, methods=["POST"]))

        if config.enable_docs:
            from apflow.api.docs.swagger_ui import setup_swagger_ui
            setup_swagger_ui(app)

        return app

    async def handle_request(self, operation_id: str, params: dict) -> dict:
        """Delegate request to McpServer via MCP tool dispatch."""
        from apflow.api.capabilities import get_operation_by_id
        from apflow.api.mcp.server import McpServer

        op = get_operation_by_id(operation_id)
        if not op:
            raise ValueError(f"Unknown operation: {operation_id}")

        mcp_server = McpServer()
        tool_name = op.get_mcp_tool_name()
        mcp_request = {
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": params},
        }
        return await mcp_server.handle_request(mcp_request)

    async def handle_streaming_request(
        self, operation_id: str, params: dict
    ) -> AsyncIterator[dict]:
        """MCP does not natively support streaming; yields single result."""
        result = await self.handle_request(operation_id, params)
        yield result

    def get_discovery_info(self) -> dict:
        """Return discovery info for this adapter."""
        from apflow.api.capabilities import get_all_operations
        return {
            "protocol": "mcp",
            "status": "active",
            "operations": [op.id for op in get_all_operations()],
            "description": "MCP (Model Context Protocol) Server",
        }
```

### 6. Run adapter tests (should pass now)

```bash
pytest tests/api/a2a/test_a2a_protocol_adapter.py tests/api/mcp/test_mcp_protocol_adapter.py -v
```

### 7. Run all existing tests to verify no regressions

```bash
pytest tests/api/ -v
```

### 8. Run linting and type checking

```bash
ruff check --fix src/apflow/api/a2a/protocol_adapter.py src/apflow/api/mcp/protocol_adapter.py
black src/apflow/api/a2a/protocol_adapter.py src/apflow/api/mcp/protocol_adapter.py
pyright src/apflow/api/a2a/protocol_adapter.py src/apflow/api/mcp/protocol_adapter.py
```

## Acceptance Criteria

- [ ] `A2AProtocolAdapter` class exists in `src/apflow/api/a2a/protocol_adapter.py`
- [ ] `MCPProtocolAdapter` class exists in `src/apflow/api/mcp/protocol_adapter.py`
- [ ] Both pass `isinstance(adapter, ProtocolAdapter)` check
- [ ] `A2AProtocolAdapter.protocol_name` returns `"a2a"`
- [ ] `MCPProtocolAdapter.protocol_name` returns `"mcp"`
- [ ] `A2AProtocolAdapter.create_app()` produces a callable ASGI application (wraps existing `create_a2a_server()`)
- [ ] `MCPProtocolAdapter.create_app()` produces a FastAPI application (wraps existing `McpServer`)
- [ ] `get_discovery_info()` returns `{ protocol, status, operations, description }` for each adapter
- [ ] Both adapters use lazy imports in `create_app()` to avoid `ImportError` when optional packages are missing
- [ ] All tests in `tests/api/a2a/test_a2a_protocol_adapter.py` pass
- [ ] All tests in `tests/api/mcp/test_mcp_protocol_adapter.py` pass
- [ ] All existing tests in `tests/api/` pass without modification (no regressions)
- [ ] `ruff check`, `black`, and `pyright` pass with zero errors

## Dependencies

- **Depends on**: T1 (protocol-adapter-interface) -- requires `ProtocolAdapter` Protocol and `ProtocolAdapterConfig`
- **Required by**: T3 (protocol-registry)

## Estimated Time

~5 hours

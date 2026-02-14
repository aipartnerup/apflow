# T4: Protocol Adapter, Server Integration, and End-to-End Tests

## Goal

Implement the `GraphQLProtocolAdapter` that conforms to the `ProtocolAdapter` interface, integrate it into the app factory and protocol registry, add the optional dependency to `pyproject.toml`, and write end-to-end integration tests that exercise the full stack from GraphQL query through ASGI to TaskRoutes.

## Files Involved

**Create:**
- `src/apflow/api/graphql/server.py` -- `GraphQLProtocolAdapter` implementation
- `tests/unit/api/graphql/test_server.py` -- Adapter unit tests
- `tests/integration/api/graphql/__init__.py` -- Integration test package marker
- `tests/integration/api/graphql/test_graphql_e2e.py` -- End-to-end integration tests

**Modify:**
- `src/apflow/api/graphql/__init__.py` -- Export `GraphQLProtocolAdapter`
- `src/apflow/api/protocols.py` -- Register `"graphql"` in `PROTOCOL_DEPENDENCIES`
- `src/apflow/api/app.py` -- Add `create_graphql_server()` and `"graphql"` case in `create_app_by_protocol()`
- `pyproject.toml` -- Add `graphql` optional dependency extra

**Reference (read-only):**
- `src/apflow/api/mcp/adapter.py` -- Adapter pattern: `TaskRoutesAdapter`
- `src/apflow/api/mcp/server.py` -- `McpServer` as structural reference for server class
- `src/apflow/api/capabilities.py` -- `OperationDef`, capabilities registry

## Steps

### 1. Write adapter unit tests (TDD -- red phase)

Create `tests/unit/api/graphql/test_server.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_graphql_adapter_protocol_name():
    from apflow.api.graphql.server import GraphQLProtocolAdapter
    adapter = GraphQLProtocolAdapter()
    assert adapter.protocol_name == "graphql"


def test_graphql_adapter_supported_operations():
    from apflow.api.graphql.server import GraphQLProtocolAdapter
    adapter = GraphQLProtocolAdapter()
    ops = adapter.supported_operations
    assert "task" in str(ops).lower()


def test_graphql_adapter_create_app_returns_asgi():
    from apflow.api.graphql.server import GraphQLProtocolAdapter
    adapter = GraphQLProtocolAdapter()
    app = adapter.create_app()
    # ASGI app must be callable
    assert callable(app)


def test_graphql_adapter_get_discovery_info():
    from apflow.api.graphql.server import GraphQLProtocolAdapter
    adapter = GraphQLProtocolAdapter()
    info = adapter.get_discovery_info()
    assert "graphql" in info.get("protocol", "").lower()
    assert "endpoint" in info


def test_graphql_adapter_graphiql_toggle():
    """GraphiQL should be enabled when APFLOW_ENABLE_DOCS=true."""
    with patch.dict("os.environ", {"APFLOW_ENABLE_DOCS": "true"}):
        from apflow.api.graphql.server import GraphQLProtocolAdapter
        adapter = GraphQLProtocolAdapter()
        app = adapter.create_app()
        # GraphiQL route should be accessible
        ...


def test_graphql_adapter_context_injects_task_routes():
    """ASGI context must include task_routes and DataLoaders."""
    from apflow.api.graphql.server import GraphQLProtocolAdapter
    adapter = GraphQLProtocolAdapter()
    context = adapter._build_context()
    assert "task_routes" in context
    assert "task_children_loader" in context
    assert "task_by_id_loader" in context
```

### 2. Write end-to-end integration tests

Create `tests/integration/api/graphql/test_graphql_e2e.py`:

```python
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def graphql_app():
    """Create a GraphQL ASGI application for testing."""
    from apflow.api.app import create_graphql_server
    return create_graphql_server(
        base_url="http://localhost:8000",
        enable_system_routes=False,
        enable_docs=True,
    )


@pytest.fixture
def client(graphql_app):
    return TestClient(graphql_app)


def test_graphql_endpoint_responds(client):
    """POST /graphql must accept a GraphQL query and return data."""
    response = client.post(
        "/graphql",
        json={"query": "{ __schema { queryType { name } } }"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["__schema"]["queryType"]["name"] == "Query"


def test_graphql_introspection(client):
    """Full introspection query must succeed."""
    response = client.post(
        "/graphql",
        json={"query": "{ __schema { types { name } } }"},
    )
    assert response.status_code == 200
    type_names = [t["name"] for t in response.json()["data"]["__schema"]["types"]]
    assert "TaskType" in type_names
    assert "TaskStatusEnum" in type_names


def test_create_and_get_task(client):
    """Full create -> get cycle via GraphQL."""
    # Create
    create_resp = client.post(
        "/graphql",
        json={
            "query": """
                mutation CreateTask($input: CreateTaskInput!) {
                    createTask(input: $input) {
                        id
                        name
                        status
                    }
                }
            """,
            "variables": {"input": {"name": "E2E Test Task"}},
        },
    )
    assert create_resp.status_code == 200
    task = create_resp.json()["data"]["createTask"]
    assert task["name"] == "E2E Test Task"
    task_id = task["id"]

    # Get
    get_resp = client.post(
        "/graphql",
        json={
            "query": """
                query GetTask($id: String!) {
                    task(taskId: $id) { id name status }
                }
            """,
            "variables": {"id": task_id},
        },
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["task"]["id"] == task_id


def test_list_tasks_with_pagination(client):
    """List query supports limit and offset."""
    resp = client.post(
        "/graphql",
        json={
            "query": """
                query ListTasks($limit: Int, $offset: Int) {
                    tasks(limit: $limit, offset: $offset) { id name }
                }
            """,
            "variables": {"limit": 5, "offset": 0},
        },
    )
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"]["tasks"], list)


def test_graphiql_available_when_docs_enabled(client):
    """GET /graphql should serve GraphiQL playground when docs enabled."""
    resp = client.get("/graphql", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert "graphiql" in resp.text.lower() or "graphql" in resp.text.lower()


@pytest.mark.asyncio
async def test_subscription_via_websocket(graphql_app):
    """WebSocket subscription must deliver task status updates."""
    from starlette.testclient import TestClient

    client = TestClient(graphql_app)
    with client.websocket_connect(
        "/graphql", subprotocols=["graphql-transport-ws"]
    ) as ws:
        # Connection init
        ws.send_json({"type": "connection_init"})
        response = ws.receive_json()
        assert response["type"] == "connection_ack"

        # Subscribe to task status changes (assumes a task exists)
        ws.send_json({
            "id": "1",
            "type": "subscribe",
            "payload": {
                "query": """
                    subscription TaskStatus($taskId: String!) {
                        taskStatusChanged(taskId: $taskId) { id status }
                    }
                """,
                "variables": {"taskId": "test-task-id"},
            },
        })

        # The subscription should start (even if no immediate events)
        # Close cleanly
        ws.send_json({"id": "1", "type": "complete"})


def test_create_app_by_protocol_graphql():
    """create_app_by_protocol('graphql') must return a working ASGI app."""
    from apflow.api.app import create_app_by_protocol
    app = create_app_by_protocol(protocol="graphql")
    assert callable(app)
```

### 3. Implement `GraphQLProtocolAdapter`

Create `src/apflow/api/graphql/server.py`:

```python
import os
from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING

from apflow.api.capabilities import get_all_operations
from apflow.api.graphql.loaders import create_task_by_id_loader, create_task_children_loader
from apflow.api.graphql.schema import schema
from apflow.api.routes.tasks import TaskRoutes
from apflow.core.config import get_task_model_class
from apflow.logger import get_logger

if TYPE_CHECKING:
    pass  # ProtocolAdapter from protocol-abstraction-phase2

logger = get_logger(__name__)


class GraphQLProtocolAdapter:
    """
    GraphQL protocol adapter for apflow.

    Implements the ProtocolAdapter interface (from protocol-abstraction-phase2)
    and creates a Strawberry ASGI application that delegates all business logic
    to TaskRoutes handler methods.
    """

    def __init__(
        self,
        task_routes_class: Optional[Type[TaskRoutes]] = None,
    ):
        task_routes_cls = task_routes_class or TaskRoutes
        self.task_routes = task_routes_cls(
            task_model_class=get_task_model_class(),
            verify_token_func=None,
            verify_permission_func=None,
        )

    @property
    def protocol_name(self) -> str:
        return "graphql"

    @property
    def supported_operations(self) -> List[str]:
        return [op.id for op in get_all_operations()]

    def _build_context(self) -> Dict[str, Any]:
        """Build the Strawberry context dict injected into every resolver."""
        return {
            "task_routes": self.task_routes,
            "task_by_id_loader": create_task_by_id_loader(self.task_routes),
            "task_children_loader": create_task_children_loader(self.task_routes),
        }

    def create_app(self) -> Any:
        """Create a Strawberry ASGI application."""
        from strawberry.asgi import GraphQL

        enable_graphiql = os.getenv("APFLOW_ENABLE_DOCS", "true").lower() in (
            "true", "1", "yes"
        )

        context = self._build_context()

        async def get_context() -> Dict[str, Any]:
            return context

        app = GraphQL(
            schema,
            graphiql=enable_graphiql,
            context_getter=get_context,
        )
        return app

    def get_discovery_info(self) -> Dict[str, Any]:
        return {
            "protocol": "graphql",
            "endpoint": "/graphql",
            "graphiql": os.getenv("APFLOW_ENABLE_DOCS", "true").lower() in (
                "true", "1", "yes"
            ),
            "subscription_protocols": ["graphql-transport-ws"],
            "operations_count": len(self.supported_operations),
        }
```

### 4. Register in protocol registry

Edit `src/apflow/api/protocols.py` -- add `"graphql"` entry to `PROTOCOL_DEPENDENCIES`:

```python
PROTOCOL_DEPENDENCIES = {
    "a2a": (
        "apflow.api.a2a.server",
        "a2a",
        "A2A Protocol Server",
    ),
    "mcp": (
        "apflow.api.mcp.server",
        "a2a",
        "MCP (Model Context Protocol) Server",
    ),
    "graphql": (
        "apflow.api.graphql.server",
        "graphql",
        "GraphQL Protocol Server",
    ),
}
```

### 5. Add `create_graphql_server()` to app factory

Edit `src/apflow/api/app.py`:

```python
def create_graphql_server(
    base_url: str,
    enable_system_routes: bool,
    enable_docs: bool = True,
    task_routes_class: Optional["Type[TaskRoutes]"] = None,
) -> Any:
    """Create GraphQL Protocol Server"""
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from apflow.api.graphql.server import GraphQLProtocolAdapter

    logger.info(
        f"GraphQL Server configuration: "
        f"System routes={enable_system_routes}, "
        f"Docs={enable_docs}"
    )

    adapter = GraphQLProtocolAdapter(task_routes_class=task_routes_class)
    graphql_app = adapter.create_app()

    routes = [Mount("/graphql", app=graphql_app)]

    if enable_system_routes:
        from apflow.api.routes.system import SystemRoutes
        system_routes = SystemRoutes()

        async def system_handler(request):
            return await system_routes.handle_system_requests(request)

        routes.append(Route("/system", system_handler, methods=["POST"]))

    return Starlette(routes=routes)
```

Add the `"graphql"` case in `create_app_by_protocol()`:

```python
    elif protocol == "graphql":
        return create_graphql_server(
            base_url=base_url,
            enable_system_routes=enable_system_routes,
            enable_docs=enable_docs,
            task_routes_class=task_routes_class,
        )
```

### 6. Add optional dependency in `pyproject.toml`

```toml
[project.optional-dependencies]
graphql = [
    "strawberry-graphql[asgi]>=0.230.0",
]
```

### 7. Guard imports for optional dependency isolation

Ensure all `strawberry` imports in the `graphql` package are guarded:

```python
# In src/apflow/api/graphql/__init__.py
try:
    from apflow.api.graphql.server import GraphQLProtocolAdapter
except ImportError:
    # strawberry-graphql not installed
    GraphQLProtocolAdapter = None  # type: ignore[assignment,misc]
```

### 8. Run full test suite

```bash
# Install graphql extra
pip install -e ".[graphql]"

# Unit tests
pytest tests/unit/api/graphql/ -v

# Integration tests
pytest tests/integration/api/graphql/ -v

# Full regression (ensure existing tests still pass)
pytest tests/ -v --ignore=tests/integration/api/graphql/

# Linting and type checking
ruff check --fix .
black .
pyright .
```

### 9. Manual smoke test

```bash
# Start the GraphQL server
APFLOW_API_PROTOCOL=graphql python -m apflow.api

# In another terminal:
# Test introspection
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { queryType { name } } }"}'

# Test GraphiQL (open in browser)
open http://localhost:8000/graphql
```

## Acceptance Criteria

- [ ] `GraphQLProtocolAdapter` implements `ProtocolAdapter` interface (protocol_name, supported_operations, create_app, get_discovery_info)
- [ ] `create_app()` returns a working ASGI application that handles POST /graphql
- [ ] GraphiQL playground is available at GET /graphql when `APFLOW_ENABLE_DOCS=true`
- [ ] GraphiQL is disabled when `APFLOW_ENABLE_DOCS=false`
- [ ] Context injection provides `task_routes`, `task_by_id_loader`, `task_children_loader` to all resolvers
- [ ] `"graphql"` is registered in `PROTOCOL_DEPENDENCIES` in `api/protocols.py`
- [ ] `create_graphql_server()` exists in `api/app.py` and works correctly
- [ ] `create_app_by_protocol("graphql")` returns a functional ASGI app
- [ ] `pyproject.toml` has `graphql = ["strawberry-graphql[asgi]>=0.230.0"]` in optional dependencies
- [ ] All `strawberry` imports are guarded behind `try/except ImportError`
- [ ] End-to-end test: introspection query returns expected schema types
- [ ] End-to-end test: create + get mutation/query cycle works
- [ ] End-to-end test: list with pagination works
- [ ] End-to-end test: WebSocket subscription connects and receives `connection_ack`
- [ ] All existing API tests pass unchanged (no regressions)
- [ ] `ruff check`, `black`, `pyright` report zero issues
- [ ] All tests pass: `pytest tests/unit/api/graphql/ tests/integration/api/graphql/ -v`

## Dependencies

- **Depends on:** T2 (resolvers -- query/mutation resolvers must be implemented), T3 (subscriptions -- subscription resolvers must be implemented)
- **Required by:** None (this is the final task in the graphql-adapter feature)

## Estimated Time

4-5 hours

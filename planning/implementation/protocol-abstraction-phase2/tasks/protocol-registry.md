# T3: Build ProtocolRegistry and Unified Server Factory

## Goal

Implement the `ProtocolRegistry` class that discovers, validates, and instantiates protocol adapters, then refactor `create_app_by_protocol()` in `app.py` to use the registry instead of the current `if/elif` chain. The registry auto-registers built-in A2A and MCP adapters and supports external adapter registration. After this task, adding a new protocol requires only implementing `ProtocolAdapter` and calling `registry.register()`.

## Files Involved

| Action | File |
|--------|------|
| Modify | `src/apflow/api/protocols.py` |
| Modify | `src/apflow/api/app.py` |
| Create | `tests/api/test_protocol_registry.py` |

## Steps

### 1. Write registry tests first (`tests/api/test_protocol_registry.py`)

```python
"""Tests for ProtocolRegistry and unified server factory."""

import pytest
from typing import Any, AsyncIterator
from apflow.api.protocols import (
    ProtocolAdapter,
    ProtocolAdapterConfig,
    ProtocolRegistry,
)


class FakeAdapter:
    """Minimal ProtocolAdapter for testing."""

    @property
    def protocol_name(self) -> str:
        return "fake"

    @property
    def supported_operations(self) -> list[str]:
        return ["fake.ping"]

    def create_app(self, config: ProtocolAdapterConfig) -> Any:
        return None

    async def handle_request(self, operation_id: str, params: dict) -> dict:
        return {"ok": True}

    async def handle_streaming_request(
        self, operation_id: str, params: dict
    ) -> AsyncIterator[dict]:
        yield {"ok": True}

    def get_discovery_info(self) -> dict:
        return {"protocol": "fake", "status": "active", "operations": ["fake.ping"]}


class TestProtocolRegistry:
    """Test ProtocolRegistry behavior."""

    @pytest.fixture
    def registry(self):
        return ProtocolRegistry()

    def test_register_adapter_class(self, registry):
        """register() stores an adapter class by its protocol_name."""
        registry.register(FakeAdapter)
        assert "fake" in registry.list_protocols()

    def test_get_adapter_returns_instance(self, registry):
        """get_adapter() instantiates and returns a ProtocolAdapter."""
        registry.register(FakeAdapter)
        adapter = registry.get_adapter("fake")
        assert isinstance(adapter, ProtocolAdapter)
        assert adapter.protocol_name == "fake"

    def test_get_adapter_raises_for_unknown_protocol(self, registry):
        """get_adapter() raises ValueError for unregistered protocol."""
        with pytest.raises(ValueError, match="Unknown protocol"):
            registry.get_adapter("nonexistent")

    def test_list_protocols_returns_all_names(self, registry):
        """list_protocols() returns all registered protocol names."""
        registry.register(FakeAdapter)
        protocols = registry.list_protocols()
        assert "fake" in protocols

    def test_duplicate_registration_overwrites(self, registry):
        """Registering same protocol_name twice overwrites the first."""

        class FakeAdapterV2:
            @property
            def protocol_name(self) -> str:
                return "fake"

            @property
            def supported_operations(self) -> list[str]:
                return ["fake.ping", "fake.pong"]

            def create_app(self, config: ProtocolAdapterConfig) -> Any:
                return None

            async def handle_request(self, operation_id: str, params: dict) -> dict:
                return {}

            async def handle_streaming_request(
                self, operation_id: str, params: dict
            ) -> AsyncIterator[dict]:
                yield {}

            def get_discovery_info(self) -> dict:
                return {"protocol": "fake", "status": "active", "operations": []}

        registry.register(FakeAdapter)
        registry.register(FakeAdapterV2)
        adapter = registry.get_adapter("fake")
        assert "fake.pong" in adapter.supported_operations

    def test_get_discovery_aggregates_all_adapters(self, registry):
        """get_discovery() returns aggregated info from all adapters."""
        registry.register(FakeAdapter)
        discovery = registry.get_discovery()
        assert "fake" in discovery
        assert discovery["fake"]["protocol"] == "fake"


class TestBuiltInAdaptersAutoRegistered:
    """Test that built-in A2A and MCP adapters are pre-registered."""

    def test_default_registry_has_a2a(self):
        from apflow.api.protocols import protocol_registry
        assert "a2a" in protocol_registry.list_protocols()

    def test_default_registry_has_mcp(self):
        from apflow.api.protocols import protocol_registry
        assert "mcp" in protocol_registry.list_protocols()


class TestCreateAppByProtocolBackwardCompatibility:
    """Verify create_app_by_protocol() still works with same signature."""

    def test_a2a_app_creation(self):
        from apflow.api.app import create_app_by_protocol
        app = create_app_by_protocol(protocol="a2a")
        assert app is not None
        assert callable(app)

    def test_mcp_app_creation(self):
        from apflow.api.app import create_app_by_protocol
        app = create_app_by_protocol(protocol="mcp")
        assert app is not None

    def test_unknown_protocol_raises_value_error(self):
        from apflow.api.app import create_app_by_protocol
        with pytest.raises(ValueError):
            create_app_by_protocol(protocol="nonexistent")
```

### 2. Run tests (should fail -- no registry implementation yet)

```bash
pytest tests/api/test_protocol_registry.py -v
```

### 3. Implement `ProtocolRegistry` in `protocols.py`

Add the `ProtocolRegistry` class and module-level singleton to `src/apflow/api/protocols.py`, after the `ProtocolAdapter` definition:

```python
import logging

logger = logging.getLogger(__name__)


class ProtocolRegistry:
    """Registry for protocol adapters.

    Discovers, validates, and instantiates ProtocolAdapter implementations.
    Supports both built-in and externally registered adapters.
    """

    def __init__(self) -> None:
        self._adapter_classes: dict[str, type] = {}

    def register(self, adapter_class: type) -> None:
        """Register a protocol adapter class.

        The class is instantiated to read its protocol_name, then stored
        by that name. Duplicate registrations overwrite with a warning.
        """
        instance = adapter_class()
        name = instance.protocol_name
        if name in self._adapter_classes:
            logger.warning(
                f"Overwriting existing adapter for protocol '{name}'"
            )
        self._adapter_classes[name] = adapter_class

    def get_adapter(self, protocol: str) -> "ProtocolAdapter":
        """Get an adapter instance for the given protocol name.

        Raises:
            ValueError: If protocol is not registered.
        """
        adapter_class = self._adapter_classes.get(protocol)
        if adapter_class is None:
            registered = ", ".join(self.list_protocols()) or "(none)"
            raise ValueError(
                f"Unknown protocol '{protocol}'. "
                f"Registered protocols: {registered}"
            )
        return adapter_class()

    def list_protocols(self) -> list[str]:
        """Return names of all registered protocols."""
        return list(self._adapter_classes.keys())

    def get_discovery(self) -> dict[str, dict]:
        """Return aggregated discovery info from all registered adapters."""
        result: dict[str, dict] = {}
        for name, adapter_class in self._adapter_classes.items():
            adapter = adapter_class()
            result[name] = adapter.get_discovery_info()
        return result


def _create_default_registry() -> ProtocolRegistry:
    """Create registry with built-in adapters pre-registered.

    Uses lazy imports to avoid ImportError when optional packages are missing.
    """
    registry = ProtocolRegistry()

    try:
        from apflow.api.a2a.protocol_adapter import A2AProtocolAdapter
        registry.register(A2AProtocolAdapter)
    except ImportError:
        logger.info("A2A adapter not available (missing dependencies)")

    try:
        from apflow.api.mcp.protocol_adapter import MCPProtocolAdapter
        registry.register(MCPProtocolAdapter)
    except ImportError:
        logger.info("MCP adapter not available (missing dependencies)")

    return registry


# Module-level singleton with built-in adapters pre-registered
protocol_registry = _create_default_registry()
```

### 4. Refactor `create_app_by_protocol()` in `app.py`

Replace the `if/elif` chain with registry delegation. Keep the function signature and all configuration logic identical.

The key change is replacing:
```python
# OLD
if protocol == "a2a":
    return create_a2a_server(...)
elif protocol == "mcp":
    return create_mcp_server(...)
elif protocol == "rest":
    return create_rest_server()
else:
    raise ValueError(...)
```

With:
```python
# NEW
from apflow.api.protocols import protocol_registry, ProtocolAdapterConfig

config = ProtocolAdapterConfig(
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

adapter = protocol_registry.get_adapter(protocol)
return adapter.create_app(config)
```

**Important**: Keep the existing `create_a2a_server()` and `create_mcp_server()` wrapper functions in `app.py` for direct-call backward compatibility. Only change the dispatch logic inside `create_app_by_protocol()`.

### 5. Run registry tests (should pass now)

```bash
pytest tests/api/test_protocol_registry.py -v
```

### 6. Run ALL existing tests to verify no regressions

```bash
pytest tests/api/ -v
```

This is critical -- the refactoring of `create_app_by_protocol()` must not break any existing test in `tests/api/test_main.py` or other test files.

### 7. Run linting and type checking

```bash
ruff check --fix src/apflow/api/protocols.py src/apflow/api/app.py
black src/apflow/api/protocols.py src/apflow/api/app.py
pyright src/apflow/api/protocols.py src/apflow/api/app.py
```

## Acceptance Criteria

- [ ] `ProtocolRegistry` class exists in `src/apflow/api/protocols.py` with `register()`, `get_adapter()`, `list_protocols()`, `get_discovery()` methods
- [ ] Module-level `protocol_registry` singleton is created with A2A and MCP pre-registered
- [ ] `protocol_registry.list_protocols()` returns `["a2a", "mcp"]` (order may vary)
- [ ] `protocol_registry.get_adapter("a2a")` returns an `A2AProtocolAdapter` instance
- [ ] `protocol_registry.get_adapter("mcp")` returns an `MCPProtocolAdapter` instance
- [ ] `protocol_registry.get_adapter("unknown")` raises `ValueError`
- [ ] Duplicate registration overwrites with a warning log
- [ ] `get_discovery()` returns aggregated info from all adapters
- [ ] `create_app_by_protocol()` uses the registry internally (same external signature, same return types)
- [ ] `create_app_by_protocol(protocol="a2a")` produces same app as before (callable ASGI)
- [ ] `create_app_by_protocol(protocol="mcp")` produces same app as before (FastAPI)
- [ ] All tests in `tests/api/test_protocol_registry.py` pass
- [ ] All existing tests in `tests/api/` pass without modification (zero regressions)
- [ ] `ruff check`, `black`, and `pyright` pass with zero errors
- [ ] A new protocol can be added by: (1) implementing `ProtocolAdapter`, (2) calling `protocol_registry.register()`

## Dependencies

- **Depends on**: T1 (protocol-adapter-interface), T2 (adapter-implementations)
- **Required by**: T4 (discovery-validation)

## Estimated Time

~4 hours

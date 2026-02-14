# T4: Enhanced Discovery Endpoint and Backward Compatibility Validation

## Goal

Enhance the `/tasks/methods` discovery endpoint to include per-protocol availability information sourced from the `ProtocolRegistry`. Run the full existing test suite to verify zero regressions from all prior tasks. Add integration tests verifying multi-protocol scenarios work end-to-end.

## Files Involved

| Action | File |
|--------|------|
| Modify | `src/apflow/api/capabilities.py` |
| Modify | Route handler for `/tasks/methods` (in `src/apflow/api/a2a/custom_starlette_app.py` or applicable route file) |
| Create | `tests/api/test_protocol_discovery.py` |

## Steps

### 1. Write discovery tests first (`tests/api/test_protocol_discovery.py`)

```python
"""Tests for enhanced protocol discovery endpoint."""

import pytest
from apflow.api.capabilities import get_methods_discovery
from apflow.api.protocols import ProtocolRegistry, protocol_registry


class TestEnhancedDiscoveryFunction:
    """Test get_methods_discovery() with protocol registry integration."""

    def test_discovery_includes_protocols_section(self):
        """Enhanced discovery response includes a 'protocols' section."""
        result = get_methods_discovery(registry=protocol_registry)
        assert "protocols" in result
        assert isinstance(result["protocols"], dict)

    def test_discovery_protocols_contain_a2a(self):
        """The protocols section includes A2A with correct status."""
        result = get_methods_discovery(registry=protocol_registry)
        protocols = result["protocols"]
        assert "a2a" in protocols
        assert protocols["a2a"]["status"] in ("active", "available", "not_installed")

    def test_discovery_protocols_contain_mcp(self):
        """The protocols section includes MCP with correct status."""
        result = get_methods_discovery(registry=protocol_registry)
        protocols = result["protocols"]
        assert "mcp" in protocols
        assert protocols["mcp"]["status"] in ("active", "available", "not_installed")

    def test_discovery_protocol_operations_match_capabilities(self):
        """Each protocol's operations list should be non-empty."""
        result = get_methods_discovery(registry=protocol_registry)
        for name, info in result["protocols"].items():
            assert "operations" in info
            assert isinstance(info["operations"], list)
            assert len(info["operations"]) > 0

    def test_discovery_backward_compatible(self):
        """Existing fields (total, categories, methods) are still present."""
        result = get_methods_discovery(registry=protocol_registry)
        assert "total" in result
        assert "categories" in result
        assert "methods" in result
        assert isinstance(result["total"], int)
        assert result["total"] > 0

    def test_discovery_without_registry_still_works(self):
        """Calling get_methods_discovery() without registry returns existing format."""
        result = get_methods_discovery()
        assert "total" in result
        assert "categories" in result
        assert "methods" in result
        # Without registry, protocols section may be absent or empty
        if "protocols" in result:
            assert result["protocols"] == {}


class TestProtocolDiscoveryWithCustomRegistry:
    """Test discovery with custom/empty registries."""

    def test_empty_registry_returns_empty_protocols(self):
        """Empty registry returns empty protocols section."""
        empty_registry = ProtocolRegistry()
        result = get_methods_discovery(registry=empty_registry)
        assert result["protocols"] == {}

    def test_custom_adapter_appears_in_discovery(self):
        """A custom-registered adapter appears in discovery output."""
        from typing import Any, AsyncIterator
        from apflow.api.protocols import ProtocolAdapterConfig

        class CustomAdapter:
            @property
            def protocol_name(self) -> str:
                return "custom"

            @property
            def supported_operations(self) -> list[str]:
                return ["custom.ping"]

            def create_app(self, config: ProtocolAdapterConfig) -> Any:
                return None

            async def handle_request(self, operation_id: str, params: dict) -> dict:
                return {}

            async def handle_streaming_request(
                self, operation_id: str, params: dict
            ) -> AsyncIterator[dict]:
                yield {}

            def get_discovery_info(self) -> dict:
                return {
                    "protocol": "custom",
                    "status": "active",
                    "operations": ["custom.ping"],
                }

        registry = ProtocolRegistry()
        registry.register(CustomAdapter)
        result = get_methods_discovery(registry=registry)
        assert "custom" in result["protocols"]
        assert result["protocols"]["custom"]["protocol"] == "custom"


class TestFullRegressionSuite:
    """Meta-tests verifying backward compatibility across the codebase.

    These tests import and exercise the same paths as existing tests
    to confirm no regressions from T1-T3 changes.
    """

    def test_create_app_by_protocol_a2a(self):
        """create_app_by_protocol('a2a') still returns a callable ASGI app."""
        from apflow.api.app import create_app_by_protocol
        app = create_app_by_protocol(protocol="a2a")
        assert app is not None
        assert callable(app)

    def test_create_app_by_protocol_mcp(self):
        """create_app_by_protocol('mcp') still returns an app."""
        from apflow.api.app import create_app_by_protocol
        app = create_app_by_protocol(protocol="mcp")
        assert app is not None

    def test_protocol_dependencies_dict_unchanged(self):
        """PROTOCOL_DEPENDENCIES dict in protocols.py is still intact."""
        from apflow.api.protocols import PROTOCOL_DEPENDENCIES
        assert "a2a" in PROTOCOL_DEPENDENCIES
        assert "mcp" in PROTOCOL_DEPENDENCIES

    def test_check_protocol_dependency_still_works(self):
        """check_protocol_dependency() still validates correctly."""
        from apflow.api.protocols import check_protocol_dependency
        # Should not raise for installed protocols
        check_protocol_dependency("a2a")
        check_protocol_dependency("mcp")

    def test_get_supported_protocols_still_works(self):
        """get_supported_protocols() returns same list."""
        from apflow.api.protocols import get_supported_protocols
        protocols = get_supported_protocols()
        assert "a2a" in protocols
        assert "mcp" in protocols
```

### 2. Run discovery tests (should fail -- `get_methods_discovery()` does not accept `registry` yet)

```bash
pytest tests/api/test_protocol_discovery.py -v
```

### 3. Update `get_methods_discovery()` in `capabilities.py`

Add an optional `registry` parameter to `get_methods_discovery()`. When provided, include a `protocols` section in the response. When omitted, the function behaves identically to the current implementation.

```python
def get_methods_discovery(
    registry: "ProtocolRegistry | None" = None,
) -> Dict[str, Any]:
    """Generate discovery response for GET /tasks/methods endpoint.

    Args:
        registry: Optional ProtocolRegistry. When provided, includes
                  per-protocol availability info in the response.

    Returns a structured summary of all available methods grouped by category,
    suitable for both human inspection and programmatic discovery.
    """
    from __future__ import annotations  # if needed for forward refs

    ops = get_all_operations()
    by_category: Dict[str, list[Dict[str, Any]]] = {}
    for op in ops:
        by_category.setdefault(op.category, []).append(op.to_discovery_dict())

    result: Dict[str, Any] = {
        "total": len(ops),
        "categories": list(by_category.keys()),
        "methods": by_category,
    }

    # Add per-protocol info when registry is provided
    if registry is not None:
        result["protocols"] = registry.get_discovery()
    else:
        result["protocols"] = {}

    return result
```

**Note**: The `from __future__ import annotations` must be at the top of the file if used. Alternatively, use `Optional["ProtocolRegistry"]` with a string annotation to avoid the circular import. The simplest approach is to use `TYPE_CHECKING`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apflow.api.protocols import ProtocolRegistry
```

And annotate the parameter as:
```python
def get_methods_discovery(
    registry: "ProtocolRegistry | None" = None,
) -> Dict[str, Any]:
```

### 4. Update the `/tasks/methods` route handler

Locate where `get_methods_discovery()` is called in the route handler and pass the `protocol_registry` singleton. This is likely in `src/apflow/api/a2a/custom_starlette_app.py` or `src/apflow/api/routes/`.

Find the handler:
```bash
grep -rn "get_methods_discovery" src/apflow/api/
```

Update the call to pass the registry:
```python
from apflow.api.protocols import protocol_registry

# In the route handler:
methods = get_methods_discovery(registry=protocol_registry)
```

### 5. Run discovery tests (should pass now)

```bash
pytest tests/api/test_protocol_discovery.py -v
```

### 6. Run the FULL existing test suite

This is the most critical step -- verify zero regressions across the entire `tests/api/` directory.

```bash
pytest tests/api/ -v --tb=short
```

If any test fails, analyze the failure and fix without changing the existing test expectations. The fix must be in the production code, not in the tests.

### 7. Run linting and type checking on all modified files

```bash
ruff check --fix src/apflow/api/capabilities.py src/apflow/api/protocols.py src/apflow/api/app.py
black src/apflow/api/capabilities.py src/apflow/api/protocols.py src/apflow/api/app.py
pyright src/apflow/api/capabilities.py src/apflow/api/protocols.py src/apflow/api/app.py
```

### 8. Verify the new protocol extensibility story

As a smoke test, confirm that a new protocol can be added with minimal code:

```python
# This should be all that's needed to add a new protocol:
from apflow.api.protocols import protocol_registry

class MyProtocolAdapter:
    # ... implement ProtocolAdapter interface ...
    pass

protocol_registry.register(MyProtocolAdapter)

# Now create_app_by_protocol(protocol="my_protocol") works
```

Verify this pattern works in a test within `tests/api/test_protocol_discovery.py` (already covered in `TestProtocolDiscoveryWithCustomRegistry`).

## Acceptance Criteria

- [ ] `get_methods_discovery()` accepts an optional `registry` parameter
- [ ] When `registry` is provided, the response includes a `protocols` section with per-protocol info
- [ ] Each protocol entry contains `protocol`, `status`, `operations`, and `description`
- [ ] When `registry` is omitted, the response is backward-compatible (existing fields unchanged)
- [ ] The `/tasks/methods` route handler passes `protocol_registry` to `get_methods_discovery()`
- [ ] All tests in `tests/api/test_protocol_discovery.py` pass
- [ ] **All existing tests in `tests/api/` pass without modification** (zero regressions from T1-T4)
- [ ] All existing tests in `tests/api/a2a/` pass without modification
- [ ] All existing tests in `tests/api/mcp/` pass without modification
- [ ] `ruff check`, `black`, and `pyright` pass with zero errors on all modified files
- [ ] Enhanced discovery response is backward-compatible (existing consumers see same `total`, `categories`, `methods` fields)

## Dependencies

- **Depends on**: T3 (protocol-registry) -- requires `ProtocolRegistry` and `protocol_registry` singleton
- **Required by**: nothing (final task)

## Estimated Time

~3 hours

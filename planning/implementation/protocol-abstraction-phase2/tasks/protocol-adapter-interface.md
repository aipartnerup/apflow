# T1: Define ProtocolAdapter Protocol and ProtocolAdapterConfig

## Goal

Define the formal `ProtocolAdapter` interface using PEP 544 `typing.Protocol` with `@runtime_checkable`, and a `ProtocolAdapterConfig` dataclass that centralizes configuration for all protocol adapters. This is the foundational interface that all subsequent tasks build upon.

## Files Involved

| Action | File |
|--------|------|
| Modify | `src/apflow/api/protocols.py` |
| Create | `tests/api/test_protocol_adapter.py` |

## Steps

### 1. Write tests first (`tests/api/test_protocol_adapter.py`)

Create the test file that validates the Protocol and config dataclass behavior before implementing them.

```python
"""Tests for ProtocolAdapter Protocol and ProtocolAdapterConfig."""

import pytest
from typing import AsyncIterator, Any

from apflow.api.protocols import ProtocolAdapter, ProtocolAdapterConfig


class TestProtocolAdapterConfig:
    """Test ProtocolAdapterConfig dataclass construction."""

    def test_config_with_required_fields(self):
        """Config can be constructed with all required fields."""
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
        assert config.base_url == "http://localhost:8000"
        assert config.jwt_algorithm == "HS256"

    def test_config_with_overrides(self):
        """Config fields can be overridden."""
        config = ProtocolAdapterConfig(
            base_url="https://prod.example.com",
            enable_system_routes=False,
            enable_docs=False,
            jwt_secret_key="my-secret",
            jwt_algorithm="RS256",
            task_routes_class=None,
            custom_routes=None,
            custom_middleware=None,
            verify_token_func=None,
            verify_permission_func=None,
        )
        assert config.jwt_secret_key == "my-secret"
        assert config.jwt_algorithm == "RS256"
        assert config.enable_docs is False


class TestProtocolAdapterProtocol:
    """Test ProtocolAdapter Protocol structural subtyping."""

    def test_conforming_class_passes_isinstance(self):
        """A class with all required members passes isinstance check."""

        class GoodAdapter:
            @property
            def protocol_name(self) -> str:
                return "test"

            @property
            def supported_operations(self) -> list[str]:
                return ["op.one"]

            def create_app(self, config: ProtocolAdapterConfig) -> Any:
                return None

            async def handle_request(self, operation_id: str, params: dict) -> dict:
                return {}

            async def handle_streaming_request(
                self, operation_id: str, params: dict
            ) -> AsyncIterator[dict]:
                yield {}

            def get_discovery_info(self) -> dict:
                return {}

        adapter = GoodAdapter()
        assert isinstance(adapter, ProtocolAdapter)

    def test_non_conforming_class_fails_isinstance(self):
        """A class missing required members fails isinstance check."""

        class BadAdapter:
            pass

        adapter = BadAdapter()
        assert not isinstance(adapter, ProtocolAdapter)

    def test_partial_conformance_fails(self):
        """A class with only some members fails isinstance check."""

        class PartialAdapter:
            @property
            def protocol_name(self) -> str:
                return "partial"

            def create_app(self, config: ProtocolAdapterConfig) -> Any:
                return None

        adapter = PartialAdapter()
        assert not isinstance(adapter, ProtocolAdapter)
```

### 2. Run the tests (they should fail -- no implementation yet)

```bash
pytest tests/api/test_protocol_adapter.py -v
```

### 3. Implement `ProtocolAdapter` and `ProtocolAdapterConfig` in `protocols.py`

Add the following to the **end** of `src/apflow/api/protocols.py`, keeping all existing code intact:

```python
from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol, runtime_checkable


@dataclass
class ProtocolAdapterConfig:
    """Shared configuration for all protocol adapters."""

    base_url: str
    enable_system_routes: bool
    enable_docs: bool
    jwt_secret_key: str | None
    jwt_algorithm: str
    task_routes_class: type | None
    custom_routes: list | None
    custom_middleware: list | None
    verify_token_func: Any | None
    verify_permission_func: Any | None


@runtime_checkable
class ProtocolAdapter(Protocol):
    """Protocol interface that all protocol adapters must implement.

    Uses PEP 544 structural subtyping -- adapters satisfy this interface
    without explicit inheritance, keeping them loosely coupled and testable.
    """

    @property
    def protocol_name(self) -> str: ...

    @property
    def supported_operations(self) -> list[str]: ...

    def create_app(self, config: ProtocolAdapterConfig) -> Any: ...

    async def handle_request(self, operation_id: str, params: dict) -> dict: ...

    async def handle_streaming_request(
        self, operation_id: str, params: dict
    ) -> AsyncIterator[dict]: ...

    def get_discovery_info(self) -> dict: ...
```

### 4. Run the tests again (they should pass)

```bash
pytest tests/api/test_protocol_adapter.py -v
```

### 5. Run linting and type checking

```bash
ruff check --fix src/apflow/api/protocols.py tests/api/test_protocol_adapter.py
black src/apflow/api/protocols.py tests/api/test_protocol_adapter.py
pyright src/apflow/api/protocols.py
```

### 6. Run existing tests to verify no regressions

```bash
pytest tests/api/test_main.py -v
```

## Acceptance Criteria

- [ ] `ProtocolAdapterConfig` dataclass is defined in `src/apflow/api/protocols.py` with all 10 fields
- [ ] `ProtocolAdapter` Protocol is defined with `@runtime_checkable` and 6 members: `protocol_name`, `supported_operations`, `create_app`, `handle_request`, `handle_streaming_request`, `get_discovery_info`
- [ ] All existing functions in `protocols.py` remain unchanged (backward compatibility)
- [ ] `isinstance(conforming_obj, ProtocolAdapter)` returns `True` for a class implementing all members
- [ ] `isinstance(non_conforming_obj, ProtocolAdapter)` returns `False` for a class missing members
- [ ] All tests in `tests/api/test_protocol_adapter.py` pass
- [ ] All existing tests in `tests/api/test_main.py` pass (no regressions)
- [ ] `ruff check`, `black`, and `pyright` pass with zero errors

## Dependencies

- **Depends on**: nothing
- **Required by**: T2 (adapter-implementations), T3 (protocol-registry)

## Estimated Time

~3 hours

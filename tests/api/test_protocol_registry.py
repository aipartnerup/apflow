"""Tests for ProtocolRegistry and unified server factory."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from apflow.api.protocols import (
    ProtocolAdapter,
    ProtocolAdapterConfig,
    ProtocolRegistry,
)


class _FakeAdapter:
    """Minimal ProtocolAdapter for testing."""

    @property
    def protocol_name(self) -> str:
        return "fake"

    @property
    def supported_operations(self) -> list[str]:
        return ["fake.ping"]

    def create_app(self, config: ProtocolAdapterConfig) -> Any:
        return None

    async def handle_request(self, operation_id: str, params: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    async def handle_streaming_request(
        self, operation_id: str, params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        yield {"ok": True}

    def get_discovery_info(self) -> dict[str, Any]:
        return {"protocol": "fake", "status": "active", "operations": ["fake.ping"]}


class TestProtocolRegistry:
    """Test ProtocolRegistry behavior."""

    def test_register_adapter_class(self) -> None:
        """register() stores an adapter class by its protocol_name."""
        registry = ProtocolRegistry()
        registry.register(_FakeAdapter)
        assert "fake" in registry.list_protocols()

    def test_get_adapter_returns_instance(self) -> None:
        """get_adapter() instantiates and returns a ProtocolAdapter."""
        registry = ProtocolRegistry()
        registry.register(_FakeAdapter)
        adapter = registry.get_adapter("fake")
        assert isinstance(adapter, ProtocolAdapter)
        assert adapter.protocol_name == "fake"

    def test_get_adapter_raises_for_unknown_protocol(self) -> None:
        """get_adapter() raises ValueError for unregistered protocol."""
        registry = ProtocolRegistry()
        with pytest.raises(ValueError, match="Unknown protocol"):
            registry.get_adapter("nonexistent")

    def test_list_protocols_returns_all_names(self) -> None:
        """list_protocols() returns all registered protocol names."""
        registry = ProtocolRegistry()
        registry.register(_FakeAdapter)
        assert "fake" in registry.list_protocols()

    def test_duplicate_registration_overwrites(self) -> None:
        """Registering same protocol_name twice overwrites the first."""

        class _FakeAdapterV2:
            @property
            def protocol_name(self) -> str:
                return "fake"

            @property
            def supported_operations(self) -> list[str]:
                return ["fake.ping", "fake.pong"]

            def create_app(self, config: ProtocolAdapterConfig) -> Any:
                return None

            async def handle_request(
                self, operation_id: str, params: dict[str, Any]
            ) -> dict[str, Any]:
                return {}

            async def handle_streaming_request(
                self, operation_id: str, params: dict[str, Any]
            ) -> AsyncIterator[dict[str, Any]]:
                yield {}

            def get_discovery_info(self) -> dict[str, Any]:
                return {"protocol": "fake", "status": "active", "operations": []}

        registry = ProtocolRegistry()
        registry.register(_FakeAdapter)
        registry.register(_FakeAdapterV2)
        adapter = registry.get_adapter("fake")
        assert "fake.pong" in adapter.supported_operations

    def test_get_discovery_aggregates_all_adapters(self) -> None:
        """get_discovery() returns aggregated info from all adapters."""
        registry = ProtocolRegistry()
        registry.register(_FakeAdapter)
        discovery = registry.get_discovery()
        assert "fake" in discovery
        assert discovery["fake"]["protocol"] == "fake"


class TestBuiltInAdaptersAutoRegistered:
    """Test that built-in A2A and MCP adapters are pre-registered."""

    def test_default_registry_has_a2a(self) -> None:
        from apflow.api.protocols import get_protocol_registry

        assert "a2a" in get_protocol_registry().list_protocols()

    def test_default_registry_has_mcp(self) -> None:
        from apflow.api.protocols import get_protocol_registry

        assert "mcp" in get_protocol_registry().list_protocols()


class TestCreateAppByProtocolBackwardCompatibility:
    """Verify create_app_by_protocol() still works with same signature."""

    def test_a2a_app_creation(self) -> None:
        from apflow.api.app import create_app_by_protocol

        app = create_app_by_protocol(protocol="a2a")
        assert app is not None
        assert callable(app)

    def test_mcp_app_creation(self) -> None:
        from apflow.api.app import create_app_by_protocol

        app = create_app_by_protocol(protocol="mcp")
        assert app is not None

    def test_unknown_protocol_raises_value_error(self) -> None:
        from apflow.api.app import create_app_by_protocol

        with pytest.raises(ValueError):
            create_app_by_protocol(protocol="nonexistent")

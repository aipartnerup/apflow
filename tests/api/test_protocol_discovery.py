"""Tests for enhanced protocol discovery endpoint."""

from typing import Any, AsyncIterator

from apflow.api.protocols import (
    ProtocolAdapterConfig,
    ProtocolRegistry,
    get_protocol_registry,
)


class TestEnhancedDiscoveryFunction:
    """Test get_methods_discovery() with protocol registry integration."""

    def test_discovery_includes_protocols_section(self) -> None:
        """Enhanced discovery response includes a 'protocols' section."""
        from apflow.api.capabilities import get_methods_discovery

        result = get_methods_discovery(registry=get_protocol_registry())
        assert "protocols" in result
        assert isinstance(result["protocols"], dict)

    def test_discovery_protocols_contain_a2a(self) -> None:
        """The protocols section includes A2A."""
        from apflow.api.capabilities import get_methods_discovery

        result = get_methods_discovery(registry=get_protocol_registry())
        protocols = result["protocols"]
        assert "a2a" in protocols
        assert "status" in protocols["a2a"]

    def test_discovery_protocols_contain_mcp(self) -> None:
        """The protocols section includes MCP."""
        from apflow.api.capabilities import get_methods_discovery

        result = get_methods_discovery(registry=get_protocol_registry())
        protocols = result["protocols"]
        assert "mcp" in protocols
        assert "status" in protocols["mcp"]

    def test_discovery_protocol_operations_match_capabilities(self) -> None:
        """Each protocol's operations list should be non-empty."""
        from apflow.api.capabilities import get_methods_discovery

        result = get_methods_discovery(registry=get_protocol_registry())
        for _name, info in result["protocols"].items():
            assert "operations" in info
            assert isinstance(info["operations"], list)
            assert len(info["operations"]) > 0

    def test_discovery_backward_compatible(self) -> None:
        """Existing fields (total, categories, methods) are still present."""
        from apflow.api.capabilities import get_methods_discovery

        result = get_methods_discovery(registry=get_protocol_registry())
        assert "total" in result
        assert "categories" in result
        assert "methods" in result
        assert isinstance(result["total"], int)
        assert result["total"] > 0

    def test_discovery_without_registry_still_works(self) -> None:
        """Calling get_methods_discovery() without registry returns existing format."""
        from apflow.api.capabilities import get_methods_discovery

        result = get_methods_discovery()
        assert "total" in result
        assert "categories" in result
        assert "methods" in result
        # Without registry, protocols section should be absent or empty
        if "protocols" in result:
            assert result["protocols"] == {}


class TestProtocolDiscoveryWithCustomRegistry:
    """Test discovery with custom/empty registries."""

    def test_empty_registry_returns_empty_protocols(self) -> None:
        """Empty registry returns empty protocols section."""
        from apflow.api.capabilities import get_methods_discovery

        empty_registry = ProtocolRegistry()
        result = get_methods_discovery(registry=empty_registry)
        assert result["protocols"] == {}

    def test_custom_adapter_appears_in_discovery(self) -> None:
        """A custom-registered adapter appears in discovery output."""
        from apflow.api.capabilities import get_methods_discovery

        class CustomAdapter:
            @property
            def protocol_name(self) -> str:
                return "custom"

            @property
            def supported_operations(self) -> list[str]:
                return ["custom.ping"]

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
    """Verify backward compatibility across the codebase."""

    def test_create_app_by_protocol_a2a(self) -> None:
        """create_app_by_protocol('a2a') still returns a callable ASGI app."""
        from apflow.api.app import create_app_by_protocol

        app = create_app_by_protocol(protocol="a2a")
        assert app is not None
        assert callable(app)

    def test_create_app_by_protocol_mcp(self) -> None:
        """create_app_by_protocol('mcp') still returns an app."""
        from apflow.api.app import create_app_by_protocol

        app = create_app_by_protocol(protocol="mcp")
        assert app is not None

    def test_protocol_dependencies_dict_unchanged(self) -> None:
        """PROTOCOL_DEPENDENCIES dict in protocols.py is still intact."""
        from apflow.api.protocols import PROTOCOL_DEPENDENCIES

        assert "a2a" in PROTOCOL_DEPENDENCIES
        assert "mcp" in PROTOCOL_DEPENDENCIES

    def test_check_protocol_dependency_still_works(self) -> None:
        """check_protocol_dependency() still validates correctly."""
        from apflow.api.protocols import check_protocol_dependency

        check_protocol_dependency("a2a")
        check_protocol_dependency("mcp")

    def test_get_supported_protocols_still_works(self) -> None:
        """get_supported_protocols() returns same list."""
        from apflow.api.protocols import get_supported_protocols

        protocols = get_supported_protocols()
        assert "a2a" in protocols
        assert "mcp" in protocols

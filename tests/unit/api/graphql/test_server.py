"""Tests for GraphQLProtocolAdapter."""

from __future__ import annotations

import pytest

from apflow.api.graphql.server import GraphQLProtocolAdapter
from apflow.api.protocols import ProtocolAdapterConfig


@pytest.fixture
def adapter() -> GraphQLProtocolAdapter:
    return GraphQLProtocolAdapter()


@pytest.fixture
def config() -> ProtocolAdapterConfig:
    return ProtocolAdapterConfig(
        base_url="http://localhost:8000",
        enable_system_routes=False,
        enable_docs=True,
    )


class TestProtocolName:
    """Tests for protocol_name property."""

    def test_returns_graphql(self, adapter: GraphQLProtocolAdapter) -> None:
        assert adapter.protocol_name == "graphql"


class TestSupportedOperations:
    """Tests for supported_operations property."""

    def test_returns_list_of_strings(self, adapter: GraphQLProtocolAdapter) -> None:
        ops = adapter.supported_operations
        assert isinstance(ops, list)
        assert len(ops) > 0
        assert all(isinstance(op, str) for op in ops)


class TestCreateApp:
    """Tests for create_app method."""

    def test_returns_callable_asgi_app(
        self, adapter: GraphQLProtocolAdapter, config: ProtocolAdapterConfig
    ) -> None:
        app = adapter.create_app(config)
        assert callable(app)

    def test_app_has_routes(
        self, adapter: GraphQLProtocolAdapter, config: ProtocolAdapterConfig
    ) -> None:
        app = adapter.create_app(config)
        assert hasattr(app, "routes")


class TestGetDiscoveryInfo:
    """Tests for get_discovery_info method."""

    def test_includes_protocol(self, adapter: GraphQLProtocolAdapter) -> None:
        info = adapter.get_discovery_info()
        assert info["protocol"] == "graphql"

    def test_includes_endpoint(self, adapter: GraphQLProtocolAdapter) -> None:
        info = adapter.get_discovery_info()
        assert info["endpoint"] == "/graphql"

    def test_includes_subscription_protocols(self, adapter: GraphQLProtocolAdapter) -> None:
        info = adapter.get_discovery_info()
        assert "graphql-transport-ws" in info["subscription_protocols"]

    def test_includes_operations(self, adapter: GraphQLProtocolAdapter) -> None:
        info = adapter.get_discovery_info()
        assert isinstance(info["operations"], list)
        assert len(info["operations"]) > 0


class TestHandleRequest:
    """Tests for handle_request method."""

    @pytest.mark.asyncio
    async def test_unknown_operation_raises(self, adapter: GraphQLProtocolAdapter) -> None:
        with pytest.raises(ValueError, match="Unknown operation"):
            await adapter.handle_request("nonexistent.op", {})


class TestHandleStreamingRequest:
    """Tests for handle_streaming_request method."""

    @pytest.mark.asyncio
    async def test_unknown_operation_raises(self, adapter: GraphQLProtocolAdapter) -> None:
        with pytest.raises(ValueError, match="Unknown operation"):
            async for _ in adapter.handle_streaming_request("nonexistent.op", {}):
                pass


class TestProtocolAdapterConformance:
    """Tests that GraphQLProtocolAdapter conforms to ProtocolAdapter."""

    def test_is_protocol_adapter(self, adapter: GraphQLProtocolAdapter) -> None:
        from apflow.api.protocols import ProtocolAdapter

        assert isinstance(adapter, ProtocolAdapter)

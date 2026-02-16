"""Tests for MCPProtocolAdapter."""

from typing import Any

from apflow.api.protocols import ProtocolAdapter, ProtocolAdapterConfig


class TestMCPProtocolAdapter:
    """Test MCPProtocolAdapter conformance and behavior."""

    def _make_adapter(self) -> Any:
        from apflow.api.mcp.protocol_adapter import MCPProtocolAdapter

        return MCPProtocolAdapter()

    def test_satisfies_protocol_adapter_interface(self) -> None:
        """MCPProtocolAdapter passes isinstance(obj, ProtocolAdapter)."""
        adapter = self._make_adapter()
        assert isinstance(adapter, ProtocolAdapter)

    def test_protocol_name_returns_mcp(self) -> None:
        """protocol_name property returns 'mcp'."""
        adapter = self._make_adapter()
        assert adapter.protocol_name == "mcp"

    def test_supported_operations_returns_all_operations(self) -> None:
        """supported_operations includes all operation IDs."""
        adapter = self._make_adapter()
        ops = adapter.supported_operations
        assert isinstance(ops, list)
        assert len(ops) > 0
        assert "tasks.create" in ops
        assert "tasks.list" in ops
        assert "tasks.execute" in ops

    def test_get_discovery_info_returns_correct_structure(self) -> None:
        """get_discovery_info returns dict with protocol, status, operations."""
        adapter = self._make_adapter()
        info = adapter.get_discovery_info()
        assert info["protocol"] == "mcp"
        assert "status" in info
        assert "operations" in info
        assert isinstance(info["operations"], list)

    def test_create_app_produces_app(self) -> None:
        """create_app returns an application instance."""
        adapter = self._make_adapter()
        config = ProtocolAdapterConfig(base_url="http://localhost:8000")
        app = adapter.create_app(config)
        assert app is not None

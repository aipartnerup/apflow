"""Tests for A2AProtocolAdapter."""

from typing import Any

from apflow.api.protocols import ProtocolAdapter, ProtocolAdapterConfig


class TestA2AProtocolAdapter:
    """Test A2AProtocolAdapter conformance and behavior."""

    def _make_adapter(self) -> Any:
        from apflow.api.a2a.protocol_adapter import A2AProtocolAdapter

        return A2AProtocolAdapter()

    def test_satisfies_protocol_adapter_interface(self) -> None:
        """A2AProtocolAdapter passes isinstance(obj, ProtocolAdapter)."""
        adapter = self._make_adapter()
        assert isinstance(adapter, ProtocolAdapter)

    def test_protocol_name_returns_a2a(self) -> None:
        """protocol_name property returns 'a2a'."""
        adapter = self._make_adapter()
        assert adapter.protocol_name == "a2a"

    def test_supported_operations_returns_operation_ids(self) -> None:
        """supported_operations includes known operation IDs."""
        adapter = self._make_adapter()
        ops = adapter.supported_operations
        assert isinstance(ops, list)
        assert len(ops) > 0
        assert "tasks.execute" in ops
        assert "tasks.generate" in ops
        assert "tasks.cancel" in ops

    def test_get_discovery_info_returns_correct_structure(self) -> None:
        """get_discovery_info returns dict with protocol, status, operations."""
        adapter = self._make_adapter()
        info = adapter.get_discovery_info()
        assert info["protocol"] == "a2a"
        assert "status" in info
        assert "operations" in info
        assert isinstance(info["operations"], list)

    def test_create_app_produces_asgi_app(self) -> None:
        """create_app returns an ASGI-compatible application."""
        adapter = self._make_adapter()
        config = ProtocolAdapterConfig(base_url="http://localhost:8000")
        app = adapter.create_app(config)
        assert app is not None
        assert callable(app)

"""Tests for ProtocolAdapter Protocol and ProtocolAdapterConfig."""

from typing import Any, AsyncIterator

from apflow.api.protocols import ProtocolAdapter, ProtocolAdapterConfig


class TestProtocolAdapterConfig:
    """Test ProtocolAdapterConfig dataclass construction."""

    def test_config_with_defaults(self) -> None:
        """Config can be constructed with only required fields, using defaults."""
        config = ProtocolAdapterConfig(base_url="http://localhost:8000")
        assert config.base_url == "http://localhost:8000"
        assert config.enable_system_routes is True
        assert config.enable_docs is True
        assert config.jwt_secret_key is None
        assert config.jwt_algorithm == "HS256"
        assert config.task_routes_class is None
        assert config.custom_routes is None
        assert config.custom_middleware is None
        assert config.verify_token_func is None
        assert config.verify_permission_func is None

    def test_config_with_overrides(self) -> None:
        """Config fields can be overridden."""
        config = ProtocolAdapterConfig(
            base_url="https://prod.example.com",
            enable_system_routes=False,
            enable_docs=False,
            jwt_secret_key="my-secret",
            jwt_algorithm="RS256",
        )
        assert config.base_url == "https://prod.example.com"
        assert config.jwt_secret_key == "my-secret"
        assert config.jwt_algorithm == "RS256"
        assert config.enable_docs is False
        assert config.enable_system_routes is False

    def test_config_with_custom_functions(self) -> None:
        """Config accepts custom verification functions."""

        def my_token_func(token: str) -> dict[str, Any] | None:
            return {"user_id": "test"}

        def my_permission_func(
            user_id: str, target_user_id: str | None, roles: list[str] | None
        ) -> bool:
            return True

        config = ProtocolAdapterConfig(
            base_url="http://localhost:8000",
            verify_token_func=my_token_func,
            verify_permission_func=my_permission_func,
        )
        assert config.verify_token_func is my_token_func
        assert config.verify_permission_func is my_permission_func


class TestProtocolAdapterProtocol:
    """Test ProtocolAdapter Protocol structural subtyping."""

    def test_conforming_class_passes_isinstance(self) -> None:
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

            async def handle_request(
                self, operation_id: str, params: dict[str, Any]
            ) -> dict[str, Any]:
                return {}

            async def handle_streaming_request(
                self, operation_id: str, params: dict[str, Any]
            ) -> AsyncIterator[dict[str, Any]]:
                yield {}

            def get_discovery_info(self) -> dict[str, Any]:
                return {}

        adapter = GoodAdapter()
        assert isinstance(adapter, ProtocolAdapter)

    def test_non_conforming_class_fails_isinstance(self) -> None:
        """A class missing required members fails isinstance check."""

        class BadAdapter:
            pass

        adapter = BadAdapter()
        assert not isinstance(adapter, ProtocolAdapter)

    def test_partial_conformance_fails(self) -> None:
        """A class with only some members fails isinstance check."""

        class PartialAdapter:
            @property
            def protocol_name(self) -> str:
                return "partial"

            def create_app(self, config: ProtocolAdapterConfig) -> Any:
                return None

        adapter = PartialAdapter()
        assert not isinstance(adapter, ProtocolAdapter)

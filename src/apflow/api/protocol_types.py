"""Shared types for the protocol subsystem.

This module defines the types shared across protocol adapters, the registry,
and capabilities. It has **no** imports from other ``apflow.api`` modules,
which makes it safe to import from any layer without creating cycles.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable  # noqa: F401 (Callable from collections.abc)


@dataclass
class ProtocolAdapterConfig:
    """Shared configuration for all protocol adapters.

    Centralizes the parameters that every protocol adapter needs when
    creating an ASGI application.
    """

    base_url: str
    enable_system_routes: bool = True
    enable_docs: bool = True
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    task_routes_class: type | None = None
    custom_routes: list[Any] | None = None
    custom_middleware: list[Any] | None = None
    verify_token_func: Any | None = None
    verify_permission_func: Any | None = None


@runtime_checkable
class ProtocolAdapter(Protocol):
    """Protocol interface that all protocol adapters must implement.

    Uses PEP 544 structural subtyping -- adapters satisfy this interface
    without explicit inheritance, keeping them loosely coupled and testable.
    """

    @property
    def protocol_name(self) -> str:
        """Unique identifier for this protocol (e.g. 'a2a', 'mcp', 'graphql')."""
        ...

    @property
    def supported_operations(self) -> list[str]:
        """Operation IDs supported by this adapter."""
        ...

    def create_app(self, config: ProtocolAdapterConfig) -> Any:
        """Create an ASGI application for this protocol."""
        ...

    async def handle_request(self, operation_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handle a single request for the given operation."""
        ...

    async def handle_streaming_request(
        self, operation_id: str, params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle a streaming request for the given operation."""
        ...

    def get_discovery_info(self) -> dict[str, Any]:
        """Return metadata for the protocol discovery endpoint."""
        ...


class ProtocolRegistry:
    """Registry for protocol adapters.

    Discovers, validates, and instantiates ProtocolAdapter implementations.
    Supports both built-in and externally registered adapters.
    """

    def __init__(self) -> None:
        self._adapter_classes: dict[str, type] = {}

    def register(self, adapter_class: type) -> None:
        """Register a protocol adapter class by its protocol_name."""
        instance = adapter_class()
        name: str = instance.protocol_name
        if name in self._adapter_classes:
            import logging

            logging.getLogger(__name__).warning(
                "Overwriting existing adapter for protocol '%s'", name
            )
        self._adapter_classes[name] = adapter_class

    def get_adapter(self, protocol: str) -> ProtocolAdapter:
        """Return an adapter instance for the given protocol name."""
        adapter_class = self._adapter_classes.get(protocol)
        if adapter_class is None:
            registered = ", ".join(self.list_protocols()) or "(none)"
            raise ValueError(f"Unknown protocol '{protocol}'. Registered protocols: {registered}")
        return adapter_class()  # type: ignore[return-value]

    def list_protocols(self) -> list[str]:
        """Return names of all registered protocols."""
        return list(self._adapter_classes.keys())

    def get_discovery(self) -> dict[str, dict[str, Any]]:
        """Return aggregated discovery info from all registered adapters."""
        result: dict[str, dict[str, Any]] = {}
        for name, adapter_class in self._adapter_classes.items():
            adapter = adapter_class()
            result[name] = adapter.get_discovery_info()
        return result


# ---------------------------------------------------------------------------
# Lazy protocol registry – lives here so any module can import it without
# pulling in ``protocols`` (which imports adapters).
# ---------------------------------------------------------------------------

_protocol_registry: ProtocolRegistry | None = None
_registry_factory: Callable[[], ProtocolRegistry] | None = None


def set_registry_factory(factory: Callable[[], ProtocolRegistry]) -> None:
    """Set the factory used to create the default protocol registry.

    Called once by ``protocols.py`` at import time to register the builder
    that discovers built-in adapters.
    """
    global _registry_factory
    _registry_factory = factory


def get_protocol_registry() -> ProtocolRegistry:
    """Return the lazily-initialised default protocol registry."""
    global _protocol_registry
    if _protocol_registry is None:
        if _registry_factory is not None:
            _protocol_registry = _registry_factory()
        else:
            _protocol_registry = ProtocolRegistry()
    return _protocol_registry

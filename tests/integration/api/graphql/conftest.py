"""Integration test fixtures for GraphQL adapter."""

from typing import Any

import pytest
from starlette.types import ASGIApp
from starlette.testclient import TestClient

strawberry = pytest.importorskip("strawberry", reason="strawberry-graphql not installed")

from apflow.api.graphql.server import GraphQLProtocolAdapter  # noqa: E402
from apflow.api.protocol_types import ProtocolAdapterConfig  # noqa: E402


@pytest.fixture
def graphql_config() -> ProtocolAdapterConfig:
    return ProtocolAdapterConfig(
        base_url="http://localhost:8000",
        enable_system_routes=False,
        enable_docs=True,
    )


@pytest.fixture
def graphql_app(graphql_config: ProtocolAdapterConfig) -> Any:
    adapter = GraphQLProtocolAdapter()
    return adapter.create_app(graphql_config)


@pytest.fixture
def client(graphql_app: ASGIApp) -> TestClient:
    return TestClient(graphql_app)

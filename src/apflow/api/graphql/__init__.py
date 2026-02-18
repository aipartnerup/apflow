"""GraphQL protocol adapter for apflow."""

try:
    from apflow.api.graphql.server import GraphQLProtocolAdapter
except ImportError:
    GraphQLProtocolAdapter = None  # type: ignore[assignment,misc]

__all__ = ["GraphQLProtocolAdapter"]

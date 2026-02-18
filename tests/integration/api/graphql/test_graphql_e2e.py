"""End-to-end integration tests for the GraphQL adapter.

These tests exercise the full ASGI stack: HTTP request -> Starlette ->
Strawberry GraphQL -> schema introspection.  No database is required
because only introspection and schema-shape queries are performed.
"""

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not pytest.importorskip("strawberry", reason="strawberry-graphql not installed"),
    reason="strawberry-graphql not installed",
)

# -- Introspection helpers ------------------------------------------------


INTROSPECTION_QUERY_TYPE = """
{
  __schema {
    queryType { name }
  }
}
"""

INTROSPECTION_ALL_TYPES = """
{
  __schema {
    types { name }
  }
}
"""

INTROSPECTION_QUERY_FIELDS = """
{
  __type(name: "Query") {
    fields { name }
  }
}
"""

INTROSPECTION_MUTATION_FIELDS = """
{
  __type(name: "Mutation") {
    fields { name }
  }
}
"""

INTROSPECTION_SUBSCRIPTION_FIELDS = """
{
  __type(name: "Subscription") {
    fields { name }
  }
}
"""


def _post_graphql(client: TestClient, query: str) -> dict:
    """Send a GraphQL POST request and return parsed JSON."""
    response = client.post("/graphql", json={"query": query})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    return response.json()


# -- Tests ----------------------------------------------------------------


class TestIntrospection:
    """Verify the schema is reachable and well-formed via introspection."""

    def test_introspection_returns_query_type(self, client: TestClient) -> None:
        """POST /graphql with __schema introspection returns queryType 'Query'."""
        data = _post_graphql(client, INTROSPECTION_QUERY_TYPE)
        query_type_name = data["data"]["__schema"]["queryType"]["name"]
        assert query_type_name == "Query"

    def test_introspection_includes_task_types(self, client: TestClient) -> None:
        """Schema types include TaskType, TaskStatusEnum, TaskTreeType, TaskProgressEvent."""
        data = _post_graphql(client, INTROSPECTION_ALL_TYPES)
        type_names = {t["name"] for t in data["data"]["__schema"]["types"]}

        expected_types = {"TaskType", "TaskStatusEnum", "TaskTreeType", "TaskProgressEvent"}
        missing = expected_types - type_names
        assert not missing, f"Missing types in schema: {missing}"


class TestSchemaFields:
    """Verify that Query, Mutation, and Subscription expose expected fields."""

    def test_query_fields_in_schema(self, client: TestClient) -> None:
        """Query type has task, tasks, taskChildren, taskTree, runningTasks."""
        data = _post_graphql(client, INTROSPECTION_QUERY_FIELDS)
        field_names = {f["name"] for f in data["data"]["__type"]["fields"]}

        expected = {"task", "tasks", "taskChildren", "taskTree", "runningTasks"}
        missing = expected - field_names
        assert not missing, f"Missing query fields: {missing}"

    def test_mutation_fields_in_schema(self, client: TestClient) -> None:
        """Mutation type has createTask, updateTask, cancelTask, deleteTask, executeTask."""
        data = _post_graphql(client, INTROSPECTION_MUTATION_FIELDS)
        field_names = {f["name"] for f in data["data"]["__type"]["fields"]}

        expected = {"createTask", "updateTask", "cancelTask", "deleteTask", "executeTask"}
        missing = expected - field_names
        assert not missing, f"Missing mutation fields: {missing}"

    def test_subscription_fields_in_schema(self, client: TestClient) -> None:
        """Subscription type has taskStatusChanged, taskProgress."""
        data = _post_graphql(client, INTROSPECTION_SUBSCRIPTION_FIELDS)
        field_names = {f["name"] for f in data["data"]["__type"]["fields"]}

        expected = {"taskStatusChanged", "taskProgress"}
        missing = expected - field_names
        assert not missing, f"Missing subscription fields: {missing}"


class TestGraphiQL:
    """Verify GraphiQL playground availability."""

    def test_graphiql_available(self, client: TestClient) -> None:
        """GET /graphql with Accept: text/html serves the GraphiQL playground."""
        response = client.get("/graphql", headers={"Accept": "text/html"})
        assert response.status_code == 200
        body = response.text.lower()
        assert (
            "graphql" in body or "graphiql" in body
        ), "Expected GraphiQL page but response did not contain 'graphql' or 'graphiql'"


class TestQueryDepthLimiting:
    """Verify that the QueryDepthLimiter extension rejects overly deep queries."""

    def test_query_depth_limiting(self, client: TestClient) -> None:
        """A query exceeding max depth 10 returns an error."""
        # Build a deeply nested introspection query that exceeds depth 10.
        # Each __type nesting adds depth; 12 levels should trigger the limiter.
        deep_query = (
            "{ __schema { types { " + "fields { type { " * 11 + "name" + " } }" * 11 + " } } }"
        )

        response = client.post("/graphql", json={"query": deep_query})
        data = response.json()

        # The depth limiter should produce errors in the response.
        assert "errors" in data, f"Expected depth-limit error but got: {data}"

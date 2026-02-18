"""Tests for GraphQL schema assembly."""

from apflow.api.graphql.schema import schema


class TestSchemaIntrospection:
    """Tests for schema introspection."""

    def test_schema_has_query_type(self) -> None:
        """Schema exposes a Query type."""
        result = schema.execute_sync("{ __schema { queryType { name } } }")
        assert result.errors is None
        assert result.data is not None
        assert result.data["__schema"]["queryType"]["name"] == "Query"

    def test_schema_has_mutation_type(self) -> None:
        """Schema exposes a Mutation type."""
        result = schema.execute_sync("{ __schema { mutationType { name } } }")
        assert result.errors is None
        assert result.data is not None
        assert result.data["__schema"]["mutationType"]["name"] == "Mutation"

    def test_schema_has_subscription_type(self) -> None:
        """Schema exposes a Subscription type."""
        result = schema.execute_sync("{ __schema { subscriptionType { name } } }")
        assert result.errors is None
        assert result.data is not None
        assert result.data["__schema"]["subscriptionType"]["name"] == "Subscription"

    def test_schema_types_list_exists(self) -> None:
        """Schema introspection returns a list of types."""
        result = schema.execute_sync("{ __schema { types { name } } }")
        assert result.errors is None
        assert result.data is not None
        type_names = {t["name"] for t in result.data["__schema"]["types"]}
        assert "Query" in type_names
        assert "Mutation" in type_names
        assert "Subscription" in type_names

    def test_schema_exposes_task_type(self) -> None:
        """Schema includes TaskType in its type list."""
        result = schema.execute_sync("{ __schema { types { name } } }")
        assert result.errors is None
        assert result.data is not None
        type_names = {t["name"] for t in result.data["__schema"]["types"]}
        assert "TaskType" in type_names

    def test_schema_exposes_task_tree_type(self) -> None:
        """Schema includes TaskTreeType in its type list."""
        result = schema.execute_sync("{ __schema { types { name } } }")
        assert result.errors is None
        assert result.data is not None
        type_names = {t["name"] for t in result.data["__schema"]["types"]}
        assert "TaskTreeType" in type_names

    def test_schema_exposes_task_progress_event(self) -> None:
        """Schema includes TaskProgressEvent in its type list."""
        result = schema.execute_sync("{ __schema { types { name } } }")
        assert result.errors is None
        assert result.data is not None
        type_names = {t["name"] for t in result.data["__schema"]["types"]}
        assert "TaskProgressEvent" in type_names

    def test_query_has_task_field(self) -> None:
        """Query type exposes task field."""
        query = """
        {
            __type(name: "Query") {
                fields { name }
            }
        }
        """
        result = schema.execute_sync(query)
        assert result.errors is None
        assert result.data is not None
        field_names = {f["name"] for f in result.data["__type"]["fields"]}
        assert "task" in field_names
        assert "tasks" in field_names
        assert "taskChildren" in field_names

    def test_query_has_task_tree_field(self) -> None:
        """Query type exposes taskTree field."""
        query = """
        {
            __type(name: "Query") {
                fields { name }
            }
        }
        """
        result = schema.execute_sync(query)
        assert result.errors is None
        assert result.data is not None
        field_names = {f["name"] for f in result.data["__type"]["fields"]}
        assert "taskTree" in field_names

    def test_query_has_running_tasks_field(self) -> None:
        """Query type exposes runningTasks field."""
        query = """
        {
            __type(name: "Query") {
                fields { name }
            }
        }
        """
        result = schema.execute_sync(query)
        assert result.errors is None
        assert result.data is not None
        field_names = {f["name"] for f in result.data["__type"]["fields"]}
        assert "runningTasks" in field_names

    def test_mutation_has_crud_fields(self) -> None:
        """Mutation type exposes CRUD operations."""
        query = """
        {
            __type(name: "Mutation") {
                fields { name }
            }
        }
        """
        result = schema.execute_sync(query)
        assert result.errors is None
        assert result.data is not None
        field_names = {f["name"] for f in result.data["__type"]["fields"]}
        assert "createTask" in field_names
        assert "updateTask" in field_names
        assert "cancelTask" in field_names
        assert "deleteTask" in field_names

    def test_mutation_has_execute_task_field(self) -> None:
        """Mutation type exposes executeTask field."""
        query = """
        {
            __type(name: "Mutation") {
                fields { name }
            }
        }
        """
        result = schema.execute_sync(query)
        assert result.errors is None
        assert result.data is not None
        field_names = {f["name"] for f in result.data["__type"]["fields"]}
        assert "executeTask" in field_names

    def test_subscription_has_status_changed(self) -> None:
        """Subscription type exposes taskStatusChanged."""
        query = """
        {
            __type(name: "Subscription") {
                fields { name }
            }
        }
        """
        result = schema.execute_sync(query)
        assert result.errors is None
        assert result.data is not None
        field_names = {f["name"] for f in result.data["__type"]["fields"]}
        assert "taskStatusChanged" in field_names

    def test_subscription_has_task_progress(self) -> None:
        """Subscription type exposes taskProgress."""
        query = """
        {
            __type(name: "Subscription") {
                fields { name }
            }
        }
        """
        result = schema.execute_sync(query)
        assert result.errors is None
        assert result.data is not None
        field_names = {f["name"] for f in result.data["__type"]["fields"]}
        assert "taskProgress" in field_names

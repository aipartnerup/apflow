# T1: Define GraphQL Types and Schema

## Goal

Create the Strawberry GraphQL type system and schema assembly that maps apflow's domain model (TaskModel, TaskStatus, executors) to GraphQL types and input types. This establishes the contract that all resolvers will implement against.

## Files Involved

**Create:**
- `src/apflow/api/graphql/__init__.py` -- Package marker, exports `GraphQLProtocolAdapter`
- `src/apflow/api/graphql/types.py` -- Strawberry type definitions
- `src/apflow/api/graphql/schema.py` -- Schema assembly (Query, Mutation, Subscription stubs)
- `src/apflow/api/graphql/resolvers/__init__.py` -- Resolvers sub-package marker
- `tests/unit/api/graphql/__init__.py` -- Test package marker
- `tests/unit/api/graphql/test_types.py` -- Type definition tests
- `tests/unit/api/graphql/test_schema.py` -- Schema introspection tests

**Reference (read-only):**
- `src/apflow/core/types.py` -- `TaskStatus` constants
- `src/apflow/api/capabilities.py` -- `OperationDef` and operation registry
- `src/apflow/api/mcp/adapter.py` -- Adapter pattern reference

## Steps

### 1. Write type definition tests (TDD -- red phase)

Create `tests/unit/api/graphql/test_types.py`:

```python
import strawberry
from apflow.api.graphql.types import (
    TaskStatusEnum,
    TaskType,
    TaskTreeType,
    ExecutorType,
    CreateTaskInput,
    UpdateTaskInput,
    task_model_to_graphql,
)
from apflow.core.types import TaskStatus


def test_task_status_enum_has_all_statuses():
    """TaskStatusEnum must mirror all TaskStatus constants."""
    expected = {TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED,
                TaskStatus.FAILED, TaskStatus.CANCELLED}
    enum_values = {member.value for member in TaskStatusEnum}
    assert enum_values == expected


def test_task_type_has_required_fields():
    """TaskType must expose all core TaskModel fields."""
    info = strawberry.Schema(query=...).introspect()  # simplified
    required = {"id", "name", "status", "priority", "progress",
                "result", "error", "createdAt", "updatedAt", "parentId"}
    # Assert all required fields exist in TaskType
    ...


def test_create_task_input_validation():
    """CreateTaskInput must require 'name' field."""
    inp = CreateTaskInput(name="test")
    assert inp.name == "test"


def test_task_model_to_graphql_conversion():
    """Converter must map all TaskModel fields to TaskType fields."""
    # Use a mock/fake TaskModel dict
    model_dict = {
        "id": "abc-123", "name": "Test", "status": "pending",
        "priority": 5, "progress": 0.0, "result": None, "error": None,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": None,
        "parent_id": None,
    }
    result = task_model_to_graphql(model_dict)
    assert result.id == "abc-123"
    assert result.status == TaskStatusEnum.PENDING
```

### 2. Create the `types.py` module

Define Strawberry types that mirror the domain model:

```python
import strawberry
from typing import Optional, List
from enum import Enum
from datetime import datetime


@strawberry.enum
class TaskStatusEnum(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@strawberry.type
class TaskType:
    id: str
    name: str
    status: TaskStatusEnum
    priority: int
    progress: float
    result: Optional[str]
    error: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    parent_id: Optional[str]
    description: Optional[str] = None
    children: Optional[List["TaskType"]] = None


@strawberry.type
class TaskTreeType:
    root: TaskType
    total_tasks: int
    completed_tasks: int
    failed_tasks: int


@strawberry.type
class ExecutorType:
    name: str
    executor_type: str
    description: Optional[str] = None


@strawberry.input
class CreateTaskInput:
    name: str
    description: Optional[str] = None
    executor: Optional[str] = None
    priority: Optional[int] = None
    inputs: Optional[strawberry.scalars.JSON] = None
    parent_id: Optional[str] = None


@strawberry.input
class UpdateTaskInput:
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatusEnum] = None
    inputs: Optional[strawberry.scalars.JSON] = None
```

Include a converter function:

```python
def task_model_to_graphql(data: dict) -> TaskType:
    """Convert a TaskModel dict (from TaskRoutes response) to a TaskType."""
    ...
```

### 3. Create the `schema.py` module

Assemble Query, Mutation, and Subscription type stubs into a `strawberry.Schema`:

```python
import strawberry
from apflow.api.graphql.types import TaskType


@strawberry.type
class Query:
    @strawberry.field
    def placeholder(self) -> str:
        return "GraphQL schema loaded"  # replaced in T2


@strawberry.type
class Mutation:
    @strawberry.mutation
    def placeholder(self) -> str:
        return "mutations loaded"  # replaced in T2


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def placeholder(self) -> str:
        yield "subscriptions loaded"  # replaced in T3


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
```

### 4. Write schema introspection tests

Create `tests/unit/api/graphql/test_schema.py`:

```python
from apflow.api.graphql.schema import schema


def test_schema_has_query_type():
    result = schema.execute_sync("{ __schema { queryType { name } } }")
    assert result.data["__schema"]["queryType"]["name"] == "Query"


def test_schema_has_mutation_type():
    result = schema.execute_sync("{ __schema { mutationType { name } } }")
    assert result.data["__schema"]["mutationType"]["name"] == "Mutation"


def test_schema_has_subscription_type():
    result = schema.execute_sync("{ __schema { subscriptionType { name } } }")
    assert result.data["__schema"]["subscriptionType"]["name"] == "Subscription"


def test_task_status_enum_in_schema():
    result = schema.execute_sync("""
        { __type(name: "TaskStatusEnum") { enumValues { name } } }
    """)
    values = {v["name"] for v in result.data["__type"]["enumValues"]}
    assert "PENDING" in values
    assert "COMPLETED" in values
```

### 5. Create package `__init__.py` files

- `src/apflow/api/graphql/__init__.py`: Empty or with lazy import of `GraphQLProtocolAdapter`
- `src/apflow/api/graphql/resolvers/__init__.py`: Empty package marker
- `tests/unit/api/graphql/__init__.py`: Empty package marker

### 6. Run tests and verify

```bash
pytest tests/unit/api/graphql/test_types.py tests/unit/api/graphql/test_schema.py -v
ruff check --fix src/apflow/api/graphql/
black src/apflow/api/graphql/ tests/unit/api/graphql/
pyright src/apflow/api/graphql/
```

## Acceptance Criteria

- [ ] `TaskStatusEnum` contains all five values matching `TaskStatus` constants (PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED)
- [ ] `TaskType` exposes fields: id, name, status, priority, progress, result, error, created_at, updated_at, parent_id, description, children
- [ ] `TaskTreeType` exposes: root, total_tasks, completed_tasks, failed_tasks
- [ ] `ExecutorType` exposes: name, executor_type, description
- [ ] `CreateTaskInput` requires `name`, optional fields for description, executor, priority, inputs, parent_id
- [ ] `UpdateTaskInput` has all optional fields (name, description, status, inputs)
- [ ] `task_model_to_graphql()` correctly converts TaskRoutes response dicts to `TaskType` instances
- [ ] Schema introspection confirms Query, Mutation, Subscription types exist
- [ ] Schema introspection confirms `TaskStatusEnum` is present with correct enum values
- [ ] All imports are guarded with `try/except ImportError` for optional dependency isolation
- [ ] `ruff check`, `black`, `pyright` report zero issues on all new files
- [ ] All tests pass: `pytest tests/unit/api/graphql/test_types.py tests/unit/api/graphql/test_schema.py -v`

## Dependencies

- **Depends on:** `protocol-abstraction-phase2` (ProtocolAdapter interface must exist; however, types/schema work can proceed in parallel since the adapter is in T4)
- **Required by:** T2 (resolvers), T3 (subscriptions), T4 (adapter integration)

## Estimated Time

3-4 hours

# T2: Implement Query and Mutation Resolvers with DataLoaders

## Goal

Implement all GraphQL query and mutation resolvers that delegate to `TaskRoutes` handler methods, plus DataLoaders for N+1 query prevention. Resolvers translate between Strawberry's typed GraphQL interface and the dict-based `TaskRoutes` API, using the capabilities registry for operation routing.

## Files Involved

**Create:**
- `src/apflow/api/graphql/resolvers/queries.py` -- Query resolvers
- `src/apflow/api/graphql/resolvers/mutations.py` -- Mutation resolvers
- `src/apflow/api/graphql/loaders.py` -- DataLoader definitions
- `tests/unit/api/graphql/test_queries.py` -- Query resolver tests
- `tests/unit/api/graphql/test_mutations.py` -- Mutation resolver tests
- `tests/unit/api/graphql/test_loaders.py` -- DataLoader tests

**Modify:**
- `src/apflow/api/graphql/schema.py` -- Replace placeholder Query/Mutation with real resolvers

**Reference (read-only):**
- `src/apflow/api/routes/tasks.py` -- TaskRoutes handler signatures
- `src/apflow/api/capabilities.py` -- `OperationDef`, `get_handler_method()`
- `src/apflow/api/mcp/adapter.py` -- Adapter pattern: `call_by_tool_name()` routing via capabilities

## Steps

### 1. Write query resolver tests (TDD -- red phase)

Create `tests/unit/api/graphql/test_queries.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from apflow.api.graphql.resolvers.queries import (
    resolve_task,
    resolve_tasks,
    resolve_task_tree,
    resolve_task_children,
    resolve_running_tasks,
)
from apflow.api.graphql.types import TaskType, TaskStatusEnum


@pytest.fixture
def mock_task_routes():
    routes = AsyncMock()
    routes.handle_task_get.return_value = {
        "id": "task-1", "name": "Test", "status": "pending",
        "priority": 5, "progress": 0.0, "result": None, "error": None,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": None,
        "parent_id": None,
    }
    return routes


@pytest.fixture
def mock_info(mock_task_routes):
    info = MagicMock()
    info.context = {"task_routes": mock_task_routes}
    return info


@pytest.mark.asyncio
async def test_resolve_task_delegates_to_handle_task_get(mock_info, mock_task_routes):
    result = await resolve_task(info=mock_info, task_id="task-1")
    mock_task_routes.handle_task_get.assert_called_once()
    assert isinstance(result, TaskType)
    assert result.id == "task-1"


@pytest.mark.asyncio
async def test_resolve_tasks_with_filters(mock_info, mock_task_routes):
    mock_task_routes.handle_tasks_list.return_value = [...]
    result = await resolve_tasks(info=mock_info, status=TaskStatusEnum.PENDING, limit=10, offset=0)
    mock_task_routes.handle_tasks_list.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_task_not_found_raises_error(mock_info, mock_task_routes):
    mock_task_routes.handle_task_get.side_effect = ValueError("Task not found")
    with pytest.raises(ValueError):
        await resolve_task(info=mock_info, task_id="nonexistent")
```

### 2. Write mutation resolver tests (TDD -- red phase)

Create `tests/unit/api/graphql/test_mutations.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from apflow.api.graphql.resolvers.mutations import (
    resolve_create_task,
    resolve_update_task,
    resolve_cancel_task,
    resolve_delete_task,
    resolve_execute_task,
)
from apflow.api.graphql.types import CreateTaskInput, UpdateTaskInput, TaskType


@pytest.fixture
def mock_task_routes():
    routes = AsyncMock()
    routes.handle_task_create.return_value = {
        "id": "new-1", "name": "Created", "status": "pending",
        "priority": 5, "progress": 0.0, "result": None, "error": None,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": None,
        "parent_id": None,
    }
    return routes


@pytest.mark.asyncio
async def test_resolve_create_task_delegates(mock_task_routes):
    info = MagicMock()
    info.context = {"task_routes": mock_task_routes}
    inp = CreateTaskInput(name="New Task")
    result = await resolve_create_task(info=info, input=inp)
    mock_task_routes.handle_task_create.assert_called_once()
    assert isinstance(result, TaskType)


@pytest.mark.asyncio
async def test_resolve_cancel_task_delegates(mock_task_routes):
    info = MagicMock()
    info.context = {"task_routes": mock_task_routes}
    mock_task_routes.handle_task_cancel.return_value = {"status": "cancelled"}
    result = await resolve_cancel_task(info=info, task_id="task-1")
    mock_task_routes.handle_task_cancel.assert_called_once()
```

### 3. Write DataLoader tests (TDD -- red phase)

Create `tests/unit/api/graphql/test_loaders.py`:

```python
import pytest
from unittest.mock import AsyncMock
from apflow.api.graphql.loaders import TaskChildrenLoader, TaskByIdLoader


@pytest.mark.asyncio
async def test_task_children_loader_batches_requests():
    """DataLoader must batch multiple parent_id lookups into a single call."""
    mock_routes = AsyncMock()
    mock_routes.handle_task_children.return_value = [
        {"id": "child-1", "parent_id": "parent-1", ...},
        {"id": "child-2", "parent_id": "parent-2", ...},
    ]
    loader = TaskChildrenLoader(task_routes=mock_routes)
    # Request children for two different parents
    results = await loader.load_many(["parent-1", "parent-2"])
    assert len(results) == 2


@pytest.mark.asyncio
async def test_task_by_id_loader_deduplicates():
    """Requesting the same ID twice should only call the handler once."""
    mock_routes = AsyncMock()
    loader = TaskByIdLoader(task_routes=mock_routes)
    await loader.load_many(["id-1", "id-1"])
    # Should deduplicate to a single batch call
```

### 4. Implement DataLoaders

Create `src/apflow/api/graphql/loaders.py`:

```python
from typing import Any, Dict, List
from strawberry.dataloader import DataLoader
from apflow.api.routes.tasks import TaskRoutes
from apflow.api.graphql.types import TaskType, task_model_to_graphql


async def load_tasks_by_id(keys: List[str], task_routes: TaskRoutes) -> List[TaskType]:
    """Batch-load tasks by ID."""
    results: List[TaskType] = []
    for task_id in keys:
        data = await task_routes.handle_task_get({"task_id": task_id}, None, "")
        results.append(task_model_to_graphql(data))
    return results


async def load_children_by_parent_id(keys: List[str], task_routes: TaskRoutes) -> List[List[TaskType]]:
    """Batch-load children for multiple parent IDs."""
    results: List[List[TaskType]] = []
    for parent_id in keys:
        children = await task_routes.handle_task_children({"task_id": parent_id}, None, "")
        results.append([task_model_to_graphql(c) for c in children])
    return results


def create_task_by_id_loader(task_routes: TaskRoutes) -> DataLoader:
    async def batch_fn(keys: List[str]) -> List[TaskType]:
        return await load_tasks_by_id(keys, task_routes)
    return DataLoader(load_fn=batch_fn)


def create_task_children_loader(task_routes: TaskRoutes) -> DataLoader:
    async def batch_fn(keys: List[str]) -> List[List[TaskType]]:
        return await load_children_by_parent_id(keys, task_routes)
    return DataLoader(load_fn=batch_fn)
```

### 5. Implement query resolvers

Create `src/apflow/api/graphql/resolvers/queries.py`:

```python
from typing import Optional, List
import strawberry
from strawberry.types import Info
from apflow.api.graphql.types import (
    TaskType, TaskTreeType, TaskStatusEnum,
    task_model_to_graphql,
)


async def resolve_task(info: Info, task_id: str) -> TaskType:
    task_routes = info.context["task_routes"]
    data = await task_routes.handle_task_get({"task_id": task_id}, None, "")
    return task_model_to_graphql(data)


async def resolve_tasks(
    info: Info,
    status: Optional[TaskStatusEnum] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[TaskType]:
    task_routes = info.context["task_routes"]
    params = {}
    if status is not None:
        params["status"] = status.value
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    data = await task_routes.handle_tasks_list(params, None, "")
    return [task_model_to_graphql(t) for t in data]


async def resolve_task_tree(info: Info, root_id: str) -> TaskTreeType:
    task_routes = info.context["task_routes"]
    data = await task_routes.handle_task_tree({"task_id": root_id}, None, "")
    # Build TaskTreeType from response
    ...


async def resolve_task_children(info: Info, parent_id: str) -> List[TaskType]:
    loader = info.context["task_children_loader"]
    return await loader.load(parent_id)


async def resolve_running_tasks(info: Info) -> List[TaskType]:
    task_routes = info.context["task_routes"]
    data = await task_routes.handle_running_tasks_list({}, None, "")
    return [task_model_to_graphql(t) for t in data]
```

### 6. Implement mutation resolvers

Create `src/apflow/api/graphql/resolvers/mutations.py`:

```python
from typing import Optional, List
import strawberry
from strawberry.types import Info
from apflow.api.graphql.types import (
    TaskType, CreateTaskInput, UpdateTaskInput,
    task_model_to_graphql,
)


async def resolve_create_task(info: Info, input: CreateTaskInput) -> TaskType:
    task_routes = info.context["task_routes"]
    task_dict = {"name": input.name}
    if input.description is not None:
        task_dict["description"] = input.description
    if input.executor is not None:
        task_dict["executor"] = input.executor
    if input.priority is not None:
        task_dict["priority"] = input.priority
    if input.inputs is not None:
        task_dict["inputs"] = input.inputs
    if input.parent_id is not None:
        task_dict["parent_id"] = input.parent_id
    data = await task_routes.handle_task_create([task_dict], None, "")
    return task_model_to_graphql(data)


async def resolve_update_task(info: Info, task_id: str, input: UpdateTaskInput) -> TaskType:
    task_routes = info.context["task_routes"]
    params = {"task_id": task_id}
    if input.name is not None:
        params["name"] = input.name
    if input.description is not None:
        params["description"] = input.description
    if input.status is not None:
        params["status"] = input.status.value
    if input.inputs is not None:
        params["inputs"] = input.inputs
    data = await task_routes.handle_task_update(params, None, "")
    return task_model_to_graphql(data)


async def resolve_cancel_task(info: Info, task_id: str) -> TaskType:
    task_routes = info.context["task_routes"]
    data = await task_routes.handle_task_cancel({"task_id": task_id}, None, "")
    return task_model_to_graphql(data)


async def resolve_delete_task(info: Info, task_id: str) -> bool:
    task_routes = info.context["task_routes"]
    await task_routes.handle_task_delete({"task_id": task_id}, None, "")
    return True


async def resolve_execute_task(
    info: Info, task_id: str, use_streaming: Optional[bool] = False
) -> TaskType:
    task_routes = info.context["task_routes"]
    params = {"task_id": task_id, "use_streaming": use_streaming}
    data = await task_routes.handle_task_execute(params, None, "")
    return task_model_to_graphql(data)
```

### 7. Update schema.py to wire real resolvers

Replace the placeholder stubs in `schema.py` with the real resolver functions:

```python
import strawberry
from apflow.api.graphql.resolvers.queries import (
    resolve_task, resolve_tasks, resolve_task_tree,
    resolve_task_children, resolve_running_tasks,
)
from apflow.api.graphql.resolvers.mutations import (
    resolve_create_task, resolve_update_task,
    resolve_cancel_task, resolve_delete_task, resolve_execute_task,
)
from apflow.api.graphql.types import TaskType, TaskTreeType, CreateTaskInput, UpdateTaskInput, TaskStatusEnum


@strawberry.type
class Query:
    task: TaskType = strawberry.field(resolver=resolve_task)
    tasks: list[TaskType] = strawberry.field(resolver=resolve_tasks)
    task_tree: TaskTreeType = strawberry.field(resolver=resolve_task_tree)
    task_children: list[TaskType] = strawberry.field(resolver=resolve_task_children)
    running_tasks: list[TaskType] = strawberry.field(resolver=resolve_running_tasks)


@strawberry.type
class Mutation:
    create_task: TaskType = strawberry.mutation(resolver=resolve_create_task)
    update_task: TaskType = strawberry.mutation(resolver=resolve_update_task)
    cancel_task: TaskType = strawberry.mutation(resolver=resolve_cancel_task)
    delete_task: bool = strawberry.mutation(resolver=resolve_delete_task)
    execute_task: TaskType = strawberry.mutation(resolver=resolve_execute_task)
```

### 8. Run tests and verify

```bash
pytest tests/unit/api/graphql/ -v
ruff check --fix src/apflow/api/graphql/
black src/apflow/api/graphql/ tests/unit/api/graphql/
pyright src/apflow/api/graphql/
```

## Acceptance Criteria

- [ ] All query resolvers delegate to the correct `TaskRoutes.handle_*` method:
  - `task(id)` -> `handle_task_get`
  - `tasks(status, limit, offset)` -> `handle_tasks_list`
  - `taskTree(rootId)` -> `handle_task_tree`
  - `taskChildren(parentId)` -> `handle_task_children` (via DataLoader)
  - `runningTasks` -> `handle_running_tasks_list`
- [ ] All mutation resolvers delegate to the correct `TaskRoutes.handle_*` method:
  - `createTask(input)` -> `handle_task_create`
  - `updateTask(id, input)` -> `handle_task_update`
  - `cancelTask(id)` -> `handle_task_cancel`
  - `deleteTask(id)` -> `handle_task_delete`
  - `executeTask(id)` -> `handle_task_execute`
- [ ] DataLoaders batch child-task and task-by-id lookups (verified by test)
- [ ] Error handling: task-not-found and validation errors map to GraphQL errors
- [ ] Pagination parameters (limit, offset) pass through to `handle_tasks_list`
- [ ] Status filter converts `TaskStatusEnum` value to string for TaskRoutes
- [ ] `schema.py` wires real resolvers (no more placeholders for Query/Mutation)
- [ ] `ruff check`, `black`, `pyright` report zero issues
- [ ] All tests pass: `pytest tests/unit/api/graphql/ -v`

## Dependencies

- **Depends on:** T1 (schema-types -- types and schema module must exist)
- **Required by:** T3 (subscriptions), T4 (adapter integration)

## Estimated Time

5-6 hours

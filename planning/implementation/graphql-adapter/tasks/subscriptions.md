# T3: Implement Subscription Resolvers

## Goal

Implement GraphQL subscription resolvers that deliver real-time task status changes and execution progress updates over WebSocket, connecting to the existing `TaskStreamingContext` and `_task_streaming_events` infrastructure in `api/routes/tasks.py`.

## Files Involved

**Create:**
- `src/apflow/api/graphql/resolvers/subscriptions.py` -- Subscription resolvers
- `tests/unit/api/graphql/test_subscriptions.py` -- Subscription tests

**Modify:**
- `src/apflow/api/graphql/schema.py` -- Replace Subscription placeholder with real subscription resolvers

**Reference (read-only):**
- `src/apflow/api/routes/tasks.py` -- `TaskStreamingContext`, `_task_streaming_events`, `get_task_streaming_events()`
- `src/apflow/api/graphql/types.py` -- `TaskType`, `TaskStatusEnum`, `task_model_to_graphql()`

## Steps

### 1. Write subscription tests (TDD -- red phase)

Create `tests/unit/api/graphql/test_subscriptions.py`:

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from apflow.api.graphql.resolvers.subscriptions import (
    subscribe_task_status_changed,
    subscribe_task_progress,
)
from apflow.api.graphql.types import TaskType, TaskStatusEnum


@pytest.fixture
def mock_info():
    info = MagicMock()
    info.context = {
        "task_routes": AsyncMock(),
    }
    return info


@pytest.mark.asyncio
async def test_task_status_changed_yields_updates(mock_info):
    """Subscription must yield TaskType when task status changes."""
    mock_routes = mock_info.context["task_routes"]
    # Simulate status change: pending -> in_progress -> completed
    mock_routes.handle_task_get.side_effect = [
        {"id": "t1", "name": "Test", "status": "pending", "priority": 5,
         "progress": 0.0, "result": None, "error": None,
         "created_at": "2026-01-01T00:00:00Z", "updated_at": None, "parent_id": None},
        {"id": "t1", "name": "Test", "status": "in_progress", "priority": 5,
         "progress": 0.5, "result": None, "error": None,
         "created_at": "2026-01-01T00:00:00Z", "updated_at": None, "parent_id": None},
        {"id": "t1", "name": "Test", "status": "completed", "priority": 5,
         "progress": 1.0, "result": "done", "error": None,
         "created_at": "2026-01-01T00:00:00Z", "updated_at": None, "parent_id": None},
    ]

    updates = []
    async for update in subscribe_task_status_changed(info=mock_info, task_id="t1"):
        updates.append(update)
        if update.status == TaskStatusEnum.COMPLETED:
            break

    assert len(updates) >= 1
    assert isinstance(updates[0], TaskType)


@pytest.mark.asyncio
async def test_task_progress_yields_from_streaming_events(mock_info):
    """Subscription must yield progress events from TaskStreamingContext."""
    fake_events = [
        {"type": "progress", "task_id": "t1", "progress": 0.25, "message": "Step 1"},
        {"type": "progress", "task_id": "t1", "progress": 0.75, "message": "Step 2"},
        {"type": "complete", "task_id": "t1", "progress": 1.0, "message": "Done"},
    ]

    with patch(
        "apflow.api.graphql.resolvers.subscriptions.get_task_streaming_events",
        return_value=fake_events,
    ):
        updates = []
        async for event in subscribe_task_progress(info=mock_info, task_id="t1"):
            updates.append(event)
            if event.progress >= 1.0:
                break

    assert len(updates) == 3
    assert updates[-1].progress == 1.0


@pytest.mark.asyncio
async def test_subscription_cleanup_on_disconnect():
    """Subscription generator must clean up resources when client disconnects."""
    info = MagicMock()
    info.context = {"task_routes": AsyncMock()}

    gen = subscribe_task_status_changed(info=info, task_id="t1")
    # Simulate disconnect by closing the generator
    await gen.aclose()
    # No exception means cleanup succeeded


@pytest.mark.asyncio
async def test_subscription_respects_terminal_status():
    """Subscription must stop yielding after task reaches terminal status."""
    info = MagicMock()
    task_routes = AsyncMock()
    info.context = {"task_routes": task_routes}
    task_routes.handle_task_get.return_value = {
        "id": "t1", "name": "Test", "status": "failed", "priority": 5,
        "progress": 0.0, "result": None, "error": "boom",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": None, "parent_id": None,
    }

    updates = []
    async for update in subscribe_task_status_changed(info=info, task_id="t1"):
        updates.append(update)
        # Generator should terminate after yielding terminal status
        break

    assert updates[0].status in (TaskStatusEnum.FAILED, TaskStatusEnum.COMPLETED, TaskStatusEnum.CANCELLED)
```

### 2. Define subscription event types

Add a progress event type to `types.py` (or a new section in subscriptions):

```python
@strawberry.type
class TaskProgressEvent:
    task_id: str
    progress: float
    message: Optional[str] = None
    event_type: str = "progress"  # "progress", "status_change", "complete", "error"
```

### 3. Implement subscription resolvers

Create `src/apflow/api/graphql/resolvers/subscriptions.py`:

```python
import asyncio
from typing import AsyncGenerator, Optional
import strawberry
from strawberry.types import Info

from apflow.api.graphql.types import TaskType, TaskProgressEvent, task_model_to_graphql
from apflow.api.routes.tasks import get_task_streaming_events
from apflow.core.types import TaskStatus
from apflow.logger import get_logger

logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 0.5
MAX_POLL_DURATION_SECONDS = 300  # 5 minutes max subscription lifetime


async def subscribe_task_status_changed(
    info: Info, task_id: str
) -> AsyncGenerator[TaskType, None]:
    """
    Subscribe to status changes for a specific task.

    Polls the task's current status at intervals. Yields a TaskType
    each time the status changes. Terminates when the task reaches
    a terminal status (completed, failed, cancelled).
    """
    task_routes = info.context["task_routes"]
    last_status: Optional[str] = None
    elapsed = 0.0

    try:
        while elapsed < MAX_POLL_DURATION_SECONDS:
            data = await task_routes.handle_task_get(
                {"task_id": task_id}, None, ""
            )
            current_status = data.get("status")

            if current_status != last_status:
                last_status = current_status
                yield task_model_to_graphql(data)

                if TaskStatus.is_terminal(current_status):
                    return

            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
    except asyncio.CancelledError:
        logger.info(f"Subscription cancelled for task {task_id}")
    finally:
        logger.info(f"Subscription ended for task {task_id}")


async def subscribe_task_progress(
    info: Info, task_id: str
) -> AsyncGenerator[TaskProgressEvent, None]:
    """
    Subscribe to execution progress for a specific task.

    Reads from the global streaming events store populated by
    TaskStreamingContext during task execution.
    """
    last_index = 0
    elapsed = 0.0

    try:
        while elapsed < MAX_POLL_DURATION_SECONDS:
            events = await get_task_streaming_events(task_id)

            for event in events[last_index:]:
                yield TaskProgressEvent(
                    task_id=task_id,
                    progress=event.get("progress", 0.0),
                    message=event.get("message"),
                    event_type=event.get("type", "progress"),
                )
                last_index += 1

                if event.get("type") == "complete":
                    return

            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
    except asyncio.CancelledError:
        logger.info(f"Progress subscription cancelled for task {task_id}")
    finally:
        logger.info(f"Progress subscription ended for task {task_id}")
```

### 4. Update schema.py with real Subscription type

Replace the placeholder Subscription class:

```python
from apflow.api.graphql.resolvers.subscriptions import (
    subscribe_task_status_changed,
    subscribe_task_progress,
)
from apflow.api.graphql.types import TaskType, TaskProgressEvent


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def task_status_changed(
        self, info: Info, task_id: str
    ) -> AsyncGenerator[TaskType, None]:
        async for update in subscribe_task_status_changed(info, task_id):
            yield update

    @strawberry.subscription
    async def task_progress(
        self, info: Info, task_id: str
    ) -> AsyncGenerator[TaskProgressEvent, None]:
        async for event in subscribe_task_progress(info, task_id):
            yield event
```

### 5. Configure WebSocket transport

Ensure the schema supports the `graphql-transport-ws` sub-protocol. This is handled by Strawberry's ASGI integration automatically, but document the configuration:

```python
# In schema.py or server.py (T4)
# Strawberry's GraphQL ASGI app handles WS transport natively.
# The subscription_protocols parameter controls which WS sub-protocols are accepted.
# Default: ["graphql-transport-ws", "graphql-ws"]
```

### 6. Add bounded queue for backpressure protection

Implement a simple bounded queue wrapper to prevent unbounded buffering when the client is slow to consume:

```python
MAX_SUBSCRIPTION_BUFFER = 100

class BoundedEventBuffer:
    """Drop-oldest buffer for subscription events."""

    def __init__(self, max_size: int = MAX_SUBSCRIPTION_BUFFER):
        self._buffer: asyncio.Queue = asyncio.Queue(maxsize=max_size)

    async def put(self, event: Any) -> None:
        if self._buffer.full():
            self._buffer.get_nowait()  # drop oldest
        await self._buffer.put(event)

    async def get(self) -> Any:
        return await self._buffer.get()
```

### 7. Run tests and verify

```bash
pytest tests/unit/api/graphql/test_subscriptions.py -v
ruff check --fix src/apflow/api/graphql/resolvers/subscriptions.py
black src/apflow/api/graphql/ tests/unit/api/graphql/
pyright src/apflow/api/graphql/
```

## Acceptance Criteria

- [ ] `taskStatusChanged(taskId)` yields `TaskType` updates when the task status changes
- [ ] `taskStatusChanged` terminates after the task reaches a terminal status (completed, failed, cancelled)
- [ ] `taskProgress(taskId)` yields `TaskProgressEvent` objects from `get_task_streaming_events()`
- [ ] `taskProgress` terminates after receiving a `"complete"` event
- [ ] Subscriptions clean up resources on client disconnect (`asyncio.CancelledError` handled)
- [ ] Maximum subscription lifetime enforced (default 5 minutes) to prevent resource leaks
- [ ] Bounded event buffer implemented to prevent unbounded memory growth on slow clients
- [ ] `TaskProgressEvent` type defined with fields: task_id, progress, message, event_type
- [ ] Schema `Subscription` type updated with real resolvers (no more placeholder)
- [ ] WebSocket transport uses `graphql-transport-ws` sub-protocol
- [ ] `ruff check`, `black`, `pyright` report zero issues
- [ ] All tests pass: `pytest tests/unit/api/graphql/test_subscriptions.py -v`

## Dependencies

- **Depends on:** T2 (resolvers -- query/mutation resolvers and schema wiring must be in place)
- **Required by:** T4 (adapter integration -- subscriptions must work before server integration)

## Estimated Time

3-4 hours

"""GraphQL subscription resolvers for real-time updates."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Optional

from strawberry.types import Info

from apflow.api.graphql.types import (
    TaskProgressEvent,
    TaskType,
    task_model_to_graphql,
)
from apflow.core.types import TaskStatus
from apflow.logger import get_logger

logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 0.5
MAX_POLL_DURATION_SECONDS = 300
PROGRESS_POLL_INTERVAL_SECONDS = 0.3


async def subscribe_task_status_changed(info: Info, task_id: str) -> AsyncGenerator[TaskType, None]:
    """Subscribe to status changes for a specific task.

    Polls the task's current status at intervals. Yields a TaskType
    each time the status changes. Terminates when the task reaches
    a terminal status (completed, failed, cancelled).
    """
    task_routes = info.context["task_routes"]
    last_status: Optional[str] = None
    elapsed = 0.0

    try:
        while elapsed < MAX_POLL_DURATION_SECONDS:
            data = await task_routes.handle_task_get({"task_id": task_id}, None, "")
            current_status = data.get("status")

            if current_status != last_status:
                last_status = current_status
                yield task_model_to_graphql(data)

                if TaskStatus.is_terminal(current_status):
                    return

            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
    except asyncio.CancelledError:
        logger.info("Subscription cancelled for task %s", task_id)
    finally:
        logger.info("Subscription ended for task %s", task_id)


async def subscribe_task_progress(
    info: Info,  # noqa: ARG001 — required by Strawberry subscription interface
    task_id: str,
) -> AsyncGenerator[TaskProgressEvent, None]:
    """Subscribe to progress events for a task execution.

    Reads events from the streaming infrastructure via
    get_task_streaming_events(). Yields TaskProgressEvent objects.
    Terminates when a 'complete' event type is encountered.
    """
    _ = info  # satisfy pyright — parameter required by Strawberry
    from apflow.api.routes.tasks import get_task_streaming_events

    last_index = 0
    elapsed = 0.0

    try:
        while elapsed < MAX_POLL_DURATION_SECONDS:
            events: list[dict[str, Any]] = await get_task_streaming_events(task_id)

            for event in events[last_index:]:
                event_type = event.get("type", "progress")
                progress_event = TaskProgressEvent(
                    task_id=task_id,
                    progress=float(event.get("progress", 0.0)),
                    message=event.get("message"),
                    event_type=event_type,
                )
                yield progress_event

                if event_type == "complete":
                    return

            last_index = len(events)
            await asyncio.sleep(PROGRESS_POLL_INTERVAL_SECONDS)
            elapsed += PROGRESS_POLL_INTERVAL_SECONDS
    except asyncio.CancelledError:
        logger.info("Progress subscription cancelled for task %s", task_id)
    finally:
        logger.info("Progress subscription ended for task %s", task_id)

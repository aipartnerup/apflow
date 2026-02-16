"""GraphQL query resolvers delegating to TaskRoutes."""

from __future__ import annotations

from typing import Optional

from strawberry.types import Info

from apflow.api.graphql.types import (
    TaskStatusEnum,
    TaskType,
    task_model_to_graphql,
)


async def resolve_task(info: Info, task_id: str) -> TaskType:
    """Resolve a single task by ID."""
    task_routes = info.context["task_routes"]
    data = await task_routes.handle_task_get({"task_id": task_id}, None, "")
    return task_model_to_graphql(data)


async def resolve_tasks(
    info: Info,
    status: Optional[TaskStatusEnum] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list[TaskType]:
    """Resolve a list of tasks with optional filters."""
    task_routes = info.context["task_routes"]
    params: dict[str, object] = {}
    if status is not None:
        params["status"] = status.value
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    data = await task_routes.handle_tasks_list(params, None, "")
    return [task_model_to_graphql(t) for t in data]


async def resolve_task_children(info: Info, parent_id: str) -> list[TaskType]:
    """Resolve children of a task."""
    task_routes = info.context["task_routes"]
    data = await task_routes.handle_tasks_list({"parent_id": parent_id}, None, "")
    return [task_model_to_graphql(t) for t in data]

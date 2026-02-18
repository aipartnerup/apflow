"""GraphQL query resolvers delegating to TaskRoutes."""

from __future__ import annotations

from typing import Any, Optional

from strawberry.types import Info

from apflow.api.graphql.types import (
    TaskStatusEnum,
    TaskTreeType,
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
    data = await task_routes.handle_task_children({"parent_id": parent_id}, None, "")
    return [task_model_to_graphql(t) for t in data]


def _count_tree_stats(tree_data: dict[str, Any]) -> tuple[int, int, int]:
    """Count total, completed, and failed tasks in a tree dict.

    The tree dict has shape: {"task": {...}, "children": [...]}.
    Returns (total, completed, failed).
    """
    task = tree_data.get("task", {})
    status = task.get("status", "")
    total = 1
    completed = 1 if status == "completed" else 0
    failed = 1 if status == "failed" else 0
    for child in tree_data.get("children", []):
        ct, cc, cf = _count_tree_stats(child)
        total += ct
        completed += cc
        failed += cf
    return total, completed, failed


async def resolve_task_tree(info: Info, root_id: str) -> TaskTreeType:
    """Resolve a task tree by root ID."""
    task_routes = info.context["task_routes"]
    data = await task_routes.handle_task_tree({"root_id": root_id}, None, "")
    if data is None:
        raise ValueError(f"Task tree not found for root_id={root_id}")
    root_task = task_model_to_graphql(data["task"])
    total, completed, failed = _count_tree_stats(data)
    return TaskTreeType(
        root=root_task,
        total_tasks=total,
        completed_tasks=completed,
        failed_tasks=failed,
    )


async def resolve_running_tasks(
    info: Info,
    limit: Optional[int] = None,
) -> list[TaskType]:
    """Resolve currently running tasks."""
    task_routes = info.context["task_routes"]
    params: dict[str, object] = {}
    if limit is not None:
        params["limit"] = limit
    data = await task_routes.handle_running_tasks_list(params, None, "")
    return [task_model_to_graphql(t) for t in data]

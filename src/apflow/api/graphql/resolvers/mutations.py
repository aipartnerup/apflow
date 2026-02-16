"""GraphQL mutation resolvers delegating to TaskRoutes."""

from __future__ import annotations

from typing import Any

from strawberry.types import Info

from apflow.api.graphql.types import (
    CreateTaskInput,
    TaskType,
    UpdateTaskInput,
    task_model_to_graphql,
)


async def resolve_create_task(info: Info, task_input: CreateTaskInput) -> TaskType:
    """Create a new task."""
    task_routes = info.context["task_routes"]
    task_dict: dict[str, Any] = {"name": task_input.name}
    if task_input.description is not None:
        task_dict["description"] = task_input.description
    if task_input.executor is not None:
        task_dict["executor"] = task_input.executor
    if task_input.priority is not None:
        task_dict["priority"] = task_input.priority
    if task_input.inputs is not None:
        task_dict["inputs"] = task_input.inputs
    if task_input.parent_id is not None:
        task_dict["parent_id"] = task_input.parent_id
    data = await task_routes.handle_task_create([task_dict], None, "")
    if isinstance(data, list):
        data = data[0]
    return task_model_to_graphql(data)


async def resolve_update_task(info: Info, task_id: str, task_input: UpdateTaskInput) -> TaskType:
    """Update an existing task."""
    task_routes = info.context["task_routes"]
    params: dict[str, Any] = {"task_id": task_id}
    if task_input.name is not None:
        params["name"] = task_input.name
    if task_input.description is not None:
        params["description"] = task_input.description
    if task_input.status is not None:
        params["status"] = task_input.status.value
    if task_input.inputs is not None:
        params["inputs"] = task_input.inputs
    data = await task_routes.handle_task_update(params, None, "")
    return task_model_to_graphql(data)


async def resolve_cancel_task(info: Info, task_id: str) -> bool:
    """Cancel a task."""
    task_routes = info.context["task_routes"]
    await task_routes.handle_task_cancel({"task_id": task_id}, None, "")
    return True


async def resolve_delete_task(info: Info, task_id: str) -> bool:
    """Delete a task."""
    task_routes = info.context["task_routes"]
    await task_routes.handle_task_delete({"task_id": task_id}, None, "")
    return True

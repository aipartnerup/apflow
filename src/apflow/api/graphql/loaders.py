"""Strawberry DataLoader definitions for N+1 query prevention."""

from __future__ import annotations

from typing import Any

from strawberry.dataloader import DataLoader

from apflow.api.graphql.types import TaskType, task_model_to_graphql


async def load_tasks_by_id(keys: list[str], task_routes: Any) -> list[TaskType]:
    """Batch-load tasks by their IDs.

    Loads each task individually via handle_task_get, but batches within
    a single GraphQL execution to avoid N+1 queries across fields.
    """
    results: list[TaskType] = []
    for key in keys:
        data: dict[str, Any] = await task_routes.handle_task_get(
            {"task_id": key}, None, ""  # type: ignore[arg-type]
        )
        results.append(task_model_to_graphql(data))
    return results


async def load_children_by_parent_id(keys: list[str], task_routes: Any) -> list[list[TaskType]]:
    """Batch-load children for multiple parent IDs.

    Returns a list of lists, one per key, maintaining order.
    """
    results: list[list[TaskType]] = []
    for parent_id in keys:
        children = await task_routes.handle_task_children(
            {"parent_id": parent_id}, None, ""  # type: ignore[arg-type]
        )
        results.append([task_model_to_graphql(c) for c in children])
    return results


def create_task_by_id_loader(task_routes: Any) -> DataLoader[str, TaskType]:
    """Create a DataLoader that batches task-by-ID lookups."""

    async def _load(keys: list[str]) -> list[TaskType]:
        return await load_tasks_by_id(keys, task_routes)

    return DataLoader(load_fn=_load)


def create_task_children_loader(
    task_routes: Any,
) -> DataLoader[str, list[TaskType]]:
    """Create a DataLoader that batches children-by-parent-ID lookups."""

    async def _load(keys: list[str]) -> list[list[TaskType]]:
        return await load_children_by_parent_id(keys, task_routes)

    return DataLoader(load_fn=_load)

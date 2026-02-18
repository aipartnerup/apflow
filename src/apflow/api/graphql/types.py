"""Strawberry GraphQL type definitions for apflow."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

import strawberry


@strawberry.enum
class TaskStatusEnum(Enum):
    """Task status enum mirroring TaskStatus constants."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_STATUS_MAP: dict[str, TaskStatusEnum] = {
    "pending": TaskStatusEnum.PENDING,
    "in_progress": TaskStatusEnum.IN_PROGRESS,
    "completed": TaskStatusEnum.COMPLETED,
    "failed": TaskStatusEnum.FAILED,
    "cancelled": TaskStatusEnum.CANCELLED,
}


@strawberry.type
class TaskType:
    """GraphQL representation of a task."""

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
    children: Optional[list[TaskType]] = None


@strawberry.input
class CreateTaskInput:
    """Input for creating a new task."""

    name: str
    description: Optional[str] = None
    executor: Optional[str] = None
    priority: Optional[int] = None
    inputs: Optional[strawberry.scalars.JSON] = None
    parent_id: Optional[str] = None


@strawberry.input
class UpdateTaskInput:
    """Input for updating an existing task."""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatusEnum] = None
    inputs: Optional[strawberry.scalars.JSON] = None


@strawberry.type
class TaskTreeType:
    """GraphQL representation of a task tree."""

    root: TaskType
    total_tasks: int
    completed_tasks: int
    failed_tasks: int


@strawberry.type
class TaskProgressEvent:
    """Progress event for task execution subscriptions."""

    task_id: str
    progress: float
    message: Optional[str] = None
    event_type: str = "progress"


def task_model_to_graphql(data: dict[str, Any]) -> TaskType:
    """Convert a TaskModel dict to a TaskType instance."""
    status_str = data.get("status", "pending")
    status = _STATUS_MAP.get(status_str, TaskStatusEnum.PENDING)

    return TaskType(
        id=data.get("id", ""),
        name=data.get("name", ""),
        status=status,
        priority=data.get("priority", 0),
        progress=data.get("progress", 0.0),
        result=data.get("result"),
        error=data.get("error"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        parent_id=data.get("parent_id"),
        description=data.get("description"),
    )

"""Shared fixtures and helpers for GraphQL tests."""

import pytest

strawberry = pytest.importorskip("strawberry", reason="strawberry-graphql not installed")


def make_task_dict(
    task_id: str = "task-1",
    name: str = "Test Task",
    status: str = "pending",
    progress: float = 0.0,
    parent_id: str | None = None,
) -> dict:
    """Create a task dictionary for testing.

    Shared helper used across all GraphQL test modules.
    """
    return {
        "id": task_id,
        "name": name,
        "status": status,
        "priority": 5,
        "progress": progress,
        "result": None,
        "error": None,
        "created_at": None,
        "updated_at": None,
        "parent_id": parent_id,
    }

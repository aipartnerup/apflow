"""Shared type definitions for distributed task orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from apflow.core.storage.sqlalchemy.models import TaskModel

TaskExecutorFn = Callable[["TaskModel"], Awaitable[dict[str, Any]]]

NodeCapabilities = dict[str, Any]

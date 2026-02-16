"""Shared type definitions for distributed task orchestration."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

TaskExecutorFn = Callable[[Any], Awaitable[dict[str, Any]]]

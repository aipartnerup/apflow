"""
Core interfaces for apflow

This module defines the core interfaces that all implementations must follow.
Interfaces are abstract contracts that define what methods must be implemented.
"""

__all__ = [
    "ExecutableTask",
]


def __getattr__(name):
    """Lazy import to avoid loading apflow.core.extensions at package import time"""
    if name == "ExecutableTask":
        from apflow.core.interfaces.executable_task import ExecutableTask
        return ExecutableTask
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


"""
Core interfaces for apflow

This module defines the core interfaces that all implementations must follow.
Interfaces are abstract contracts that define what methods must be implemented.
"""

from apflow.core.interfaces.executable_task import ExecutableTask

__all__ = [
    "ExecutableTask",
]


"""
Unified extension system for apflow

This module provides a unified extension registration and discovery system
for all types of extensions (executors, storage, hooks, transformers, etc.).

All extensions implement the Extension interface and are registered through
the ExtensionRegistry using globally unique IDs.
"""

from apflow.core.extensions.base import Extension
from apflow.core.extensions.types import ExtensionCategory
from apflow.core.extensions.protocol import ExecutorFactory, ExecutorLike
from apflow.core.extensions.registry import (
    ExtensionRegistry,
    get_registry,
    register_extension,
    add_executor_hook,
)
from apflow.core.extensions.decorators import (
    executor_register,
    storage_register,
    hook_register,
)
from apflow.core.config import register_task_tree_hook, get_task_tree_hooks
from apflow.core.extensions.executor_metadata import (
    get_executor_metadata,
    validate_task_format,
    get_all_executor_metadata,
)

__all__ = [
    "Extension",
    "ExtensionCategory",
    "ExecutorFactory",
    "ExecutorLike",
    "ExtensionRegistry",
    "get_registry",
    "register_extension",
    "add_executor_hook",
    "executor_register",
    "storage_register",
    "hook_register",
    "register_task_tree_hook",
    "get_task_tree_hooks",
    "get_executor_metadata",
    "validate_task_format",
    "get_all_executor_metadata",
]


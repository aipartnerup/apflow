"""
Unified decorators for apflow

This module provides a single entry point for all decorators used in apflow.
Similar to Flask's app decorators (@app.before_request, @app.route, etc.), this module
provides a clean, unified API for registering hooks and extensions.

All decorators are part of the core framework and can be imported from:
    from apflow import register_pre_hook, register_post_hook, executor_register
    
Or directly from core:
    from apflow.core.decorators import register_pre_hook

Usage:
    from apflow import register_pre_hook, register_post_hook, executor_register
    
    @register_pre_hook
    async def my_pre_hook(task):
        ...
    
    @register_post_hook
    async def my_post_hook(task, inputs, result):
        ...
    
    @executor_register()
    class MyExecutor(BaseTask):
        ...
"""

# Re-export configuration decorators
from apflow.core.config import (
    register_pre_hook,
    register_post_hook,
    set_task_model_class,
    get_task_model_class,
    clear_config,
    set_use_task_creator,
    get_use_task_creator,
    set_require_existing_tasks,
    get_require_existing_tasks,
    register_task_tree_hook,
    get_task_tree_hooks,
    task_model_register,
)

# Re-export extension decorators
from apflow.core.extensions.decorators import (
    executor_register,
    storage_register,
    hook_register,
)

# Re-export tool decorator
from apflow.core.tools.decorators import tool_register

__all__ = [
    # Hook decorators
    "register_pre_hook",
    "register_post_hook",
    "register_task_tree_hook",
    "get_task_tree_hooks",
    # TaskModel configuration
    "set_task_model_class",
    "get_task_model_class",
    "task_model_register",
    "clear_config",
    # TaskCreator configuration
    "set_use_task_creator",
    "get_use_task_creator",
    # Task execution mode configuration
    "set_require_existing_tasks",
    "get_require_existing_tasks",
    # Extension registration
    "executor_register",
    "storage_register",
    "hook_register",
    # Tool registration
    "tool_register",
]


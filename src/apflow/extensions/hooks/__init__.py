"""
Hook extensions

Provides lifecycle hook implementations as ExtensionCategory.HOOK extensions.
"""

# Auto-register hooks when imported
from apflow.extensions.hooks import pre_execution_hook  # noqa: F401
from apflow.extensions.hooks import post_execution_hook  # noqa: F401

__all__ = ["pre_execution_hook", "post_execution_hook"]


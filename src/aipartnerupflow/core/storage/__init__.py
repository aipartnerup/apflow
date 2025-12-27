"""
Storage module for aipartnerupflow

Provides database session factory with default DuckDB (embedded, zero-config) and optional PostgreSQL support.
"""

from aipartnerupflow.core.storage.factory import (
    create_session,
    get_default_session,
    set_default_session,
    reset_default_session,
    # Session pool functions
    create_pooled_session,
    PooledSessionContext,
    create_task_tree_session,
    get_session_pool_manager,
    reset_session_pool_manager,
    SessionLimitExceeded,
    # Backward compatibility (deprecated)
    create_storage,
    get_default_storage,
)

from aipartnerupflow.core.storage.context import (
    get_hook_session,
    get_hook_repository,
)

__all__ = [
    "create_session",
    "get_default_session",
    "set_default_session",
    "reset_default_session",
    # Session pool functions
    "create_pooled_session",
    "PooledSessionContext",
    "create_task_tree_session",
    "get_session_pool_manager",
    "reset_session_pool_manager",
    "SessionLimitExceeded",
    # Hook execution context
    "get_hook_session",
    "get_hook_repository",
    # Backward compatibility (deprecated)
    "create_storage",
    "get_default_storage",
]

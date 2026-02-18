"""
Local conftest for session pool tests.

Prevents get_session_pool_manager() from auto-initializing with DATABASE_URL,
allowing tests to control their own database configuration via connection_string.

Without this fix, the full test suite can pollute DATABASE_URL with a PostgreSQL
URL (via use_test_db_session), causing get_session_pool_manager() to auto-initialize
with PostgreSQL (async mode). PooledSessionContext.__aenter__ then skips
re-initialization because engine is already set, ignoring the test's DuckDB
connection_string parameter, and returns AsyncSession instead of Session.
"""

import pytest
from unittest.mock import patch

from apflow.core.storage.factory import (
    SessionPoolManager,
    SessionRegistry,
    reset_session_pool_manager,
)


@pytest.fixture(autouse=True)
def _isolate_session_pool_manager():
    """
    Patch get_session_pool_manager() to create an uninitialized manager on demand.

    The real get_session_pool_manager() auto-initializes from DATABASE_URL.
    This patched version creates the manager without initializing, so that
    PooledSessionContext.__aenter__ initializes it with the test's own
    connection_string. The manager is created lazily (at call time, not at
    fixture setup time), preserving monkeypatch.setenv effects.
    """
    reset_session_pool_manager()

    def _lazy_get_or_create():
        manager = SessionRegistry.get_session_pool_manager()
        if manager is None:
            with SessionRegistry.get_session_pool_lock():
                manager = SessionRegistry.get_session_pool_manager()
                if manager is None:
                    manager = SessionPoolManager()
                    SessionRegistry.set_session_pool_manager(manager)
        return manager

    with (
        patch(
            "apflow.core.storage.factory.get_session_pool_manager",
            side_effect=_lazy_get_or_create,
        ),
        patch(
            "tests.core.storage.sqlalchemy.test_session_pool.get_session_pool_manager",
            side_effect=_lazy_get_or_create,
        ),
    ):
        yield

    reset_session_pool_manager()

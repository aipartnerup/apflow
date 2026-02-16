"""Tests for distributed runtime startup integration in the API server."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apflow.api.main import _DistributedLifespanApp, _init_distributed_runtime


class TestInitDistributedRuntime:
    """Tests for _init_distributed_runtime()."""

    @patch("apflow.core.distributed.config.DistributedConfig.from_env")
    def test_disabled_returns_none(self, mock_from_env: MagicMock) -> None:
        """When cluster mode is disabled, return (None, None)."""
        mock_config = MagicMock()
        mock_config.enabled = False
        mock_from_env.return_value = mock_config

        runtime, session_factory = _init_distributed_runtime()

        assert runtime is None
        assert session_factory is None

    @patch("apflow.core.execution.task_executor.TaskExecutor")
    @patch("apflow.core.distributed.runtime.DistributedRuntime", autospec=False)
    @patch("apflow.core.storage.factory.normalize_postgresql_url", return_value="postgresql://test")
    @patch("apflow.core.storage.factory.is_postgresql_url", return_value=True)
    @patch(
        "apflow.core.storage.factory._get_database_url_from_env", return_value="postgresql://test"
    )
    @patch("apflow.core.distributed.config.DistributedConfig.from_env")
    def test_enabled_creates_runtime(
        self,
        mock_from_env: MagicMock,
        mock_get_db_url: MagicMock,
        mock_is_pg: MagicMock,
        mock_normalize: MagicMock,
        mock_runtime_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """When cluster mode is enabled with a PostgreSQL URL, create and inject runtime."""
        mock_config = MagicMock()
        mock_config.enabled = True
        mock_config.node_id = "node-abc123"
        mock_config.node_role = "auto"
        mock_from_env.return_value = mock_config

        mock_runtime = MagicMock()
        mock_runtime_cls.return_value = mock_runtime

        mock_executor = MagicMock()
        mock_executor_cls.return_value = mock_executor

        runtime, session_factory = _init_distributed_runtime()

        assert runtime is mock_runtime
        assert session_factory is not None
        mock_config.validate_and_initialize.assert_called_once()
        mock_runtime_cls.assert_called_once_with(mock_config, session_factory)
        mock_executor.set_distributed_runtime.assert_called_once_with(mock_runtime)

    @patch("apflow.core.storage.factory._get_database_url_from_env", return_value=None)
    @patch("apflow.core.distributed.config.DistributedConfig.from_env")
    def test_no_db_url_returns_none(
        self,
        mock_from_env: MagicMock,
        mock_get_db_url: MagicMock,
    ) -> None:
        """When no DATABASE_URL is set, return (None, None) with a warning."""
        mock_config = MagicMock()
        mock_config.enabled = True
        mock_from_env.return_value = mock_config

        runtime, session_factory = _init_distributed_runtime()

        assert runtime is None
        assert session_factory is None

    @patch("apflow.core.storage.factory.is_postgresql_url", return_value=False)
    @patch(
        "apflow.core.storage.factory._get_database_url_from_env", return_value="duckdb:///test.db"
    )
    @patch("apflow.core.distributed.config.DistributedConfig.from_env")
    def test_non_postgresql_url_returns_none(
        self,
        mock_from_env: MagicMock,
        mock_get_db_url: MagicMock,
        mock_is_pg: MagicMock,
    ) -> None:
        """When DATABASE_URL is not PostgreSQL, return (None, None)."""
        mock_config = MagicMock()
        mock_config.enabled = True
        mock_from_env.return_value = mock_config

        runtime, session_factory = _init_distributed_runtime()

        assert runtime is None
        assert session_factory is None


class TestDistributedLifespanApp:
    """Tests for _DistributedLifespanApp ASGI wrapper."""

    @pytest.mark.asyncio
    async def test_startup_shutdown_lifecycle(self) -> None:
        """ASGI lifespan events should start and stop the runtime."""
        mock_runtime = MagicMock()
        mock_runtime.start = AsyncMock()
        mock_runtime.shutdown = AsyncMock()

        mock_inner_app = AsyncMock()
        wrapper = _DistributedLifespanApp(mock_inner_app, mock_runtime)

        sent_messages: list[dict[str, str]] = []

        async def mock_send(msg: dict[str, str]) -> None:
            sent_messages.append(msg)

        messages = iter(
            [
                {"type": "lifespan.startup"},
                {"type": "lifespan.shutdown"},
            ]
        )

        async def mock_receive() -> dict[str, str]:
            return next(messages)

        scope = {"type": "lifespan"}

        await wrapper(scope, mock_receive, mock_send)

        assert {"type": "lifespan.startup.complete"} in sent_messages
        assert {"type": "lifespan.shutdown.complete"} in sent_messages
        mock_runtime.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_lifespan_delegates_to_inner_app(self) -> None:
        """Non-lifespan scopes should be forwarded to the inner app."""
        mock_runtime = MagicMock()
        mock_inner_app = AsyncMock()

        wrapper = _DistributedLifespanApp(mock_inner_app, mock_runtime)

        scope = {"type": "http"}
        receive = AsyncMock()
        send = AsyncMock()

        await wrapper(scope, receive, send)

        mock_inner_app.assert_awaited_once_with(scope, receive, send)


class TestCreateRunnableAppDistributed:
    """Tests for distributed integration in create_runnable_app()."""

    @patch("apflow.api.main._init_distributed_runtime", return_value=(None, None))
    @patch("apflow.api.main.create_app_by_protocol")
    @patch("apflow.api.main._load_custom_task_model")
    @patch("apflow.api.main.get_default_session")
    @patch("apflow.api.main.initialize_extensions")
    @patch("apflow.api.main._load_env_file")
    @patch("apflow.api.main._setup_development_environment")
    def test_without_distributed_returns_plain_app(
        self,
        mock_setup_dev: MagicMock,
        mock_load_env: MagicMock,
        mock_init_ext: MagicMock,
        mock_get_session: MagicMock,
        mock_load_task_model: MagicMock,
        mock_create_app: MagicMock,
        mock_init_dist: MagicMock,
    ) -> None:
        """When distributed is disabled, app is not wrapped."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        sentinel_app = MagicMock()
        mock_create_app.return_value = sentinel_app

        from apflow.api.main import create_runnable_app

        app = create_runnable_app()

        assert app is sentinel_app
        mock_init_dist.assert_called_once()

    @patch("apflow.api.main._init_distributed_runtime")
    @patch("apflow.api.main.create_app_by_protocol")
    @patch("apflow.api.main._load_custom_task_model")
    @patch("apflow.api.main.get_default_session")
    @patch("apflow.api.main.initialize_extensions")
    @patch("apflow.api.main._load_env_file")
    @patch("apflow.api.main._setup_development_environment")
    def test_with_distributed_wraps_app(
        self,
        mock_setup_dev: MagicMock,
        mock_load_env: MagicMock,
        mock_init_ext: MagicMock,
        mock_get_session: MagicMock,
        mock_load_task_model: MagicMock,
        mock_create_app: MagicMock,
        mock_init_dist: MagicMock,
    ) -> None:
        """When distributed is enabled, app is wrapped with _DistributedLifespanApp."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        sentinel_app = MagicMock()
        mock_create_app.return_value = sentinel_app

        mock_runtime = MagicMock()
        mock_init_dist.return_value = (mock_runtime, MagicMock())

        from apflow.api.main import create_runnable_app

        app = create_runnable_app()

        assert isinstance(app, _DistributedLifespanApp)
        assert app._app is sentinel_app
        assert app._runtime is mock_runtime

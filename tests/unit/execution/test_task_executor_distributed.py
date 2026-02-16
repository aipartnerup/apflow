"""Tests for TaskExecutor distributed integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apflow.core.execution.task_executor import TaskExecutor


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset TaskExecutor singleton between tests."""
    TaskExecutor._instance = None
    TaskExecutor._initialized = False
    yield
    TaskExecutor._instance = None
    TaskExecutor._initialized = False


class TestDistributedConfigLoading:
    """Tests that TaskExecutor loads DistributedConfig from env."""

    def test_loads_distributed_config(self) -> None:
        """TaskExecutor initialises distributed_config from environment."""
        executor = TaskExecutor()
        assert executor.distributed_config is not None
        assert isinstance(executor.distributed_config.enabled, bool)

    def test_distributed_runtime_defaults_none(self) -> None:
        """distributed_runtime defaults to None until explicitly set."""
        executor = TaskExecutor()
        assert executor.distributed_runtime is None

    def test_set_distributed_runtime(self) -> None:
        """set_distributed_runtime attaches the runtime object."""
        executor = TaskExecutor()
        runtime = MagicMock()
        executor.set_distributed_runtime(runtime)
        assert executor.distributed_runtime is runtime


class TestLeaderOrSingleNode:
    """Tests for _is_leader_or_single_node helper."""

    def test_single_node_mode_returns_true(self) -> None:
        """When distributed is disabled, always returns True."""
        executor = TaskExecutor()
        executor.distributed_config.enabled = False
        assert executor._is_leader_or_single_node() is True

    def test_distributed_no_runtime_returns_true(self) -> None:
        """When distributed enabled but no runtime attached, returns True."""
        executor = TaskExecutor()
        executor.distributed_config.enabled = True
        executor.distributed_runtime = None
        assert executor._is_leader_or_single_node() is True

    def test_leader_returns_true(self) -> None:
        """When runtime reports is_leader=True, returns True."""
        executor = TaskExecutor()
        executor.distributed_config.enabled = True
        runtime = MagicMock()
        runtime.is_leader = True
        executor.distributed_runtime = runtime
        assert executor._is_leader_or_single_node() is True

    def test_non_leader_returns_false(self) -> None:
        """When runtime reports is_leader=False, returns False."""
        executor = TaskExecutor()
        executor.distributed_config.enabled = True
        runtime = MagicMock()
        runtime.is_leader = False
        executor.distributed_runtime = runtime
        assert executor._is_leader_or_single_node() is False


class TestExecuteTaskTreeDistributedRejection:
    """Tests that execute_task_tree rejects on non-leader nodes."""

    @pytest.mark.asyncio
    async def test_non_leader_rejects_execution(self) -> None:
        """execute_task_tree returns rejection dict when node is not leader."""
        executor = TaskExecutor()
        executor.distributed_config.enabled = True
        runtime = MagicMock()
        runtime.is_leader = False
        runtime.current_role = "worker"
        executor.distributed_runtime = runtime

        task_tree = MagicMock()
        result = await executor.execute_task_tree(
            task_tree=task_tree,
            root_task_id="root-1",
            db_session=MagicMock(),
        )

        assert result["status"] == "rejected"
        assert result["root_task_id"] == "root-1"
        assert "leader" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_single_node_does_not_reject(self) -> None:
        """execute_task_tree does not reject in single-node mode."""
        executor = TaskExecutor()
        executor.distributed_config.enabled = False

        # Mock everything so we don't actually execute
        with patch.object(executor, "is_task_running", return_value=True):
            task_tree = MagicMock()
            result = await executor.execute_task_tree(
                task_tree=task_tree,
                root_task_id="root-1",
                db_session=MagicMock(),
            )

        # Should hit the "already running" check, not rejection
        assert result["status"] == "already_running"

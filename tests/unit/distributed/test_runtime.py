"""Tests for DistributedRuntime coordinator with role selection."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from apflow.core.distributed.config import DistributedConfig, utcnow as _utcnow
from apflow.core.distributed.runtime import DistributedRuntime


def _make_config(**overrides: Any) -> DistributedConfig:
    """Create a test DistributedConfig with fast intervals."""
    defaults = {
        "enabled": True,
        "node_id": "test-node",
        "node_role": "auto",
        "poll_interval_seconds": 0.05,
        "heartbeat_interval_seconds": 0.05,
        "lease_duration_seconds": 30,
        "leader_renew_seconds": 0.05,
        "leader_lease_seconds": 30,
        "lease_cleanup_interval_seconds": 0.05,
        "max_parallel_tasks_per_node": 2,
    }
    defaults.update(overrides)
    return DistributedConfig(**defaults)


def _make_runtime(
    config: DistributedConfig | None = None,
    node_registry: MagicMock | None = None,
    leader_election: MagicMock | None = None,
    lease_manager: MagicMock | None = None,
    idempotency_manager: MagicMock | None = None,
    session_factory: MagicMock | None = None,
    task_executor: AsyncMock | None = None,
) -> DistributedRuntime:
    """Create a DistributedRuntime with injected mock dependencies."""
    cfg = config or _make_config()
    runtime = DistributedRuntime.__new__(DistributedRuntime)
    runtime._config = cfg
    runtime._node_id = cfg.node_id or "test-node"
    runtime._session_factory = session_factory or MagicMock()
    runtime._node_registry = node_registry or MagicMock()
    runtime._leader_election = leader_election or MagicMock()
    runtime._lease_manager = lease_manager or MagicMock()
    runtime._idempotency = idempotency_manager or MagicMock()
    runtime._task_executor = task_executor or AsyncMock(return_value={"status": "completed"})
    runtime._role = "initializing"
    runtime._lease_token = None
    runtime._lease_expires_at = None
    runtime._worker_runtime = None
    runtime._background_tasks = []
    runtime._shutdown_event = asyncio.Event()
    return runtime


class TestRoleSelection:
    """Tests for role selection state machine."""

    @pytest.mark.asyncio
    async def test_auto_role_attempts_leader_first(self) -> None:
        """node_role='auto': try_acquire is called; on success, role becomes 'leader'."""
        election = MagicMock()
        election.try_acquire.return_value = (True, "lease-token-abc")

        runtime = _make_runtime(
            config=_make_config(node_role="auto"),
            leader_election=election,
        )

        await runtime._select_role()

        election.try_acquire.assert_called_once_with("test-node")
        assert runtime.current_role == "leader"
        assert runtime.is_leader is True

    @pytest.mark.asyncio
    async def test_auto_role_falls_back_to_worker(self) -> None:
        """node_role='auto': if try_acquire fails, role becomes 'worker'."""
        election = MagicMock()
        election.try_acquire.return_value = (False, None)

        runtime = _make_runtime(
            config=_make_config(node_role="auto"),
            leader_election=election,
        )

        await runtime._select_role()

        assert runtime.current_role == "worker"
        assert runtime.is_leader is False

    @pytest.mark.asyncio
    async def test_leader_role_succeeds_on_acquire(self) -> None:
        """node_role='leader': becomes leader if acquire succeeds."""
        election = MagicMock()
        election.try_acquire.return_value = (True, "lease-token-xyz")

        runtime = _make_runtime(
            config=_make_config(node_role="leader"),
            leader_election=election,
        )

        await runtime._select_role()

        assert runtime.current_role == "leader"

    @pytest.mark.asyncio
    async def test_leader_role_fails_if_cannot_acquire(self) -> None:
        """node_role='leader': raises RuntimeError if leadership acquisition fails."""
        election = MagicMock()
        election.try_acquire.return_value = (False, None)

        runtime = _make_runtime(
            config=_make_config(node_role="leader"),
            leader_election=election,
        )

        with pytest.raises(RuntimeError, match="could not acquire leadership"):
            await runtime._select_role()

    @pytest.mark.asyncio
    async def test_worker_role_never_attempts_leadership(self) -> None:
        """node_role='worker': try_acquire is never called."""
        election = MagicMock()

        runtime = _make_runtime(
            config=_make_config(node_role="worker"),
            leader_election=election,
        )

        await runtime._select_role()

        election.try_acquire.assert_not_called()
        assert runtime.current_role == "worker"

    @pytest.mark.asyncio
    async def test_observer_role_read_only(self) -> None:
        """node_role='observer': no leader election, no worker polling."""
        election = MagicMock()

        runtime = _make_runtime(
            config=_make_config(node_role="observer"),
            leader_election=election,
        )

        await runtime._select_role()

        election.try_acquire.assert_not_called()
        assert runtime.current_role == "observer"
        assert runtime.is_leader is False


class TestLifecycle:
    """Tests for start/shutdown lifecycle."""

    @pytest.mark.asyncio
    async def test_start_registers_node_and_selects_role(self) -> None:
        """start() registers node and selects role."""
        registry = MagicMock()
        election = MagicMock()
        election.try_acquire.return_value = (False, None)

        runtime = _make_runtime(
            config=_make_config(node_role="observer"),
            node_registry=registry,
            leader_election=election,
        )

        task = asyncio.create_task(runtime.start())
        await asyncio.sleep(0.1)
        await runtime.shutdown()
        await task

        registry.register_node.assert_called_once()
        assert runtime.current_role == "observer"

    @pytest.mark.asyncio
    async def test_shutdown_sets_event(self) -> None:
        """shutdown() sets the shutdown event."""
        runtime = _make_runtime(config=_make_config(node_role="observer"))

        task = asyncio.create_task(runtime.start())
        await asyncio.sleep(0.1)
        await runtime.shutdown()
        await task

        assert runtime._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_deregisters_node(self) -> None:
        """shutdown() deregisters node from registry."""
        registry = MagicMock()
        runtime = _make_runtime(
            config=_make_config(node_role="observer"),
            node_registry=registry,
        )

        task = asyncio.create_task(runtime.start())
        await asyncio.sleep(0.1)
        await runtime.shutdown()
        await task

        registry.deregister_node.assert_called_once_with("test-node")

    @pytest.mark.asyncio
    async def test_shutdown_releases_leadership(self) -> None:
        """shutdown() releases leadership if node was leader."""
        election = MagicMock()
        election.try_acquire.return_value = (True, "token-abc")

        runtime = _make_runtime(
            config=_make_config(node_role="leader"),
            leader_election=election,
        )

        task = asyncio.create_task(runtime.start())
        await asyncio.sleep(0.1)
        await runtime.shutdown()
        await task

        election.release_leadership.assert_called_once_with("test-node", "token-abc")


class TestLeaderBackgroundTasks:
    """Tests for leader-specific background tasks."""

    @pytest.mark.asyncio
    async def test_leader_runs_lease_cleanup_loop(self) -> None:
        """Leader runs cleanup_expired_leases periodically."""
        election = MagicMock()
        election.try_acquire.return_value = (True, "token")
        election.renew_leadership.return_value = True
        lease_mgr = MagicMock()

        runtime = _make_runtime(
            config=_make_config(node_role="leader"),
            leader_election=election,
            lease_manager=lease_mgr,
        )

        task = asyncio.create_task(runtime.start())
        await asyncio.sleep(0.2)
        await runtime.shutdown()
        await task

        assert lease_mgr.cleanup_expired_leases.call_count >= 1

    @pytest.mark.asyncio
    async def test_leader_runs_node_cleanup_loop(self) -> None:
        """Leader detects stale and dead nodes periodically."""
        election = MagicMock()
        election.try_acquire.return_value = (True, "token")
        election.renew_leadership.return_value = True
        registry = MagicMock()

        runtime = _make_runtime(
            config=_make_config(node_role="leader"),
            leader_election=election,
            node_registry=registry,
        )

        task = asyncio.create_task(runtime.start())
        await asyncio.sleep(0.2)
        await runtime.shutdown()
        await task

        assert registry.detect_stale_nodes.call_count >= 1
        assert registry.detect_dead_nodes.call_count >= 1

    @pytest.mark.asyncio
    async def test_leader_renewal_loop(self) -> None:
        """Leader renews its own leadership lease periodically."""
        election = MagicMock()
        election.try_acquire.return_value = (True, "token")
        election.renew_leadership.return_value = True

        runtime = _make_runtime(
            config=_make_config(node_role="leader"),
            leader_election=election,
        )

        task = asyncio.create_task(runtime.start())
        await asyncio.sleep(0.2)
        await runtime.shutdown()
        await task

        assert election.renew_leadership.call_count >= 1

    @pytest.mark.asyncio
    async def test_leader_renewal_failure_demotes_to_worker(self) -> None:
        """If leader lease renewal fails, runtime transitions to worker role."""
        election = MagicMock()
        election.try_acquire.return_value = (True, "token")
        election.renew_leadership.return_value = False

        runtime = _make_runtime(
            config=_make_config(node_role="leader"),
            leader_election=election,
        )

        task = asyncio.create_task(runtime.start())
        await asyncio.sleep(0.2)
        await runtime.shutdown()
        await task

        assert runtime.current_role == "worker"


class TestProperties:
    """Tests for runtime properties."""

    @pytest.mark.asyncio
    async def test_is_leader_property(self) -> None:
        """is_leader returns True only when role is 'leader' with a valid lease."""
        runtime = _make_runtime()
        future = (_utcnow() + timedelta(seconds=300)).timestamp()

        runtime._role = "leader"
        runtime._lease_expires_at = future
        assert runtime.is_leader is True

        runtime._role = "worker"
        assert runtime.is_leader is False

        runtime._role = "observer"
        assert runtime.is_leader is False

    @pytest.mark.asyncio
    async def test_is_leader_expired_lease_demotes(self) -> None:
        """is_leader returns False and demotes to worker when lease is expired."""
        runtime = _make_runtime()
        past = (_utcnow() - timedelta(seconds=10)).timestamp()

        runtime._role = "leader"
        runtime._lease_token = "token"
        runtime._lease_expires_at = past

        assert runtime.is_leader is False
        assert runtime.current_role == "worker"
        assert runtime._lease_token is None
        assert runtime._lease_expires_at is None

    @pytest.mark.asyncio
    async def test_current_role_property(self) -> None:
        """current_role returns the active role string."""
        runtime = _make_runtime()

        runtime._role = "leader"
        assert runtime.current_role == "leader"

        runtime._role = "worker"
        assert runtime.current_role == "worker"

        runtime._role = "observer"
        assert runtime.current_role == "observer"

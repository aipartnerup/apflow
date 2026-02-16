"""Tests for LeaseManager distributed service."""

from datetime import datetime, timedelta, timezone

from apflow.core.distributed.lease_manager import LeaseManager
from apflow.core.storage.sqlalchemy.models import (
    TaskLease,
    TaskModel,
)


class TestLeaseManager:
    """Tests for LeaseManager service methods."""

    def test_acquire_lease_success(
        self, session_factory, config, session, sample_node, sample_task
    ):
        """Acquiring a lease on an unleased task succeeds."""
        manager = LeaseManager(session_factory, config)

        lease = manager.acquire_lease("task-1", "worker-1")

        assert lease is not None
        assert lease.task_id == "task-1"
        assert lease.node_id == "worker-1"
        assert len(lease.lease_token) == 32
        assert lease.expires_at > datetime.now(timezone.utc)

    def test_acquire_lease_already_leased(
        self, session_factory, config, session, sample_node, sample_task
    ):
        """Acquiring a lease on an already-leased task returns None."""
        manager = LeaseManager(session_factory, config)

        first = manager.acquire_lease("task-1", "worker-1")
        assert first is not None

        second = manager.acquire_lease("task-1", "worker-1")
        assert second is None

    def test_renew_lease_extends_expiry(
        self, session_factory, config, session, sample_node, sample_task
    ):
        """Renewing a valid lease extends its expiry time."""
        manager = LeaseManager(session_factory, config)

        lease = manager.acquire_lease("task-1", "worker-1")
        assert lease is not None

        old_expiry = lease.expires_at
        result = manager.renew_lease(lease.lease_token)

        assert result is True

        # Verify expiry was extended
        session.expire_all()
        updated = session.get(TaskLease, "task-1")
        assert updated is not None
        assert updated.expires_at > old_expiry

    def test_renew_lease_invalid_token_fails(self, session_factory, config):
        """Renewing with an invalid token returns False."""
        manager = LeaseManager(session_factory, config)

        result = manager.renew_lease("nonexistent-token-abcdef1234567890")
        assert result is False

    def test_renew_lease_expired_fails(
        self, session_factory, config, session, sample_node, sample_task
    ):
        """Renewing an expired lease returns False."""
        manager = LeaseManager(session_factory, config)

        lease = manager.acquire_lease("task-1", "worker-1")
        assert lease is not None

        # Force the lease to be expired
        db_lease = session.get(TaskLease, "task-1")
        db_lease.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        session.commit()

        result = manager.renew_lease(lease.lease_token)
        assert result is False

    def test_cleanup_expired_leases(
        self, session_factory, config, session, sample_node, sample_task
    ):
        """Cleanup removes expired leases and reverts task status to pending."""
        manager = LeaseManager(session_factory, config)

        lease = manager.acquire_lease("task-1", "worker-1")
        assert lease is not None

        # Mark task as in_progress and expire the lease
        task = session.get(TaskModel, "task-1")
        task.status = "in_progress"
        db_lease = session.get(TaskLease, "task-1")
        db_lease.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        session.commit()

        cleaned = manager.cleanup_expired_leases()

        assert "task-1" in cleaned

        # Verify lease removed
        session.expire_all()
        remaining = session.get(TaskLease, "task-1")
        assert remaining is None

        # Verify task reverted to pending
        task = session.get(TaskModel, "task-1")
        assert task.status == "pending"

    def test_release_lease_removes_entry(
        self, session_factory, config, session, sample_node, sample_task
    ):
        """Releasing a lease with the correct token removes it."""
        manager = LeaseManager(session_factory, config)

        lease = manager.acquire_lease("task-1", "worker-1")
        assert lease is not None

        manager.release_lease("task-1", lease.lease_token)

        session.expire_all()
        remaining = session.get(TaskLease, "task-1")
        assert remaining is None

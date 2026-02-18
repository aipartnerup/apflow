"""Tests for LeaderElection distributed service."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from apflow.core.distributed.config import as_utc, utcnow as _utcnow
from apflow.core.distributed.leader_election import LeaderElection
from apflow.core.storage.sqlalchemy.models import ClusterLeader, DistributedNode


@pytest.fixture
def leader_node(session) -> DistributedNode:
    """A registered node that can be used for leader election."""
    node = DistributedNode(
        node_id="leader-1",
        executor_types=["a2a"],
        capabilities={},
        status="healthy",
        heartbeat_at=datetime.now(timezone.utc),
    )
    session.add(node)
    session.commit()
    return node


@pytest.fixture
def second_node(session) -> DistributedNode:
    """A second registered node for contention tests."""
    node = DistributedNode(
        node_id="leader-2",
        executor_types=["a2a"],
        capabilities={},
        status="healthy",
        heartbeat_at=datetime.now(timezone.utc),
    )
    session.add(node)
    session.commit()
    return node


class TestLeaderElection:
    """Tests for LeaderElection service methods."""

    def test_first_node_wins_leadership(self, session_factory, config, leader_node):
        """The first node to try_acquire becomes leader."""
        election = LeaderElection(session_factory, config)

        success, token = election.try_acquire("leader-1")

        assert success is True
        assert token is not None
        assert len(token) == 32

    def test_second_node_fails_gracefully(self, session_factory, config, leader_node, second_node):
        """A second node cannot acquire leadership while the first holds it."""
        election = LeaderElection(session_factory, config)

        success_1, token_1 = election.try_acquire("leader-1")
        assert success_1 is True

        success_2, token_2 = election.try_acquire("leader-2")
        assert success_2 is False
        assert token_2 is None

    def test_renew_extends_ttl(self, session_factory, config, session, leader_node):
        """Renewing leadership extends the expiry time."""
        election = LeaderElection(session_factory, config)

        success, token = election.try_acquire("leader-1")
        assert success is True
        assert token is not None

        old_leader = session.get(ClusterLeader, "singleton")
        old_expiry = old_leader.expires_at

        result = election.renew_leadership("leader-1", token)
        assert result is True

        session.refresh(old_leader)
        assert as_utc(old_leader.expires_at) > as_utc(old_expiry)

    def test_renew_wrong_token_fails(self, session_factory, config, leader_node):
        """Renewing with the wrong token returns False."""
        election = LeaderElection(session_factory, config)

        success, _ = election.try_acquire("leader-1")
        assert success is True

        result = election.renew_leadership("leader-1", "wrong-token-abcdef1234567890")
        assert result is False

    def test_stale_leader_replaced(
        self, session_factory, config, session, leader_node, second_node
    ):
        """After a stale leader is cleaned up, a new node can acquire leadership."""
        election = LeaderElection(session_factory, config)

        success_1, token_1 = election.try_acquire("leader-1")
        assert success_1 is True

        # Expire the leader lease
        leader_row = session.get(ClusterLeader, "singleton")
        leader_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        session.commit()

        cleaned = election.cleanup_stale_leader()
        assert cleaned is True

        # Now second node can acquire
        success_2, token_2 = election.try_acquire("leader-2")
        assert success_2 is True
        assert token_2 is not None

    def test_graceful_release(self, session_factory, config, session, leader_node):
        """Releasing leadership removes the leader row."""
        election = LeaderElection(session_factory, config)

        success, token = election.try_acquire("leader-1")
        assert success is True
        assert token is not None

        election.release_leadership("leader-1", token)

        session.expire_all()
        remaining = session.get(ClusterLeader, "singleton")
        assert remaining is None

    def test_get_current_leader(self, session_factory, config, leader_node):
        """get_current_leader returns the active leader's node_id."""
        election = LeaderElection(session_factory, config)

        # No leader yet
        assert election.get_current_leader() is None

        success, _ = election.try_acquire("leader-1")
        assert success is True

        assert election.get_current_leader() == "leader-1"

    def test_is_leader_true_for_holder(self, session_factory, config, leader_node, second_node):
        """is_leader returns True only for the current leader node."""
        election = LeaderElection(session_factory, config)

        success, _ = election.try_acquire("leader-1")
        assert success is True

        assert election.is_leader("leader-1") is True
        assert election.is_leader("leader-2") is False

    def test_get_current_leader_returns_none_when_expired(
        self, session_factory, config, leader_node
    ):
        """get_current_leader returns None when leader lease is expired."""
        election = LeaderElection(session_factory, config)

        acquired, token = election.try_acquire("leader-1")
        assert acquired

        # Fast-forward time past expiry
        future_time = _utcnow() + timedelta(seconds=config.leader_lease_seconds + 10)
        with patch("apflow.core.distributed.leader_election._utcnow", return_value=future_time):
            assert election.get_current_leader() is None


class TestLeaderElectionORMFallback:
    """Tests for the ORM-based fallback leader acquisition path."""

    def test_try_acquire_orm_path(self, session_factory, config, leader_node):
        """ORM path acquires leadership when is_postgresql returns False."""
        election = LeaderElection(session_factory, config)
        with patch(
            "apflow.core.distributed.leader_election.is_postgresql",
            return_value=False,
        ):
            acquired, token = election.try_acquire("leader-1")
        assert acquired is True
        assert token is not None
        assert len(token) == 32

    def test_try_acquire_orm_path_held_by_other(
        self, session_factory, config, leader_node, second_node
    ):
        """ORM path fails when active leader exists."""
        election = LeaderElection(session_factory, config)
        with patch(
            "apflow.core.distributed.leader_election.is_postgresql",
            return_value=False,
        ):
            acquired1, token1 = election.try_acquire("leader-1")
            acquired2, token2 = election.try_acquire("leader-2")
        assert acquired1 is True
        assert token1 is not None
        assert acquired2 is False
        assert token2 is None

    def test_try_acquire_orm_path_expired_leader_replaced(
        self, session_factory, config, leader_node, second_node
    ):
        """ORM path replaces expired leader."""
        election = LeaderElection(session_factory, config)
        with patch(
            "apflow.core.distributed.leader_election.is_postgresql",
            return_value=False,
        ):
            acquired1, token1 = election.try_acquire("leader-1")
            assert acquired1 is True

            # Time-travel past expiry so the leader row is expired
            future = datetime.now(timezone.utc) + timedelta(
                seconds=config.leader_lease_seconds + 10
            )
            with patch(
                "apflow.core.distributed.leader_election._utcnow",
                return_value=future,
            ):
                acquired2, token2 = election.try_acquire("leader-2")

        assert acquired2 is True
        assert token2 is not None


class TestLeaderElectionValidation:
    """Tests for input validation guards in LeaderElection."""

    def test_try_acquire_empty_node_id_raises(self, session_factory, config):
        """try_acquire rejects empty node_id."""
        election = LeaderElection(session_factory, config)
        with pytest.raises(ValueError, match="must not be empty"):
            election.try_acquire("")

    def test_renew_leadership_empty_node_id_raises(self, session_factory, config):
        """renew_leadership rejects empty node_id."""
        election = LeaderElection(session_factory, config)
        with pytest.raises(ValueError, match="must not be empty"):
            election.renew_leadership("", "token")

    def test_renew_leadership_empty_token_raises(self, session_factory, config):
        """renew_leadership rejects empty lease_token."""
        election = LeaderElection(session_factory, config)
        with pytest.raises(ValueError, match="must not be empty"):
            election.renew_leadership("node-1", "")

    def test_release_leadership_empty_node_id_raises(self, session_factory, config):
        """release_leadership rejects empty node_id."""
        election = LeaderElection(session_factory, config)
        with pytest.raises(ValueError, match="must not be empty"):
            election.release_leadership("", "token")

    def test_release_leadership_empty_token_raises(self, session_factory, config):
        """release_leadership rejects empty lease_token."""
        election = LeaderElection(session_factory, config)
        with pytest.raises(ValueError, match="must not be empty"):
            election.release_leadership("node-1", "")

    def test_is_leader_empty_node_id_raises(self, session_factory, config):
        """is_leader rejects empty node_id."""
        election = LeaderElection(session_factory, config)
        with pytest.raises(ValueError, match="must not be empty"):
            election.is_leader("")

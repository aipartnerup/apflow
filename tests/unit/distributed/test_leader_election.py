"""Tests for LeaderElection distributed service."""

import pytest
from datetime import datetime, timedelta, timezone

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
        assert old_leader.expires_at > old_expiry

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

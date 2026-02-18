"""Leader election service for distributed cluster coordination.

Provides leader election using a singleton database row pattern.
Only one node can hold leadership at a time, with lease-based expiration.
"""

import uuid
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apflow.core.distributed.config import (
    DistributedConfig,
    as_utc,
    is_postgresql,
    utcnow as _utcnow,
)
from apflow.core.storage.sqlalchemy.models import ClusterLeader
from apflow.logger import get_logger

logger = get_logger(__name__)

SINGLETON_LEADER_ID = "singleton"


class LeaderElection:
    """Manages leader election via a singleton database row with lease expiry."""

    def __init__(self, session_factory: sessionmaker, config: DistributedConfig) -> None:
        self._session_factory = session_factory
        self._config = config

    def try_acquire(self, node_id: str) -> tuple[bool, str | None]:
        """Attempt to acquire leadership for the given node.

        Returns (True, lease_token) if leadership was acquired,
        or (False, None) if another node currently holds it or lost a race.
        """
        if not node_id:
            raise ValueError("node_id must not be empty")

        with self._session_factory() as session:
            if is_postgresql(session):
                return self._try_acquire_postgresql(session, node_id)
            return self._try_acquire_default(session, node_id)

    def _try_acquire_postgresql(self, session: Session, node_id: str) -> tuple[bool, str | None]:
        """Atomic leader acquisition using PostgreSQL INSERT ON CONFLICT."""
        now = _utcnow()
        lease_token = uuid.uuid4().hex[:32]
        expires_at = now + timedelta(seconds=self._config.leader_lease_seconds)

        # Delete expired rows first
        session.execute(
            text(
                "DELETE FROM apflow_cluster_leader " "WHERE leader_id = :lid AND expires_at <= :now"
            ),
            {"lid": SINGLETON_LEADER_ID, "now": now},
        )

        # Atomic insert; DO NOTHING if a live row exists
        result = session.execute(
            text(
                "INSERT INTO apflow_cluster_leader "
                "(leader_id, node_id, lease_token, expires_at) "
                "VALUES (:lid, :nid, :tok, :exp) "
                "ON CONFLICT (leader_id) DO NOTHING "
                "RETURNING node_id"
            ),
            {
                "lid": SINGLETON_LEADER_ID,
                "nid": node_id,
                "tok": lease_token,
                "exp": expires_at,
            },
        )
        row = result.fetchone()
        session.commit()

        if row is not None:
            logger.info("Leadership acquired by node %s", node_id)
            return True, lease_token

        logger.info("Leadership acquisition failed for %s: held by another node", node_id)
        return False, None

    def _try_acquire_default(self, session: Session, node_id: str) -> tuple[bool, str | None]:
        """ORM-based leader acquisition for SQLite and other dialects."""
        existing = session.get(ClusterLeader, SINGLETON_LEADER_ID)
        now = _utcnow()

        # SQLAlchemy Column[DateTime] comparison not recognized by pyright as supporting > operator
        if existing is not None and as_utc(existing.expires_at) > now:  # type: ignore[operator]
            logger.info(
                "Leadership acquisition failed for %s: held by %s",
                node_id,
                existing.node_id,
            )
            return False, None

        # Remove expired leader row if present
        if existing is not None:
            session.delete(existing)
            session.flush()

        lease_token = uuid.uuid4().hex[:32]
        expires_at = now + timedelta(seconds=self._config.leader_lease_seconds)

        leader = ClusterLeader(
            leader_id=SINGLETON_LEADER_ID,
            node_id=node_id,
            lease_token=lease_token,
            expires_at=expires_at,
        )
        session.add(leader)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.info("Leadership acquisition race lost for node %s", node_id)
            return False, None
        logger.info("Leadership acquired by node %s", node_id)
        return True, lease_token

    def renew_leadership(self, node_id: str, lease_token: str) -> bool:
        """Renew leadership lease if the node_id and token match.

        Uses an atomic UPDATE with a WHERE clause that checks node_id,
        lease_token, and expiry to prevent TOCTOU races where a stale
        leader could accidentally extend a different node's lease.

        Returns True if renewal succeeded, False otherwise.
        """
        if not node_id or not lease_token:
            raise ValueError("node_id and lease_token must not be empty")

        with self._session_factory() as session:
            now = _utcnow()
            new_expires = now + timedelta(seconds=self._config.leader_lease_seconds)
            result = session.execute(
                text(
                    "UPDATE apflow_cluster_leader "
                    "SET expires_at = :exp "
                    "WHERE leader_id = :lid AND node_id = :nid "
                    "AND lease_token = :tok AND expires_at > :now"
                ),
                {
                    "exp": new_expires,
                    "lid": SINGLETON_LEADER_ID,
                    "nid": node_id,
                    "tok": lease_token,
                    "now": now,
                },
            )
            session.commit()

            if result.rowcount > 0:
                logger.info("Leadership renewed by node %s", node_id)
                return True

            logger.info("Leadership renewal failed for node %s", node_id)
            return False

    def release_leadership(self, node_id: str, lease_token: str) -> None:
        """Gracefully release leadership if the node_id and token match.

        Uses an atomic DELETE with a WHERE clause to prevent TOCTOU races
        where a stale leader could delete a different node's leadership row.
        """
        if not node_id or not lease_token:
            raise ValueError("node_id and lease_token must not be empty")

        with self._session_factory() as session:
            result = session.execute(
                text(
                    "DELETE FROM apflow_cluster_leader "
                    "WHERE leader_id = :lid AND node_id = :nid AND lease_token = :tok"
                ),
                {"lid": SINGLETON_LEADER_ID, "nid": node_id, "tok": lease_token},
            )
            session.commit()

            if result.rowcount > 0:
                logger.info("Leadership released by node %s", node_id)
            else:
                logger.info(
                    "Leadership release skipped for node %s: mismatch or not found",
                    node_id,
                )

    def cleanup_stale_leader(self) -> bool:
        """Remove the leader row if its lease has expired.

        Uses an atomic DELETE with a WHERE clause on expiry to prevent
        TOCTOU races where a valid leader could be removed.

        Returns True if a stale leader was removed, False otherwise.
        """
        with self._session_factory() as session:
            now = _utcnow()
            result = session.execute(
                text(
                    "DELETE FROM apflow_cluster_leader "
                    "WHERE leader_id = :lid AND expires_at <= :now"
                ),
                {"lid": SINGLETON_LEADER_ID, "now": now},
            )
            session.commit()

            if result.rowcount > 0:
                logger.info("Stale leader removed")
                return True
            return False

    def get_current_leader(self) -> str | None:
        """Return the node_id of the current leader, or None if no valid leader."""
        with self._session_factory() as session:
            leader = session.get(ClusterLeader, SINGLETON_LEADER_ID)
            if leader is None:
                return None

            now = _utcnow()
            # <= treats exact expiry as expired, consistent with cleanup_stale_leader for safety
            if as_utc(leader.expires_at) <= now:  # type: ignore[operator]  — Column datetime comparison
                return None

            return leader.node_id

    def is_leader(self, node_id: str) -> bool:
        """Check if the given node is the current active leader."""
        if not node_id:
            raise ValueError("node_id must not be empty")

        current = self.get_current_leader()
        return current == node_id

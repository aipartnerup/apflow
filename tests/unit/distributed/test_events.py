"""Tests for distributed task event emission."""

import pytest

from apflow.core.distributed.events import emit_task_event, VALID_EVENT_TYPES
from apflow.core.storage.sqlalchemy.models import TaskEvent


class TestEmitTaskEvent:
    """Tests for emit_task_event function."""

    def test_emit_valid_event(self, session_factory, session, sample_task):
        """Emitting a valid event writes a TaskEvent row."""
        emit_task_event(session_factory, "task-1", "task_started", "worker-1")

        session.expire_all()
        events = session.query(TaskEvent).filter(TaskEvent.task_id == "task-1").all()
        assert len(events) == 1
        assert events[0].event_type == "task_started"
        assert events[0].node_id == "worker-1"

    def test_emit_with_details(self, session_factory, session, sample_task):
        """Event details are persisted as JSON."""
        details = {"error": "connection timeout"}
        emit_task_event(session_factory, "task-1", "task_failed", "worker-1", details)

        session.expire_all()
        event = session.query(TaskEvent).filter(TaskEvent.task_id == "task-1").one()
        assert event.details == details

    def test_emit_without_node_id(self, session_factory, session, sample_task):
        """node_id is optional (e.g. for reassigned events)."""
        emit_task_event(session_factory, "task-1", "task_reassigned")

        session.expire_all()
        event = session.query(TaskEvent).filter(TaskEvent.task_id == "task-1").one()
        assert event.node_id is None

    def test_emit_empty_task_id_raises(self, session_factory):
        """Empty task_id raises ValueError."""
        with pytest.raises(ValueError, match="task_id must not be empty"):
            emit_task_event(session_factory, "", "task_started")

    def test_emit_invalid_event_type_raises(self, session_factory):
        """Invalid event_type raises ValueError."""
        with pytest.raises(ValueError, match="event_type must be one of"):
            emit_task_event(session_factory, "task-1", "invalid_type")

    def test_emit_all_valid_event_types(self, session_factory, session, sample_task):
        """All declared event types can be emitted successfully."""
        for event_type in VALID_EVENT_TYPES:
            emit_task_event(session_factory, "task-1", event_type, "worker-1")

        session.expire_all()
        events = session.query(TaskEvent).filter(TaskEvent.task_id == "task-1").all()
        assert len(events) == len(VALID_EVENT_TYPES)

    def test_emit_database_error_is_swallowed(self):
        """Database errors are logged but do not propagate."""
        from unittest.mock import MagicMock

        broken_factory = MagicMock(side_effect=RuntimeError("db down"))

        # Should not raise
        emit_task_event(broken_factory, "task-1", "task_started", "worker-1")

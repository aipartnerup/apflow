"""Tests for GraphQL subscription resolvers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apflow.api.graphql.resolvers.subscriptions import (
    subscribe_task_progress,
    subscribe_task_status_changed,
)
from apflow.api.graphql.types import TaskProgressEvent, TaskStatusEnum, TaskType

from .conftest import make_task_dict


@pytest.fixture
def mock_task_routes() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_info(mock_task_routes: AsyncMock) -> MagicMock:
    info = MagicMock()
    info.context = {"task_routes": mock_task_routes}
    return info


class TestSubscribeTaskStatusChanged:
    """Tests for subscribe_task_status_changed."""

    @pytest.mark.asyncio
    async def test_yields_on_status_change(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        """Subscription yields TaskType when status changes."""
        mock_task_routes.handle_task_get.side_effect = [
            make_task_dict(status="pending"),
            make_task_dict(status="in_progress"),
            make_task_dict(status="completed"),
        ]

        updates: list[TaskType] = []
        with patch(
            "apflow.api.graphql.resolvers.subscriptions.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async for update in subscribe_task_status_changed(info=mock_info, task_id="t1"):
                updates.append(update)

        assert len(updates) == 3
        assert updates[0].status == TaskStatusEnum.PENDING
        assert updates[1].status == TaskStatusEnum.IN_PROGRESS
        assert updates[2].status == TaskStatusEnum.COMPLETED

    @pytest.mark.asyncio
    async def test_stops_at_terminal_status(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        """Subscription terminates when task reaches terminal status."""
        mock_task_routes.handle_task_get.side_effect = [
            make_task_dict(status="pending"),
            make_task_dict(status="failed"),
        ]

        updates: list[TaskType] = []
        with patch(
            "apflow.api.graphql.resolvers.subscriptions.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async for update in subscribe_task_status_changed(info=mock_info, task_id="t1"):
                updates.append(update)

        assert len(updates) == 2
        assert updates[-1].status == TaskStatusEnum.FAILED

    @pytest.mark.asyncio
    async def test_skips_duplicate_status(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        """Subscription does not yield when status hasn't changed."""
        mock_task_routes.handle_task_get.side_effect = [
            make_task_dict(status="pending"),
            make_task_dict(status="pending"),
            make_task_dict(status="completed"),
        ]

        updates: list[TaskType] = []
        with patch(
            "apflow.api.graphql.resolvers.subscriptions.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async for update in subscribe_task_status_changed(info=mock_info, task_id="t1"):
                updates.append(update)

        # Only 2 yields: pending (first) + completed (changed)
        assert len(updates) == 2
        assert updates[0].status == TaskStatusEnum.PENDING
        assert updates[1].status == TaskStatusEnum.COMPLETED

    @pytest.mark.asyncio
    async def test_cleanup_on_close(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        """Subscription generator cleans up on aclose()."""
        mock_task_routes.handle_task_get.return_value = make_task_dict(status="pending")

        gen = subscribe_task_status_changed(info=mock_info, task_id="t1")
        # No exception means cleanup succeeded
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_yields_task_type_instances(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        """All yielded values are TaskType instances."""
        mock_task_routes.handle_task_get.side_effect = [
            make_task_dict(status="completed"),
        ]

        with patch(
            "apflow.api.graphql.resolvers.subscriptions.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async for update in subscribe_task_status_changed(info=mock_info, task_id="t1"):
                assert isinstance(update, TaskType)
                assert update.id == "task-1"


class TestSubscribeTaskProgress:
    """Tests for subscribe_task_progress."""

    @pytest.mark.asyncio
    async def test_yields_progress_events(self, mock_info: MagicMock) -> None:
        """Subscription yields TaskProgressEvent objects."""
        events = [
            {"type": "progress", "progress": 0.25, "message": "Starting"},
            {"type": "progress", "progress": 0.50, "message": "Halfway"},
            {"type": "complete", "progress": 1.0, "message": "Done"},
        ]

        call_count = 0

        async def mock_get_events(_task_id: str) -> list:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return events[:2]
            return events

        with (
            patch(
                "apflow.api.routes.tasks.get_task_streaming_events",
                side_effect=mock_get_events,
            ),
            patch(
                "apflow.api.graphql.resolvers.subscriptions.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            results: list[TaskProgressEvent] = []
            async for event in subscribe_task_progress(info=mock_info, task_id="t1"):
                results.append(event)

        assert len(results) == 3
        assert results[0].progress == 0.25
        assert results[0].message == "Starting"
        assert results[0].event_type == "progress"
        assert results[2].event_type == "complete"
        assert results[2].progress == 1.0

    @pytest.mark.asyncio
    async def test_terminates_on_complete_event(self, mock_info: MagicMock) -> None:
        """Subscription terminates when event_type is 'complete'."""
        events = [
            {"type": "complete", "progress": 1.0, "message": "Done"},
        ]

        async def mock_get_events(_task_id: str) -> list:
            return events

        with (
            patch(
                "apflow.api.routes.tasks.get_task_streaming_events",
                side_effect=mock_get_events,
            ),
            patch(
                "apflow.api.graphql.resolvers.subscriptions.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            results: list[TaskProgressEvent] = []
            async for event in subscribe_task_progress(info=mock_info, task_id="t1"):
                results.append(event)

        assert len(results) == 1
        assert results[0].event_type == "complete"

    @pytest.mark.asyncio
    async def test_yields_task_progress_event_instances(self, mock_info: MagicMock) -> None:
        """All yielded values are TaskProgressEvent instances."""
        events = [
            {"type": "progress", "progress": 0.5, "message": "Working"},
            {"type": "complete", "progress": 1.0, "message": "Done"},
        ]

        async def mock_get_events(_task_id: str) -> list:
            return events

        with (
            patch(
                "apflow.api.routes.tasks.get_task_streaming_events",
                side_effect=mock_get_events,
            ),
            patch(
                "apflow.api.graphql.resolvers.subscriptions.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            async for event in subscribe_task_progress(info=mock_info, task_id="t1"):
                assert isinstance(event, TaskProgressEvent)
                assert event.task_id == "t1"

    @pytest.mark.asyncio
    async def test_no_events_waits_and_polls(self, mock_info: MagicMock) -> None:
        """When no events exist, the subscription polls and waits."""
        call_count = 0

        async def mock_get_events(_task_id: str) -> list:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return []
            return [{"type": "complete", "progress": 1.0, "message": "Done"}]

        with (
            patch(
                "apflow.api.routes.tasks.get_task_streaming_events",
                side_effect=mock_get_events,
            ),
            patch(
                "apflow.api.graphql.resolvers.subscriptions.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            results: list[TaskProgressEvent] = []
            async for event in subscribe_task_progress(info=mock_info, task_id="t1"):
                results.append(event)

        assert len(results) == 1
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_cleanup_on_close(self, mock_info: MagicMock) -> None:
        """Subscription generator cleans up on aclose()."""

        async def mock_get_events(_task_id: str) -> list:
            return []

        with patch(
            "apflow.api.routes.tasks.get_task_streaming_events",
            side_effect=mock_get_events,
        ):
            gen = subscribe_task_progress(info=mock_info, task_id="t1")
            await gen.aclose()

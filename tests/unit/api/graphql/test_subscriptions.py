"""Tests for GraphQL subscription resolvers."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apflow.api.graphql.resolvers.subscriptions import (
    subscribe_task_status_changed,
)
from apflow.api.graphql.types import TaskStatusEnum, TaskType


def _make_task_dict(
    task_id: str = "t1",
    name: str = "Test",
    status: str = "pending",
) -> dict:
    return {
        "id": task_id,
        "name": name,
        "status": status,
        "priority": 5,
        "progress": 0.0,
        "result": None,
        "error": None,
        "created_at": None,
        "updated_at": None,
        "parent_id": None,
    }


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
            _make_task_dict(status="pending"),
            _make_task_dict(status="in_progress"),
            _make_task_dict(status="completed"),
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
            _make_task_dict(status="pending"),
            _make_task_dict(status="failed"),
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
            _make_task_dict(status="pending"),
            _make_task_dict(status="pending"),
            _make_task_dict(status="completed"),
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
        mock_task_routes.handle_task_get.return_value = _make_task_dict(status="pending")

        gen = subscribe_task_status_changed(info=mock_info, task_id="t1")
        # No exception means cleanup succeeded
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_yields_task_type_instances(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        """All yielded values are TaskType instances."""
        mock_task_routes.handle_task_get.side_effect = [
            _make_task_dict(status="completed"),
        ]

        with patch(
            "apflow.api.graphql.resolvers.subscriptions.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async for update in subscribe_task_status_changed(info=mock_info, task_id="t1"):
                assert isinstance(update, TaskType)
                assert update.id == "t1"

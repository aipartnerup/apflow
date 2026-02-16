"""Tests for GraphQL query resolvers."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from apflow.api.graphql.resolvers.queries import (
    resolve_task,
    resolve_tasks,
    resolve_task_children,
)
from apflow.api.graphql.types import TaskStatusEnum, TaskType


def _make_task_dict(
    task_id: str = "task-1",
    name: str = "Test Task",
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
    routes = AsyncMock()
    routes.handle_task_get.return_value = _make_task_dict()
    routes.handle_tasks_list.return_value = [
        _make_task_dict("t1", "Task 1"),
        _make_task_dict("t2", "Task 2"),
    ]
    return routes


@pytest.fixture
def mock_info(mock_task_routes: AsyncMock) -> MagicMock:
    info = MagicMock()
    info.context = {"task_routes": mock_task_routes}
    return info


class TestResolveTask:
    """Tests for resolve_task query."""

    @pytest.mark.asyncio
    async def test_delegates_to_handle_task_get(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        result = await resolve_task(info=mock_info, task_id="task-1")
        mock_task_routes.handle_task_get.assert_called_once_with({"task_id": "task-1"}, None, "")
        assert isinstance(result, TaskType)
        assert result.id == "task-1"

    @pytest.mark.asyncio
    async def test_returns_correct_task_type(self, mock_info: MagicMock) -> None:
        result = await resolve_task(info=mock_info, task_id="task-1")
        assert result.name == "Test Task"
        assert result.status == TaskStatusEnum.PENDING
        assert result.priority == 5

    @pytest.mark.asyncio
    async def test_propagates_error_from_routes(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        mock_task_routes.handle_task_get.side_effect = ValueError("Task not found")
        with pytest.raises(ValueError, match="Task not found"):
            await resolve_task(info=mock_info, task_id="nonexistent")


class TestResolveTasks:
    """Tests for resolve_tasks query."""

    @pytest.mark.asyncio
    async def test_returns_list_of_tasks(self, mock_info: MagicMock) -> None:
        result = await resolve_tasks(info=mock_info)
        assert len(result) == 2
        assert all(isinstance(t, TaskType) for t in result)

    @pytest.mark.asyncio
    async def test_passes_status_filter(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        await resolve_tasks(info=mock_info, status=TaskStatusEnum.IN_PROGRESS)
        call_args = mock_task_routes.handle_tasks_list.call_args
        assert call_args[0][0]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_passes_limit_and_offset(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        await resolve_tasks(info=mock_info, limit=10, offset=5)
        call_args = mock_task_routes.handle_tasks_list.call_args
        params = call_args[0][0]
        assert params["limit"] == 10
        assert params["offset"] == 5

    @pytest.mark.asyncio
    async def test_omits_none_params(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        await resolve_tasks(info=mock_info)
        call_args = mock_task_routes.handle_tasks_list.call_args
        params = call_args[0][0]
        assert "status" not in params
        assert "limit" not in params
        assert "offset" not in params


class TestResolveTaskChildren:
    """Tests for resolve_task_children query."""

    @pytest.mark.asyncio
    async def test_returns_children(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        child_data = [
            _make_task_dict("c1", "Child 1"),
            _make_task_dict("c2", "Child 2"),
        ]
        mock_task_routes.handle_tasks_list.return_value = child_data
        result = await resolve_task_children(info=mock_info, parent_id="parent-1")
        assert len(result) == 2
        assert result[0].id == "c1"

    @pytest.mark.asyncio
    async def test_passes_parent_id_filter(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        mock_task_routes.handle_tasks_list.return_value = []
        await resolve_task_children(info=mock_info, parent_id="parent-1")
        call_args = mock_task_routes.handle_tasks_list.call_args
        assert call_args[0][0]["parent_id"] == "parent-1"

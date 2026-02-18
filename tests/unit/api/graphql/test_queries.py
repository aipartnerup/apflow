"""Tests for GraphQL query resolvers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apflow.api.graphql.resolvers.queries import (
    _count_tree_stats,
    resolve_running_tasks,
    resolve_task,
    resolve_task_children,
    resolve_task_tree,
    resolve_tasks,
)
from apflow.api.graphql.types import TaskStatusEnum, TaskTreeType, TaskType

from .conftest import make_task_dict


@pytest.fixture
def mock_task_routes() -> AsyncMock:
    routes = AsyncMock()
    routes.handle_task_get.return_value = make_task_dict()
    routes.handle_tasks_list.return_value = [
        make_task_dict("t1", "Task 1"),
        make_task_dict("t2", "Task 2"),
    ]
    routes.handle_task_children.return_value = [
        make_task_dict("c1", "Child 1"),
        make_task_dict("c2", "Child 2"),
    ]
    routes.handle_task_tree.return_value = {
        "task": make_task_dict("root", "Root", "in_progress"),
        "children": [
            {
                "task": make_task_dict("c1", "Child 1", "completed"),
                "children": [],
            },
            {
                "task": make_task_dict("c2", "Child 2", "failed"),
                "children": [],
            },
        ],
    }
    routes.handle_running_tasks_list.return_value = [
        make_task_dict("r1", "Running 1", "in_progress"),
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
    async def test_delegates_to_handle_task_children(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        result = await resolve_task_children(info=mock_info, parent_id="parent-1")
        mock_task_routes.handle_task_children.assert_called_once_with(
            {"parent_id": "parent-1"}, None, ""
        )
        assert len(result) == 2
        assert result[0].id == "c1"

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_children(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        mock_task_routes.handle_task_children.return_value = []
        result = await resolve_task_children(info=mock_info, parent_id="parent-1")
        assert result == []


class TestResolveTaskTree:
    """Tests for resolve_task_tree query."""

    @pytest.mark.asyncio
    async def test_delegates_to_handle_task_tree(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        result = await resolve_task_tree(info=mock_info, root_id="root")
        mock_task_routes.handle_task_tree.assert_called_once_with({"root_id": "root"}, None, "")
        assert isinstance(result, TaskTreeType)

    @pytest.mark.asyncio
    async def test_returns_correct_tree_stats(self, mock_info: MagicMock) -> None:
        result = await resolve_task_tree(info=mock_info, root_id="root")
        assert result.root.id == "root"
        assert result.total_tasks == 3
        assert result.completed_tasks == 1
        assert result.failed_tasks == 1

    @pytest.mark.asyncio
    async def test_raises_when_tree_not_found(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        mock_task_routes.handle_task_tree.return_value = None
        with pytest.raises(ValueError, match="Task tree not found"):
            await resolve_task_tree(info=mock_info, root_id="missing")


class TestResolveRunningTasks:
    """Tests for resolve_running_tasks query."""

    @pytest.mark.asyncio
    async def test_delegates_to_handle_running_tasks_list(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        result = await resolve_running_tasks(info=mock_info)
        mock_task_routes.handle_running_tasks_list.assert_called_once_with({}, None, "")
        assert len(result) == 1
        assert result[0].id == "r1"

    @pytest.mark.asyncio
    async def test_passes_limit(self, mock_info: MagicMock, mock_task_routes: AsyncMock) -> None:
        await resolve_running_tasks(info=mock_info, limit=5)
        call_args = mock_task_routes.handle_running_tasks_list.call_args
        assert call_args[0][0]["limit"] == 5

    @pytest.mark.asyncio
    async def test_returns_empty_list(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        mock_task_routes.handle_running_tasks_list.return_value = []
        result = await resolve_running_tasks(info=mock_info)
        assert result == []


class TestCountTreeStats:
    """Tests for _count_tree_stats helper."""

    def test_single_node(self) -> None:
        tree = {"task": {"status": "completed"}, "children": []}
        total, completed, failed = _count_tree_stats(tree)
        assert total == 1
        assert completed == 1
        assert failed == 0

    def test_nested_tree(self) -> None:
        tree = {
            "task": {"status": "in_progress"},
            "children": [
                {"task": {"status": "completed"}, "children": []},
                {
                    "task": {"status": "failed"},
                    "children": [
                        {"task": {"status": "completed"}, "children": []},
                    ],
                },
            ],
        }
        total, completed, failed = _count_tree_stats(tree)
        assert total == 4
        assert completed == 2
        assert failed == 1

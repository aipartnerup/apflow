"""Tests for GraphQL mutation resolvers."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from apflow.api.graphql.resolvers.mutations import (
    resolve_create_task,
    resolve_update_task,
    resolve_cancel_task,
    resolve_delete_task,
)
from apflow.api.graphql.types import (
    CreateTaskInput,
    TaskStatusEnum,
    TaskType,
    UpdateTaskInput,
)


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
    routes.handle_task_create.return_value = [_make_task_dict("new-1", "Created Task")]
    routes.handle_task_update.return_value = _make_task_dict("task-1", "Updated", "in_progress")
    routes.handle_task_cancel.return_value = None
    routes.handle_task_delete.return_value = None
    return routes


@pytest.fixture
def mock_info(mock_task_routes: AsyncMock) -> MagicMock:
    info = MagicMock()
    info.context = {"task_routes": mock_task_routes}
    return info


class TestResolveCreateTask:
    """Tests for resolve_create_task mutation."""

    @pytest.mark.asyncio
    async def test_creates_task_with_name(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        inp = CreateTaskInput(name="New Task")
        result = await resolve_create_task(info=mock_info, task_input=inp)
        mock_task_routes.handle_task_create.assert_called_once()
        assert isinstance(result, TaskType)

    @pytest.mark.asyncio
    async def test_passes_optional_fields(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        inp = CreateTaskInput(
            name="Full Task",
            description="desc",
            executor="exec1",
            priority=10,
            parent_id="parent-1",
        )
        await resolve_create_task(info=mock_info, task_input=inp)
        call_args = mock_task_routes.handle_task_create.call_args
        task_list = call_args[0][0]
        assert task_list[0]["name"] == "Full Task"
        assert task_list[0]["description"] == "desc"
        assert task_list[0]["executor"] == "exec1"
        assert task_list[0]["priority"] == 10
        assert task_list[0]["parent_id"] == "parent-1"

    @pytest.mark.asyncio
    async def test_handles_single_dict_return(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        mock_task_routes.handle_task_create.return_value = _make_task_dict("single-1", "Single")
        inp = CreateTaskInput(name="Single")
        result = await resolve_create_task(info=mock_info, task_input=inp)
        assert result.id == "single-1"

    @pytest.mark.asyncio
    async def test_omits_none_optional_fields(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        inp = CreateTaskInput(name="Minimal")
        await resolve_create_task(info=mock_info, task_input=inp)
        call_args = mock_task_routes.handle_task_create.call_args
        task_dict = call_args[0][0][0]
        assert "description" not in task_dict
        assert "executor" not in task_dict
        assert "priority" not in task_dict
        assert "parent_id" not in task_dict


class TestResolveUpdateTask:
    """Tests for resolve_update_task mutation."""

    @pytest.mark.asyncio
    async def test_updates_task(self, mock_info: MagicMock, mock_task_routes: AsyncMock) -> None:
        inp = UpdateTaskInput(name="Updated Name")
        result = await resolve_update_task(info=mock_info, task_id="task-1", task_input=inp)
        mock_task_routes.handle_task_update.assert_called_once()
        assert isinstance(result, TaskType)

    @pytest.mark.asyncio
    async def test_passes_status_as_string_value(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        inp = UpdateTaskInput(status=TaskStatusEnum.COMPLETED)
        await resolve_update_task(info=mock_info, task_id="task-1", task_input=inp)
        call_args = mock_task_routes.handle_task_update.call_args
        params = call_args[0][0]
        assert params["status"] == "completed"

    @pytest.mark.asyncio
    async def test_omits_none_fields(
        self, mock_info: MagicMock, mock_task_routes: AsyncMock
    ) -> None:
        inp = UpdateTaskInput(name="Only Name")
        await resolve_update_task(info=mock_info, task_id="task-1", task_input=inp)
        call_args = mock_task_routes.handle_task_update.call_args
        params = call_args[0][0]
        assert params["task_id"] == "task-1"
        assert params["name"] == "Only Name"
        assert "description" not in params
        assert "status" not in params


class TestResolveCancelTask:
    """Tests for resolve_cancel_task mutation."""

    @pytest.mark.asyncio
    async def test_cancels_task(self, mock_info: MagicMock, mock_task_routes: AsyncMock) -> None:
        result = await resolve_cancel_task(info=mock_info, task_id="task-1")
        mock_task_routes.handle_task_cancel.assert_called_once_with({"task_id": "task-1"}, None, "")
        assert result is True


class TestResolveDeleteTask:
    """Tests for resolve_delete_task mutation."""

    @pytest.mark.asyncio
    async def test_deletes_task(self, mock_info: MagicMock, mock_task_routes: AsyncMock) -> None:
        result = await resolve_delete_task(info=mock_info, task_id="task-1")
        mock_task_routes.handle_task_delete.assert_called_once_with({"task_id": "task-1"}, None, "")
        assert result is True

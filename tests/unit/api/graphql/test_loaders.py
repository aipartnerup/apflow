"""Tests for GraphQL DataLoaders."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from apflow.api.graphql.loaders import (
    create_task_by_id_loader,
    create_task_children_loader,
    load_children_by_parent_id,
    load_tasks_by_id,
)
from apflow.api.graphql.types import TaskType

from .conftest import make_task_dict


@pytest.fixture
def mock_task_routes() -> AsyncMock:
    routes = AsyncMock()
    routes.handle_task_get.side_effect = lambda params, *_: make_task_dict(
        task_id=params["task_id"],
        name=f"Task {params['task_id']}",
    )
    routes.handle_task_children.side_effect = lambda params, *_: [
        make_task_dict(task_id=f"{params['parent_id']}-child-1"),
        make_task_dict(task_id=f"{params['parent_id']}-child-2"),
    ]
    return routes


class TestLoadTasksById:
    """Tests for load_tasks_by_id batch loader."""

    @pytest.mark.asyncio
    async def test_loads_single_task(self, mock_task_routes: AsyncMock) -> None:
        results = await load_tasks_by_id(["t1"], mock_task_routes)
        assert len(results) == 1
        assert isinstance(results[0], TaskType)
        assert results[0].id == "t1"

    @pytest.mark.asyncio
    async def test_loads_multiple_tasks(self, mock_task_routes: AsyncMock) -> None:
        results = await load_tasks_by_id(["t1", "t2", "t3"], mock_task_routes)
        assert len(results) == 3
        assert results[0].id == "t1"
        assert results[1].id == "t2"
        assert results[2].id == "t3"

    @pytest.mark.asyncio
    async def test_empty_keys(self, mock_task_routes: AsyncMock) -> None:
        results = await load_tasks_by_id([], mock_task_routes)
        assert results == []
        mock_task_routes.handle_task_get.assert_not_called()

    @pytest.mark.asyncio
    async def test_preserves_key_order(self, mock_task_routes: AsyncMock) -> None:
        results = await load_tasks_by_id(["b", "a", "c"], mock_task_routes)
        assert [r.id for r in results] == ["b", "a", "c"]


class TestLoadChildrenByParentId:
    """Tests for load_children_by_parent_id batch loader."""

    @pytest.mark.asyncio
    async def test_loads_children_for_single_parent(self, mock_task_routes: AsyncMock) -> None:
        results = await load_children_by_parent_id(["p1"], mock_task_routes)
        assert len(results) == 1
        assert len(results[0]) == 2
        assert results[0][0].id == "p1-child-1"

    @pytest.mark.asyncio
    async def test_loads_children_for_multiple_parents(self, mock_task_routes: AsyncMock) -> None:
        results = await load_children_by_parent_id(["p1", "p2"], mock_task_routes)
        assert len(results) == 2
        assert results[0][0].id == "p1-child-1"
        assert results[1][0].id == "p2-child-1"

    @pytest.mark.asyncio
    async def test_empty_keys(self, mock_task_routes: AsyncMock) -> None:
        results = await load_children_by_parent_id([], mock_task_routes)
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_list_of_lists(self, mock_task_routes: AsyncMock) -> None:
        results = await load_children_by_parent_id(["p1"], mock_task_routes)
        assert isinstance(results, list)
        assert isinstance(results[0], list)
        assert all(isinstance(t, TaskType) for t in results[0])


class TestCreateTaskByIdLoader:
    """Tests for create_task_by_id_loader factory."""

    @pytest.mark.asyncio
    async def test_creates_working_loader(self, mock_task_routes: AsyncMock) -> None:
        loader = create_task_by_id_loader(mock_task_routes)
        result = await loader.load("t1")
        assert isinstance(result, TaskType)
        assert result.id == "t1"


class TestCreateTaskChildrenLoader:
    """Tests for create_task_children_loader factory."""

    @pytest.mark.asyncio
    async def test_creates_working_loader(self, mock_task_routes: AsyncMock) -> None:
        loader = create_task_children_loader(mock_task_routes)
        result = await loader.load("p1")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].id == "p1-child-1"

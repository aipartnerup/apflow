"""
API-mode tests for CLI tasks commands.

These tests verify that CLI commands call the API client when configured and
properly surface the API responses.
"""
from __future__ import annotations

import importlib
import json
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from click.testing import CliRunner

from apflow.cli.main import cli

runner = CliRunner()


@pytest.fixture()
def api_mock_client():
    """Provide an AsyncMock with task API methods."""
    client = AsyncMock()
    client.count_tasks = AsyncMock(return_value={
        "total": 2,
        "pending": 1,
        "in_progress": 1,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
    })
    client.list_tasks = AsyncMock(return_value=[{"id": "t1"}, {"id": "t2"}])
    client.get_tasks_status = AsyncMock(return_value=[{"task_id": "t1", "status": "pending"}])
    client.cancel_tasks = AsyncMock(return_value=[{"task_id": "t1", "status": "cancelled"}])
    client.copy_task = AsyncMock(return_value={"tasks": [{"id": "c1"}], "saved": False})
    client.create_tasks = AsyncMock(return_value={"task": {"id": "new-root"}})
    client.update_task = AsyncMock(return_value={"id": "t1", "status": "completed"})
    client.delete_task = AsyncMock(return_value={"success": True, "task_id": "t1"})
    client.get_task_tree = AsyncMock(return_value={"task": {"id": "t1"}, "children": []})
    client.get_task_children = AsyncMock(return_value=[{"id": "child-1"}])
    return client


@pytest.fixture()
def force_api_mode(monkeypatch: pytest.MonkeyPatch, api_mock_client: AsyncMock):
    """Force CLI to use API and yield the mock client used by commands."""

    @asynccontextmanager
    async def fake_client_cm():
        yield api_mock_client

    tasks_module = importlib.import_module("apflow.cli.commands.tasks")

    # Ensure CLI thinks API is configured and uses our fake client context manager.
    monkeypatch.setattr(tasks_module, "should_use_api", lambda: True)
    monkeypatch.setattr(tasks_module, "get_api_client_if_configured", fake_client_cm)
    return api_mock_client


def test_tasks_count_uses_api(force_api_mode: AsyncMock):
    result = runner.invoke(cli, ["tasks", "count", "--format", "json"])

    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["total"] == 2
    force_api_mode.count_tasks.assert_awaited_once()


def test_tasks_list_uses_api(force_api_mode: AsyncMock):
    result = runner.invoke(cli, ["tasks", "list"])

    assert result.exit_code == 0
    tasks = json.loads(result.stdout)
    assert tasks == [{"id": "t1"}, {"id": "t2"}]
    force_api_mode.list_tasks.assert_awaited_once()


def test_tasks_status_uses_api(force_api_mode: AsyncMock):
    result = runner.invoke(cli, ["tasks", "status", "t1", "t2"])

    assert result.exit_code == 0
    statuses = json.loads(result.stdout)
    assert statuses[0]["task_id"] == "t1"
    force_api_mode.get_tasks_status.assert_awaited_once_with(["t1", "t2"])


def test_tasks_cancel_uses_api(force_api_mode: AsyncMock):
    result = runner.invoke(cli, ["tasks", "cancel", "t1", "t2", "--force"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["status"] == "cancelled"
    force_api_mode.cancel_tasks.assert_awaited_once()


def test_tasks_copy_uses_api_preview(force_api_mode: AsyncMock, tmp_path: Path):
    output_file = tmp_path / "copy.json"
    result = runner.invoke(
        cli,
        ["tasks", "copy", "t1", "--dry-run", "--output", str(output_file)],
    )

    assert result.exit_code == 0
    saved = json.loads(output_file.read_text())
    assert saved["saved"] is False
    force_api_mode.copy_task.assert_awaited_once()


def test_tasks_create_uses_api(force_api_mode: AsyncMock, tmp_path: Path):
    payload = [{"name": "Task A", "schemas": {"method": "noop"}}]
    task_file = tmp_path / "tasks.json"
    task_file.write_text(json.dumps(payload))

    result = runner.invoke(cli, ["tasks", "create", "--file", str(task_file)])

    assert result.exit_code == 0
    force_api_mode.create_tasks.assert_awaited_once()


def test_tasks_update_uses_api(force_api_mode: AsyncMock):
    result = runner.invoke(cli, ["tasks", "update", "t1", "--status", "completed"])

    assert result.exit_code == 0
    force_api_mode.update_task.assert_awaited_once()


def test_tasks_delete_uses_api(force_api_mode: AsyncMock):
    result = runner.invoke(cli, ["tasks", "delete", "t1"])

    assert result.exit_code == 0
    force_api_mode.delete_task.assert_awaited_once()


def test_tasks_tree_and_children_use_api(force_api_mode: AsyncMock):
    tree_result = runner.invoke(cli, ["tasks", "tree", "t1"])
    children_result = runner.invoke(cli, ["tasks", "children", "--task-id", "t1"])

    assert tree_result.exit_code == 0
    assert children_result.exit_code == 0
    force_api_mode.get_task_tree.assert_awaited_once()
    force_api_mode.get_task_children.assert_awaited_once()

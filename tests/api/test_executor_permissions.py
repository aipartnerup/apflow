"""
Tests for executor permission checks via APFLOW_EXTENSIONS

These tests verify that when APFLOW_EXTENSIONS is set, only executors
from the specified extensions can be accessed via the API.
"""

import os
from unittest.mock import patch

import pytest

from apflow.core.extensions.manager import get_allowed_executor_ids


class TestExecutorPermissions:
    """Test executor permission checks"""

    def test_get_allowed_executor_ids_not_set(self):
        """Test that None is returned when APFLOW_EXTENSIONS is not set"""
        with patch.dict(os.environ, {}, clear=True):
            result = get_allowed_executor_ids()
            assert result is None

    def test_get_allowed_executor_ids_stdio_only(self):
        """Test allowed executors when only stdio is enabled"""
        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio"}):
            result = get_allowed_executor_ids()
            assert result is not None
            assert "system_info_executor" in result
            assert "command_executor" in result
            assert "rest_executor" not in result
            assert "crewai_executor" not in result

    def test_get_allowed_executor_ids_multiple(self):
        """Test allowed executors with multiple extensions"""
        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio,http,crewai"}):
            result = get_allowed_executor_ids()
            assert result is not None
            assert "system_info_executor" in result
            assert "command_executor" in result
            assert "rest_executor" in result
            assert "crewai_executor" in result
            assert "ssh_executor" not in result

    def test_get_allowed_executor_ids_empty_string(self):
        """Test that empty string behaves like not set"""
        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": ""}):
            result = get_allowed_executor_ids()
            assert result is None

    def test_get_allowed_executor_ids_whitespace(self):
        """Test handling of whitespace in extension list"""
        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": " stdio , http "}):
            result = get_allowed_executor_ids()
            assert result is not None
            assert "system_info_executor" in result
            assert "rest_executor" in result

    def test_get_allowed_executor_ids_unknown_extension(self):
        """Test that unknown extensions don't break parsing"""
        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio,unknown_extension"}):
            result = get_allowed_executor_ids()
            assert result is not None
            assert "system_info_executor" in result
            assert "command_executor" in result


@pytest.mark.asyncio
class TestTaskExecutionPermissions:
    """Test that task execution respects executor permissions"""

    async def test_execute_task_with_allowed_executor(self, task_manager_with_session):
        """Test that allowed executors can be executed"""
        from apflow.core.storage.sqlalchemy.models import TaskModel

        task_manager, session = task_manager_with_session

        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio,http"}):
            # Create a task with allowed executor
            task = TaskModel(
                name="Test Task",
                user_id="test_user",
                schemas={"method": "system_info_executor"},
                inputs={"resource": "cpu"},
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            # Execute task - should succeed
            result = await task_manager._execute_task_with_schemas(task, task.inputs)

            # Should not have error
            assert "error" not in result or "not allowed" not in result.get("error", "")

    async def test_execute_task_with_disallowed_executor_via_method(
        self, task_manager_with_session
    ):
        """Test that disallowed executors are blocked when specified via method"""
        from apflow.core.storage.sqlalchemy.models import TaskModel

        task_manager, session = task_manager_with_session

        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio"}):
            # Create a task with disallowed executor (crewai)
            task = TaskModel(
                name="Test Task",
                user_id="test_user",
                schemas={"method": "crewai_executor"},
                inputs={},
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            # Execute task - should fail with permission error
            result = await task_manager._execute_task_with_schemas(task, task.inputs)

            # Should have permission error
            assert "error" in result
            assert "not allowed" in result["error"]
            assert "allowed_executors" in result
            assert "crewai_executor" not in result["allowed_executors"]

    async def test_execute_task_with_disallowed_executor_via_type(
        self, task_manager_with_session
    ):
        """Test that disallowed executors are blocked when resolved via type"""
        from apflow.core.storage.sqlalchemy.models import TaskModel

        task_manager, session = task_manager_with_session

        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio"}):
            # Create a task with disallowed type
            task = TaskModel(
                name="Test Task",
                user_id="test_user",
                schemas={"type": "crewai", "method": "crewai_executor"},
                inputs={},
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            # Execute task - should fail with permission error
            result = await task_manager._execute_task_with_schemas(task, task.inputs)

            # Should have permission error
            assert "error" in result
            assert "not allowed" in result["error"]

    async def test_execute_task_no_restrictions(self, task_manager_with_session):
        """Test that all executors work when APFLOW_EXTENSIONS is not set"""
        from apflow.core.storage.sqlalchemy.models import TaskModel

        task_manager, session = task_manager_with_session

        # Clear APFLOW_EXTENSIONS
        with patch.dict(os.environ, {}, clear=True):
            # Create a task with any executor
            task = TaskModel(
                name="Test Task",
                user_id="test_user",
                schemas={"method": "system_info_executor"},
                inputs={"resource": "cpu"},
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            # Execute task - should succeed
            result = await task_manager._execute_task_with_schemas(task, task.inputs)

            # Should not have permission error
            assert "error" not in result or "not allowed" not in result.get("error", "")

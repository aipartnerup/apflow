"""
Additional tests for TaskRepository to increase coverage
"""

import pytest
from apflow.core.storage.sqlalchemy.task_repository import TaskRepository


class TestTaskRepositoryAdditional:
    """Additional tests for TaskRepository to achieve 80%+ coverage"""

    @pytest.mark.asyncio
    async def test_create_task_with_all_optional_fields(self, sync_db_session):
        """Test creating task with all optional fields"""
        repo = TaskRepository(sync_db_session)

        task = await repo.create_task(
            name="full_task",
            user_id="test_user",
            parent_id="parent123",
            priority=5,
            inputs={"key": "value"},
            params={"param1": "val1"},
            schemas={"input_schema": {}, "output_schema": {}},
            result={"output": "data"}
        )

        assert task.name == "full_task"
        assert task.parent_id == "parent123"
        assert task.priority == 5
        assert task.inputs == {"key": "value"}
        assert task.params == {"param1": "val1"}
        assert task.schemas == {"input_schema": {}, "output_schema": {}}
        assert task.result == {"output": "data"}

    @pytest.mark.asyncio
    async def test_update_task_name(self, sync_db_session):
        """Test updating task name"""
        repo = TaskRepository(sync_db_session)

        task = await repo.create_task(name="original", user_id="test_user")
        await repo.update_task_name(task.id, "updated_name")

        updated_task = await repo.get_task_by_id(task.id)
        assert updated_task.name == "updated_name"

    @pytest.mark.asyncio
    async def test_update_task_priority(self, sync_db_session):
        """Test updating task priority"""
        repo = TaskRepository(sync_db_session)

        task = await repo.create_task(name="test", user_id="test_user")
        await repo.update_task_priority(task.id, 10)

        updated_task = await repo.get_task_by_id(task.id)
        assert updated_task.priority == 10

    @pytest.mark.asyncio
    async def test_update_task_params(self, sync_db_session):
        """Test updating task params"""
        repo = TaskRepository(sync_db_session)

        task = await repo.create_task(name="test", user_id="test_user")
        new_params = {"new_key": "new_value"}
        await repo.update_task_params(task.id, new_params)

        updated_task = await repo.get_task_by_id(task.id)
        assert updated_task.params == new_params

    @pytest.mark.asyncio
    async def test_update_task_schemas(self, sync_db_session):
        """Test updating task schemas"""
        repo = TaskRepository(sync_db_session)

        task = await repo.create_task(name="test", user_id="test_user")
        new_schemas = {"output_schema": {"type": "object"}}
        await repo.update_task_schemas(task.id, new_schemas)

        updated_task = await repo.get_task_by_id(task.id)
        assert updated_task.schemas == new_schemas

    @pytest.mark.asyncio
    async def test_update_task_status_with_result(self, sync_db_session):
        """Test updating task status with result"""
        repo = TaskRepository(sync_db_session)

        task = await repo.create_task(name="test", user_id="test_user")
        result_data = {"completed": True, "output": "success"}
        await repo.update_task_status(
            task_id=task.id,
            status="completed",
            result=result_data
        )

        updated_task = await repo.get_task_by_id(task.id)
        assert updated_task.result == result_data

    @pytest.mark.asyncio
    async def test_update_task_inputs(self, sync_db_session):
        """Test updating task inputs"""
        repo = TaskRepository(sync_db_session)

        task = await repo.create_task(name="test", user_id="test_user")
        new_inputs = {"input1": "value1"}
        await repo.update_task_inputs(task.id, new_inputs)

        updated_task = await repo.get_task_by_id(task.id)
        assert updated_task.inputs == new_inputs

    @pytest.mark.asyncio
    async def test_delete_task(self, sync_db_session):
        """Test deleting a task"""
        repo = TaskRepository(sync_db_session)

        task = await repo.create_task(name="to_delete", user_id="test_user")
        task_id = task.id

        await repo.delete_task(task_id)

        deleted_task = await repo.get_task_by_id(task_id)
        assert deleted_task is None

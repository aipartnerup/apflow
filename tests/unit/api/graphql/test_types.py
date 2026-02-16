"""Tests for GraphQL type definitions."""

from apflow.api.graphql.types import (
    CreateTaskInput,
    TaskStatusEnum,
    TaskType,
    UpdateTaskInput,
    task_model_to_graphql,
)
from apflow.core.types import TaskStatus


class TestTaskStatusEnum:
    """Tests for TaskStatusEnum Strawberry enum."""

    def test_has_all_statuses(self) -> None:
        """TaskStatusEnum mirrors all TaskStatus constants."""
        expected = {
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
        enum_values = {member.value for member in TaskStatusEnum}
        assert enum_values == expected

    def test_pending_value(self) -> None:
        """PENDING enum value matches TaskStatus."""
        assert TaskStatusEnum.PENDING.value == "pending"

    def test_in_progress_value(self) -> None:
        """IN_PROGRESS enum value matches TaskStatus."""
        assert TaskStatusEnum.IN_PROGRESS.value == "in_progress"


class TestTaskType:
    """Tests for TaskType Strawberry type."""

    def test_has_required_fields(self) -> None:
        """TaskType exposes all core fields."""
        task = TaskType(
            id="abc-123",
            name="Test Task",
            status=TaskStatusEnum.PENDING,
            priority=5,
            progress=0.0,
            result=None,
            error=None,
            created_at=None,
            updated_at=None,
            parent_id=None,
        )
        assert task.id == "abc-123"
        assert task.name == "Test Task"
        assert task.status == TaskStatusEnum.PENDING
        assert task.priority == 5

    def test_optional_description(self) -> None:
        """TaskType has optional description field."""
        task = TaskType(
            id="1",
            name="T",
            status=TaskStatusEnum.PENDING,
            priority=0,
            progress=0.0,
            result=None,
            error=None,
            created_at=None,
            updated_at=None,
            parent_id=None,
            description="A description",
        )
        assert task.description == "A description"


class TestInputTypes:
    """Tests for GraphQL input types."""

    def test_create_task_input_required_name(self) -> None:
        """CreateTaskInput requires name field."""
        inp = CreateTaskInput(name="test-task")
        assert inp.name == "test-task"

    def test_create_task_input_optional_fields(self) -> None:
        """CreateTaskInput has optional priority, executor, description."""
        inp = CreateTaskInput(
            name="test",
            description="desc",
            executor="http",
            priority=10,
        )
        assert inp.description == "desc"
        assert inp.executor == "http"
        assert inp.priority == 10

    def test_update_task_input_all_optional(self) -> None:
        """UpdateTaskInput has all optional fields."""
        inp = UpdateTaskInput()
        assert inp.name is None
        assert inp.status is None


class TestTaskModelToGraphQL:
    """Tests for task_model_to_graphql converter."""

    def test_converts_basic_fields(self) -> None:
        """Converter maps TaskModel dict fields to TaskType."""
        model_dict = {
            "id": "abc-123",
            "name": "Test Task",
            "status": "pending",
            "priority": 5,
            "progress": 0.5,
            "result": None,
            "error": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": None,
            "parent_id": None,
        }
        result = task_model_to_graphql(model_dict)
        assert result.id == "abc-123"
        assert result.name == "Test Task"
        assert result.status == TaskStatusEnum.PENDING
        assert result.priority == 5
        assert result.progress == 0.5

    def test_converts_completed_status(self) -> None:
        """Converter handles completed status."""
        model_dict = {
            "id": "1",
            "name": "Done",
            "status": "completed",
            "priority": 0,
            "progress": 1.0,
            "result": '{"output": "done"}',
            "error": None,
            "created_at": None,
            "updated_at": None,
            "parent_id": "root",
        }
        result = task_model_to_graphql(model_dict)
        assert result.status == TaskStatusEnum.COMPLETED
        assert result.parent_id == "root"

    def test_converts_with_description(self) -> None:
        """Converter includes description if present."""
        model_dict = {
            "id": "1",
            "name": "Test",
            "status": "pending",
            "priority": 0,
            "progress": 0.0,
            "result": None,
            "error": None,
            "created_at": None,
            "updated_at": None,
            "parent_id": None,
            "description": "A test task",
        }
        result = task_model_to_graphql(model_dict)
        assert result.description == "A test task"

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


from apflow.core.config_manager import get_config_manager
from apflow.core.execution.task_executor import TaskExecutor
from apflow.core.execution.task_manager import TaskManager
from apflow.core.extensions import ExtensionCategory, get_registry
from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
from apflow.core.types import TaskTreeNode


@dataclass
class TaskBuilder:
    """Fluent builder for creating and executing tasks."""

    task_manager: TaskManager
    executor_id: str
    name: Optional[str] = None
    user_id: Optional[str] = None
    parent_id: Optional[str] = None
    priority: int = 2
    inputs: Dict[str, Any] = field(default_factory=dict)
    schemas: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    original_task_id: Optional[str] = None
    has_copy: bool = False
    use_streaming: bool = False
    streaming_callbacks_context: Optional[Any] = None
    use_demo: bool = False
    demo_sleep_scale: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.executor_id:
            raise ValueError("executor_id is required for TaskBuilder")
        self.params.setdefault("executor_id", self.executor_id)
        self._validate_executor_id()

    def with_name(self, name: str) -> "TaskBuilder":
        self.name = name
        return self

    def with_user(self, user_id: str) -> "TaskBuilder":
        self.user_id = user_id
        return self

    def with_parent(self, parent_id: str) -> "TaskBuilder":
        self.parent_id = parent_id
        return self

    def with_priority(self, priority: int) -> "TaskBuilder":
        self.priority = priority
        return self

    def with_inputs(self, inputs: Dict[str, Any]) -> "TaskBuilder":
        self.inputs.update(inputs)
        return self

    def with_input(self, key: str, value: Any) -> "TaskBuilder":
        self.inputs[key] = value
        return self

    def with_params(self, params: Dict[str, Any]) -> "TaskBuilder":
        merged = params.copy()
        merged.setdefault("executor_id", self.executor_id)
        self.params.update(merged)
        return self

    def with_schemas(self, schemas: Dict[str, Any]) -> "TaskBuilder":
        self.schemas.update(schemas)
        return self

    def with_dependencies(self, dependencies: Sequence[Dict[str, Any]]) -> "TaskBuilder":
        self.dependencies.extend(dependencies)
        return self

    def depends_on(self, *task_ids: str) -> "TaskBuilder":
        for task_id in task_ids:
            self.dependencies.append({"id": task_id, "required": True})
        return self

    def copy_of(self, original_task_id: str) -> "TaskBuilder":
        self.original_task_id = original_task_id
        self.has_copy = True
        return self

    def enable_streaming(self, context: Optional[Any] = None) -> "TaskBuilder":
        self.use_streaming = True
        self.streaming_callbacks_context = context
        return self

    def enable_demo_mode(self, sleep_scale: Optional[float] = None) -> "TaskBuilder":
        self.use_demo = True
        self.demo_sleep_scale = sleep_scale
        return self

    async def build(self) -> TaskTreeNode:
        self._validate_required_fields()
        task_repository = self._get_task_repository()
        task = await task_repository.create_task(
            name=self.name or "Unnamed Task",
            user_id=self.user_id,
            parent_id=self.parent_id,
            priority=self.priority,
            dependencies=self.dependencies or None,
            inputs=self.inputs or None,
            schemas=self.schemas or None,
            params=self.params or None,
            original_task_id=self.original_task_id,
            has_copy=self.has_copy,
        )
        return TaskTreeNode(task)

    async def execute(self) -> Dict[str, Any]:
        task_tree = await self.build()
        config_manager = get_config_manager()
        previous_scale = None
        if self.demo_sleep_scale is not None:
            previous_scale = config_manager.get_demo_sleep_scale()
            config_manager.set_demo_sleep_scale(self.demo_sleep_scale)

        try:
            executor = TaskExecutor()
            result = await executor.execute_task_tree(
                task_tree=task_tree,
                root_task_id=task_tree.task.id,
                use_streaming=self.use_streaming,
                streaming_callbacks_context=self.streaming_callbacks_context,
                use_demo=self.use_demo,
                db_session=self.task_manager.db,
            )
            updated_task = await self.task_manager.task_repository.get_task_by_id(task_tree.task.id)
            if updated_task and updated_task.result is not None:
                result["result"] = updated_task.result
            return result
        finally:
            if previous_scale is not None:
                config_manager.set_demo_sleep_scale(previous_scale)

    def _validate_executor_id(self) -> None:
        registry = get_registry()
        extension = registry.get_by_id(self.executor_id)
        if not extension or extension.category != ExtensionCategory.EXECUTOR:
            raise ValueError(f"Executor '{self.executor_id}' is not registered as an executor")

    def _validate_required_fields(self) -> None:
        self._validate_executor_id()
        if not self.name:
            raise ValueError("Task name is required")

    def _get_task_repository(self) -> TaskRepository:
        return self.task_manager.task_repository


__all__ = ["TaskBuilder"]

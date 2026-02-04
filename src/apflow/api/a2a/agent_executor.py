"""
Agent executor for A2A protocol that handles task tree execution and generation.

After architecture refactoring, this executor only handles agent-level actions:
- tasks.execute (simple + streaming)
- tasks.generate (via /tasks adapter)
- cancel (A2A native tasks/cancel)

CRUD operations (create, get, update, delete, list, etc.) should use
POST /tasks (Native API) instead of A2A message/send.
"""

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, new_agent_parts_message
from a2a.types import DataPart, Task, Artifact, Part
from a2a.types import TaskStatusUpdateEvent, TaskStatus, TaskState
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable
from datetime import datetime, timezone

from apflow.core.execution.task_executor import TaskExecutor
from apflow.core.execution.task_creator import TaskCreator
from apflow.core.storage import get_default_session
from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
from apflow.core.config import get_task_model_class
from apflow.api.a2a.event_queue_bridge import EventQueueBridge
from apflow.api.a2a.task_routes_adapter import TaskRoutesAdapter
from apflow.api.routes.tasks import TaskRoutes
from apflow.logger import get_logger

logger = get_logger(__name__)

# Methods that this executor handles via A2A message/send
_EXECUTE_METHODS = {"tasks.execute", "execute_task_tree"}
_GENERATE_METHOD = "tasks.generate"


class AIPartnerUpFlowAgentExecutor(AgentExecutor):
    """
    Agent executor for A2A protocol.

    Handles agent-level actions only:
    - tasks.execute: Execute a task tree (simple or streaming mode)
    - tasks.generate: Generate a task tree from natural language via LLM
    - cancel: Cancel a running task (via A2A tasks/cancel)

    CRUD operations return an error directing clients to POST /tasks.
    """

    def __init__(
        self,
        task_routes: Optional[TaskRoutes] = None,
        verify_token_func: Optional["Callable[[str], Optional[dict]]"] = None,
    ):
        """
        Initialize agent executor. Configuration (task_model_class, hooks) is automatically
        retrieved from the global config registry.
        """
        super().__init__()
        self.task_model_class = get_task_model_class()
        self.task_routes = task_routes or TaskRoutes(task_model_class=self.task_model_class)
        self.task_routes_adapter = TaskRoutesAdapter(self.task_routes)
        self.task_executor = TaskExecutor()
        self.verify_token_func = verify_token_func

    @property
    def pre_hooks(self) -> list:
        """Get pre-hooks from task executor"""
        return self.task_executor.pre_hooks

    @property
    def post_hooks(self) -> list:
        """Get post-hooks from task executor"""
        return self.task_executor.post_hooks

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> Any:
        """
        Execute agent-level action based on method/skill_id.

        Supported:
        - tasks.execute: Execute task tree (simple or streaming)
        - tasks.generate: Generate task tree via LLM
        - No method: Default to task execution (backward compat)

        Other methods return an error directing clients to POST /tasks.
        """
        logger.debug(f"Context configuration: {context.configuration}")
        logger.debug(f"Context metadata: {context.metadata}")

        method = self.task_routes_adapter.extract_method(context)
        skill_id = context.metadata.get("skill_id") if context.metadata else None

        # ── tasks.execute ──────────────────────────────────────────
        if method in _EXECUTE_METHODS or skill_id in _EXECUTE_METHODS:
            return await self._route_execute(context, event_queue)

        # ── tasks.generate ─────────────────────────────────────────
        if method == _GENERATE_METHOD or skill_id == _GENERATE_METHOD:
            return await self._route_generate(context, event_queue)

        # ── No method specified: default to execute (backward compat)
        if not method:
            logger.warning("No method specified in context, defaulting to task execution")
            return await self._route_execute(context, event_queue)

        # ── Any other method: not supported via A2A message/send ───
        error_msg = (
            f"Method '{method}' is not supported via A2A message/send. "
            f"Use POST /tasks with JSON-RPC format instead. "
            f"A2A message/send supports: tasks.execute, tasks.generate"
        )
        logger.warning(error_msg)
        await self._send_error_update(event_queue, context, error_msg)
        raise ValueError(error_msg)

    # ── Route helpers ──────────────────────────────────────────────

    async def _route_execute(self, context: RequestContext, event_queue: EventQueue) -> Any:
        """Route to simple or streaming execution mode."""
        if self._should_use_streaming_mode(context):
            await self._execute_streaming_mode(context, event_queue)
            return None
        return await self._execute_simple_mode(context, event_queue)

    async def _route_generate(self, context: RequestContext, event_queue: EventQueue) -> Any:
        """Route tasks.generate to TaskRoutes handler and wrap result."""
        try:
            # Extract params from metadata
            params: Dict[str, Any] = {}
            if context.metadata:
                for key, value in context.metadata.items():
                    if key not in ("method", "skill_id", "stream"):
                        params[key] = value

            # Also extract from message parts
            if context.message and hasattr(context.message, "parts"):
                for part in context.message.parts:
                    data = self._extract_single_part_data(part)
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if key not in params:
                                params[key] = value

            request_id = str(uuid.uuid4())
            result = await self.task_routes.handle_task_generate(params, None, request_id)

            task_id = context.task_id or str(uuid.uuid4())
            context_id = context.context_id or task_id

            status_update = TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(
                    state=TaskState.completed,
                    message=new_agent_parts_message(
                        [
                            DataPart(
                                data={
                                    "protocol": "a2a",
                                    "result": result,
                                }
                            )
                        ]
                    ),
                ),
                final=True,
            )
            await event_queue.enqueue_event(status_update)
            return result

        except Exception as e:
            logger.error(f"Error in tasks.generate: {str(e)}", exc_info=True)
            await self._send_error_update(event_queue, context, str(e))
            raise

    # ── Execution modes ────────────────────────────────────────────

    def _should_use_streaming_mode(self, context: RequestContext) -> bool:
        """Check if streaming mode should be used (metadata.stream = True)."""
        if context.metadata and context.metadata.get("stream") is True:
            logger.debug("Using streaming mode from metadata.stream")
            return True
        logger.debug("Using simple mode")
        return False

    async def _execute_simple_mode(self, context: RequestContext, event_queue: EventQueue) -> Any:
        """Simple mode: return result directly, no intermediate status updates."""
        try:
            db_session = get_default_session()

            tasks = await self._extract_tasks_from_context(context)
            if not tasks:
                raise ValueError("No tasks provided in request")
            if isinstance(tasks, list) and all(isinstance(t, dict) for t in tasks):
                logger.debug(f"Extracted tasks with IDs: {[t.get('id') for t in tasks]}")
            else:
                logger.debug(f"Extracted tasks: {tasks}")

            context_id = context.context_id or str(uuid.uuid4())

            require_existing_tasks = (
                context.metadata.get("require_existing_tasks") if context.metadata else None
            )
            use_demo = self._extract_use_demo(context)

            execution_result = await self.task_executor.execute_tasks(
                tasks=tasks,
                root_task_id=None,
                use_streaming=False,
                require_existing_tasks=require_existing_tasks,
                use_demo=use_demo,
                db_session=db_session,
            )

            logger.debug(f"Execution result root_task_id: {execution_result.get('root_task_id')}")

            final_status = execution_result["status"]
            actual_root_task_id = execution_result["root_task_id"]

            task_id = context.task_id or actual_root_task_id
            context_id = context.context_id or actual_root_task_id

            task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
            root_task_model = await task_repository.get_task_by_id(actual_root_task_id)
            if not root_task_model:
                raise ValueError(f"Root task {actual_root_task_id} not found after execution")

            task_state = TaskState.completed if final_status == "completed" else TaskState.failed
            task_status_message = f"Task execution {final_status}"

            artifacts = [
                Artifact(
                    artifact_id=str(uuid.uuid4()),
                    parts=[
                        Part(
                            root=DataPart(
                                kind="data",
                                data={
                                    "status": final_status,
                                    "progress": float(execution_result["progress"]),
                                    "root_task_id": actual_root_task_id,
                                    "task_count": len(tasks),
                                    "result": root_task_model.result,
                                },
                            )
                        )
                    ],
                )
            ]

            metadata: Dict[str, Any] = {
                "protocol": "a2a",
                "root_task_id": actual_root_task_id,
            }
            if root_task_model.user_id:
                metadata["user_id"] = root_task_model.user_id

            a2a_task = Task(
                id=task_id,
                context_id=context_id,
                kind="task",
                status=TaskStatus(
                    state=task_state,
                    message=new_agent_text_message(task_status_message),
                ),
                artifacts=artifacts,
                metadata=metadata,
            )

            completed_status = TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(
                    state=task_state,
                    message=new_agent_parts_message(
                        [
                            DataPart(
                                data={
                                    "protocol": "a2a",
                                    "status": final_status,
                                    "progress": execution_result["progress"],
                                    "root_task_id": actual_root_task_id,
                                    "task_count": len(tasks),
                                }
                            )
                        ]
                    ),
                ),
                final=True,
            )
            await event_queue.enqueue_event(completed_status)

            return a2a_task

        except Exception as e:
            logger.error(f"Error in simple mode execution: {str(e)}", exc_info=True)

            task_id = context.task_id or str(uuid.uuid4())
            context_id = context.context_id or str(uuid.uuid4())

            error_status = TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(
                    state=TaskState.failed,
                    message=new_agent_text_message(f"Error: {str(e)}"),
                ),
                final=True,
            )
            await event_queue.enqueue_event(error_status)
            raise

    async def _execute_streaming_mode(
        self, context: RequestContext, event_queue: EventQueue
    ) -> Any:
        """Streaming mode: push multiple status update events with real-time progress."""
        if not context.task_id or not context.context_id:
            raise ValueError("Task ID and Context ID are required for streaming mode")

        logger.info("Starting streaming mode execution")
        logger.info(f"Task ID: {context.task_id}, Context ID: {context.context_id}")

        try:
            db_session = get_default_session()

            tasks = await self._extract_tasks_from_context(context)
            if not tasks:
                raise ValueError("No tasks provided in request")

            logger.info(f"Received {len(tasks)} tasks to execute")

            event_queue_bridge = EventQueueBridge(event_queue, context)
            use_demo = self._extract_use_demo(context)

            execution_result = await self.task_executor.execute_tasks(
                tasks=tasks,
                root_task_id=None,
                use_streaming=True,
                streaming_callbacks_context=event_queue_bridge,
                require_existing_tasks=None,
                use_demo=use_demo,
                db_session=db_session,
            )

            logger.info("Task tree execution started with streaming")

            return {
                "status": "in_progress",
                "task_count": len(tasks),
                "root_task_id": execution_result["root_task_id"],
            }

        except Exception as e:
            logger.error(f"Error in streaming mode execution: {str(e)}", exc_info=True)
            await self._send_error_update(event_queue, context, str(e))
            raise

    # ── Task extraction ────────────────────────────────────────────

    async def _extract_tasks_from_context(self, context: RequestContext) -> List[Dict[str, Any]]:
        """
        Extract tasks array from request context.
        Supports from_copy, from_mixed, from_link, from_archive scenarios.
        """
        meta = context.metadata or {}
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=self.task_model_class)
        task_creator = TaskCreator(db_session)
        copy_modes = ["from_copy", "from_mixed", "from_link", "from_archive"]

        mode = None
        for m in copy_modes:
            v = meta.get(m, False)
            if v is True:
                mode = m
                break

        if mode:
            task_id = meta.get("task_id")
            if not task_id:
                raise ValueError(f"{mode} requires task_id in metadata")
            original_task = await task_repository.get_task_by_id(task_id)
            if not original_task:
                raise ValueError(f"Original task not found for {mode} with id {task_id}")
            _save = meta.get("_save", True)
            _recursive = meta.get("_recursive", False)
            creator_method = getattr(task_creator, mode)
            tree = await creator_method(
                _original_task=original_task,
                _save=_save,
                _recursive=_recursive,
            )
            logger.info(f"Extracted 1 task tree from {mode} scenario (task_id={task_id})")
            return tree.output_list()

        # Default: extract tasks from message parts
        tasks: list[Dict[str, Any]] = []
        if context.message and hasattr(context.message, "parts"):
            for part in context.message.parts:
                data = self._extract_single_part_data(part)
                if data:
                    if (
                        isinstance(data, dict)
                        and "tasks" in data
                        and isinstance(data["tasks"], list)
                    ):
                        tasks.extend(data["tasks"])
                    else:
                        tasks.append(data)
        if not tasks:
            raise ValueError("No tasks found in context.message.parts or metadata")
        logger.info(f"Extracted {len(tasks)} tasks from context.message.parts")
        return tasks

    def _extract_single_part_data(self, part: Any) -> Any:
        """Extract data from a single A2A part."""
        if hasattr(part, "root"):
            data_part = part.root
            if (
                hasattr(data_part, "kind")
                and data_part.kind == "data"
                and hasattr(data_part, "data")
            ):
                return data_part.data

        if hasattr(part, "kind") and part.kind == "data" and hasattr(part, "data"):
            return part.data

        return None

    # ── Helpers ────────────────────────────────────────────────────

    def _extract_use_demo(self, context: RequestContext) -> bool:
        """Extract use_demo flag from context metadata/message/configuration."""
        use_demo = False
        if context.metadata:
            use_demo = context.metadata.get("use_demo", False)
        if not use_demo and context.message and hasattr(context.message, "metadata"):
            message_metadata = context.message.metadata
            if isinstance(message_metadata, dict):
                use_demo = message_metadata.get("use_demo", False)
        if not use_demo and context.configuration:
            try:
                config_dict = (
                    context.configuration.model_dump(exclude_none=True)
                    if hasattr(context.configuration, "model_dump")
                    else context.configuration.dict(exclude_none=True)
                )
                use_demo = config_dict.get("use_demo", False)
            except (AttributeError, TypeError):
                pass
        return use_demo

    async def _send_error_update(
        self, event_queue: EventQueue, context: RequestContext, error: str
    ) -> None:
        """Send error status via EventQueue."""
        error_data = {
            "protocol": "a2a",
            "status": "failed",
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        status_update = TaskStatusUpdateEvent(
            task_id=context.task_id or "unknown",
            context_id=context.context_id or "unknown",
            status=TaskStatus(
                state=TaskState.failed,
                message=new_agent_parts_message([DataPart(data=error_data)]),
            ),
            final=True,
        )
        await event_queue.enqueue_event(status_update)

    # ── Cancel (A2A native tasks/cancel) ───────────────────────────

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Cancel task execution.

        Called by A2A SDK for tasks/cancel JSON-RPC method.
        """
        try:
            task_id = None
            if context.task_id:
                task_id = context.task_id
            elif context.context_id:
                task_id = context.context_id
            elif context.metadata:
                task_id = context.metadata.get("task_id") or context.metadata.get("context_id")

            if not task_id:
                error_msg = "Task ID not found in context. Provide task_id or context_id."
                logger.error(error_msg)
                await self._send_cancel_error(event_queue, context, error_msg)
                return

            metadata = context.metadata or {}
            error_message = metadata.get("error_message")
            force = metadata.get("force", False)
            if force:
                logger.info(f"Force cancellation requested for task {task_id}")

            db_session = get_default_session()
            logger.info(f"Cancelling task {task_id}")

            cancel_result = await self.task_executor.cancel_task(
                task_id=task_id,
                error_message=error_message,
                db_session=db_session,
            )

            result_status = cancel_result.get("status", "failed")
            task_state = TaskState.canceled if result_status == "cancelled" else TaskState.failed

            event_data: Dict[str, Any] = {
                "protocol": "a2a",
                "status": result_status,
                "message": cancel_result.get("message", "Cancellation completed"),
            }
            if cancel_result.get("token_usage"):
                event_data["token_usage"] = cancel_result["token_usage"]
            if cancel_result.get("result"):
                event_data["result"] = cancel_result["result"]
            if cancel_result.get("error"):
                event_data["error"] = cancel_result["error"]
            event_data["timestamp"] = datetime.now(timezone.utc).isoformat()

            status_update = TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context.context_id or task_id,
                status=TaskStatus(
                    state=task_state,
                    message=new_agent_parts_message([DataPart(data=event_data)]),
                ),
                final=True,
            )
            await event_queue.enqueue_event(status_update)
            logger.info(f"Task {task_id} cancellation completed with status: {result_status}")

        except Exception as e:
            logger.error(f"Error cancelling task: {str(e)}", exc_info=True)
            await self._send_cancel_error(event_queue, context, f"Failed to cancel task: {str(e)}")

    async def _send_cancel_error(
        self,
        event_queue: EventQueue,
        context: RequestContext,
        error: str,
    ) -> None:
        """Send cancellation error via EventQueue."""
        task_id = context.task_id or context.context_id
        if not task_id and context.metadata:
            task_id = context.metadata.get("task_id") or context.metadata.get("context_id")
        task_id = task_id or "unknown"

        error_data = {
            "protocol": "a2a",
            "status": "failed",
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        status_update = TaskStatusUpdateEvent(
            task_id=task_id,
            context_id=context.context_id or task_id,
            status=TaskStatus(
                state=TaskState.failed,
                message=new_agent_parts_message([DataPart(data=error_data)]),
            ),
            final=True,
        )
        await event_queue.enqueue_event(status_update)

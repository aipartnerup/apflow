"""
Adapter class to convert between A2A protocol format and TaskRoutes format

After the architecture refactoring, this adapter is focused on:
1. Extracting method/skill_id from RequestContext (for routing in AgentExecutor)
2. Converting task dicts to A2A Task objects (used by execute results)

CRUD operations are no longer routed through the A2A "/" endpoint;
they go directly through POST /tasks (Native API).
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from a2a.server.agent_execution import RequestContext
from a2a.types import Artifact, DataPart, Part, Task, TaskState, TaskStatus
from a2a.utils import new_agent_text_message

from apflow.api.routes.tasks import TaskRoutes
from apflow.logger import get_logger

if TYPE_CHECKING:
    from typing import Callable

logger = get_logger(__name__)


# Backward-compatible skill_id aliases
_SKILL_ID_ALIASES: Dict[str, str] = {
    "execute_task_tree": "tasks.execute",
}


class TaskRoutesAdapter:
    """
    Lightweight adapter between A2A protocol and TaskRoutes.

    Responsibilities:
    - Extract method name from RequestContext metadata/skill_id
    - Convert apflow task dicts to A2A Task objects for execute results
    """

    def __init__(
        self,
        task_routes: TaskRoutes,
        verify_token_func: Optional["Callable[[str], Optional[dict]]"] = None,
    ):
        self.task_routes = task_routes
        self.verify_token_func = verify_token_func

    def extract_method(self, context: RequestContext) -> Optional[str]:
        """
        Extract method name from RequestContext.

        Checks: metadata.method -> metadata.skill_id -> configuration.method

        Returns:
            Method name (e.g. "tasks.execute", "tasks.generate") or None
        """
        if context.metadata:
            method = context.metadata.get("method")
            if method:
                return method

            skill_id = context.metadata.get("skill_id")
            if skill_id:
                return _SKILL_ID_ALIASES.get(skill_id, skill_id)

        if context.configuration:
            method = getattr(context.configuration, "method", None)
            if method:
                return method

        return None

    # ── A2A Task conversion helpers (used by AgentExecutor for execute results) ──

    def convert_to_a2a_task(
        self,
        task_dict: Dict[str, Any],
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> Task:
        """Convert task dictionary to A2A Task object."""
        task_id = task_id or task_dict.get("id")
        context_id = context_id or task_id

        status_str = task_dict.get("status", "pending")
        status_map = {
            "pending": TaskState.pending,
            "in_progress": TaskState.in_progress,
            "completed": TaskState.completed,
            "failed": TaskState.failed,
            "cancelled": TaskState.canceled,
        }
        task_state = status_map.get(status_str, TaskState.pending)

        status_message = f"Task {status_str}"
        if task_dict.get("error"):
            status_message = f"Task failed: {task_dict.get('error')}"

        artifacts: list[Artifact] = []
        if task_dict.get("result") is not None:
            artifacts.append(
                Artifact(
                    artifact_id=str(task_dict.get("id", task_id)),
                    parts=[
                        Part(
                            root=DataPart(
                                kind="data",
                                data={
                                    "protocol": "a2a",
                                    "task_id": task_id,
                                    "status": status_str,
                                    "result": task_dict.get("result"),
                                    "progress": float(task_dict.get("progress", 0.0)),
                                },
                            )
                        )
                    ],
                )
            )

        metadata: Dict[str, Any] = {
            "protocol": "a2a",
            "task_id": task_id,
        }
        if task_dict.get("user_id"):
            metadata["user_id"] = task_dict["user_id"]
        if task_dict.get("root_task_id"):
            metadata["root_task_id"] = task_dict["root_task_id"]

        return Task(
            id=task_id,
            context_id=context_id,
            kind="task",
            status=TaskStatus(
                state=task_state,
                message=new_agent_text_message(status_message),
            ),
            artifacts=artifacts,
            metadata=metadata,
        )

    def convert_list_to_a2a_tasks(
        self,
        task_list: List[Dict[str, Any]],
        context_id: Optional[str] = None,
    ) -> List[Task]:
        """Convert list of task dictionaries to A2A Task objects."""
        return [
            self.convert_to_a2a_task(task_dict, context_id=context_id) for task_dict in task_list
        ]

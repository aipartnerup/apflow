"""
Unified Capabilities Registry for apflow API

Single source of truth for all task operations. Generates both A2A AgentSkill
definitions and MCP tool definitions from the same registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from apflow.api.protocol_types import ProtocolRegistry


# Operation categories
CATEGORY_AGENT_ACTION = "agent_action"
CATEGORY_CRUD = "crud"
CATEGORY_QUERY = "query"
CATEGORY_MONITORING = "monitoring"
CATEGORY_SCHEDULING = "scheduling"


@dataclass
class OperationDef:
    """Defines a single API operation, shared across all protocols."""

    id: str
    name: str
    description: str
    tags: list[str]
    examples: list[str]
    input_schema: Dict[str, Any]
    category: str
    supports_streaming: bool = False
    mcp_tool_name: Optional[str] = None
    handler_method: Optional[str] = None
    input_modes: list[str] = field(default_factory=lambda: ["application/json"])
    output_modes: list[str] = field(default_factory=lambda: ["application/json"])

    def to_agent_skill(self) -> Any:
        """Convert to A2A AgentSkill object."""
        from a2a.types import AgentSkill

        return AgentSkill(
            id=self.id,
            name=self.name,
            description=self.description,
            tags=self.tags,
            examples=self.examples,
            input_modes=self.input_modes,
            output_modes=self.output_modes,
        )

    def to_mcp_tool_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool definition dictionary."""
        return {
            "name": self.get_mcp_tool_name(),
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    def to_discovery_dict(self) -> Dict[str, Any]:
        """Convert to discovery format for GET /tasks/methods endpoint."""
        return {
            "method": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "input_schema": self.input_schema,
            "supports_streaming": self.supports_streaming,
            "examples": self.examples,
        }

    def get_mcp_tool_name(self) -> str:
        """Get MCP tool name (dots replaced with underscores)."""
        if self.mcp_tool_name:
            return self.mcp_tool_name
        return self.id.replace(".", "_")

    def get_handler_method(self) -> str:
        """Get the TaskRoutes handler method name for this operation."""
        if self.handler_method:
            return self.handler_method
        # Default: tasks.create -> handle_task_create, tasks.list -> handle_tasks_list
        parts = self.id.split(".")
        if len(parts) == 2 and parts[0] == "tasks":
            method = parts[1]
            if method == "list":
                return "handle_tasks_list"
            if method == "count":
                return "handle_tasks_count"
            return f"handle_task_{method}"
        # tasks.running.list -> handle_running_tasks_list
        if len(parts) == 3 and parts[0] == "tasks" and parts[1] == "running":
            return f"handle_running_tasks_{parts[2]}"
        # tasks.scheduled.list -> handle_scheduled_tasks_list
        if len(parts) == 3 and parts[0] == "tasks" and parts[1] == "scheduled":
            return f"handle_scheduled_tasks_{parts[2]}"
        # tasks.webhook.trigger -> handle_webhook_trigger
        if len(parts) == 3 and parts[0] == "tasks" and parts[1] == "webhook":
            return f"handle_webhook_{parts[2]}"
        return f"handle_{self.id.replace('.', '_')}"


def _build_operations() -> list[OperationDef]:
    """Build the complete list of operations."""
    ops: list[OperationDef] = []

    # ── Agent Actions ──────────────────────────────────────────────
    ops.append(
        OperationDef(
            id="tasks.execute",
            name="Execute Task Tree",
            description="Execute a complete task tree with multiple tasks",
            tags=["task", "orchestration", "workflow", "execution"],
            examples=["execute task tree", "run tasks", "process task hierarchy"],
            category=CATEGORY_AGENT_ACTION,
            supports_streaming=True,
            mcp_tool_name="execute_task",
            handler_method="handle_task_execute",
            output_modes=["application/json", "text/event-stream"],
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to execute (optional if tasks is provided)",
                    },
                    "tasks": {
                        "type": "array",
                        "description": "Array of task dictionaries to execute (optional if task_id is provided)",
                    },
                    "use_streaming": {
                        "type": "boolean",
                        "description": "Enable streaming mode for real-time updates (default: false)",
                    },
                    "webhook_config": {
                        "type": "object",
                        "description": "Webhook configuration for push notifications",
                        "properties": {
                            "url": {"type": "string"},
                            "headers": {"type": "object"},
                            "method": {"type": "string"},
                            "timeout": {"type": "number"},
                            "max_retries": {"type": "integer"},
                        },
                    },
                },
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.generate",
            name="Generate Task Tree",
            description="Generate a task tree JSON array from natural language requirement using LLM",
            tags=["task", "generate", "llm", "ai", "automation"],
            examples=[
                "generate task tree",
                "create task from requirement",
                "auto-generate workflow",
            ],
            category=CATEGORY_AGENT_ACTION,
            mcp_tool_name="generate_task_tree",
            handler_method="handle_task_generate",
            input_schema={
                "type": "object",
                "properties": {
                    "requirement": {
                        "type": "string",
                        "description": "Natural language requirement to generate task tree from",
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context for task generation",
                    },
                },
                "required": ["requirement"],
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.cancel",
            name="Cancel Task",
            description="Cancel one or more running tasks",
            tags=["task", "cancel", "stop", "control"],
            examples=["cancel task", "stop task", "abort task"],
            category=CATEGORY_AGENT_ACTION,
            mcp_tool_name="cancel_task",
            handler_method="handle_task_cancel",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to cancel",
                    }
                },
                "required": ["task_id"],
            },
        )
    )

    # ── CRUD Operations ────────────────────────────────────────────
    ops.append(
        OperationDef(
            id="tasks.create",
            name="Create Task",
            description="Create a new task or task tree",
            tags=["task", "create", "crud"],
            examples=["create task", "create task tree", "add task"],
            category=CATEGORY_CRUD,
            mcp_tool_name="create_task",
            handler_method="handle_task_create",
            input_schema={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "Array of task dictionaries to create (can be single task in array)",
                        "items": {
                            "type": "object",
                            "description": "Task definition with name, description, executor, inputs, etc.",
                        },
                    }
                },
                "required": ["tasks"],
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.get",
            name="Get Task",
            description="Get a task by ID",
            tags=["task", "get", "crud", "read"],
            examples=["get task", "retrieve task", "fetch task"],
            category=CATEGORY_CRUD,
            mcp_tool_name="get_task",
            handler_method="handle_task_get",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to retrieve",
                    }
                },
                "required": ["task_id"],
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.update",
            name="Update Task",
            description="Update an existing task",
            tags=["task", "update", "crud", "modify"],
            examples=["update task", "modify task", "edit task"],
            category=CATEGORY_CRUD,
            mcp_tool_name="update_task",
            handler_method="handle_task_update",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to update",
                    },
                    "name": {"type": "string", "description": "Task name"},
                    "description": {
                        "type": "string",
                        "description": "Task description",
                    },
                    "status": {"type": "string", "description": "Task status"},
                    "inputs": {"type": "object", "description": "Task inputs"},
                    "schemas": {"type": "object", "description": "Task schemas"},
                },
                "required": ["task_id"],
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.delete",
            name="Delete Task",
            description="Delete a task and its children (if all are pending)",
            tags=["task", "delete", "crud", "remove"],
            examples=["delete task", "remove task", "drop task"],
            category=CATEGORY_CRUD,
            mcp_tool_name="delete_task",
            handler_method="handle_task_delete",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to delete",
                    }
                },
                "required": ["task_id"],
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.clone",
            name="Clone Task",
            description="Clone/link/archive a task (origin types: copy, link, archive, mixed)",
            tags=["task", "clone", "copy", "duplicate"],
            examples=["clone task", "copy task", "duplicate task"],
            category=CATEGORY_CRUD,
            mcp_tool_name="clone_task",
            handler_method="handle_task_clone",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Source task ID to clone",
                    },
                    "origin_type": {
                        "type": "string",
                        "description": "Clone mode: copy, link, archive, mixed",
                        "enum": ["copy", "link", "archive", "mixed"],
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Clone children recursively (default: false)",
                    },
                },
                "required": ["task_id"],
            },
        )
    )

    # ── Query Operations ───────────────────────────────────────────
    ops.append(
        OperationDef(
            id="tasks.detail",
            name="Get Task Detail",
            description="Get full task details including all fields",
            tags=["task", "detail", "query", "read"],
            examples=["get task detail", "task details", "full task info"],
            category=CATEGORY_QUERY,
            mcp_tool_name="get_task_detail",
            handler_method="handle_task_detail",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to get details for",
                    }
                },
                "required": ["task_id"],
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.tree",
            name="Get Task Tree",
            description="Get task tree structure with nested children",
            tags=["task", "tree", "query", "hierarchy"],
            examples=["get task tree", "task hierarchy", "task structure"],
            category=CATEGORY_QUERY,
            mcp_tool_name="get_task_tree",
            handler_method="handle_task_tree",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Root task ID to get tree for",
                    }
                },
                "required": ["task_id"],
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.list",
            name="List Tasks",
            description="List all tasks with optional filters (user_id, status, root_only)",
            tags=["task", "list", "query", "search"],
            examples=["list tasks", "get all tasks", "search tasks"],
            category=CATEGORY_QUERY,
            mcp_tool_name="list_tasks",
            handler_method="handle_tasks_list",
            input_schema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status (pending, in_progress, completed, failed, cancelled)",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Filter by user ID",
                    },
                    "root_only": {
                        "type": "boolean",
                        "description": "Only return root tasks (default: false)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination",
                    },
                },
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.children",
            name="Get Task Children",
            description="Get child tasks for a given parent task",
            tags=["task", "children", "query", "hierarchy"],
            examples=["get task children", "list children", "child tasks"],
            category=CATEGORY_QUERY,
            mcp_tool_name="get_task_children",
            handler_method="handle_task_children",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Parent task ID",
                    }
                },
                "required": ["task_id"],
            },
        )
    )

    # ── Monitoring Operations ──────────────────────────────────────
    ops.append(
        OperationDef(
            id="tasks.running.list",
            name="List Running Tasks",
            description="List currently running tasks from memory",
            tags=["task", "running", "monitoring", "status"],
            examples=["list running tasks", "active tasks", "current tasks"],
            category=CATEGORY_MONITORING,
            mcp_tool_name="list_running_tasks",
            handler_method="handle_running_tasks_list",
            input_schema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Filter by user ID",
                    }
                },
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.running.status",
            name="Get Running Task Status",
            description="Get status of multiple running tasks",
            tags=["task", "running", "status", "monitoring"],
            examples=["get task status", "check task status", "task status"],
            category=CATEGORY_MONITORING,
            mcp_tool_name="get_task_status",
            handler_method="handle_running_tasks_status",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to get status for",
                    }
                },
                "required": ["task_id"],
            },
        )
    )

    ops.append(
        OperationDef(
            id="tasks.running.count",
            name="Count Running Tasks",
            description="Get count of running tasks by status",
            tags=["task", "running", "count", "monitoring"],
            examples=["count running tasks", "task count", "number of tasks"],
            category=CATEGORY_MONITORING,
            mcp_tool_name="count_running_tasks",
            handler_method="handle_running_tasks_count",
            input_schema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Filter by user ID",
                    }
                },
            },
        )
    )

    return ops


# Module-level singleton
_operations: Optional[list[OperationDef]] = None


def get_all_operations() -> list[OperationDef]:
    """Get all registered operations."""
    global _operations
    if _operations is None:
        _operations = _build_operations()
    return _operations


def get_operations_by_category(category: str) -> list[OperationDef]:
    """Get operations filtered by category."""
    return [op for op in get_all_operations() if op.category == category]


def get_agent_action_operations() -> list[OperationDef]:
    """Get operations suitable for A2A agent actions (execute, generate, cancel)."""
    return get_operations_by_category(CATEGORY_AGENT_ACTION)


def get_operation_by_id(operation_id: str) -> Optional[OperationDef]:
    """Get a single operation by its ID."""
    for op in get_all_operations():
        if op.id == operation_id:
            return op
    return None


def get_mcp_tool_name_to_operation() -> Dict[str, OperationDef]:
    """Get mapping from MCP tool name to operation definition."""
    return {op.get_mcp_tool_name(): op for op in get_all_operations()}


def get_all_agent_skills() -> list[Any]:
    """Generate all A2A AgentSkill objects from registry."""
    return [op.to_agent_skill() for op in get_all_operations()]


def get_all_mcp_tool_dicts() -> list[Dict[str, Any]]:
    """Generate all MCP tool definition dictionaries from registry."""
    return [op.to_mcp_tool_dict() for op in get_all_operations()]


def get_methods_discovery(
    registry: ProtocolRegistry | None = None,
) -> Dict[str, Any]:
    """Generate discovery response for GET /tasks/methods endpoint.

    Args:
        registry: Optional ProtocolRegistry. When provided, includes
                  per-protocol availability info in the response.

    Returns a structured summary of all available methods grouped by category,
    suitable for both human inspection and programmatic discovery.
    """
    ops = get_all_operations()
    by_category: Dict[str, list[Dict[str, Any]]] = {}
    for op in ops:
        by_category.setdefault(op.category, []).append(op.to_discovery_dict())

    result: Dict[str, Any] = {
        "total": len(ops),
        "categories": list(by_category.keys()),
        "methods": by_category,
    }

    if registry is not None:
        result["protocols"] = registry.get_discovery()
    else:
        result["protocols"] = {}

    return result


async def dispatch_operation(
    operation_id: str,
    params: Dict[str, Any],
    verify_token_func: Any = None,
    verify_permission_func: Any = None,
) -> Dict[str, Any]:
    """Dispatch an operation by looking up its handler in TaskRoutes.

    Shared implementation used by all protocol adapters for handle_request.
    In distributed mode, mutating operations are rejected on non-leader nodes.
    """
    from apflow.api.routes.tasks import TaskRoutes
    from apflow.core.config import get_task_model_class

    op = get_operation_by_id(operation_id)
    if op is None:
        raise ValueError(f"Unknown operation: {operation_id}")

    # In distributed mode, enforce leader-only for mutating operations
    if op.category in (CATEGORY_AGENT_ACTION, CATEGORY_CRUD):
        rejection = _check_distributed_leader(op)
        if rejection is not None:
            return rejection

    handler_name = op.get_handler_method()
    task_routes = TaskRoutes(
        task_model_class=get_task_model_class(),  # type: ignore[arg-type]
        verify_token_func=verify_token_func,
        verify_permission_func=verify_permission_func,
    )
    handler = getattr(task_routes, handler_name, None)
    if handler is None:
        raise ValueError(f"No handler for operation: {operation_id}")

    return await handler(params, None, "")


def _check_distributed_leader(op: OperationDef) -> Optional[Dict[str, Any]]:
    """Return an error dict if distributed mode is active and this node is not leader."""
    from apflow.core.distributed.config import DistributedConfig

    config = DistributedConfig.from_env()
    if not config.enabled:
        return None

    from apflow.core.execution.task_executor import TaskExecutor

    executor = TaskExecutor()
    if executor._is_leader_or_single_node():
        return None

    current_role = (
        executor.distributed_runtime.current_role if executor.distributed_runtime else "unknown"
    )
    return {
        "error": "operation_rejected",
        "operation": op.id,
        "message": "This node is not the cluster leader. "
        "Mutating operations are only allowed on the leader node.",
        "current_role": current_role,
    }

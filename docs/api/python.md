# Python API Reference

> **Looking for a quick syntax lookup?** See the [API Quick Reference](quick-reference.md) for concise code patterns and usage. This document provides detailed explanations and examples.

Complete reference for apflow's Python API. This document lists all available APIs and how to use them.

**For detailed implementation details, see:**
- Source code: `src/apflow/` (well-documented with docstrings)
- Test cases: `tests/` (comprehensive examples of all features)

## Table of Contents

1. [Overview](#overview)
2. [TaskManager](#taskmanager)
3. [ExecutableTask](#executabletask)
4. [BaseTask](#basetask)
5. [TaskTreeNode](#tasktreenode)
6. [TaskRepository](#taskrepository)
7. [TaskExecutor](#taskexecutor)
8. [TaskCreator](#taskcreator)
9. [Extension Registry](#extension-registry)
10. [Hooks](#hooks)
11. [Common Patterns](#common-patterns)

## Overview

The core API consists of:

- **TaskManager**: Task orchestration and execution engine
- **ExecutableTask**: Interface for all task executors
- **BaseTask**: Recommended base class for custom executors
- **TaskTreeNode**: Task tree structure representation
- **TaskRepository**: Database operations for tasks
- **TaskExecutor**: Singleton for task execution management
- **TaskCreator**: Task tree creation from arrays
- **ExtensionRegistry**: Extension discovery and management

**Understanding Lifecycles:**

For a complete understanding of task execution flow, database session management, and hook context lifecycle, see [Task Tree Execution Lifecycle](../architecture/task-tree-lifecycle.md). This is essential reading for:
- Implementing hooks that access the database
- Understanding session scope and transaction boundaries
- Debugging execution issues
- Ensuring proper resource cleanup

## Quick Start Example

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    # Create database session
    db = create_session()
    
    # Create task manager
    task_manager = TaskManager(db)
    
    # Create a task
    task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="user123",
        inputs={"resource": "cpu"}
    )
    
    # Build and execute task tree
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # Get result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Result: {result.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## TaskManager

The main class for orchestrating and executing task trees.

### Initialization

```python
from apflow import TaskManager, create_session

db = create_session()
task_manager = TaskManager(
    db,
    root_task_id=None,              # Optional: Root task ID for streaming
    pre_hooks=None,                 # Optional: List of pre-execution hooks
    post_hooks=None,                # Optional: List of post-execution hooks
    executor_instances=None         # Optional: Shared executor instances dict
)
```

**See**: `src/apflow/core/execution/task_manager.py` for full implementation details.

### Main Methods

#### `distribute_task_tree(task_tree, use_callback=True)`

Execute a task tree with dependency management and priority scheduling.

```python
result = await task_manager.distribute_task_tree(
    task_tree: TaskTreeNode,
    use_callback: bool = True
) -> TaskTreeNode
```

**See**: `tests/core/execution/test_task_manager.py` for comprehensive examples.

#### `distribute_task_tree_with_streaming(task_tree, use_callback=True)`

Execute a task tree with real-time streaming for progress updates.

```python
await task_manager.distribute_task_tree_with_streaming(
    task_tree: TaskTreeNode,
    use_callback: bool = True
) -> None
```

#### `cancel_task(task_id, error_message=None)`

Cancel a running task execution.

```python
result = await task_manager.cancel_task(
    task_id: str,
    error_message: str | None = None
) -> Dict[str, Any]
```

### Properties

- `task_repository` (TaskRepository): Access to task repository for database operations
- `streaming_callbacks` (StreamingCallbacks): Streaming callbacks instance

**See**: Source code in `src/apflow/core/execution/task_manager.py` for all available methods and detailed documentation.

## BaseTask

Recommended base class for creating custom executors. Provides automatic registration via decorator.

### Usage

```python
from apflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class MyExecutor(BaseTask):
    id = "my_executor"
    name = "My Executor"
    description = "Does something useful"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "result": "..."}
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter"}
            },
            "required": ["param"]
        }
```

**See**: `tests/extensions/tools/test_tools_decorator.py` and `docs/guides/custom-tasks.md` for examples.

## ExecutableTask

Abstract base class for all task executors. Use `BaseTask` for simplicity, or `ExecutableTask` for more control.

### Required Interface

- `id` (property): Unique identifier
- `name` (property): Display name
- `description` (property): Description
- `execute(inputs)`: Main execution logic (async)
- `get_input_schema()`: Return JSON Schema for inputs

### Optional Methods

- `cancel()`: Cancel task execution (optional)

**See**: `src/apflow/core/interfaces/executable_task.py` for full interface definition.

## TaskTreeNode

Represents a node in a task tree structure.

### Main Methods

- `add_child(child)`: Add a child node
- `calculate_progress()`: Calculate progress (0.0 to 1.0)
- `calculate_status()`: Calculate overall status

### Properties

- `task` (TaskModel): The task model instance
- `children` (List[TaskTreeNode]): List of child nodes

**See**: `src/apflow/core/types.py` for full implementation and `tests/core/execution/test_task_manager.py` for usage examples.

## TaskRepository

Database operations for tasks.

### Main Methods

- `create_task(...)`: Create a new task
- `get_task_by_id(task_id)`: Get task by ID
- `get_root_task(task)`: Get root task
- `build_task_tree(task)`: Build task tree from task
- `update_task_status(task_id, status, ...)`: Update task status and related fields (error, result, progress, timestamps)
- `update_task_inputs(task_id, inputs)`: Update task inputs
- `update_task_dependencies(task_id, dependencies)`: Update task dependencies (with validation)
- `update_task_name(task_id, name)`: Update task name
- `update_task_priority(task_id, priority)`: Update task priority
- `update_task_params(task_id, params)`: Update executor parameters
- `update_task_schemas(task_id, schemas)`: Update validation schemas
- `delete_task(task_id)`: Physically delete a task from the database
- `get_all_children_recursive(task_id)`: Recursively get all child tasks (including grandchildren)
- `find_dependent_tasks(task_id)`: Find all tasks that depend on a given task (reverse dependencies)
- `list_tasks(...)`: List tasks with filters

**See**: `src/apflow/core/storage/sqlalchemy/task_repository.py` for all methods and `tests/core/storage/sqlalchemy/test_task_repository.py` for examples.

**Note on Task Updates:**
- Critical fields (`parent_id`, `user_id`, `dependencies`) are validated strictly:
  - `parent_id` and `user_id`: Cannot be updated (always rejected)
  - `dependencies`: Can only be updated for `pending` tasks, with validation for references, circular dependencies, and executing dependents
- Other fields can be updated freely from any task status
- For API-level updates with validation, use the `tasks.update` JSON-RPC endpoint via `TaskRoutes.handle_task_update()`

**Note on Task Deletion:**
- `delete_task()` performs physical deletion (not soft-delete)
- For API-level deletion with validation, use the `tasks.delete` JSON-RPC endpoint via `TaskRoutes.handle_task_delete()`
- The API endpoint validates that all tasks (task + children) are pending and checks for dependencies before deletion

## TaskCreator

Create task trees from task arrays.

### Main Methods

- `create_task_tree_from_array(tasks)`: Create task tree from array of task dictionaries
- `create_task_copy(original_task, children=False, copy_mode="minimal", custom_task_ids=None, custom_include_children=False, reset_fields=None, save=True)`: Create a copy of an existing task tree for re-execution.
  - `children` (bool): If `True`, also copy each direct child task with its dependencies (deduplication ensures tasks depending on multiple copied tasks are only copied once). Default: `False`.
  - `copy_mode` (str): Copy mode - `"minimal"` (default), `"full"`, or `"custom"`.
    - `"minimal"`: Copies minimal subtree (original_task + children + dependents). All copied tasks are marked as pending for re-execution.
    - `"full"`: Copies complete tree from root. Tasks that need re-execution are marked as pending, unrelated successful tasks are marked as completed with preserved token_usage.
    - `"custom"`: Copies only specified tasks. Requires `custom_task_ids` parameter.
  - `custom_task_ids` (list[str], optional): List of task IDs to copy. Required when `copy_mode="custom"`. Only tasks with IDs in this list (and their dependencies) will be copied.
  - `custom_include_children` (bool): If `True`, also include all children recursively when using `copy_mode="custom"`. Default: `False`.
  - `reset_fields` (list[str], optional): List of field names to reset during copy. Common fields: `["status", "progress", "result", "error"]`. Default: `None` (uses mode-specific defaults).
  - `save` (bool): If `True` (default), saves copied tasks to database and returns `TaskTreeNode`. If `False`, returns task array without saving to database (suitable for preview or direct use with `tasks.create`).
  - **Returns**: `TaskTreeNode` when `save=True`, or `List[Dict[str, Any]]` (task array) when `save=False`.
  - **Note**: All copied tasks receive new UUIDs for clear task tree relationships. Dependencies correctly reference new task IDs within the copied tree.

**See**: `src/apflow/core/execution/task_creator.py` for implementation and `tests/core/execution/test_task_creator.py` for examples.

## TaskModel

Database model for tasks.

### Main Fields

- `id`, `parent_id`, `user_id`, `name`, `status`, `priority`
- `dependencies`, `inputs`, `params`, `result`, `error`, `schemas`
- `progress`, `has_children`
- `created_at`, `started_at`, `updated_at`, `completed_at`
- `original_task_id`, `has_copy`

### Methods

- `to_dict()`: Convert model to dictionary

**See**: `src/apflow/core/storage/sqlalchemy/models.py` for full model definition.

## TaskStatus

Task status constants and utilities.

### Constants

- `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `CANCELLED`

### Methods

- `is_terminal(status)`: Check if status is terminal
- `is_active(status)`: Check if status is active

**See**: `src/apflow/core/storage/sqlalchemy/models.py` for implementation.

## Utility Functions

### Session Management

- `create_pooled_session()`: Create a pooled database session context manager (recommended)
- `create_session()`: Create a new raw database session
- `get_default_session()`: **Deprecated**. Use `create_pooled_session()` instead.

### Extension Registry

- `executor_register()`: Decorator to register executors (recommended)
- `register_pre_hook(hook)`: Register pre-execution hook
- `register_post_hook(hook)`: Register post-execution hook
- `register_task_tree_hook(event, hook)`: Register task tree lifecycle hook
- `get_registry()`: Get extension registry instance

### Hook Database Access

- `get_hook_repository()`: Get TaskRepository instance in hook context (recommended)
- `get_hook_session()`: Get database session in hook context

Hooks can access the database using the same session as TaskManager:

```python
from apflow import register_pre_hook, get_hook_repository

@register_pre_hook
async def my_hook(task):
    # Get repository from hook context
    repo = get_hook_repository()
    if repo:
        # Modify task fields
        await repo.update_task_priority(task.id, 10)
        # Query other tasks
        pending = await repo.get_tasks_by_status("pending")
```

**See**: `src/apflow/core/decorators.py` and `src/apflow/core/extensions/registry.py` for implementation.

### Type Definitions

- `TaskPreHook`: Type alias for pre-execution hook functions
- `TaskPostHook`: Type alias for post-execution hook functions

**See**: `src/apflow/core/extensions/types.py` for type definitions.

## Error Handling

### Common Exceptions

- `ValueError`: Invalid input parameters
- `RuntimeError`: Execution errors
- `KeyError`: Missing required fields

### Error Response Format

Tasks that fail return:

```python
{
    "status": "failed",
    "error": "Error message",
    "error_type": "ExceptionType"
}
```

## Common Patterns

### Pattern 1: Simple Task Execution

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create task
    task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="user123",
        inputs={"resource": "cpu"}
    )
    
    # Build tree
    tree = TaskTreeNode(task)
    
    # Execute
    await task_manager.distribute_task_tree(tree)
    
    # Get result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Status: {result.status}")
    print(f"Result: {result.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Pattern 2: Sequential Tasks (Dependencies)

```python
# Create tasks with dependencies
task1 = await task_manager.task_repository.create_task(
    name="fetch_data",
    user_id="user123",
    priority=1
)

task2 = await task_manager.task_repository.create_task(
    name="process_data",
    user_id="user123",
    parent_id=task1.id,
    dependencies=[{"id": task1.id, "required": True}],  # Waits for task1
    priority=2,
    inputs={"data": []}  # Will be populated from task1 result
)

task3 = await task_manager.task_repository.create_task(
    name="save_results",
    user_id="user123",
    parent_id=task1.id,
    dependencies=[{"id": task2.id, "required": True}],  # Waits for task2
    priority=3
)

# Build tree
root = TaskTreeNode(task1)
root.add_child(TaskTreeNode(task2))
root.add_child(TaskTreeNode(task3))

# Execute (order: task1 → task2 → task3)
await task_manager.distribute_task_tree(root)
```

### Pattern 3: Parallel Tasks

```python
# Create root
root_task = await task_manager.task_repository.create_task(
    name="root",
    user_id="user123",
    priority=1
)

# Create parallel tasks (no dependencies between them)
task1 = await task_manager.task_repository.create_task(
    name="task1",
    user_id="user123",
    parent_id=root_task.id,
    priority=2
)

task2 = await task_manager.task_repository.create_task(
    name="task2",
    user_id="user123",
    parent_id=root_task.id,
    priority=2  # Same priority, no dependencies = parallel
)

task3 = await task_manager.task_repository.create_task(
    name="task3",
    user_id="user123",
    parent_id=root_task.id,
    priority=2
)

# Build tree
root = TaskTreeNode(root_task)
root.add_child(TaskTreeNode(task1))
root.add_child(TaskTreeNode(task2))
root.add_child(TaskTreeNode(task3))

# Execute (all three run in parallel)
await task_manager.distribute_task_tree(root)
```

### Pattern 4: Error Handling

```python
# Execute task tree
await task_manager.distribute_task_tree(task_tree)

# Check all tasks for errors
def check_task_status(task_id):
    task = await task_manager.task_repository.get_task_by_id(task_id)
    if task.status == "failed":
        print(f"Task {task_id} failed: {task.error}")
        return False
    elif task.status == "completed":
        print(f"Task {task_id} completed: {task.result}")
        return True
    return None

# Check root task
root_status = check_task_status(root_task.id)

# Check all children
for child in task_tree.children:
    check_task_status(child.task.id)
```

### Pattern 5: Using TaskExecutor

```python
from apflow.core.execution.task_executor import TaskExecutor

# Get singleton instance
executor = TaskExecutor()

# Execute tasks from definitions
tasks = [
    {
        "id": "task1",
        "name": "my_executor",
        "user_id": "user123",
        "inputs": {"key": "value"}
    },
    {
        "id": "task2",
        "name": "my_executor",
        "user_id": "user123",
        "parent_id": "task1",
        "dependencies": [{"id": "task1", "required": True}],
        "inputs": {"key": "value2"}
    }
]

# Execute
result = await executor.execute_tasks(
    tasks=tasks,
    root_task_id="root_123",
    use_streaming=False
)

print(f"Execution result: {result}")
```

### Pattern 6: Custom Executor with Error Handling

```python
from apflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class RobustExecutor(BaseTask):
    id = "robust_executor"
    name = "Robust Executor"
    description = "Executor with comprehensive error handling"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Validate inputs
            if not inputs.get("data"):
                return {
                    "status": "failed",
                    "error": "data is required",
                    "error_type": "validation_error"
                }
            
            # Process
            result = self._process(inputs["data"])
            
            return {
                "status": "completed",
                "result": result
            }
        except ValueError as e:
            return {
                "status": "failed",
                "error": str(e),
                "error_type": "ValueError"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def _process(self, data):
        # Your processing logic
        return {"processed": data}
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Data to process"}
            },
            "required": ["data"]
        }
```

## A2A Protocol Integration

apflow implements the A2A (Agent-to-Agent) Protocol standard, allowing seamless integration with other A2A-compatible agents and services.

### Using A2A Client SDK

The A2A protocol provides an official client SDK for easy integration. Here's how to use it with apflow:

#### Installation

```bash
pip install a2a
```

#### Basic Example

```python
from a2a.client import ClientFactory, ClientConfig
from a2a.types import Message, DataPart, Role, AgentCard
import httpx
import uuid
import asyncio

async def execute_task_via_a2a():
    # Create HTTP client
    httpx_client = httpx.AsyncClient(base_url="http://localhost:8000")
    
    # Create A2A client config
    config = ClientConfig(
        streaming=True,
        polling=False,
        httpx_client=httpx_client
    )
    
    # Create client factory
    factory = ClientFactory(config=config)
    
    # Fetch agent card
    from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
    card_response = await httpx_client.get(AGENT_CARD_WELL_KNOWN_PATH)
    agent_card = AgentCard(**card_response.json())
    
    # Create A2A client
    client = factory.create(card=agent_card)
    
    # Prepare task data
    task_data = {
        "id": "task-1",
        "name": "My Task",
        "user_id": "user123",
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {}
    }
    
    # Create A2A message
    data_part = DataPart(kind="data", data={"tasks": [task_data]})
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[data_part]
    )
    
    # Send message and process responses
    async for response in client.send_message(message):
        if isinstance(response, Message):
            for part in response.parts:
                if part.kind == "data" and isinstance(part.data, dict):
                    result = part.data
                    print(f"Status: {result.get('status')}")
                    print(f"Progress: {result.get('progress')}")
    
    await httpx_client.aclose()

# Run
asyncio.run(execute_task_via_a2a())
```

### Push Notification Configuration

You can use push notifications to receive task execution updates via callback URL:

```python
from a2a.types import Configuration, PushNotificationConfig

# Create push notification config
push_config = PushNotificationConfig(
    url="https://your-server.com/callback",
    headers={
        "Authorization": "Bearer your-token"
    }
)

# Create configuration
configuration = Configuration(
    push_notification_config=push_config
)

# Create message with configuration
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[data_part],
    configuration=configuration
)

# Send message - server will use callback mode
async for response in client.send_message(message):
    # Initial response only
    print(f"Initial response: {response}")
    break
```

The server will send task status updates to your callback URL as the task executes.

### Cancelling Tasks

You can cancel a running task using the A2A Protocol `cancel` method:

```python
from a2a.client import ClientFactory, ClientConfig
from a2a.types import Message, DataPart, Role, AgentCard, RequestContext
import httpx
import uuid
import asyncio

async def cancel_task_via_a2a():
    # Create HTTP client
    httpx_client = httpx.AsyncClient(base_url="http://localhost:8000")
    
    # Create A2A client config
    config = ClientConfig(
        streaming=True,
        polling=False,
        httpx_client=httpx_client
    )
    
    # Create client factory
    factory = ClientFactory(config=config)
    
    # Fetch agent card
    from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
    card_response = await httpx_client.get(AGENT_CARD_WELL_KNOWN_PATH)
    agent_card = AgentCard(**card_response.json())
    
    # Create A2A client
    client = factory.create(card=agent_card)
    
    # Create cancel request
    # Task ID can be provided in multiple ways (priority order):
    # 1. task_id in RequestContext
    # 2. context_id in RequestContext
    # 3. metadata.task_id
    # 4. metadata.context_id
    cancel_message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[],  # Empty parts for cancel
        task_id="my-running-task",  # Task ID to cancel
        metadata={
            "error_message": "User requested cancellation"  # Optional custom message
        }
    )
    
    # Send cancel request and process responses
    async for response in client.send_message(cancel_message):
        if isinstance(response, Message):
            for part in response.parts:
                if part.kind == "data" and isinstance(part.data, dict):
                    result = part.data
                    status = result.get("status")
                    if status == "cancelled":
                        print(f"Task cancelled successfully: {result.get('message')}")
                        if "token_usage" in result:
                            print(f"Token usage: {result['token_usage']}")
                        if "result" in result:
                            print(f"Partial result: {result['result']}")
                    elif status == "failed":
                        print(f"Cancellation failed: {result.get('error', result.get('message'))}")
    
    await httpx_client.aclose()

# Run
asyncio.run(cancel_task_via_a2a())
```

**Notes:**
- The `cancel()` method sends a `TaskStatusUpdateEvent` through the EventQueue
- Task ID extraction follows priority: `task_id` > `context_id` > `metadata.task_id` > `metadata.context_id`
- If the task supports cancellation, the executor's `cancel()` method will be called
- Token usage and partial results are preserved if available
- The response includes `protocol: "a2a"` in the event data

### Streaming Mode

Enable streaming mode to receive real-time progress updates:

```python
# Create message with streaming enabled via metadata
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[data_part],
    metadata={"stream": True}
)

# Send message - will receive multiple updates
async for response in client.send_message(message):
    if isinstance(response, Message):
        # Process streaming updates
        for part in response.parts:
            if part.kind == "data":
                update = part.data
                print(f"Update: {update}")
```

### Task Tree Execution

Execute complex task trees with dependencies:

```python
tasks = [
    {
        "id": "parent-task",
        "name": "Parent Task",
        "user_id": "user123",
        "dependencies": [
            {"id": "child-1", "required": True},
            {"id": "child-2", "required": True}
        ],
        "schemas": {
            "method": "aggregate_results_executor"
        },
        "inputs": {}
    },
    {
        "id": "child-1",
        "name": "Child Task 1",
        "parent_id": "parent-task",
        "user_id": "user123",
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {"resource": "cpu"}
    },
    {
        "id": "child-2",
        "name": "Child Task 2",
        "parent_id": "parent-task",
        "user_id": "user123",
        "dependencies": [{"id": "child-1", "required": True}],
        "schemas": {
            "method": "system_info_executor"
        },
        "inputs": {"resource": "memory"}
    }
]

# Create message with task tree
data_part = DataPart(kind="data", data={"tasks": tasks})
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[data_part]
)

# Execute task tree
async for response in client.send_message(message):
    # Process responses
    pass
```

### Copy Before Execution

The A2A protocol supports copying existing tasks before execution. This is useful for preserving execution history while creating new execution instances.

#### Basic Copy Execution

To copy a task before execution, set `copy_execution=True` in the message metadata:

```python
from a2a.types import Message, DataPart, Role
import uuid

# Create message with copy_execution metadata
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[DataPart(kind="data", data={})],  # Empty tasks array when copying
    metadata={
        "task_id": "existing-task-id",
        "copy_execution": True
    }
)

# Execute copied task
async for response in client.send_message(message):
    if isinstance(response, Message):
        for part in response.parts:
            if part.kind == "data" and isinstance(part.data, dict):
                result = part.data
                print(f"Copied task ID: {result.get('root_task_id')}")
                print(f"Original task ID: {result.get('metadata', {}).get('original_task_id')}")
```

#### Copy with Children

To also copy child tasks and their dependencies:

```python
message = Message(
    message_id=str(uuid.uuid4()),
    role=Role.user,
    parts=[DataPart(kind="data", data={})],
    metadata={
        "task_id": "parent-task-id",
        "copy_execution": True,
        "copy_children": True  # Also copy children
    }
)
```

#### Complete Example

```python
import asyncio
from a2a.client import ClientFactory, ClientConfig
from a2a.types import Message, DataPart, Role, AgentCard
import httpx

async def copy_and_execute_task():
    # Setup A2A client
    httpx_client = httpx.AsyncClient(base_url="http://localhost:8000")
    config = ClientConfig(streaming=True, httpx_client=httpx_client)
    factory = ClientFactory(config=config)
    
    # Get agent card
    card_response = await httpx_client.get("/.well-known/agent-card")
    agent_card = AgentCard(**card_response.json())
    client = factory.create(card=agent_card)
    
    # Copy existing task and execute
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[DataPart(kind="data", data={})],
        metadata={
            "task_id": "my-existing-task-id",
            "copy_execution": True,
            "copy_children": True,
            "stream": True  # Enable streaming
        }
    )
    
    # Process responses
    async for response in client.send_message(message):
        if isinstance(response, Message):
            for part in response.parts:
                if part.kind == "data" and isinstance(part.data, dict):
                    data = part.data
                    if "metadata" in data and "original_task_id" in data["metadata"]:
                        print(f"Original: {data['metadata']['original_task_id']}")
                        print(f"Copied: {data.get('root_task_id')}")
                    print(f"Status: {data.get('status')}, Progress: {data.get('progress')}")
    
    await httpx_client.aclose()

asyncio.run(copy_and_execute_task())
```

**Key Points:**
- `metadata.task_id`: The ID of the existing task to copy
- `metadata.copy_execution`: Set to `True` to enable copy execution
- `metadata.copy_children`: Set to `True` to also copy child tasks (optional)
- The response includes `original_task_id` in metadata for reference
- Original task remains unchanged; a new copy is created and executed

### A2A Protocol Documentation

For detailed information about the A2A Protocol, please refer to the official documentation:

- **A2A Protocol Official Documentation**: [https://www.a2aprotocol.org/en/docs](https://www.a2aprotocol.org/en/docs)
- **A2A Protocol Homepage**: [https://www.a2aprotocol.org](https://www.a2aprotocol.org)

## See Also

- [Task Orchestration Guide](../guides/task-orchestration.md)
- [Custom Tasks Guide](../guides/custom-tasks.md)
- [Architecture Documentation](../architecture/overview.md)
- [HTTP API Reference](./http.md)


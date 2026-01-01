# Extending apflow

> **For end users:** See the [Custom Tasks Guide](../guides/custom-tasks.md) for a step-by-step tutorial on creating your own executors. This document is focused on contributors and advanced extension patterns.

This guide explains how to extend apflow by creating custom executors, extensions, tools, and hooks.

## Overview

apflow is designed to be extensible. You can create:

1. **Custom Executors**: Task execution implementations
2. **Custom Extensions**: Storage, hooks, and other extension types
3. **Custom Tools**: Reusable tools for executors
4. **Custom Hooks**: Pre/post execution hooks
5. **CLI Extensions**: Additional subcommands for the `apflow` CLI

## Creating a Custom Executor

### Method 1: Implement ExecutableTask Directly

For maximum flexibility:

```python
from apflow import ExecutableTask
from typing import Dict, Any

class MyCustomExecutor(ExecutableTask):
    """Custom executor implementation"""
    
    id = "my_custom_executor"
    name = "My Custom Executor"
    description = "Executes custom business logic"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
        # Your execution logic here
        result = {
            "status": "completed",
            "data": inputs.get("data")
        }
        return result
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Define input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Input data"
                }
            },
            "required": ["data"]
        }
    
    async def cancel(self) -> Dict[str, Any]:
        """Optional: Implement cancellation support"""
        return {
            "status": "cancelled",
            "message": "Task cancelled"
        }
```

### Method 2: Inherit from BaseTask

For common functionality:

```python
from apflow import BaseTask
from typing import Dict, Any
from pydantic import BaseModel

# Define input schema using Pydantic
class MyTaskInputs(BaseModel):
    data: str
    count: int = 10

class MyCustomExecutor(BaseTask):
    """Custom executor using BaseTask"""
    
    id = "my_custom_executor"
    name = "My Custom Executor"
    description = "Executes custom business logic"
    
    # Use Pydantic model for input validation
    inputs_schema = MyTaskInputs
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
        # Inputs are automatically validated against inputs_schema
        data = inputs["data"]
        count = inputs["count"]
        
        # Your execution logic
        result = {
            "status": "completed",
            "processed_items": count,
            "data": data
        }
        
        # Check for cancellation (if supported)
        if self.cancellation_checker and self.cancellation_checker():
            return {
                "status": "cancelled",
                "message": "Task was cancelled"
            }
        
        return result
```

### Registering Your Executor

```python
from apflow import executor_register

# Register the executor
executor_register(MyCustomExecutor())

# Or register with custom ID
executor_register(MyCustomExecutor(), executor_id="custom_id")
```

## Creating Custom Extensions

### Extension Categories

Extensions are categorized by `ExtensionCategory`:

- `EXECUTOR`: Task executors (implement `ExecutableTask`)
- `STORAGE`: Storage backends
- `HOOK`: Pre/post execution hooks
- `TOOL`: Reusable tools

### Example: Custom Storage Extension

```python
from apflow.core.extensions.base import Extension
from apflow.core.extensions.types import ExtensionCategory
from apflow.core.extensions.storage import StorageExtension

class MyCustomStorage(StorageExtension):
    """Custom storage implementation"""
    
    id = "my_custom_storage"
    name = "My Custom Storage"
    category = ExtensionCategory.STORAGE
    
    async def save_task(self, task):
        """Save task to storage"""
        # Your storage logic
        pass
    
    async def get_task(self, task_id):
        """Retrieve task from storage"""
        # Your retrieval logic
        pass
```

### Registering Extensions

```python
from apflow import storage_register

storage_register(MyCustomStorage())
```

## Creating Custom Tools

Tools are reusable utilities that can be used by executors:

```python
from apflow.core.tools.base import Tool
from typing import Dict, Any

class MyCustomTool(Tool):
    """Custom tool implementation"""
    
    id = "my_custom_tool"
    name = "My Custom Tool"
    description = "Performs a specific operation"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool"""
        # Tool logic
        return {"result": "tool_output"}
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        }
```

**Registering:**
```python
from apflow import tool_register

tool_register(MyCustomTool())
```

## Creating Custom Hooks

Hooks allow you to modify task behavior before and after execution.

### Pre-Execution Hooks

Modify task inputs before execution:

```python
from apflow import register_pre_hook

@register_pre_hook
async def validate_and_transform(task):
    """Validate and transform task inputs"""
    if task.inputs and "url" in task.inputs:
        url = task.inputs["url"]
        # Ensure URL has protocol
        if not url.startswith(("http://", "https://")):
            task.inputs["url"] = f"https://{url}"
    
    # Add timestamp
    task.inputs["_processed_at"] = datetime.now().isoformat()
```

**Note:** Modifications to `task.inputs` in pre-hooks are automatically detected and persisted to the database. No explicit save required!

### Post-Execution Hooks

Process results after execution:

```python
from apflow import register_post_hook

@register_post_hook
async def log_and_notify(task, inputs, result):
    """Log execution and send notification"""
    logger.info(f"Task {task.id} completed")
    logger.info(f"Inputs: {inputs}")
    logger.info(f"Result: {result}")
    
    # Send notification (example)
    if result.get("status") == "failed":
        send_alert(f"Task {task.id} failed: {result.get('error')}")
```

### Accessing Database in Hooks

Hooks can access the database using the same session as TaskManager:

```python
from apflow import register_pre_hook, get_hook_repository

@register_pre_hook
async def modify_task_fields(task):
    """Modify task fields using hook repository"""
    # Get repository from hook context
    repo = get_hook_repository()
    if not repo:
        return  # Not in hook context
    
    # Modify task fields explicitly
    await repo.update_task_name(task.id, "Modified Name")
    await repo.update_task_priority(task.id, 10)
    
    # Query other tasks
    pending_tasks = await repo.get_tasks_by_status("pending")
    print(f"Found {len(pending_tasks)} pending tasks")
    
    # Modify dependency tasks
    if task.dependencies:
        dep_id = task.dependencies[0]["id"]
        await repo.update_task_priority(dep_id, 100)
```

**Key Points:**
- `get_hook_repository()` returns the same repository instance used by TaskManager
- All hooks in the same execution share the same database session/transaction
- Changes made by one hook are visible to subsequent hooks
- No need to open separate database sessions
- Thread-safe and context-isolated (uses Python's ContextVar)

**Lifecycle and Context:**

Hook database access is managed through a context that spans the entire task tree execution:

1. **Hook Context Lifecycle**: Set at task tree distribution start, cleared in finally block (guaranteed)
2. **Session Lifecycle**: Shared session created at TaskExecutor entry, used by all hooks and tasks
3. **Execution Timeline**: `set_hook_context()` → all hooks execute → `clear_hook_context()` (always)

For detailed lifecycle information, see [Task Tree Execution Lifecycle](../architecture/task-tree-lifecycle.md).

**Available Hook Repository Methods:**
- `update_task_name(task_id, name)` - Update task name
- `update_task_priority(task_id, priority)` - Update task priority
- `update_task_status(task_id, status)` - Update task status
- `update_task_params(task_id, params)` - Update task params
- `update_task_inputs(task_id, inputs)` - Update task inputs (usually not needed, direct modification is auto-saved)
- `get_task_by_id(task_id)` - Query task by ID
- `get_tasks_by_status(status)` - Query tasks by status
- And all other TaskRepository methods...
```

## Using Custom TaskModel

Extend TaskModel to add custom fields:

```python
from apflow.core.storage.sqlalchemy.models import TaskModel
from sqlalchemy import Column, String, Integer
from apflow import set_task_model_class

class ProjectTaskModel(TaskModel):
    """Custom TaskModel with project and department fields"""
    __tablename__ = "apflow_tasks"
    
    project_id = Column(String(255), nullable=True, index=True)
    department = Column(String(100), nullable=True)
    priority_level = Column(Integer, default=2)

# Set custom model (must be called before creating tasks)
set_task_model_class(ProjectTaskModel)

# Now you can use custom fields
task = await task_manager.task_repository.create_task(
    name="my_task",
    user_id="user123",
    project_id="proj-123",  # Custom field
    department="engineering",  # Custom field
    priority_level=1,  # Custom field
    inputs={...}
)
```

## Advanced: Cancellation Support

Implement cancellation for long-running tasks:

```python
class CancellableExecutor(ExecutableTask):
    """Executor with cancellation support"""
    
    id = "cancellable_executor"
    name = "Cancellable Executor"
    description = "Supports cancellation during execution"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with cancellation checks"""
        # TaskManager sets cancellation_checker if executor supports it
        cancellation_checker = getattr(self, 'cancellation_checker', None)
        
        for i in range(100):
            # Check for cancellation
            if cancellation_checker and cancellation_checker():
                return {
                    "status": "cancelled",
                    "message": "Task was cancelled",
                    "progress": i / 100
                }
            
            # Do work
            await asyncio.sleep(0.1)
        
        return {"status": "completed", "progress": 1.0}
    
    async def cancel(self) -> Dict[str, Any]:
        """Handle cancellation request"""
        # Cleanup logic here
        return {
            "status": "cancelled",
            "message": "Cancellation requested"
        }

## Creating CLI Extensions

CLI extensions allow you to register new subcommand groups to the `apflow` CLI. There are two methods:

1. **Decorator-based registration** (recommended for internal extensions)
2. **Entry points registration** (recommended for external packages)

### Method 1: Using `@cli_register` Decorator

The `@cli_register()` decorator provides a clean, declarative way to register CLI extensions:

```python
from apflow.cli import CLIExtension, cli_register

@cli_register(name="users", help="Manage and analyze users")
class UsersCommand(CLIExtension):
    pass

# Add commands to the registered extension
from apflow.cli import get_cli_registry

users_app = get_cli_registry()["users"]

@users_app.command()
def stat():
    """Display user statistics"""
    print("User Statistics: ...")

@users_app.command()
def list():
    """List all users"""
    print("User list...")
```

#### Decorator Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Command name. If not provided, uses class name in lowercase with `_` converted to `-` |
| `help` | `str` | Help text for the command |
| `override` | `bool` | If `True`, allows overriding existing registration (default: `False`) |

#### Auto-naming Examples

```python
@cli_register()  # name will be "users"
class Users(CLIExtension):
    pass

@cli_register()  # name will be "task-manager"
class TaskManager(CLIExtension):
    pass

@cli_register()  # name will be "my-custom-command"
class my_custom_command(CLIExtension):
    pass
```

#### Override Existing Registration

```python
@cli_register(name="users", override=True)
class EnhancedUsersCommand(CLIExtension):
    """Override the existing 'users' command"""
    pass
```

### Method 2: Using Entry Points (External Packages)

For external packages, register your command group under the `apflow.cli_plugins` group in your project's `pyproject.toml`.

#### 1. Create your Command Group

```python
from apflow.cli import CLIExtension

# Create the command group
users_app = CLIExtension(help="Manage and analyze users")

@users_app.command()
def stat():
    """Display user statistics"""
    print("User Statistics: ...")

@users_app.command()
def list():
    """List all users"""
    print("User list...")
```

#### 2. Register in `pyproject.toml`

```toml
[project.entry-points."apflow.cli_plugins"]
users = "your_package.cli:users_app"
```

- The entry point **key** (`users`) will be the name of the subcommand cluster.
- The **value** points to the `CLIExtension` (or `typer.Typer`) instance.

### Usage

After registration (via decorator or entry points), the command will be available:

```bash
apflow users stat
apflow users list
```

### Supported Plugin Types

Both registration methods support two types of plugin objects:
1. **`typer.Typer` (or `CLIExtension`)**: Registered as a **subcommand group** (e.g., `apflow users <cmd>`).
2. **`Callable` (function)**: Registered as a **single command** (e.g., `apflow run-once`).

### CLI Extension API Reference

```python
from apflow.cli import (
    CLIExtension,      # Base class for CLI extensions (inherits from typer.Typer)
    cli_register,      # Decorator for registering CLI extensions
    get_cli_registry,  # Get all registered CLI extensions
)
```

## Advanced: Streaming Support

Send real-time progress updates:

```python
class StreamingExecutor(ExecutableTask):
    """Executor with streaming support"""
    
    id = "streaming_executor"
    name = "Streaming Executor"
    description = "Sends real-time progress updates"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with streaming"""
        # Access event queue (set by TaskManager)
        event_queue = getattr(self, 'event_queue', None)
        
        total_steps = 10
        for step in range(total_steps):
            # Send progress update
            if event_queue:
                await event_queue.put({
                    "type": "progress",
                    "task_id": getattr(self, 'task_id', None),
                    "data": {
                        "step": step + 1,
                        "total": total_steps,
                        "progress": (step + 1) / total_steps
                    }
                })
            
            # Do work
            await asyncio.sleep(0.5)
        
        return {"status": "completed", "steps": total_steps}
```

## Best Practices

### 1. Input Validation

Always validate inputs:

```python
def get_input_schema(self) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "required_field": {
                "type": "string",
                "description": "Required field"
            },
            "optional_field": {
                "type": "integer",
                "description": "Optional field",
                "default": 0
            }
        },
        "required": ["required_field"]
    }
```

### 2. Error Handling

Return structured error responses:

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Your logic
        return {"status": "completed", "result": result}
    except ValueError as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": "validation_error"
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": "execution_error"
        }
```

### 3. Resource Cleanup

Clean up resources properly:

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    resource = None
    try:
        resource = acquire_resource()
        # Use resource
        return {"status": "completed"}
    finally:
        if resource:
            resource.cleanup()
```

### 4. Async Best Practices

Use async/await properly:

```python
# Good: Use async I/O
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
    return {"data": data}

# Avoid: Blocking operations
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Bad: Blocking I/O
    response = requests.get(url)  # Don't do this
    return {"data": response.json()}
```

## Testing Your Extensions

### Unit Testing

```python
import pytest
from apflow import executor_register, TaskManager, create_session

@pytest.fixture
def executor():
    return MyCustomExecutor()

@pytest.fixture
def task_manager():
    executor_register(MyCustomExecutor())
    db = create_session()
    return TaskManager(db)

@pytest.mark.asyncio
async def test_executor_execution(executor, task_manager):
    """Test executor execution"""
    task = await task_manager.task_repository.create_task(
        name="my_custom_executor",
        user_id="test_user",
        inputs={"data": "test"}
    )
    
    from apflow.core.types import TaskTreeNode
    task_tree = TaskTreeNode(task)
    result = await task_manager.distribute_task_tree(task_tree)
    
    assert result["status"] == "completed"
```

## See Also

- [Architecture Documentation](../architecture/architecture.md)
- [Extension Registry Design](../architecture/extension-registry-design.md)
- [Examples](../examples/basic_task.md)
- [Development Guide](development.md)


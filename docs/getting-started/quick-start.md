# Quick Start Guide

> Get started with apflow in 10 minutes. This guide walks you through running tasks, writing custom executors, and setting up task dependencies.

**Prerequisites:**

- Python 3.10+ (3.12+ recommended)
- Basic command-line and Python knowledge

## Step 0: Install

The `standard` extra is recommended for the full experience (CLI, API server, PostgreSQL support):

```bash
pip install apflow[standard]
```

Alternatively, install the minimal core only:

```bash
pip install apflow
```

> **Need more options?** See the [Installation Guide](installation.md) for extras like CrewAI, SSH, and A2A Protocol support.

## Step 1: Run a Built-in Task via CLI

The fastest way to try apflow is through the CLI with a built-in executor. No Python code needed.

```bash
apflow run flow system_info_executor --inputs '{"resource": "cpu"}'
```

**Expected output:**

```json
{
  "status": "completed",
  "progress": 1.0,
  "root_task_id": "abc-123-def-456",
  "task_count": 1,
  "result": {
    "system": "Darwin",
    "cores": 8,
    "cpu_count": 8
  }
}
```

Try different resource types:

```bash
apflow run flow system_info_executor --inputs '{"resource": "memory"}'
apflow run flow system_info_executor --inputs '{"resource": "disk"}'
apflow run flow system_info_executor --inputs '{"resource": "all"}'
```

**What happened:**

1. The CLI parsed the command and identified the executor (`system_info_executor`)
2. A task was created in the database automatically
3. The executor ran and collected system information
4. The result was returned as JSON

## Step 2: Run a Task via Python

For programmatic usage, the `TaskBuilder` API provides a fluent interface for creating and executing tasks.

```python
import asyncio
from apflow.core.builders import TaskBuilder
from apflow import TaskManager, create_session

async def main() -> None:
    db = create_session()
    task_manager = TaskManager(db)

    result = await (
        TaskBuilder(task_manager, "system_info_executor")
        .with_name("get_cpu_info")
        .with_input("resource", "cpu")
        .execute()
    )
    print(result)

asyncio.run(main())
```

**Key points:**

- `create_session()` returns a database session (DuckDB by default, no setup needed)
- `TaskBuilder(task_manager, executor_id)` starts the builder chain
- `.with_name()` sets the task name, `.with_input()` adds input parameters
- `.execute()` builds the task, runs it, and returns the result

## Step 3: Create a Custom Executor

Create a file `greeting_executor.py` with your own executor:

```python
from typing import Dict, Any

from apflow.core.base import BaseTask
from apflow import executor_register


@executor_register()
class GreetingTask(BaseTask):
    """A simple task that creates personalized greetings."""

    id = "greeting"
    name = "Greeting Task"
    description = "Says hello in multiple languages"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        name = inputs.get("name", "World")
        language = inputs.get("language", "en")

        greetings = {
            "en": f"Hello, {name}!",
            "es": f"Hola, {name}!",
            "fr": f"Bonjour, {name}!",
        }

        message = greetings.get(language, greetings["en"])
        return {"message": message, "language": language}
```

**How it works:**

- `@executor_register()` automatically registers the executor when the module is imported
- `BaseTask` provides the base interface; you only need to implement `execute()`
- `id` is the unique identifier used to reference this executor

**Run it via Python:**

```python
import asyncio
from apflow.core.builders import TaskBuilder
from apflow import TaskManager, create_session

# Import to register the executor
from greeting_executor import GreetingTask  # noqa: F401

async def main() -> None:
    db = create_session()
    task_manager = TaskManager(db)

    result = await (
        TaskBuilder(task_manager, "greeting")
        .with_name("greet_alice")
        .with_input("name", "Alice")
        .with_input("language", "fr")
        .execute()
    )
    print(result["result"])  # {"message": "Bonjour, Alice!", "language": "fr"}

asyncio.run(main())
```

**Run it via CLI** (after importing the executor):

```bash
apflow run flow greeting --inputs '{"name": "Alice", "language": "fr"}'
```

> **Note:** Custom executors must be imported before use. Built-in executors are loaded automatically.

## Step 4: Task Dependencies

Use `.depends_on()` to chain tasks so one waits for another to finish:

```python
import asyncio
from apflow.core.builders import TaskBuilder
from apflow import TaskManager, create_session


async def main() -> None:
    db = create_session()
    task_manager = TaskManager(db)

    # Step 1: Build the first task (CPU info)
    cpu_task = await (
        TaskBuilder(task_manager, "system_info_executor")
        .with_name("get_cpu_info")
        .with_input("resource", "cpu")
        .build()
    )

    # Step 2: Build a dependent task (memory info, runs after CPU task)
    result = await (
        TaskBuilder(task_manager, "system_info_executor")
        .with_name("get_memory_info")
        .with_input("resource", "memory")
        .depends_on(cpu_task.task.id)
        .execute()
    )
    print(result)

asyncio.run(main())
```

**Key points:**

- `.build()` creates the task in the database and returns a `TaskTreeNode` without executing it
- `.depends_on(*task_ids)` declares that this task must wait for the specified tasks to complete
- `.execute()` builds and runs the task, respecting all declared dependencies

## Step 5: Start the API Server

apflow includes an A2A Protocol-compatible API server for remote task execution:

```bash
apflow serve --port 8000
```

Execute a task via HTTP:

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.execute",
    "params": {
      "tasks": [
        {
          "id": "task1",
          "name": "Get CPU Info",
          "user_id": "user123",
          "schemas": {"method": "system_info_executor"},
          "inputs": {"resource": "cpu"},
          "status": "pending"
        }
      ]
    },
    "id": "request-123"
  }'
```

Check task counts:

```bash
apflow tasks count
```

## Scale to a Distributed Cluster

When you need to scale beyond a single machine, apflow supports distributed cluster mode. Your task code stays the same -- only the runtime configuration changes.

```bash
# Set PostgreSQL as the shared database
export APFLOW_DATABASE_URL="postgresql+asyncpg://user:password@localhost/apflow"

# Start the API server (each node runs this)
apflow serve --port 8000
```

Multiple nodes share the same database and coordinate task execution automatically.

See the [Distributed Cluster Guide](../guides/distributed-cluster.md) for full setup instructions.

## Next Steps

- **[Core Concepts](concepts.md)** -- Understand tasks, executors, and the orchestration model
- **[Task Orchestration Guide](../guides/task-orchestration.md)** -- Master task trees and complex workflows
- **[Executor Selection Guide](../guides/executor-selection.md)** -- Choose the right executor for your use case
- **[Distributed Cluster Guide](../guides/distributed-cluster.md)** -- Deploy across multiple nodes
- **[Custom Tasks Guide](../guides/custom-tasks.md)** -- Build advanced executors with schemas and hooks

## Troubleshooting

### Executor not found

**Error:** `Executor 'my_executor' is not registered as an executor`

**Causes and fixes:**

- For built-in executors, verify the executor ID is correct (e.g., `system_info_executor`, not `system_info`).
- For custom executors, ensure the module is imported before use and the `@executor_register()` decorator is applied.
- The `schemas.method` field in API requests must match the executor `id` exactly.

### CLI command not found

**Error:** `command not found: apflow`

```bash
# Install with CLI support
pip install apflow[cli]

# Or install the standard bundle
pip install apflow[standard]

# Verify
apflow --version
```

### Task stays in "pending" status

- Check that dependency tasks have completed successfully.
- Verify the executor is registered (see "Executor not found" above).
- Inspect task details:

```bash
apflow tasks get <task_id>
```

### API server won't start

```bash
# Try a different port
apflow serve --port 8080

# Check if the default port is in use
lsof -i :8000
```

### Database connection error

By default, apflow uses DuckDB with no setup required. The database file is created automatically.

For PostgreSQL, set the connection string:

```bash
export APFLOW_DATABASE_URL="postgresql+asyncpg://user:password@localhost/apflow"
```

### Import error

**Error:** `ModuleNotFoundError: No module named 'apflow'`

```bash
pip install apflow

# Or with all features
pip install apflow[standard]
```

---

**Ready for more?** Continue to [Core Concepts](concepts.md) or explore the [Task Orchestration Guide](../guides/task-orchestration.md).

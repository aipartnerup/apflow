# Hello World - 5-Minute Quick Start

Get started with apflow in under 5 minutes with this minimal example.

## Installation

```bash
pip install apflow
```

## Your First Task (Python)

Create a file `hello.py`:

```python
from apflow import executor_register, TaskBuilder, execute_tasks
from apflow.extensions import BaseTask

# Define a simple executor
@executor_register()
class HelloWorld(BaseTask):
    id = "hello_world"

    async def execute(self, inputs: dict) -> dict:
        name = inputs.get("name", "World")
        return {"message": f"Hello, {name}!"}

# Create and execute a task
if __name__ == "__main__":
    task = TaskBuilder("greet_alice", "hello_world")\
        .with_inputs({"name": "Alice"})\
        .build()

    result = execute_tasks([task])
    print(result["message"])  # Output: Hello, Alice!
```

Run it:

```bash
python hello.py
```

**Output:**
```
Hello, Alice!
```

That's it! You've created and executed your first apflow task.

---

## Using the CLI

You can also use apflow via CLI without writing code:

### 1. Create a task module

`tasks.py`:
```python
from apflow import executor_register
from apflow.extensions import BaseTask

@executor_register()
class Greeter(BaseTask):
    id = "greeter"

    async def execute(self, inputs: dict) -> dict:
        return {"message": f"Hello, {inputs['name']}!"}
```

### 2. Execute via CLI

```bash
# Make sure tasks.py is imported (in same directory or PYTHONPATH)
apflow run greeter --inputs '{"name": "Bob"}'
```

**Output:**
```json
{
  "message": "Hello, Bob!"
}
```

---

## What's Happening?

1. **@executor_register()** - Registers your task executor with apflow
2. **BaseTask** - Base class providing the `execute()` interface
3. **TaskBuilder** - Fluent API for creating tasks
4. **execute_tasks()** - Executes one or more tasks and returns results

---

## Built-in Executors

Don't want to write custom code? Use built-in executors:

### REST API Call

```python
from apflow import TaskBuilder, execute_tasks

task = TaskBuilder("fetch_data", "rest_executor")\
    .with_inputs({
        "url": "https://api.github.com/users/octocat",
        "method": "GET"
    })\
    .build()

result = execute_tasks([task])
print(result["json"]["login"])  # Output: octocat
```

### Execute SSH Command

```bash
pip install apflow[ssh]
```

```python
task = TaskBuilder("check_disk", "ssh_executor")\
    .with_inputs({
        "host": "example.com",
        "username": "admin",
        "key_file": "~/.ssh/id_rsa",
        "command": "df -h"
    })\
    .build()

result = execute_tasks([task])
print(result["stdout"])
```

---

## Task Dependencies

Create workflows with dependencies:

```python
from apflow import TaskBuilder, execute_tasks

# Task 1: Fetch user data
fetch_task = TaskBuilder("fetch_user", "rest_executor")\
    .with_inputs({
        "url": "https://api.example.com/user",
        "method": "GET"
    })\
    .build()

# Task 2: Process data (depends on Task 1)
process_task = TaskBuilder("process_data", "my_processor")\
    .with_inputs({"user_id": "123"})\
    .with_dependencies([fetch_task.id])\
    .build()

# Execute: fetch_task runs first, then process_task
results = execute_tasks([fetch_task, process_task])
```

---

## Next Steps

- **[Executor Selection Guide](../guides/executor-selection.md)** - Choose the right executor for your use case
- **[Complete Quick Start](quick-start.md)** - Comprehensive tutorial with all features
- **[Task Dependencies](../guides/task-dependencies.md)** - Learn about complex workflows

## Common Questions

### Where is my data stored?

By default, apflow uses DuckDB (embedded database) stored at `.data/apflow.duckdb` in your project directory.

### How do I see task status?

```bash
# List all tasks
apflow monitor status --all

# Watch a specific task
apflow monitor watch <task-id>
```

### Can I use PostgreSQL instead of DuckDB?

Yes! Set the database URL:

```bash
export APFLOW_DATABASE_URL="postgresql://user:pass@localhost/apflow"
apflow db migrate  # Run migrations
```

### How do I deploy to production?

For production deployments, see:
- **[Production Deployment](../deployment/production.md)**
- **[Distributed Mode](../distributed/overview.md)** (multi-node orchestration)

---

## Get Help

- **Documentation**: [https://docs.apflow.dev](https://github.com/aipartnerup/apflow/tree/main/docs)
- **GitHub Issues**: [Report bugs or request features](https://github.com/aipartnerup/apflow/issues)
- **CLI Help**: `apflow --help`

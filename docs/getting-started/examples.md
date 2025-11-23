# Examples

This page contains examples and use cases for aipartnerupflow.

## Quick Start with Example Tasks

The easiest way to get started is to use the built-in example tasks. These demonstrate various features like task trees, dependencies, priorities, and different statuses.

### Initialize Example Tasks

```bash
# Initialize example tasks in the database
aipartnerupflow examples init

# Force re-initialization (even if examples already exist)
aipartnerupflow examples init --force
```

**What gets created:**
- Tasks with different statuses (completed, failed, pending, in_progress)
- Task trees with parent-child relationships
- Tasks with different priorities
- Tasks with dependencies
- CrewAI task example (requires LLM key)

**Auto-initialization:**
When the API server starts, it automatically initializes example tasks if the database is empty. This helps beginners get started quickly.

### View Example Tasks

After initialization, you can view the example tasks:

```bash
# List all tasks
aipartnerupflow tasks list

# Check specific task status
aipartnerupflow tasks status example_root_001

# View task tree
aipartnerupflow tasks tree example_root_001
```

### Execute Example Tasks

Example tasks are created in `pending` status, ready to be executed:

```bash
# Execute via CLI
aipartnerupflow run flow --tasks '[{"id": "example_root_001", ...}]'

# Or execute via API
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.create",
    "params": {
      "tasks": [{"id": "example_root_001", ...}]
    }
  }'
```

**Note:** For CrewAI example tasks, you'll need to provide an LLM API key:

```bash
# Via request header
curl -X POST http://localhost:8000/tasks \
  -H "X-LLM-API-KEY: openai:sk-your-key" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

## Example Task Structure

The example tasks demonstrate:

1. **System Analysis Project** - A task tree with parent-child relationships:
   - Root task: System Analysis Project
   - Child tasks: CPU Analysis, Memory Analysis
   - Dependent task: Disk Analysis (depends on CPU and Memory)

2. **CrewAI Research Task** - Demonstrates CrewAI integration (requires LLM key)

3. **Multi-Level Analysis** - A deeper task tree with multiple levels

4. **Various Statuses** - Tasks in different states (pending, in_progress, etc.)

## Basic Examples

Examples are also available in the test cases:

- Integration tests: `tests/integration/`
- Extension tests: `tests/extensions/`

## Example: Custom Task

```python
from aipartnerupflow import ExecutableTask
from typing import Dict, Any

class MyCustomTask(ExecutableTask):
    id = "my_custom_task"
    name = "My Custom Task"
    description = "A custom task example"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Your task logic here
        return {"result": "success"}
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input_field": {"type": "string"}
            }
        }
```

## Example: Task Tree

```python
from aipartnerupflow import TaskManager, TaskTreeNode, create_session

db = create_session()
task_manager = TaskManager(db)

# Create tasks
root = await task_manager.task_repository.create_task(
    name="root",
    user_id="user_123"
)

child1 = await task_manager.task_repository.create_task(
    name="child1",
    user_id="user_123",
    parent_id=root.id
)

child2 = await task_manager.task_repository.create_task(
    name="child2",
    user_id="user_123",
    parent_id=root.id,
    dependencies=[child1.id]  # child2 depends on child1
)

# Build and execute
tree = TaskTreeNode(root)
tree.add_child(TaskTreeNode(child1))
tree.add_child(TaskTreeNode(child2))

result = await task_manager.distribute_task_tree(tree)
```

## Example: CrewAI Task with LLM Key

```python
# Via API with header
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/tasks",
        headers={
            "Content-Type": "application/json",
            "X-LLM-API-KEY": "openai:sk-your-key"  # Provider-specific format
        },
        json={
            "jsonrpc": "2.0",
            "method": "tasks.create",
            "params": {
                "tasks": [{
                    "id": "crewai-task",
                    "name": "CrewAI Research Task",
                    "user_id": "user123",
                    "schemas": {"method": "crewai_executor"},
                    "params": {
                        "works": {
                            "agents": {
                                "researcher": {
                                    "role": "Research Analyst",
                                    "goal": "Research and analyze the given topic",
                                    "llm": "openai/gpt-4"
                                }
                            },
                            "tasks": {
                                "research": {
                                    "description": "Research the topic: {topic}",
                                    "agent": "researcher"
                                }
                            }
                        }
                    },
                    "inputs": {
                        "topic": "Artificial Intelligence"
                    }
                }]
            }
        }
    )
```

For more examples, see the test cases in the main repository.


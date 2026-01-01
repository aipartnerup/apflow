# Real-World Examples

> **See also:**
> - [Basic Task Examples](basic_task.md) for simple, copy-paste patterns
> - [Task Tree Examples](task-tree.md) for dependency and execution order patterns

Complete, runnable examples for common real-world use cases. These examples demonstrate how to use apflow in production scenarios.

## Table of Contents

1. [Data Processing Pipeline](#data-processing-pipeline)
2. [API Integration Workflow](#api-integration-workflow)
3. [Batch Processing with Dependencies](#batch-processing-with-dependencies)
4. [Error Handling and Retry](#error-handling-and-retry)
5. [Multi-Step Workflow](#multi-step-workflow)

## Data Processing Pipeline

### Scenario

Process data from multiple sources, transform it, and save results.

### Complete Example

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Step 1: Fetch data from multiple sources
    fetch_api = await task_manager.task_repository.create_task(
        name="rest_executor",  # Use built-in REST executor
        user_id="user123",
        priority=1,
        inputs={
            "url": "https://api.example.com/data",
            "method": "GET"
        }
    )
    
    fetch_db = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        priority=1,
        inputs={
            "command": "psql -c 'SELECT * FROM users LIMIT 100'"
        }
    )
    
    # Step 2: Process data (depends on both fetches)
    process_task = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        parent_id=fetch_api.id,
        dependencies=[
            {"id": fetch_api.id, "required": True},
            {"id": fetch_db.id, "required": True}
        ],
        priority=2,
        inputs={
            "command": "python process_data.py"
        }
    )
    
    # Step 3: Save results
    save_task = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        parent_id=fetch_api.id,
        dependencies=[{"id": process_task.id, "required": True}],
        priority=3,
        inputs={
            "command": "python save_results.py"
        }
    )
    
    # Build tree
    root = TaskTreeNode(fetch_api)
    root.add_child(TaskTreeNode(fetch_db))
    root.add_child(TaskTreeNode(process_task))
    root.add_child(TaskTreeNode(save_task))
    
    # Execute
    await task_manager.distribute_task_tree(root)
    
    # Check results
    final_result = await task_manager.task_repository.get_task_by_id(save_task.id)
    print(f"Pipeline completed: {final_result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Execution Flow

```
Fetch API ──┐
            ├──→ Process ──→ Save
Fetch DB ───┘
```

## API Integration Workflow

### Scenario

Call multiple APIs, aggregate results, and send notifications.

### Complete Example

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Call multiple APIs in parallel
    api1 = await task_manager.task_repository.create_task(
        name="http_request_executor",
        user_id="user123",
        priority=1,
        inputs={
            "url": "https://api.service1.com/data",
            "method": "GET"
        }
    )
    
    api2 = await task_manager.task_repository.create_task(
        name="http_request_executor",
        user_id="user123",
        priority=1,
        inputs={
            "url": "https://api.service2.com/data",
            "method": "GET"
        }
    )
    
    api3 = await task_manager.task_repository.create_task(
        name="http_request_executor",
        user_id="user123",
        priority=1,
        inputs={
            "url": "https://api.service3.com/data",
            "method": "GET"
        }
    )
    
    # Aggregate results
    aggregate = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        parent_id=api1.id,
        dependencies=[
            {"id": api1.id, "required": True},
            {"id": api2.id, "required": True},
            {"id": api3.id, "required": True}
        ],
        priority=2,
        inputs={
            "command": "python aggregate.py"
        }
    )
    
    # Send notification
    notify = await task_manager.task_repository.create_task(
        name="http_request_executor",
        user_id="user123",
        parent_id=api1.id,
        dependencies=[{"id": aggregate.id, "required": True}],
        priority=3,
        inputs={
            "url": "https://api.notification.com/send",
            "method": "POST",
            "body": {"message": "Processing complete"}
        }
    )
    
    # Build tree
    root = TaskTreeNode(api1)
    root.add_child(TaskTreeNode(api2))
    root.add_child(TaskTreeNode(api3))
    root.add_child(TaskTreeNode(aggregate))
    root.add_child(TaskTreeNode(notify))
    
    # Execute
    await task_manager.distribute_task_tree(root)
    
    print("API integration workflow completed!")

if __name__ == "__main__":
    asyncio.run(main())
```

### Execution Flow

```
API 1 ──┐
API 2 ──├──→ Aggregate ──→ Notify
API 3 ──┘
```

## Batch Processing with Dependencies

### Scenario

Process a batch of items where each item depends on the previous one.

### Complete Example

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create batch of items
    items = ["item1", "item2", "item3", "item4", "item5"]
    tasks = []
    
    # Create first task (no dependencies)
    first_task = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        priority=1,
        inputs={"command": f"process {items[0]}"}
    )
    tasks.append(first_task)
    
    # Create remaining tasks (each depends on previous)
    for i in range(1, len(items)):
        task = await task_manager.task_repository.create_task(
            name="command_executor",
            user_id="user123",
            parent_id=first_task.id,
            dependencies=[{"id": tasks[i-1].id, "required": True}],
            priority=1 + i,
            inputs={"command": f"process {items[i]}"}
        )
        tasks.append(task)
    
    # Build sequential chain
    root = TaskTreeNode(tasks[0])
    for i in range(1, len(tasks)):
        root.add_child(TaskTreeNode(tasks[i]))
    
    # Execute
    await task_manager.distribute_task_tree(root)
    
    # Check final task
    final_result = await task_manager.task_repository.get_task_by_id(tasks[-1].id)
    print(f"Batch processing completed: {final_result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Execution Flow

```
Item1 → Item2 → Item3 → Item4 → Item5
```

## Error Handling and Retry

### Scenario

Handle failures gracefully with fallback tasks.

### Complete Example

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Primary task (may fail)
    primary = await task_manager.task_repository.create_task(
        name="http_request_executor",
        user_id="user123",
        priority=1,
        inputs={
            "url": "https://unreliable-api.com/data",
            "method": "GET"
        }
    )
    
    # Fallback task (runs even if primary fails)
    fallback = await task_manager.task_repository.create_task(
        name="http_request_executor",
        user_id="user123",
        parent_id=primary.id,
        dependencies=[{"id": primary.id, "required": False}],  # Optional dependency
        priority=2,
        inputs={
            "url": "https://backup-api.com/data",
            "method": "GET"
        }
    )
    
    # Final task (works with either primary or fallback)
    final = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        parent_id=primary.id,
        dependencies=[
            {"id": primary.id, "required": False},  # Optional
            {"id": fallback.id, "required": False}  # Optional
        ],
        priority=3,
        inputs={"command": "python process_result.py"}
    )
    
    # Build tree
    root = TaskTreeNode(primary)
    root.add_child(TaskTreeNode(fallback))
    root.add_child(TaskTreeNode(final))
    
    # Execute
    await task_manager.distribute_task_tree(root)
    
    # Check results
    primary_result = await task_manager.task_repository.get_task_by_id(primary.id)
    fallback_result = await task_manager.task_repository.get_task_by_id(fallback.id)
    final_result = await task_manager.task_repository.get_task_by_id(final.id)
    
    print(f"Primary: {primary_result.status}")
    print(f"Fallback: {fallback_result.status}")
    print(f"Final: {final_result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Execution Flow

```
Primary ──┐
          ├──→ Final (works with either)
Fallback ─┘
```

## Multi-Step Workflow

### Scenario

Complex workflow with multiple stages and parallel processing.

### Complete Example

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Stage 1: Data Collection (parallel)
    collect1 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="user123",
        priority=1,
        inputs={"resource": "cpu"}
    )
    
    collect2 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="user123",
        priority=1,
        inputs={"resource": "memory"}
    )
    
    collect3 = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="user123",
        priority=1,
        inputs={"resource": "disk"}
    )
    
    # Stage 2: Processing (depends on collection)
    process1 = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        parent_id=collect1.id,
        dependencies=[{"id": collect1.id, "required": True}],
        priority=2,
        inputs={"command": "python process_cpu.py"}
    )
    
    process2 = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        parent_id=collect2.id,
        dependencies=[{"id": collect2.id, "required": True}],
        priority=2,
        inputs={"command": "python process_memory.py"}
    )
    
    process3 = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        parent_id=collect3.id,
        dependencies=[{"id": collect3.id, "required": True}],
        priority=2,
        inputs={"command": "python process_disk.py"}
    )
    
    # Stage 3: Aggregation (depends on all processing)
    aggregate = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        parent_id=collect1.id,
        dependencies=[
            {"id": process1.id, "required": True},
            {"id": process2.id, "required": True},
            {"id": process3.id, "required": True}
        ],
        priority=3,
        inputs={"command": "python aggregate.py"}
    )
    
    # Stage 4: Finalization (depends on aggregation)
    finalize = await task_manager.task_repository.create_task(
        name="command_executor",
        user_id="user123",
        parent_id=collect1.id,
        dependencies=[{"id": aggregate.id, "required": True}],
        priority=4,
        inputs={"command": "python finalize.py"}
    )
    
    # Build tree
    root = TaskTreeNode(collect1)
    root.add_child(TaskTreeNode(collect2))
    root.add_child(TaskTreeNode(collect3))
    root.add_child(TaskTreeNode(process1))
    root.add_child(TaskTreeNode(process2))
    root.add_child(TaskTreeNode(process3))
    root.add_child(TaskTreeNode(aggregate))
    root.add_child(TaskTreeNode(finalize))
    
    # Execute
    await task_manager.distribute_task_tree(root)
    
    # Check final result
    final_result = await task_manager.task_repository.get_task_by_id(finalize.id)
    print(f"Multi-step workflow completed: {final_result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Execution Flow

```
Collect1 ──→ Process1 ──┐
Collect2 ──→ Process2 ──├──→ Aggregate ──→ Finalize
Collect3 ──→ Process3 ──┘
```

## Best Practices

### 1. Use Meaningful Task Names

```python
# Good
name="fetch_user_data"
name="process_payment"
name="send_notification"

# Bad
name="task1"
name="task2"
```

### 2. Set Appropriate Priorities

```python
# Critical tasks first
priority=0  # Highest priority

# Normal tasks
priority=2  # Default

# Background tasks
priority=3  # Lower priority
```

### 3. Handle Errors Gracefully

```python
# Use optional dependencies for fallbacks
dependencies=[{"id": primary.id, "required": False}]
```

### 4. Keep Trees Manageable

- 3-5 levels deep
- 10-20 tasks per tree
- Use sub-trees for complex workflows

### 5. Monitor Task Status

```python
# Check task status after execution
task = await task_manager.task_repository.get_task_by_id(task_id)
if task.status == "failed":
    print(f"Error: {task.error}")
```

## Next Steps

- **[Task Orchestration Guide](../guides/task-orchestration.md)** - Learn more about orchestration patterns
- **[Best Practices](../guides/best-practices.md)** - Design patterns and optimization
- **[Custom Tasks](../guides/custom-tasks.md)** - Create your own executors


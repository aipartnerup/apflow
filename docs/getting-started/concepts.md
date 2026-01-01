# Core Concepts

Understanding these core concepts will help you use apflow effectively. Don't worry - we'll explain everything in simple terms!

## Why These Concepts Matter

Before diving into the technical details, let's understand why these concepts exist and what problems they solve:

**The Problem**: When building applications, you often need to coordinate multiple operations that depend on each other. For example:
- Fetch data from an API, then process it, then save it
- Run multiple tasks in parallel, but wait for all to complete before proceeding
- Handle failures gracefully and retry automatically
- Track progress and state across long-running operations

**Without a framework**, you'd write custom code to:
- Manually coordinate task execution order
- Handle dependencies and wait conditions
- Implement retry logic and error recovery
- Track state and progress
- Manage different execution methods (HTTP, SSH, Docker, etc.)

**With apflow**, these concepts provide a unified way to solve all these problems. The framework handles the complexity, so you can focus on your business logic.

Now let's learn the core concepts that make this possible!

## What is a Task?

A **task** is a unit of work that needs to be executed. Think of it like a function call, but with additional features like status tracking, dependencies, and persistence.

### Real-World Analogy

Imagine you're cooking dinner:
- **Task**: "Cook pasta"
- **Inputs**: Pasta, water, salt
- **Result**: Cooked pasta
- **Status**: pending → in_progress → completed

### In Code

```python
task = await task_repository.create_task(
    name="cook_pasta",           # What to do
    inputs={"pasta": "spaghetti", "water": "2L"},  # What you need
    user_id="chef123"            # Who's doing it
)
```

## What is Task Orchestration?

**Task orchestration** is the process of managing multiple tasks - deciding when they run, in what order, and how they relate to each other.

### Real-World Analogy

Think of a restaurant kitchen:
- The **chef** (TaskManager) coordinates everything
- Some dishes must be prepared in order (dependencies)
- Some can be prepared simultaneously (parallel tasks)
- The chef ensures everything is ready at the right time

### Why It Matters

Without orchestration, you'd have to manually manage:
- ✅ Which tasks to run
- ✅ When to run them
- ✅ What happens if one fails
- ✅ How to track progress

With apflow, the **TaskManager** handles all of this automatically!

## What is a Task Tree?

A **task tree** is a hierarchical structure that organizes related tasks. It's like a family tree for your tasks.

### Visual Example

```mermaid
flowchart TD
    Root["Root Task: Prepare Dinner"] --> Task1["Task 1: Buy Ingredients"]
    Root --> Task2["Task 2: Cook Main Course"]
    Root --> Task3["Task 3: Set Table"]
    
    Task1 --> Task11["Task 1.1: Go to Store"]
    Task2 --> Task21["Task 2.1: Cook Pasta"]
    Task2 --> Task22["Task 2.2: Make Sauce"]
    
    style Root fill:#e1f5ff
    style Task1 fill:#fff4e1
    style Task2 fill:#fff4e1
    style Task3 fill:#fff4e1
    style Task11 fill:#e8f5e9
    style Task21 fill:#e8f5e9
    style Task22 fill:#e8f5e9
```

### Key Points

- **Parent-Child Relationship**: Used for organization only (like folders)
- **Dependencies**: Control execution order (Task 2 waits for Task 1)
- **Root Task**: The top-level task that contains everything

### In Code

```python
# Create root task
root = await task_repository.create_task(name="prepare_dinner", ...)

# Create child tasks
buy_ingredients = await task_repository.create_task(
    name="buy_ingredients",
    parent_id=root.id,  # Child of root
    ...
)

# Build tree
tree = TaskTreeNode(root)
tree.add_child(TaskTreeNode(buy_ingredients))
```

## What are Dependencies?

**Dependencies** define relationships between tasks. A task with dependencies will wait for those tasks to complete before executing.

### Real-World Analogy

You can't serve dinner until:
1. ✅ Ingredients are bought (Task 1)
2. ✅ Food is cooked (Task 2)
3. ✅ Table is set (Task 3)

Task 4 (Serve Dinner) **depends on** Tasks 1, 2, and 3.

### Visual Example

```mermaid
sequenceDiagram
    participant TaskA as Task A: Fetch Data
    participant TaskB as Task B: Process Data
    participant TaskC as Task C: Save Results
    
    Note over TaskA: No dependencies<br/>Executes first
    TaskA->>TaskA: Execute
    TaskA-->>TaskB: Result available
    
    Note over TaskB: Depends on Task A<br/>Waits for completion
    TaskB->>TaskB: Execute (with Task A result)
    TaskB-->>TaskC: Result available
    
    Note over TaskC: Depends on Task B<br/>Waits for completion
    TaskC->>TaskC: Execute (with Task B result)
    TaskC-->>TaskC: Complete
```

**Execution Order**: A → B → C (automatic!)

### In Code

```python
# Task B depends on Task A
task_b = await task_repository.create_task(
    name="process_data",
    dependencies=[
        {"id": task_a.id, "required": True}  # Must wait for A
    ],
    ...
)
```

### Important Distinction

- **Parent-Child**: Organizational (like folders) - doesn't affect execution
- **Dependencies**: Execution control - determines when tasks run

```python
# Task B is a child of Task A (organization)
# But Task B depends on Task C (execution order)
task_b = await task_repository.create_task(
    parent_id=task_a.id,  # Organizational: B is child of A
    dependencies=[{"id": task_c.id}],  # Execution: B waits for C
    ...
)
```

## What are Executors?

An **executor** is the code that actually runs a task. It's like a worker that knows how to do a specific job.

### Types of Executors

1. **Built-in Executors**: Provided by apflow
   - **Core Executors** (always available):
     - `system_info_executor`: Get system information
     - `command_executor`: Run shell commands
     - `aggregate_results_executor`: Aggregate dependency results
   - **Remote Execution Executors**:
     - `rest_executor`: HTTP/REST API calls (requires `[http]`)
     - `ssh_executor`: Remote command execution via SSH (requires `[ssh]`)
     - `grpc_executor`: gRPC service calls (requires `[grpc]`)
     - `websocket_executor`: Bidirectional WebSocket communication
     - `apflow_api_executor`: Call other apflow API instances
     - `mcp_executor`: Model Context Protocol executor (stdio mode: no dependencies, HTTP mode: requires `[a2a]`)
   - **Protocol Servers**:
     - `a2a`: A2A Protocol Server (default)
     - `mcp`: MCP (Model Context Protocol) Server - exposes task orchestration as MCP tools and resources
   - **Container Executors**:
     - `docker_executor`: Containerized command execution (requires `[docker]`)
   - **AI Executors** (optional):
     - `crewai_executor`: LLM-based agents (requires `[crewai]`)
     - `batch_crewai_executor`: Batch execution of multiple crews (requires `[crewai]`)
   - **Generation Executors**:
     - `generate_executor`: Generate task tree JSON arrays from natural language requirements using LLM (requires `openai` or `anthropic` package)

2. **Custom Executors**: You create these
   - API calls
   - Data processing
   - File operations
   - Anything you need!

### Real-World Analogy

Think of executors as specialized workers:
- **Plumber** (executor) knows how to fix pipes (task type)
- **Electrician** (executor) knows how to fix wiring (task type)
- Each worker (executor) has specific skills (code)

### In Code

```python
from apflow import BaseTask, executor_register

@executor_register()
class MyCustomExecutor(BaseTask):
    """My custom task executor"""
    
    id = "my_custom_executor"
    name = "My Custom Executor"
    
    async def execute(self, inputs):
        # Your task logic here
        return {"result": "done"}
```

## What is TaskManager?

**TaskManager** is the orchestrator - it manages task execution, dependencies, and priorities. You don't need to worry about the details; it handles everything automatically.

### What TaskManager Does

1. **Checks Dependencies**: Ensures tasks wait for their dependencies
2. **Schedules Execution**: Runs tasks in the right order
3. **Handles Failures**: Manages errors and retries
4. **Tracks Progress**: Monitors task status
5. **Manages Priorities**: Executes high-priority tasks first

### TaskManager Workflow

The following diagram shows how TaskManager orchestrates task execution:

```mermaid
flowchart TD
    Start([Task Tree Received]) --> LoadTasks[Load All Tasks]
    LoadTasks --> CheckDeps[Check Dependencies for Each Task]
    CheckDeps --> ReadyTasks{Any Tasks<br/>Ready?}
    
    ReadyTasks -->|No| Wait[Wait for Dependencies]
    Wait --> CheckDeps
    
    ReadyTasks -->|Yes| SortPriority[Sort by Priority]
    SortPriority --> Execute[Execute Highest Priority Task]
    
    Execute --> UpdateStatus[Update Status: in_progress]
    UpdateStatus --> RunExecutor[Run Executor]
    RunExecutor --> Success{Success?}
    
    Success -->|Yes| Complete[Update Status: completed]
    Success -->|No| Failed[Update Status: failed]
    
    Complete --> CheckDependents[Check Dependent Tasks]
    Failed --> CheckDependents
    
    CheckDependents --> MoreReady{More Tasks<br/>Ready?}
    MoreReady -->|Yes| SortPriority
    MoreReady -->|No| AllDone{All Tasks<br/>Complete?}
    
    AllDone -->|No| CheckDeps
    AllDone -->|Yes| End([Execution Complete])
    
    style Start fill:#e1f5ff
    style Execute fill:#c8e6c9
    style Complete fill:#c8e6c9
    style End fill:#c8e6c9
    style Failed fill:#ffcdd2
    style Wait fill:#fff9c4
```

### Real-World Analogy

TaskManager is like a project manager:
- Knows what needs to be done (tasks)
- Knows the order (dependencies)
- Assigns work (execution)
- Monitors progress (status tracking)
- Handles problems (error management)

### In Code

```python
# Create TaskManager
task_manager = TaskManager(db)

# Give it a task tree
task_tree = TaskTreeNode(root_task)
task_tree.add_child(TaskTreeNode(child_task))

# TaskManager handles everything automatically
await task_manager.distribute_task_tree(task_tree)
```

## Task Lifecycle

Tasks go through different states during their lifecycle:

```
pending → in_progress → completed
              │
              └──> failed
              │
              └──> cancelled
```

### States Explained

- **pending**: Task is created but not yet executed
- **in_progress**: Task is currently running
- **completed**: Task finished successfully
- **failed**: Task execution failed
- **cancelled**: Task was cancelled before completion

### Visual Flow

```
Create Task → pending
     │
     ▼
Execute Task → in_progress
     │
     ├──> Success → completed
     │
     ├──> Error → failed
     │
     └──> Cancelled → cancelled
```

## Priorities

**Priority** controls execution order when multiple tasks are ready to run. Lower numbers = higher priority.

### Priority Levels

- **0**: Urgent (highest priority)
- **1**: High
- **2**: Normal (default)
- **3**: Low (lowest priority)

### Example

```python
# Urgent task runs first
urgent = await task_repository.create_task(
    name="urgent_task",
    priority=0,  # Executes first
    ...
)

# Normal task runs later
normal = await task_repository.create_task(
    name="normal_task",
    priority=2,  # Executes after urgent
    ...
)
```

## Putting It All Together

Here's how these concepts work together:

```python
# 1. Create TaskManager (the orchestrator)
task_manager = TaskManager(db)

# 2. Create tasks with dependencies
task_a = await task_repository.create_task(
    name="fetch_data",
    priority=1,
    ...
)

task_b = await task_repository.create_task(
    name="process_data",
    parent_id=root.id,  # Organizational: child of root
    dependencies=[{"id": task_a.id}],  # Execution: waits for A
    priority=2,
    ...
)

# 3. Build task tree (organization)
tree = TaskTreeNode(root)
tree.add_child(TaskTreeNode(task_a))
tree.add_child(TaskTreeNode(task_b))

# 4. TaskManager handles execution automatically
# - Checks dependencies
# - Executes in order (A, then B)
# - Tracks status
# - Handles errors
await task_manager.distribute_task_tree(tree)
```

## Key Takeaways

1. **Task**: A unit of work with inputs and results
2. **Task Tree**: Hierarchical organization of tasks
3. **Dependencies**: Control execution order (not parent-child!)
4. **Executor**: The code that runs a task
5. **TaskManager**: Automatically orchestrates everything
6. **Priority**: Controls execution order (lower = higher priority)

## Next Steps

Now that you understand the core concepts:

- **Ready to code?** → [Quick Start Guide](quick-start.md)
- **Want examples?** → [Basic Examples](../examples/basic_task.md)
- **Need details?** → [Task Orchestration Guide](../guides/task-orchestration.md)

---

**Confused about something?** Check the [FAQ](../guides/faq.md) or continue to [Quick Start](quick-start.md) to see these concepts in action!


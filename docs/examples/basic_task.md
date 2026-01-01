# Basic Task Examples

> **See also:**
> - [Real-World Examples](real-world.md) for advanced, production scenarios
> - [Task Tree Examples](task-tree.md) for dependency and execution order patterns

This document provides practical, copy-paste ready examples for common use cases with apflow. Each example is complete and runnable.

## Before You Start

**Prerequisites:**
- apflow installed: `pip install apflow`
- Python 3.10+ with async/await support
- Basic understanding of Python

**What You'll Learn:**
- How to use built-in executors
- How to create custom executors
- How to work with task dependencies
- How to handle errors
- Common patterns and best practices

## Example 1: Using Built-in Executor (Simplest)

**What it does:** Gets system CPU information using the built-in `system_info_executor`.

**Why start here:** No custom code needed - just use what's already available!

### Complete Runnable Code

Create `example_01_builtin.py`:

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    # Step 1: Setup
    db = create_session()
    task_manager = TaskManager(db)
    
    # Step 2: Create task using built-in executor
    # system_info_executor is already registered - just use it!
    task = await task_manager.task_repository.create_task(
        name="system_info_executor",  # Built-in executor ID
        user_id="example_user",
        inputs={"resource": "cpu"}    # Get CPU info
    )
    
    # Step 3: Execute
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # Step 4: Get result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Status: {result.status}")
    print(f"Result: {result.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Run It

```bash
python example_01_builtin.py
```

### Expected Output

```
Status: completed
Result: {'system': 'Darwin', 'cores': 8, 'cpu_count': 8, ...}
```

### Understanding the Code

1. **`create_session()`**: Creates a database connection (DuckDB by default)
2. **`TaskManager(db)`**: Creates the orchestrator
3. **`create_task()`**: Creates a task definition
   - `name`: Must match an executor ID
   - `inputs`: Parameters for the executor
4. **`TaskTreeNode()`**: Wraps task in tree structure
5. **`distribute_task_tree()`**: Executes the task
6. **`get_task_by_id()`**: Retrieves updated task with results

### Try Modifying

```python
# Get memory instead
inputs={"resource": "memory"}

# Get disk instead
inputs={"resource": "disk"}

# Get all resources
inputs={"resource": "all"}
```

## Example 2: Simple Custom Executor

**What it does:** Creates a custom executor that processes text data.

**Why this example:** Shows the basic pattern for creating custom executors.

### Complete Runnable Code

Create `example_02_custom.py`:

```python
import asyncio
from apflow import BaseTask, executor_register, TaskManager, TaskTreeNode, create_session
from typing import Dict, Any

# Step 1: Define your custom executor
@executor_register()
class TextProcessor(BaseTask):
    """Processes text data"""
    
    id = "text_processor"
    name = "Text Processor"
    description = "Processes text: count words, reverse, uppercase"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute text processing"""
        text = inputs.get("text", "")
        operation = inputs.get("operation", "count")
        
        if operation == "count":
            result = len(text.split())
        elif operation == "reverse":
            result = text[::-1]
        elif operation == "uppercase":
            result = text.upper()
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        return {
            "operation": operation,
            "input_text": text,
            "result": result
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Define input parameters"""
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to process"
                },
                "operation": {
                    "type": "string",
                    "enum": ["count", "reverse", "uppercase"],
                    "description": "Operation to perform",
                    "default": "count"
                }
            },
            "required": ["text"]
        }

# Step 2: Use your executor
async def main():
    # Import the executor (auto-registered via decorator)
    from example_02_custom import TextProcessor
    
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create task using your custom executor
    task = await task_manager.task_repository.create_task(
        name="text_processor",  # Must match executor ID
        user_id="example_user",
        inputs={
            "text": "Hello, apflow!",
            "operation": "count"
        }
    )
    
    # Execute
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # Get result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Result: {result.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Run It

```bash
python example_02_custom.py
```

### Expected Output

```
Result: {'operation': 'count', 'input_text': 'Hello, apflow!', 'result': 2}
```

### Understanding the Code

**Key Points:**
- `@executor_register()`: Automatically registers the executor
- `id`: Must be unique, used in `name` when creating tasks
- `execute()`: Async function that does the actual work
- `get_input_schema()`: Defines what inputs are expected (JSON Schema)

**Try Different Operations:**
```python
inputs={"text": "Hello", "operation": "reverse"}  # "olleH"
inputs={"text": "Hello", "operation": "uppercase"}  # "HELLO"
```

## Example 3: HTTP API Call Task

**What it does:** Calls an external HTTP API and returns the response.

**Why this example:** Shows how to integrate with external services.

### Complete Runnable Code

Create `example_03_api.py`:

```python
import asyncio
import aiohttp
from apflow import BaseTask, executor_register, TaskManager, TaskTreeNode, create_session
from typing import Dict, Any

@executor_register()
class APICallTask(BaseTask):
    """Calls an external HTTP API"""
    
    id = "api_call_task"
    name = "API Call Task"
    description = "Calls an external HTTP API and returns the response"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute API call"""
        url = inputs.get("url")
        method = inputs.get("method", "GET")
        data = inputs.get("data")
        headers = inputs.get("headers", {})
        
        async with aiohttp.ClientSession() as session:
            try:
                if method == "GET":
                    async with session.get(url, headers=headers) as response:
                        result = await response.json()
                        status_code = response.status
                elif method == "POST":
                    async with session.post(url, json=data, headers=headers) as response:
                        result = await response.json()
                        status_code = response.status
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                return {
                    "status": "completed",
                    "status_code": status_code,
                    "data": result
                }
            except Exception as e:
                return {
                    "status": "failed",
                    "error": str(e)
                }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Define input parameters"""
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "API endpoint URL"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "description": "HTTP method",
                    "default": "GET"
                },
                "data": {
                    "type": "object",
                    "description": "Request body for POST requests"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers"
                }
            },
            "required": ["url"]
        }

async def main():
    from example_03_api import APICallTask
    
    db = create_session()
    task_manager = TaskManager(db)
    
    # Call a public API (JSONPlaceholder)
    task = await task_manager.task_repository.create_task(
        name="api_call_task",
        user_id="example_user",
        inputs={
            "url": "https://jsonplaceholder.typicode.com/posts/1",
            "method": "GET"
        }
    )
    
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Status: {result.status}")
    if result.status == "completed":
        print(f"API Response: {result.result['data']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Run It

```bash
# Install aiohttp if needed
pip install aiohttp
python example_03_api.py
```

### Understanding the Code

**Error Handling:**
- Wrapped in try/except to handle network errors
- Returns error information in result
- Task status will be "failed" if exception occurs

**Try Different APIs:**
```python
# POST request
inputs={
    "url": "https://api.example.com/data",
    "method": "POST",
    "data": {"key": "value"}
}

# With headers
inputs={
    "url": "https://api.example.com/data",
    "headers": {"Authorization": "Bearer token"}
}
```

## Example 4: Task with Dependencies

**What it does:** Creates a pipeline where tasks depend on each other.

**Why this example:** Shows how dependencies control execution order.

### Complete Runnable Code

Create `example_04_dependencies.py`:

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Task 1: Get CPU info
    cpu_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="example_user",
        priority=1,
        inputs={"resource": "cpu"}
    )
    
    # Task 2: Get memory info (depends on CPU task)
    # This will wait for cpu_task to complete!
    memory_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="example_user",
        parent_id=cpu_task.id,  # Organizational
        dependencies=[{"id": cpu_task.id, "required": True}],  # Execution order
        priority=2,
        inputs={"resource": "memory"}
    )
    
    # Task 3: Get disk info (depends on memory task)
    disk_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="example_user",
        parent_id=cpu_task.id,
        dependencies=[{"id": memory_task.id, "required": True}],
        priority=2,
        inputs={"resource": "disk"}
    )
    
    # Build task tree
    root = TaskTreeNode(cpu_task)
    root.add_child(TaskTreeNode(memory_task))
    root.add_child(TaskTreeNode(disk_task))
    
    # Execute
    # Execution order: CPU → Memory → Disk (automatic!)
    await task_manager.distribute_task_tree(root)
    
    # Check results
    cpu_result = await task_manager.task_repository.get_task_by_id(cpu_task.id)
    memory_result = await task_manager.task_repository.get_task_by_id(memory_task.id)
    disk_result = await task_manager.task_repository.get_task_by_id(disk_task.id)
    
    print(f"✅ CPU: {cpu_result.status}")
    print(f"✅ Memory: {memory_result.status}")
    print(f"✅ Disk: {disk_result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding Dependencies

**Key Concept:** `dependencies` control execution order, not `parent_id`!

```
Execution Flow:
CPU Task (no dependencies) → runs first
    ↓
Memory Task (depends on CPU) → waits, then runs
    ↓
Disk Task (depends on Memory) → waits, then runs
```

**Visual Representation:**
```
Root Task
│
├── CPU Task (runs first)
│   │
│   ├── Memory Task (waits for CPU, then runs)
│   │   │
│   │   └── Disk Task (waits for Memory, then runs)
```

## Example 5: Parallel Tasks

**What it does:** Creates multiple tasks that run in parallel (no dependencies).

**Why this example:** Shows how tasks without dependencies execute simultaneously.

### Complete Runnable Code

Create `example_05_parallel.py`:

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create root task
    root_task = await task_manager.task_repository.create_task(
        name="root_task",
        user_id="example_user",
        priority=1
    )
    
    # Create three tasks with NO dependencies
    # They can all run in parallel!
    cpu_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="example_user",
        parent_id=root_task.id,
        priority=2,
        inputs={"resource": "cpu"}
    )
    
    memory_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="example_user",
        parent_id=root_task.id,
        priority=2,  # Same priority
        inputs={"resource": "memory"}
        # No dependencies - can run in parallel with cpu_task!
    )
    
    disk_task = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="example_user",
        parent_id=root_task.id,
        priority=2,
        inputs={"resource": "disk"}
        # No dependencies - can run in parallel!
    )
    
    # Build task tree
    root = TaskTreeNode(root_task)
    root.add_child(TaskTreeNode(cpu_task))
    root.add_child(TaskTreeNode(memory_task))
    root.add_child(TaskTreeNode(disk_task))
    
    # Execute
    # All three tasks run in parallel (no dependencies)
    await task_manager.distribute_task_tree(root)
    
    # Check results
    tasks = [cpu_task, memory_task, disk_task]
    for task in tasks:
        result = await task_manager.task_repository.get_task_by_id(task.id)
        print(f"✅ {task.id}: {result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding Parallel Execution

**When tasks run in parallel:**
- They have no dependencies on each other
- They have the same priority (or compatible priorities)
- TaskManager automatically handles parallel execution

**Performance Benefit:**
- 3 tasks in parallel = ~3x faster than sequential
- Great for independent operations!

## Example 6: Data Processing Pipeline

**What it does:** Creates a complete pipeline: fetch → process → save.

**Why this example:** Shows a real-world pattern with multiple steps.

### Complete Runnable Code

Create `example_06_pipeline.py`:

```python
import asyncio
from apflow import BaseTask, executor_register, TaskManager, TaskTreeNode, create_session
from typing import Dict, Any

# Step 1: Fetch data executor
@executor_register()
class FetchDataTask(BaseTask):
    """Fetches data from a source"""
    
    id = "fetch_data"
    name = "Fetch Data"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Simulate fetching data
        data_source = inputs.get("source", "api")
        return {
            "source": data_source,
            "data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "default": "api"}
            }
        }

# Step 2: Process data executor
@executor_register()
class ProcessDataTask(BaseTask):
    """Processes data"""
    
    id = "process_data"
    name = "Process Data"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Get data from inputs (could come from dependency)
        data = inputs.get("data", [])
        operation = inputs.get("operation", "sum")
        
        if operation == "sum":
            result = sum(data)
        elif operation == "average":
            result = sum(data) / len(data) if data else 0
        else:
            result = len(data)
        
        return {
            "operation": operation,
            "input_count": len(data),
            "result": result
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {"type": "array", "items": {"type": "number"}},
                "operation": {"type": "string", "enum": ["sum", "average", "count"], "default": "sum"}
            },
            "required": ["data"]
        }

# Step 3: Save results executor
@executor_register()
class SaveResultsTask(BaseTask):
    """Saves results"""
    
    id = "save_results"
    name = "Save Results"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        result = inputs.get("result")
        return {
            "saved": True,
            "result": result,
            "timestamp": "2024-01-01T00:00:00Z"
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "result": {"type": "number"}
            },
            "required": ["result"]
        }

async def main():
    # Import executors
    from example_06_pipeline import FetchDataTask, ProcessDataTask, SaveResultsTask
    
    db = create_session()
    task_manager = TaskManager(db)
    
    # Step 1: Fetch data
    fetch_task = await task_manager.task_repository.create_task(
        name="fetch_data",
        user_id="example_user",
        priority=1,
        inputs={"source": "api"}
    )
    
    # Step 2: Process data (depends on fetch)
    process_task = await task_manager.task_repository.create_task(
        name="process_data",
        user_id="example_user",
        parent_id=fetch_task.id,
        dependencies=[{"id": fetch_task.id, "required": True}],
        priority=2,
        inputs={
            "data": [],  # Will be populated from fetch_task result
            "operation": "average"
        }
    )
    
    # Step 3: Save results (depends on process)
    save_task = await task_manager.task_repository.create_task(
        name="save_results",
        user_id="example_user",
        parent_id=fetch_task.id,
        dependencies=[{"id": process_task.id, "required": True}],
        priority=3,
        inputs={"result": 0}  # Will be populated from process_task result
    )
    
    # Build pipeline
    root = TaskTreeNode(fetch_task)
    root.add_child(TaskTreeNode(process_task))
    root.add_child(TaskTreeNode(save_task))
    
    # Execute pipeline
    # Order: Fetch → Process → Save (automatic!)
    await task_manager.distribute_task_tree(root)
    
    # Check final result
    save_result = await task_manager.task_repository.get_task_by_id(save_task.id)
    print(f"✅ Pipeline completed: {save_result.status}")
    print(f"💾 Saved result: {save_result.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding the Pipeline

**Execution Flow:**
```
Fetch Data (gets data)
    ↓
Process Data (processes fetched data)
    ↓
Save Results (saves processed result)
```

**Key Points:**
- Each step depends on the previous
- TaskManager handles dependency resolution automatically
- Results flow from one task to the next

## Example 7: Error Handling

**What it does:** Shows how to handle errors gracefully in custom executors.

**Why this example:** Error handling is crucial for production code.

### Complete Runnable Code

Create `example_07_errors.py`:

```python
import asyncio
from apflow import BaseTask, executor_register, TaskManager, TaskTreeNode, create_session
from typing import Dict, Any

@executor_register()
class RobustTask(BaseTask):
    """Task with comprehensive error handling"""
    
    id = "robust_task"
    name = "Robust Task"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with error handling"""
        try:
            # Validate inputs
            data = inputs.get("data")
            if not data:
                raise ValueError("Data is required")
            
            if not isinstance(data, list):
                raise ValueError("Data must be a list")
            
            # Process data
            result = sum(data) / len(data) if data else 0
            
            return {
                "status": "completed",
                "result": result,
                "processed_count": len(data)
            }
        except ValueError as e:
            # Validation errors - return error info
            return {
                "status": "failed",
                "error": str(e),
                "error_type": "validation_error"
            }
        except Exception as e:
            # Other errors
            return {
                "status": "failed",
                "error": str(e),
                "error_type": "execution_error"
            }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of numbers"
                }
            },
            "required": ["data"]
        }

async def main():
    from example_07_errors import RobustTask
    
    db = create_session()
    task_manager = TaskManager(db)
    
    # Test 1: Valid input
    print("Test 1: Valid input")
    task1 = await task_manager.task_repository.create_task(
        name="robust_task",
        user_id="example_user",
        inputs={"data": [1, 2, 3, 4, 5]}
    )
    tree1 = TaskTreeNode(task1)
    await task_manager.distribute_task_tree(tree1)
    result1 = await task_manager.task_repository.get_task_by_id(task1.id)
    print(f"Status: {result1.status}")
    print(f"Result: {result1.result}\n")
    
    # Test 2: Invalid input (missing data)
    print("Test 2: Invalid input")
    task2 = await task_manager.task_repository.create_task(
        name="robust_task",
        user_id="example_user",
        inputs={}  # Missing required field
    )
    tree2 = TaskTreeNode(task2)
    await task_manager.distribute_task_tree(tree2)
    result2 = await task_manager.task_repository.get_task_by_id(task2.id)
    print(f"Status: {result2.status}")
    print(f"Error: {result2.result.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding Error Handling

**Best Practices:**
1. **Validate inputs early**: Check requirements before processing
2. **Return error information**: Include error type and message
3. **Don't raise exceptions**: Return error info in result instead
4. **Check task status**: Always check `task.status` after execution

**Error States:**
- `status == "failed"`: Task execution failed
- `task.error`: Error message (if available)
- `task.result`: May contain error information

## Example 8: Using CrewAI (LLM Tasks)

**What it does:** Uses CrewAI to execute LLM-based tasks.

**Why this example:** Shows how to use optional LLM features.

### Prerequisites

```bash
pip install apflow[crewai]
```

### Complete Runnable Code

Create `example_08_crewai.py`:

```python
import asyncio
from apflow.extensions.crewai import CrewaiExecutor
from apflow import TaskManager, TaskTreeNode, create_session
from apflow.core.extensions import get_registry

async def main():
    # Create a CrewAI executor
    crew = CrewaiExecutor(
        id="simple_analysis_crew",
        name="Simple Analysis Crew",
        description="Analyzes text using AI",
        agents=[
            {
                "role": "Analyst",
                "goal": "Analyze the provided text and extract key insights",
                "backstory": "You are an expert data analyst"
            }
        ],
        tasks=[
            {
                "description": "Analyze the following text: {text}",
                "agent": "Analyst"
            }
        ]
    )
    
    # Register the configured instance
    get_registry().register(crew)
    
    # Use it via TaskManager
    db = create_session()
    task_manager = TaskManager(db)
    
    task = await task_manager.task_repository.create_task(
        name="simple_analysis_crew",  # Must match crew ID
        user_id="example_user",
        inputs={
            "text": "Sales increased by 20% this quarter. Customer satisfaction is at 95%."
        }
    )
    
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Status: {result.status}")
    if result.status == "completed":
        print(f"Analysis: {result.result}")

if __name__ == "__main__":
    # Note: Requires LLM API key
    # Set via environment variable or request header
    asyncio.run(main())
```

### Understanding CrewAI Integration

**Key Points:**
- CrewAI is optional (requires `[crewai]` extra)
- CrewaiExecutor is a special executor that needs configuration
- Register the configured instance before use
- LLM API keys are required (OpenAI, Anthropic, etc.)

**Setting LLM API Key:**
```bash
# Via environment variable
export OPENAI_API_KEY="sk-your-key"

# Or via request header (for API server)
X-LLM-API-KEY: openai:sk-your-key
```

## Example 9: Task Priorities

**What it does:** Shows how priorities control execution order.

**Why this example:** Priorities help manage task scheduling.

### Complete Runnable Code

Create `example_09_priorities.py`:

```python
import asyncio
from apflow import TaskManager, TaskTreeNode, create_session

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create root task
    root = await task_manager.task_repository.create_task(
        name="root_task",
        user_id="example_user",
        priority=1
    )
    
    # Priority 0 = urgent (highest)
    urgent = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="example_user",
        parent_id=root.id,
        priority=0,  # Executes first!
        inputs={"resource": "cpu"}
    )
    
    # Priority 2 = normal
    normal = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="example_user",
        parent_id=root.id,
        priority=2,  # Executes after urgent
        inputs={"resource": "memory"}
    )
    
    # Priority 3 = low
    low = await task_manager.task_repository.create_task(
        name="system_info_executor",
        user_id="example_user",
        parent_id=root.id,
        priority=3,  # Executes last
        inputs={"resource": "disk"}
    )
    
    # Build tree
    tree = TaskTreeNode(root)
    tree.add_child(TaskTreeNode(urgent))
    tree.add_child(TaskTreeNode(normal))
    tree.add_child(TaskTreeNode(low))
    
    # Execute
    # Order: Urgent (0) → Normal (2) → Low (3)
    await task_manager.distribute_task_tree(tree)
    
    # Check execution order
    for task in [urgent, normal, low]:
        result = await task_manager.task_repository.get_task_by_id(task.id)
        print(f"Priority {task.priority}: {result.status}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding Priorities

**Priority Levels:**
- **0**: Urgent (highest priority)
- **1**: High
- **2**: Normal (default)
- **3**: Low (lowest priority)

**Rule:** Lower numbers = higher priority = execute first

**Note:** Priorities only matter when tasks are ready to run. Dependencies still take precedence!

## Example 10: Complete Workflow

**What it does:** Combines everything - custom executors, dependencies, error handling.

**Why this example:** Shows a complete, production-ready pattern.

### Complete Runnable Code

Create `example_10_complete.py`:

```python
import asyncio
from apflow import BaseTask, executor_register, TaskManager, TaskTreeNode, create_session
from typing import Dict, Any

# Executor 1: Data fetcher
@executor_register()
class DataFetcher(BaseTask):
    id = "data_fetcher"
    name = "Data Fetcher"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        source = inputs.get("source", "default")
        # Simulate fetching
        return {
            "source": source,
            "data": [10, 20, 30, 40, 50],
            "count": 5
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "default": "default"}
            }
        }

# Executor 2: Data processor
@executor_register()
class DataProcessor(BaseTask):
    id = "data_processor"
    name = "Data Processor"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data = inputs.get("data", [])
        operation = inputs.get("operation", "sum")
        
        if operation == "sum":
            result = sum(data)
        elif operation == "average":
            result = sum(data) / len(data) if data else 0
        else:
            result = max(data) if data else 0
        
        return {
            "operation": operation,
            "result": result,
            "input_count": len(data)
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {"type": "array", "items": {"type": "number"}},
                "operation": {"type": "string", "enum": ["sum", "average", "max"], "default": "sum"}
            },
            "required": ["data"]
        }

# Executor 3: Result formatter
@executor_register()
class ResultFormatter(BaseTask):
    id = "result_formatter"
    name = "Result Formatter"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        result = inputs.get("result")
        format_type = inputs.get("format", "json")
        
        if format_type == "json":
            output = {"result": result, "formatted": True}
        else:
            output = f"Result: {result}"
        
        return {
            "format": format_type,
            "output": output
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "result": {"type": "number"},
                "format": {"type": "string", "enum": ["json", "text"], "default": "json"}
            },
            "required": ["result"]
        }

async def main():
    from example_10_complete import DataFetcher, DataProcessor, ResultFormatter
    
    db = create_session()
    task_manager = TaskManager(db)
    
    # Step 1: Fetch data
    fetch = await task_manager.task_repository.create_task(
        name="data_fetcher",
        user_id="example_user",
        priority=1,
        inputs={"source": "api"}
    )
    
    # Step 2: Process data (depends on fetch)
    process = await task_manager.task_repository.create_task(
        name="data_processor",
        user_id="example_user",
        parent_id=fetch.id,
        dependencies=[{"id": fetch.id, "required": True}],
        priority=2,
        inputs={
            "data": [],  # From fetch result
            "operation": "average"
        }
    )
    
    # Step 3: Format result (depends on process)
    format_task = await task_manager.task_repository.create_task(
        name="result_formatter",
        user_id="example_user",
        parent_id=fetch.id,
        dependencies=[{"id": process.id, "required": True}],
        priority=3,
        inputs={
            "result": 0,  # From process result
            "format": "json"
        }
    )
    
    # Build workflow
    root = TaskTreeNode(fetch)
    root.add_child(TaskTreeNode(process))
    root.add_child(TaskTreeNode(format_task))
    
    # Execute complete workflow
    await task_manager.distribute_task_tree(root)
    
    # Get final result
    final = await task_manager.task_repository.get_task_by_id(format_task.id)
    print(f"✅ Workflow completed: {final.status}")
    print(f"📊 Final output: {final.result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding the Complete Workflow

**Execution Flow:**
```
Fetch Data
    ↓
Process Data (uses fetched data)
    ↓
Format Result (uses processed result)
```

**Key Features:**
- ✅ Custom executors
- ✅ Dependencies
- ✅ Error handling
- ✅ Result flow between tasks

## Common Patterns Summary

### Pattern 1: Simple Task
```python
task = await task_repository.create_task(name="executor_id", ...)
tree = TaskTreeNode(task)
await task_manager.distribute_task_tree(tree)
```

### Pattern 2: Sequential (Dependencies)
```python
task1 = await task_repository.create_task(...)
task2 = await task_repository.create_task(
    dependencies=[{"id": task1.id}],
    ...
)
```

### Pattern 3: Parallel (No Dependencies)
```python
task1 = await task_repository.create_task(...)
task2 = await task_repository.create_task(...)  # No dependency
# Both run in parallel
```

## Next Steps

- **[Task Orchestration Guide](../guides/task-orchestration.md)** - Deep dive into orchestration
- **[Custom Tasks Guide](../guides/custom-tasks.md)** - Advanced executor creation
- **[Real-World Examples](real-world.md)** - Production-ready examples
- **[Best Practices](../guides/best-practices.md)** - Learn from experts

---

**Need help?** Check the [FAQ](../guides/faq.md) or [Quick Start Guide](../getting-started/quick-start.md)

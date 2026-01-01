# Best Practices Guide

Learn from the experts. This guide covers design patterns, optimization techniques, and best practices for building robust applications with apflow.

## Table of Contents

1. [Task Design](#task-design)
2. [Orchestration Patterns](#orchestration-patterns)
3. [Error Handling](#error-handling)
4. [Performance Optimization](#performance-optimization)
5. [Code Organization](#code-organization)
6. [Testing Strategies](#testing-strategies)
7. [Production Readiness](#production-readiness)

## Understanding Lifecycles

**Important:** Before diving into best practices, understand the execution model:

- **Task Tree Execution Lifecycle**: How tasks are created, distributed, executed, and completed
- **DB Session Context Hook Lifecycle**: How hooks access the database and share context

See [Task Tree Execution Lifecycle](../architecture/task-tree-lifecycle.md) for comprehensive details on:
- Session scope and lifetime (spans entire task tree)
- Hook context setup and cleanup (guaranteed by finally blocks)
- Execution order and concurrency guarantees
- Error handling and resource cleanup patterns

## Task Design

### 1. Single Responsibility Principle

**Each task should do one thing well.**

**Good:**
```python
@executor_register()
class FetchUserData(BaseTask):
    """Fetches user data from API"""
    # Only fetches data

@executor_register()
class ProcessUserData(BaseTask):
    """Processes user data"""
    # Only processes data

@executor_register()
class SaveUserData(BaseTask):
    """Saves user data to database"""
    # Only saves data
```

**Bad:**
```python
@executor_register()
class DoEverythingWithUserData(BaseTask):
    """Fetches, processes, saves, and sends notifications"""
    # Does too much!
```

**Benefits:**
- Easier to test
- Easier to reuse
- Easier to debug
- Easier to maintain

### 2. Idempotent Tasks

**Tasks should be idempotent - running them multiple times should produce the same result.**

**Good:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    user_id = inputs.get("user_id")
    
    # Check if already processed
    existing = await self._check_if_processed(user_id)
    if existing:
        return {"status": "completed", "result": existing, "cached": True}
    
    # Process
    result = await self._process(user_id)
    await self._save_result(user_id, result)
    
    return {"status": "completed", "result": result}
```

**Benefits:**
- Safe to retry
- Can handle duplicate requests
- Better error recovery

### 3. Validate Inputs Early

**Validate all inputs at the start of execution.**

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Validate immediately
    url = inputs.get("url")
    if not url:
        return {
            "status": "failed",
            "error": "URL is required",
            "error_type": "validation_error"
        }
    
    if not isinstance(url, str):
        return {
            "status": "failed",
            "error": "URL must be a string",
            "error_type": "type_error"
        }
    
    if not url.startswith(("http://", "https://")):
        return {
            "status": "failed",
            "error": "URL must start with http:// or https://",
            "error_type": "validation_error"
        }
    
    # Continue with execution
    ...
```

**Benefits:**
- Fails fast
- Clear error messages
- Saves resources

### 4. Return Consistent Results

**Always return results in a consistent format.**

**Good:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = await self._process(inputs)
        return {
            "status": "completed",
            "result": result,
            "metadata": {
                "processed_at": datetime.now().isoformat(),
                "input_count": len(inputs)
            }
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__
        }
```

**Bad:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Sometimes returns just the result
    return result
    
    # Sometimes returns wrapped
    return {"data": result}
    
    # Sometimes returns different format
    return {"output": result, "success": True}
```

### 5. Use Async Properly

**Always use async/await for I/O operations.**

**Good:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Async HTTP request
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
    
    # Async file operation
    async with aiofiles.open(file_path, 'r') as f:
        content = await f.read()
    
    return {"status": "completed", "data": data, "content": content}
```

**Bad:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Blocking HTTP request
    import requests
    response = requests.get(url)  # Blocks the event loop!
    
    # Blocking file operation
    with open(file_path, 'r') as f:
        content = f.read()  # Blocks!
    
    return {"status": "completed"}
```

## Orchestration Patterns

### 1. Use Dependencies, Not Parent-Child for Execution Order

**Remember: `parent_id` is organizational, `dependencies` control execution.**

**Good:**
```python
# Task 1
fetch = create_task(name="fetch_data", ...)

# Task 2 depends on Task 1 (execution order)
process = create_task(
    name="process_data",
    parent_id=fetch.id,  # Organizational
    dependencies=[{"id": fetch.id, "required": True}],  # Execution order
    ...
)
```

**Bad:**
```python
# Relying on parent-child for execution order
process = create_task(
    name="process_data",
    parent_id=fetch.id,  # This doesn't guarantee execution order!
    ...
)
```

### 2. Keep Task Trees Manageable

**Break complex workflows into smaller, manageable trees.**

**Good:**
```python
# Pipeline 1: Data collection
collect_tree = build_collection_tree()

# Pipeline 2: Data processing
process_tree = build_processing_tree()

# Pipeline 3: Data storage
store_tree = build_storage_tree()

# Execute sequentially
await task_manager.distribute_task_tree(collect_tree)
await task_manager.distribute_task_tree(process_tree)
await task_manager.distribute_task_tree(store_tree)
```

**Bad:**
```python
# One massive tree with hundreds of tasks
mega_tree = build_mega_tree_with_500_tasks()
await task_manager.distribute_task_tree(mega_tree)  # Hard to manage!
```

### 3. Use Parallel Execution When Possible

**Tasks without dependencies can run in parallel.**

**Good:**
```python
# All three tasks can run in parallel
task1 = create_task(name="fetch_data_1", ...)  # No dependencies
task2 = create_task(name="fetch_data_2", ...)  # No dependencies
task3 = create_task(name="fetch_data_3", ...)  # No dependencies

# Build tree
root = TaskTreeNode(root_task)
root.add_child(TaskTreeNode(task1))
root.add_child(TaskTreeNode(task2))
root.add_child(TaskTreeNode(task3))

# All run in parallel!
await task_manager.distribute_task_tree(root)
```

**Performance Benefit:**
- 3 tasks in parallel = ~3x faster than sequential
- Great for independent operations

### 4. Use Optional Dependencies for Fallbacks

**Use optional dependencies for fallback scenarios.**

```python
# Primary task
primary = create_task(
    name="primary_fetch",
    ...
)

# Fallback task (runs even if primary fails)
fallback = create_task(
    name="fallback_fetch",
    dependencies=[{"id": primary.id, "required": False}],  # Optional
    ...
)

# Final task (runs after either primary or fallback)
final = create_task(
    name="process_result",
    dependencies=[
        {"id": primary.id, "required": False},
        {"id": fallback.id, "required": False}
    ],
    ...
)
```

### 5. Set Appropriate Priorities

**Use priorities consistently and sparingly.**

```python
# Priority convention
URGENT = 0      # Critical/emergency only
HIGH = 1        # High priority business tasks
NORMAL = 2      # Default for most tasks
LOW = 3         # Background/low priority

# Payment processing (critical)
payment = create_task(name="process_payment", priority=URGENT)

# Data processing (normal)
data = create_task(name="process_data", priority=NORMAL)

# Cleanup (low priority)
cleanup = create_task(name="cleanup", priority=LOW)
```

## Hooks Best Practices

### 1. Use Hooks for Cross-Cutting Concerns

**Good use cases:**
- Validation and transformation of inputs
- Logging and monitoring
- Authentication and authorization checks
- Metrics collection
- Notification sending

```python
from apflow import register_pre_hook, register_post_hook

@register_pre_hook
async def validate_and_enrich(task):
    """Validate inputs and add metadata"""
    # Validate
    if task.inputs and "user_id" in task.inputs:
        if not task.inputs["user_id"]:
            raise ValueError("user_id is required")
    
    # Enrich with metadata
    task.inputs["_hook_timestamp"] = datetime.now().isoformat()
    task.inputs["_environment"] = os.getenv("ENV", "production")

@register_post_hook
async def log_and_metric(task, inputs, result):
    """Log execution and collect metrics"""
    duration = (datetime.now() - task.created_at).total_seconds()
    logger.info(f"Task {task.id} completed in {duration}s")
    metrics.record("task.duration", duration, tags={"type": task.type})
```

### 2. Modify Task Fields Using Hook Repository

**For fields other than inputs, use `get_hook_repository()`:**

```python
from apflow import register_pre_hook, get_hook_repository

@register_pre_hook
async def adjust_priority_by_load(task):
    """Adjust task priority based on system load"""
    repo = get_hook_repository()
    if not repo:
        return
    
    # Query current system load
    pending_count = len(await repo.get_tasks_by_status("pending"))
    
    # Adjust priority if system is overloaded
    if pending_count > 100:
        await repo.update_task_priority(task.id, task.priority + 1)
```

**Remember:**
- `task.inputs` modifications are auto-persisted (no explicit save needed)
- Other fields require explicit repository method calls
- All hooks share the same database session
- Changes made by one hook are visible to subsequent hooks

### 3. Keep Hooks Fast and Lightweight

**Bad:**
```python
@register_pre_hook
async def slow_hook(task):
    # Don't do heavy computation in hooks!
    await expensive_api_call()  # ❌
    time.sleep(5)  # ❌
    complex_calculation()  # ❌
```

**Good:**
```python
@register_pre_hook
async def fast_hook(task):
    # Quick validation and transformation only
    if task.inputs:
        task.inputs["validated"] = True
    # Heavy work should be in separate tasks
```

### 4. Handle Hook Failures Gracefully

**Hooks should not crash the entire execution:**

```python
@register_pre_hook
async def safe_hook(task):
    """Hook with proper error handling"""
    try:
        # Your hook logic
        await validate_something(task)
    except Exception as e:
        # Log error but don't fail the task
        logger.error(f"Hook failed for task {task.id}: {e}")
        # Optionally add error flag to inputs
        if task.inputs is None:
            task.inputs = {}
        task.inputs["_hook_error"] = str(e)
```

**Note:** The framework already catches hook exceptions and logs them without failing task execution. But adding your own error handling provides more control.

## Error Handling

### 1. Return Errors, Don't Just Raise

**Return error information in results for better control.**

**Good:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = await self._process(inputs)
        return {"status": "completed", "result": result}
    except ValueError as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": "validation_error",
            "field": "input_data"
        }
    except TimeoutError as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": "timeout_error",
            "retryable": True
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": "execution_error"
        }
```

**Benefits:**
- More control over error format
- Can include additional context
- Easier to handle programmatically

### 2. Handle Dependency Failures

**Check dependency status before using results.**

```python
# After execution, check dependencies
task = await task_manager.task_repository.get_task_by_id(task_id)

if task.status == "failed":
    # Check if dependencies failed
    for dep in task.dependencies:
        dep_task = await task_manager.task_repository.get_task_by_id(dep["id"])
        if dep_task.status == "failed":
            print(f"Dependency {dep['id']} failed: {dep_task.error}")
            # Handle dependency failure
```

### 3. Use Optional Dependencies for Resilience

**Use optional dependencies for non-critical paths.**

```python
# Critical path
critical = create_task(name="critical_task", ...)

# Optional enhancement (nice to have, but not required)
optional = create_task(
    name="optional_enhancement",
    dependencies=[{"id": critical.id, "required": False}],  # Optional
    ...
)

# Final task (works with or without optional)
final = create_task(
    name="final_task",
    dependencies=[
        {"id": critical.id, "required": True},  # Required
        {"id": optional.id, "required": False}  # Optional
    ],
    ...
)
```

### 4. Implement Retry Logic

**For transient failures, implement retry logic in executors.**

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    max_retries = inputs.get("max_retries", 3)
    retry_delay = inputs.get("retry_delay", 1.0)
    
    for attempt in range(max_retries):
        try:
            result = await self._process(inputs)
            return {"status": "completed", "result": result, "attempts": attempt + 1}
        except TransientError as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            else:
                return {
                    "status": "failed",
                    "error": str(e),
                    "error_type": "transient_error",
                    "attempts": max_retries
                }
```

## Performance Optimization

### 1. Use Parallel Execution

**Run independent tasks in parallel.**

```python
# Sequential (slow)
task1 = create_task(...)
task2 = create_task(...)  # Waits for task1
task3 = create_task(...)  # Waits for task2
# Total time: time1 + time2 + time3

# Parallel (fast)
task1 = create_task(...)  # No dependencies
task2 = create_task(...)  # No dependencies
task3 = create_task(...)  # No dependencies
# Total time: max(time1, time2, time3)
```

### 2. Batch Operations

**Batch similar operations together.**

**Good:**
```python
@executor_register()
class BatchProcessor(BaseTask):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        items = inputs.get("items", [])
        
        # Process all items in parallel
        results = await asyncio.gather(*[
            self._process_item(item) for item in items
        ])
        
        return {"status": "completed", "results": results}
```

**Bad:**
```python
# Processing items one by one
for item in items:
    result = await process_item(item)  # Sequential, slow!
```

### 3. Cache Results

**Cache expensive operations.**

```python
class CachedExecutor(BaseTask):
    _cache = {}
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        cache_key = self._get_cache_key(inputs)
        
        # Check cache
        if cache_key in self._cache:
            return {
                "status": "completed",
                "result": self._cache[cache_key],
                "cached": True
            }
        
        # Compute
        result = await self._expensive_operation(inputs)
        
        # Cache
        self._cache[cache_key] = result
        
        return {"status": "completed", "result": result, "cached": False}
```

### 4. Optimize Database Queries

**Use efficient database queries in executors.**

```python
# Good: Single query with filtering
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    user_ids = inputs.get("user_ids", [])
    
    # Single query with WHERE IN
    query = "SELECT * FROM users WHERE id IN :user_ids"
    results = await db.fetch(query, user_ids=user_ids)
    
    return {"status": "completed", "users": results}

# Bad: Multiple queries in loop
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    user_ids = inputs.get("user_ids", [])
    results = []
    
    # Multiple queries (slow!)
    for user_id in user_ids:
        user = await db.fetch_one("SELECT * FROM users WHERE id = :id", id=user_id)
        results.append(user)
    
    return {"status": "completed", "users": results}
```

## Code Organization

### 1. Organize Executors by Domain

**Group related executors together.**

```
my_project/
├── executors/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── fetch.py      # Data fetching executors
│   │   └── process.py    # Data processing executors
│   ├── api/
│   │   ├── __init__.py
│   │   └── http.py       # HTTP API executors
│   └── storage/
│       ├── __init__.py
│       └── database.py   # Database executors
```

### 2. Use Shared Utilities

**Extract common functionality into utilities.**

```python
# utils/validation.py
def validate_url(url: str) -> bool:
    """Validate URL format"""
    return url.startswith(("http://", "https://"))

# executors/api.py
from utils.validation import validate_url

@executor_register()
class APICallExecutor(BaseTask):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        url = inputs.get("url")
        if not validate_url(url):
            return {"status": "failed", "error": "Invalid URL"}
        # ...
```

### 3. Use Configuration

**Externalize configuration.**

```python
# config.py
import os

API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# executors/api.py
from config import API_TIMEOUT, MAX_RETRIES

@executor_register()
class APICallExecutor(BaseTask):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        timeout = inputs.get("timeout", API_TIMEOUT)
        # ...
```

### 4. Document Your Code

**Add clear documentation.**

```python
@executor_register()
class UserDataFetcher(BaseTask):
    """
    Fetches user data from the API.
    
    This executor retrieves user information from the external API
    and returns it in a standardized format.
    
    Args (inputs):
        user_id (str): The ID of the user to fetch
        include_profile (bool): Whether to include profile data (default: False)
    
    Returns:
        dict: User data with status and result
    
    Example:
        task = create_task(
            name="user_data_fetcher",
            inputs={"user_id": "123", "include_profile": True}
        )
    """
    id = "user_data_fetcher"
    # ...
```

## Testing Strategies

### 1. Unit Test Executors

**Test executors in isolation.**

```python
import pytest
from my_executors import UserDataFetcher

@pytest.mark.asyncio
async def test_user_data_fetcher():
    executor = UserDataFetcher()
    
    # Test with valid input
    result = await executor.execute({"user_id": "123"})
    assert result["status"] == "completed"
    assert "user_id" in result["result"]
    
    # Test with invalid input
    result = await executor.execute({})
    assert result["status"] == "failed"
    assert "error" in result
```

### 2. Integration Test Task Trees

**Test complete workflows.**

```python
@pytest.mark.asyncio
async def test_user_data_pipeline():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create pipeline
    fetch = await task_manager.task_repository.create_task(
        name="user_data_fetcher",
        user_id="test_user",
        inputs={"user_id": "123"}
    )
    
    process = await task_manager.task_repository.create_task(
        name="user_data_processor",
        user_id="test_user",
        dependencies=[{"id": fetch.id, "required": True}],
        inputs={}
    )
    
    # Execute
    root = TaskTreeNode(fetch)
    root.add_child(TaskTreeNode(process))
    await task_manager.distribute_task_tree(root)
    
    # Verify
    fetch_result = await task_manager.task_repository.get_task_by_id(fetch.id)
    process_result = await task_manager.task_repository.get_task_by_id(process.id)
    
    assert fetch_result.status == "completed"
    assert process_result.status == "completed"
```

### 3. Mock External Dependencies

**Mock external services in tests.**

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_api_executor_with_mock():
    executor = APICallExecutor()
    
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"data": "test"})
        mock_response.status = 200
        
        mock_session.return_value.__aenter__.return_value.request.return_value.__aenter__.return_value = mock_response
        
        result = await executor.execute({"url": "https://api.example.com"})
        
        assert result["status"] == "completed"
        assert result["data"] == {"data": "test"}
```

## Production Readiness

### 1. Add Logging

**Log important events.**

```python
from apflow.core.utils.logger import get_logger

logger = get_logger(__name__)

@executor_register()
class LoggedExecutor(BaseTask):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Starting execution with inputs: {inputs}")
        
        try:
            result = await self._process(inputs)
            logger.info(f"Execution completed successfully")
            return {"status": "completed", "result": result}
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}
```

### 2. Add Monitoring

**Monitor task execution.**

```python
import time

@executor_register()
class MonitoredExecutor(BaseTask):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        
        try:
            result = await self._process(inputs)
            duration = time.time() - start_time
            
            # Log metrics
            logger.info(f"Execution completed in {duration:.2f}s")
            
            return {
                "status": "completed",
                "result": result,
                "duration": duration
            }
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Execution failed after {duration:.2f}s: {e}")
            return {"status": "failed", "error": str(e)}
```

### 3. Handle Timeouts

**Set appropriate timeouts.**

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    timeout = inputs.get("timeout", 30)
    
    try:
        result = await asyncio.wait_for(
            self._process(inputs),
            timeout=timeout
        )
        return {"status": "completed", "result": result}
    except asyncio.TimeoutError:
        return {
            "status": "failed",
            "error": f"Operation timed out after {timeout}s",
            "error_type": "timeout"
        }
```

### 4. Validate Production Configuration

**Validate configuration at startup.**

```python
def validate_config():
    """Validate production configuration"""
    required_vars = ["API_KEY", "DATABASE_URL"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        raise ValueError(f"Missing required environment variables: {missing}")

# Call at startup
validate_config()
```

## Summary

**Key Takeaways:**

1. **Design**: Single responsibility, idempotent, validate early
2. **Orchestration**: Use dependencies for execution order, parallelize when possible
3. **Errors**: Return errors with context, handle dependencies gracefully
4. **Performance**: Parallelize, batch, cache, optimize queries
5. **Code**: Organize by domain, use utilities, document well
6. **Testing**: Unit test executors, integration test workflows, mock dependencies
7. **Production**: Log, monitor, timeout, validate config

## Next Steps

- **[Task Orchestration Guide](task-orchestration.md)** - Learn orchestration patterns
- **[Custom Tasks Guide](custom-tasks.md)** - Create custom executors
- **[Examples](../examples/basic_task.md)** - See practical examples
- **[API Reference](../api/python.md)** - Complete API documentation

---

**Want to contribute?** Check the [Contributing Guide](../development/contributing.md)


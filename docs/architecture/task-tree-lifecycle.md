# Task Tree Execution Lifecycle

This document describes the complete lifecycle of task tree execution, including the database session context and hook execution lifecycle.

## Overview

Task tree execution involves multiple layers of coordination between TaskExecutor, TaskManager, and hooks. Understanding these lifecycles is crucial for:
- Implementing hooks that access the database
- Debugging execution issues
- Ensuring proper resource cleanup
- Maintaining data consistency

## 1. Task Tree Execution Lifecycle

### 1.1 Entry Point: TaskExecutor.execute_task_tree()

**File**: `src/apflow/core/execution/task_executor.py` (lines 151-250)

```python
async def execute_task_tree(
    self,
    task_tree: TaskTreeNode,
    root_task_id: str,
    use_streaming: bool = False,
    streaming_callbacks_context: Optional[Any] = None,
    use_demo: bool = False,
    db_session: Optional[Union[Session, AsyncSession]] = None
) -> Dict[str, Any]:
```

**Key Steps**:

1. **Session Creation** (if not provided)
   ```python
   if db_session is None:
       async with create_pooled_session() as session:
           return await self.execute_task_tree(...)  # Recursive call with session
   ```
   - Uses `create_pooled_session()` for automatic session lifecycle management
   - Session is automatically committed/rolled back by the context manager
   - Ensures all operations within the task tree share the same session

2. **Concurrent Execution Protection**
   ```python
   if self.is_task_running(root_task_id):
       return {"status": "already_running", ...}
   ```
   - Prevents multiple concurrent executions of the same task tree
   - Uses singleton `TaskTracker` for execution state tracking
   - Returns early without starting execution

3. **Execution Tracking**
   ```python
   await self.start_task_tracking(root_task_id)
   try:
       # ... execution ...
   finally:
       await self.end_task_tracking(root_task_id)
   ```
   - Registers task tree as "running" in TaskTracker
   - Guarantees cleanup in finally block even on exceptions

4. **TaskManager Creation**
   ```python
   task_manager = TaskManager(
       db_session,
       root_task_id=root_task_id,
       pre_hooks=self.pre_hooks,
       post_hooks=self.post_hooks,
       executor_instances=self._executor_instances,
       use_demo=use_demo
   )
   ```
   - Passes shared session to TaskManager
   - Passes hook lists (registered at application startup)
   - Passes shared executor_instances dict for cancellation support

5. **Task Tree Distribution**
   ```python
   if use_streaming and streaming_callbacks_context:
       await task_manager.distribute_task_tree_with_streaming(task_tree, use_callback=True)
   else:
       await task_manager.distribute_task_tree(task_tree, use_callback=True)
   ```

### 1.2 Task Manager: distribute_task_tree()

**File**: `src/apflow/core/execution/task_manager.py` (lines 268-318)

**Key Steps**:

1. **Hook Context Setup** (lines 283-285)
   ```python
   set_hook_context(self.task_repository)
   ```
   - **CRITICAL**: Sets up ContextVar for all hooks to access DB
   - Must be called BEFORE any hooks are executed
   - Thread-safe context isolation (ContextVar not thread-local)

2. **Try Block - Tree Lifecycle Hooks** (lines 286-311)
   ```python
   try:
       # 1. on_tree_created hook
       await self._call_task_tree_hooks("on_tree_created", root_task, task_tree)
       
       # 2. on_tree_started hook
       await self._call_task_tree_hooks("on_tree_started", root_task)
       
       try:
           # 3. Execute task tree recursively
           await self._execute_task_tree_recursive(task_tree, use_callback)
           
           # 4. Check final status and call completion hooks
           final_status = task_tree.calculate_status()
           if final_status == "completed":
               await self._call_task_tree_hooks("on_tree_completed", root_task, "completed")
           else:
               await self._call_task_tree_hooks("on_tree_failed", root_task, f"Tree finished with status: {final_status}")
               
       except Exception as e:
           # 5. on_tree_failed hook on exception
           await self._call_task_tree_hooks("on_tree_failed", root_task, str(e))
           raise
   ```

3. **Finally Block - Hook Context Cleanup** (lines 312-313)
   ```python
   finally:
       clear_hook_context()
   ```
   - **GUARANTEED**: Always executes even on exceptions
   - Cleans up ContextVar to prevent context leakage
   - Critical for proper resource cleanup

### 1.3 Recursive Task Tree Execution

**File**: `src/apflow/core/execution/task_manager.py` (lines 415-605)

**Key Steps**:

1. **Priority-Based Execution**
   ```python
   # Group children by priority
   priority_groups: Dict[int, List[TaskTreeNode]] = {}
   self._add_children_to_priority_groups(node, priority_groups)
   
   # Execute by priority (ascending order)
   sorted_priorities = sorted(priority_groups.keys())
   for priority in sorted_priorities:
       children_with_same_priority = priority_groups[priority]
       # ... execute children in parallel ...
   ```

2. **Parallel Execution Within Same Priority**
   ```python
   async def execute_child_and_children(child_node):
       await self._execute_single_task(child_node.task, use_callback)
       await self._execute_task_tree_recursive(child_node, use_callback)
   
   parallel_tasks = [execute_child_and_children(child_node) for child_node in ready_tasks]
   await asyncio.gather(*parallel_tasks)
   ```

3. **Dependency Resolution**
   ```python
   deps_satisfied = await are_dependencies_satisfied(
       child_task, self.task_repository, self._tasks_to_reexecute
   )
   if deps_satisfied:
       ready_tasks.append(child_node)
   else:
       waiting_tasks.append(child_node)
   ```

### 1.4 Single Task Execution

**File**: `src/apflow/core/execution/task_manager.py` (lines 627-897)

**Key Steps**:

1. **Status Checks and Updates** (lines 627-735)
   ```python
   # Refresh task from DB to get latest status
   task = await self.task_repository.get_task_by_id(task_id)
   
   # Update to in_progress
   await self.task_repository.update_task_status(
       task_id=task_id,
       status="in_progress",
       started_at=datetime.now(timezone.utc)
   )
   ```

2. **Dependency Resolution** (lines 738-759)
   ```python
   # Merge dependency results into inputs
   resolved_inputs = await resolve_task_dependencies(task, self.task_repository)
   
   if resolved_inputs != (task.inputs or {}):
       await self.task_repository.update_task_inputs(task_id, resolved_inputs)
   ```

3. **Pre-Hook Execution** (lines 761-794)
   ```python
   # Store inputs before pre-hooks for change detection
   inputs_before_pre_hooks = copy.deepcopy(task.inputs) if task.inputs else {}
   
   # Execute pre-hooks (can modify task.inputs)
   await self._execute_pre_hooks(task)
   
   # Auto-persist if inputs changed
   if inputs_after_pre_hooks != inputs_before_pre_hooks:
       await self.task_repository.update_task_inputs(task_id, inputs_to_save)
       task = await self.task_repository.get_task_by_id(task_id)  # Refresh
   ```

4. **Task Execution** (lines 807-815)
   ```python
   # Execute task using agent executor
   task_result = await self._execute_task_with_schemas(task, final_inputs)
   ```

5. **Status Update and Cleanup** (lines 832-856)
   ```python
   # Update task status
   await self.task_repository.update_task_status(
       task_id=task_id,
       status="completed",
       progress=1.0,
       result=task_result,
       error=None,
       completed_at=datetime.now(timezone.utc)
   )
   
   # Clear executor reference
   executor = self._executor_instances.pop(task_id, None)
   if executor and hasattr(executor, 'clear_task_context'):
       executor.clear_task_context()
   ```

6. **Post-Hook Execution** (lines 858-897)
   ```python
   # Execute post-hooks
   await self._execute_post_hooks(task, final_inputs, task_result)
   
   # Trigger dependent tasks via callbacks
   if use_callback:
       await self.execute_after_task(task)
   ```

## 2. Database Session Lifecycle

### 2.1 Session Scope

**Session Creation**:
- Created at `TaskExecutor.execute_task_tree()` entry point
- Shared by ALL operations within the task tree execution
- Managed by `create_pooled_session()` async context manager


**Session Lifetime & Hook Context**:
```
TaskExecutor.execute_task_tree (session created)
├── TaskManager.distribute_task_tree
│   ├── set_hook_context(self.task_repository)  [ContextVar active, shares session]
│   ├── on_tree_created hooks
│   ├── on_tree_started hooks
│   ├── _execute_task_tree_recursive
│   │   ├── _execute_single_task (task 1)
│   │   │   ├── update_task_status
│   │   │   ├── resolve_task_dependencies
│   │   │   ├── pre-hooks (can modify task.inputs)
│   │   │   ├── execute task
│   │   │   ├── update_task_status
│   │   │   └── post-hooks
│   │   ├── _execute_single_task (task 2)
│   │   └── ...
│   ├── on_tree_completed/failed hooks
│   └── clear_hook_context()  [ContextVar cleared]
└── (session automatically committed/rolled back)
```
*All hooks and task executions within a tree share the same session and ContextVar context. See also: Hook Context Lifecycle Timeline below.*

### 2.2 Commit Strategy

**Per-Operation Commits**:
- Each `TaskRepository` method commits its own transaction
- Example in `update_task_status()`:
  ```python
  await self.db.commit()
  flag_modified(task, "result")  # For JSON fields
  await self.db.refresh(task)    # Ensure fresh data
  ```

**Benefits**:
- No cascading rollbacks across the entire task tree
- Each task's status update is persisted immediately
- Failed tasks don't affect already-completed tasks
- Better error isolation and recovery

**Trade-offs**:
- Cannot roll back multiple tasks atomically
- Must handle partial failures explicitly
- Requires careful error handling in business logic

### 2.3 Session Safety Features

**1. flag_modified for JSON Fields** (lines 633, 675, 717, 833, 869 in task_repository.py)
```python
from sqlalchemy.orm.attributes import flag_modified

# After modifying JSON field
task.result = new_result
flag_modified(task, "result")  # Tell SQLAlchemy about the change
await self.db.commit()
```

**2. db.refresh After Commits** (lines 645-647 in task_repository.py)
```python
await self.db.commit()
# Refresh to get latest data from database
await self.db.refresh(task)
```

**3. Concurrent Execution Protection** (lines 188-197 in task_executor.py)
```python
if self.is_task_running(root_task_id):
    return {"status": "already_running", ...}
```

## 3. Hook Context Lifecycle

### 3.1 ContextVar-Based Context Management

**File**: `src/apflow/core/storage/context.py` (lines 10-108)

**Design Pattern**:
- Uses Python 3.7+ ContextVar (not thread-local)
- Inspired by Flask's request context and Celery's task context
- Thread-safe and async-compatible

**Implementation**:
```python
from contextvars import ContextVar

_hook_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar('hook_context', default=None)

def set_hook_context(task_repository: TaskRepository) -> None:
    """Set hook context with task repository"""
    _hook_context.set({"task_repository": task_repository})

def clear_hook_context() -> None:
    """Clear hook context"""
    _hook_context.set(None)

def get_hook_session() -> Session:
    """Get database session from hook context"""
    context = _hook_context.get()
    if context is None:
        raise RuntimeError("Hook context not set. Hooks can only access DB during task tree execution.")
    return context["task_repository"].db

def get_hook_repository() -> TaskRepository:
    """Get task repository from hook context"""
    context = _hook_context.get()
    if context is None:
        raise RuntimeError("Hook context not set. Hooks can only access DB during task tree execution.")
    return context["task_repository"]
```


### 3.2 Hook Context Lifecycle Timeline

*See the unified diagram above under Session Lifetime & Hook Context. All hooks (on_tree_created, on_tree_started, pre-hooks, post-hooks, on_tree_completed/failed) share the same session and ContextVar context, which is set at the start of distribute_task_tree and cleared in the finally block.*

### 3.3 Hook Context Guarantees

**1. Exception Safety**:
```python
try:
    set_hook_context(self.task_repository)
    # ... all hook executions ...
finally:
    clear_hook_context()  # ALWAYS executes
```

**2. Context Isolation**:
- Each task tree execution has its own ContextVar context
- Concurrent task tree executions have isolated contexts
- No context leakage between executions

**3. Session Sharing**:
- All hooks in the same task tree execution share the same session
- Same transaction context for all hooks
- Modifications in pre-hooks are visible to post-hooks

### 3.4 Hook Types and DB Access

**Pre-Hooks** (`register_pre_hook`):
- **When**: After dependency resolution, before task execution
- **Can Modify**: `task.inputs` (auto-persisted if changed)
- **DB Access**: Via `get_hook_repository()` or `get_hook_session()`
- **Use Cases**: Input validation, data transformation, pre-processing

**Post-Hooks** (`register_post_hook`):
- **When**: After task execution, before dependent tasks
- **Can Modify**: Other task fields (requires explicit repository calls)
- **DB Access**: Via `get_hook_repository()` or `get_hook_session()`
- **Use Cases**: Notifications, logging, result processing, side effects

**Task Tree Hooks** (`register_task_tree_hook`):
- **When**: Tree lifecycle events (created, started, completed, failed)
- **Can Modify**: Task fields (requires explicit repository calls)
- **DB Access**: Via `get_hook_repository()` or `get_hook_session()`
- **Use Cases**: Tree-level monitoring, cleanup, aggregation

### 3.5 Hook Modification Patterns

**Pattern 1: Auto-Persisted task.inputs** (pre-hooks only):
```python
from apflow import register_pre_hook

@register_pre_hook
async def validate_inputs(task):
    # Modify task.inputs directly
    if task.inputs and "url" in task.inputs:
        task.inputs["url"] = task.inputs["url"].strip()
    
    # Changes are auto-detected and persisted
    # No explicit repository call needed
```

**Pattern 2: Explicit Field Updates** (all hooks):
```python
from apflow import register_post_hook, get_hook_repository

@register_post_hook
async def update_metadata(task, inputs, result):
    repo = get_hook_repository()
    
    # Explicit repository call required for non-inputs fields
    await repo.update_task_params(
        task_id=task.id,
        params={"processed_at": datetime.now().isoformat()}
    )
```

**Pattern 3: Query Other Tasks**:
```python
from apflow import register_task_tree_hook, get_hook_repository

@register_task_tree_hook("on_tree_completed")
async def aggregate_results(root_task, status):
    repo = get_hook_repository()
    
    # Query dependent tasks
    all_tasks = await repo.list_tasks_by_root_task_id(root_task.id)
    
    # Aggregate and update
    total_tokens = sum(t.result.get("token_usage", 0) for t in all_tasks if t.result)
    await repo.update_task_result(
        task_id=root_task.id,
        result={"total_tokens": total_tokens}
    )
```

## 4. Error Handling and Cleanup

### 4.1 Exception Propagation

**Task Execution Errors**:
```python
try:
    task_result = await self._execute_task_with_schemas(task, final_inputs)
except Exception as e:
    # Update task status to failed
    await self.task_repository.update_task_status(
        task_id=task_id,
        status="failed",
        error=str(e),
        completed_at=datetime.now(timezone.utc)
    )
    raise  # Re-raise to propagate to tree level
```

**Hook Errors** (lines 924-929 in task_manager.py):
```python
try:
    if iscoroutinefunction(hook):
        await hook(task)
    else:
        await asyncio.to_thread(hook, task)
except Exception as e:
    # Log error but don't fail the task execution
    logger.warning(f"Pre-hook {hook.__name__} failed for task {task.id}: {str(e)}. Continuing with task execution.")
```

**Design Decision**:
- Hook errors are logged but don't fail task execution
- Ensures robustness: one broken hook doesn't break entire system
- Critical hooks should implement their own error handling

### 4.2 Resource Cleanup

**Executor Cleanup** (lines 831-837, 849-856 in task_manager.py):
```python
# Clear executor reference after execution
executor = self._executor_instances.pop(task_id, None)
if executor and hasattr(executor, 'clear_task_context'):
    executor.clear_task_context()
    logger.debug(f"Cleared task context for task {task_id}")
```

**Hook Context Cleanup** (guaranteed by finally):
```python
finally:
    clear_hook_context()  # Always executes
```

**Execution Tracking Cleanup** (in TaskExecutor):
```python
try:
    # ... execution ...
finally:
    await self.end_task_tracking(root_task_id)  # Always executes
```

## 5. Key Lifecycle Relationships

### 5.1 Session ↔ Hook Context

```
TaskExecutor creates session
    ↓
TaskManager receives session
    ↓
set_hook_context(task_repository)  ← Hook context references same session
    ↓
All hooks share this session
    ↓
clear_hook_context()  ← Context cleared
    ↓
Session committed/rolled back by context manager
```

**Important**: Hook context lifetime is WITHIN session lifetime

### 5.2 Concurrent Execution Isolation

```
Execution A (root_task_id=task-1)
├── Session A (thread/async context 1)
├── Hook Context A (ContextVar context 1)
└── TaskTracker entry A

Execution B (root_task_id=task-2)  [concurrent]
├── Session B (thread/async context 2)
├── Hook Context B (ContextVar context 2)
└── TaskTracker entry B

Execution C (root_task_id=task-1)  [rejected]
└── Rejected by TaskTracker (already running)
```

**Guarantees**:
- Different task trees execute independently
- Same task tree cannot execute concurrently
- ContextVar provides context isolation

### 5.3 Hook Execution Order

**Within Single Task**:
```
1. Update to in_progress
2. Resolve dependencies (merge into inputs)
3. Pre-hooks (can modify task.inputs)
4. Auto-persist task.inputs if changed
5. Execute task
6. Update to completed/failed
7. Post-hooks (can read result, modify other fields)
8. Trigger dependent tasks (callbacks)
```

**Within Task Tree**:
```
1. on_tree_created (tree structure created)
2. on_tree_started (execution begins)
3. Tasks execute (priority-based, parallel within priority)
   └── For each task: pre-hooks → execute → post-hooks
4. on_tree_completed/failed (all tasks finished)
```

## 6. Best Practices

### 6.1 For Hook Developers

**DO**:
- Use `get_hook_repository()` for DB access in hooks
- Handle exceptions in your hooks (don't rely on framework catching them)
- Keep hooks fast (they block task execution)
- Modify `task.inputs` directly in pre-hooks (auto-persists)
- Use explicit repository calls for other fields

**DON'T**:
- Create new sessions in hooks (use provided session)
- Perform long-running operations in hooks
- Assume hook execution order across different tasks
- Modify task attributes without repository methods (except task.inputs in pre-hooks)

### 6.2 For Extension Developers

**DO**:
- Register hooks at application startup (before TaskExecutor creation)
- Test hooks with concurrent task tree executions
- Document hook requirements and side effects
- Implement proper error handling in hooks

**DON'T**:
- Register hooks dynamically during execution
- Share mutable state between hook invocations
- Rely on hook execution order guarantees

### 6.3 For Framework Users

**DO**:
- Understand session lifecycle when debugging
- Use concurrent execution protection (already built-in)
- Monitor hook errors in logs
- Test task trees with various failure scenarios

**DON'T**:
- Execute same task tree concurrently (automatically prevented)
- Assume atomic rollback across multiple tasks (per-operation commits)
- Rely on hook execution for critical business logic (they can fail silently)

## 7. Summary

### Session Lifecycle
- **Scope**: Entire task tree execution
- **Creation**: TaskExecutor.execute_task_tree()
- **Cleanup**: Automatic via async context manager
- **Strategy**: Per-operation commits (no cascading rollbacks)

### Hook Context Lifecycle
- **Scope**: Entire task tree execution (same as session)
- **Setup**: set_hook_context() at distribute_task_tree entry
- **Cleanup**: clear_hook_context() in finally block (guaranteed)
- **Isolation**: ContextVar provides per-execution context

### Execution Lifecycle
- **Entry**: TaskExecutor.execute_task_tree()
- **Distribution**: TaskManager.distribute_task_tree()
- **Execution**: Priority-based, parallel within priority
- **Cleanup**: Guaranteed via try/finally blocks

### Key Guarantees
1. Hook context is always cleared (finally block)
2. Execution tracking is always cleaned up (finally block)
3. Each task's status updates are persisted immediately (per-operation commits)
4. Concurrent execution of same task tree is prevented (TaskTracker)
5. Hooks share same session as task execution (ContextVar)
6. Context isolation between concurrent task trees (ContextVar)

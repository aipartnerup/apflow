# Aggregate Results Design Analysis

## Problem Background

`aggregate_results` is a feature for aggregating dependency task results. The current implementation is a built-in special handling in TaskManager. We need to analyze whether it should be:
1. A built-in TaskManager feature (current implementation)
2. An executor
3. Support hooks

## Solution Comparison

### Solution 1: As TaskManager Built-in Feature (Original Implementation)

**Advantages:**
- ✅ Simple and direct, no additional executor needed
- ✅ Good performance, no executor instance creation required
- ✅ Centralized logic, core functionality of task orchestration
- ✅ Tightly integrated with dependency resolution flow

**Disadvantages:**
- ❌ Poor extensibility, custom aggregation logic requires modifying TaskManager
- ❌ Inconsistent with executor system, adds special handling
- ❌ Hard-coded logic, difficult to support multiple aggregation strategies
- ❌ High testing and maintenance costs (special path)

### Solution 2: As Executor (Recommended)

**Advantages:**
- ✅ Consistent architecture, all execution logic goes through executor
- ✅ High extensibility, users can create custom aggregation executors
- ✅ Users can customize aggregation logic without modifying the framework
- ✅ Follows single responsibility principle
- ✅ Reuses executor's testing, registration, and lifecycle management

**Disadvantages:**
- ⚠️ Requires creating an executor class (but it's simple)
- ⚠️ Requires registering executor (done automatically)

### Solution 3: Support Hooks (post-hook)

**Advantages:**
- ✅ High flexibility, users can customize aggregation in post-hook
- ✅ No framework code modification needed

**Disadvantages:**
- ❌ Aggregation logic is scattered, not centralized
- ❌ For complex aggregation scenarios, hooks may not be intuitive enough
- ❌ Requires users to understand hooks mechanism
- ❌ Cannot be executed as an independent task (hooks are callbacks after task completion)

## Final Solution: Solution 2 (As Executor) + Backward Compatibility

### Design Decision

**Reasons for adopting Solution 2 (As Executor):**

1. **Architectural Consistency**: All execution logic goes through executor, reducing special handling
2. **Extensibility**: Users can create custom aggregation strategies without modifying the framework
3. **Maintainability**: Unified executor interface, easy to test and maintain
4. **Backward Compatibility**: Keep built-in implementation as fallback, existing code doesn't need changes

### Implementation Details

#### 1. Create AggregateResultsExecutor

Location: `src/apflow/extensions/core/aggregate_results_executor.py`

- Implements `BaseTask` interface
- Uses `@executor_register()` for automatic registration
- ID: `aggregate_results_executor`
- Extracts dependency results from inputs and aggregates them

#### 2. Modify TaskManager to Support Backward Compatibility

- Keep support for `method="aggregate_results"` (deprecated)
- Prefer using `aggregate_results_executor`
- Fallback to built-in implementation if executor is not registered

#### 3. Usage

**New Way (Recommended):**
```python
{
    "schemas": {
        "input_schema": {...}
    },
    "params": {
        "executor_id": "aggregate_results_executor"
    },
    "dependencies": [
        {"id": "task-1", "required": True},
        {"id": "task-2", "required": True}
    ],
    "inputs": {}  # Dependency results will be automatically merged here
}
```

**Old Way (Backward Compatible, Deprecated):**
```python
{
    "schemas": {
        "method": "aggregate_results"  # Still supported, but will show warning
    },
    "dependencies": [...],
    "inputs": {}
}
```

### Extensibility Example

Users can create custom aggregation executors:

```python
@executor_register()
class CustomAggregator(BaseTask):
    id = "custom_aggregator"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Custom aggregation logic
        # For example: calculate average, merge specific fields, etc.
        return aggregated_result
```

## Summary

**Recommended Solution: Solution 2 (As Executor)**

- ✅ Consistent architecture, easy to maintain
- ✅ High extensibility, supports customization
- ✅ Backward compatible, doesn't affect existing code
- ✅ Follows framework design principles

**Reasons for not recommending Solution 3 (Hooks):**
- Hooks are more suitable for post-task processing (logging, notifications, etc.)
- Aggregation is core logic of task execution, should be an independent task/executor
- Hooks cannot be executed as independent tasks, limited flexibility


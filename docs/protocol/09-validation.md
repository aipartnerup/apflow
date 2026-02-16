# Validation Rules and Algorithms

This document defines the validation rules and algorithms that implementations MUST follow to ensure protocol compliance.

## Validation Principles

**MUST**: All implementations MUST validate data according to the rules defined in this document.

**MUST**: Implementations MUST reject invalid data with appropriate error codes.

**SHOULD**: Implementations SHOULD provide detailed validation error messages.

## Task Validation

### Schema Validation


Tasks MUST be validated against the JSON Schema defined in [Data Model](03-data-model.md), including provenance/reference fields:
- `origin_type` MUST be one of: `create`, `link`, `copy`, `archive`, or null.
- If `origin_type` is `link` or `archive`, `original_task_id` MUST reference a task in `completed` status (in principle).
- `original_task_id` MUST be a valid UUID v4 if present.
- `has_references` MUST be a boolean.

**Algorithm**:
```
function validateTaskSchema(task):
    // 1. Check required fields
    if not task.id:
        return error("id is required")
    if not task.name:
        return error("name is required")
    if not task.status:
        return error("status is required")
    
    // 2. Validate field types
    if not isValidUUID(task.id):
        return error("id must be valid UUID v4")
    if not isinstance(task.name, str) or len(task.name) == 0:
        return error("name must be non-empty string")
    if task.status not in ["pending", "in_progress", "completed", "failed", "cancelled"]:
        return error("status must be one of: pending, in_progress, completed, failed, cancelled")
    
    // 3. Validate field constraints
    if task.priority is not None:
        if not isinstance(task.priority, int) or task.priority < 0 or task.priority > 3:
            return error("priority must be integer in range 0-3")
    
    if task.progress is not None:
        if not isinstance(task.progress, (int, float)) or task.progress < 0.0 or task.progress > 1.0:
            return error("progress must be number in range 0.0-1.0")
    
    // 4. Validate field relationships
    if task.status == "completed" and task.result is None:
        return warning("result should be populated when status is completed")
    
    if task.status in ["failed", "cancelled"] and (task.error is None or len(task.error) == 0):
        return warning("error should be populated when status is failed or cancelled")
    
    if task.status == "pending" and task.started_at is not None:
        return error("started_at must be null when status is pending")
    
    if task.status == "in_progress" and task.started_at is None:
        return error("started_at must be set when status is in_progress")
    
    if task.status in ["completed", "failed", "cancelled"] and task.completed_at is None:
        return error("completed_at must be set when status is terminal")
    
    // 5. Validate UUIDs
    if task.parent_id is not None and not isValidUUID(task.parent_id):
        return error("parent_id must be valid UUID v4")
    
    // 6. Validate inputs against schema
    if task.schemas and task.schemas.input_schema:
        if not validateJSONSchema(task.inputs, task.schemas.input_schema):
            return error("inputs do not conform to input_schema")
    
    return success
```

**MUST**: Implementations MUST perform all validation checks listed above.

### Field Consistency Validation

Tasks MUST have consistent field values based on their status.

**Rules**:
1. If `status` is `completed`, `result` SHOULD NOT be `null`.
2. If `status` is `failed` or `cancelled`, `error` SHOULD NOT be `null`.
3. If `status` is `pending`, `started_at` MUST be `null`.
4. If `status` is `in_progress`, `started_at` MUST NOT be `null`.
5. If `status` is terminal (`completed`, `failed`, `cancelled`), `completed_at` MUST NOT be `null`.
6. `progress` MUST be in range [0.0, 1.0].

**Algorithm**:
```
function validateFieldConsistency(task):
    errors = []
    
    if task.status == "completed" and task.result is None:
        errors.append("result should be populated when status is completed")
    
    if task.status in ["failed", "cancelled"]:
        if task.error is None or len(task.error) == 0:
            errors.append("error must be populated when status is failed or cancelled")
    
    if task.status == "pending":
        if task.started_at is not None:
            errors.append("started_at must be null when status is pending")
    
    if task.status == "in_progress":
        if task.started_at is None:
            errors.append("started_at must be set when status is in_progress")
    
    if task.status in ["completed", "failed", "cancelled"]:
        if task.completed_at is None:
            errors.append("completed_at must be set when status is terminal")
    
    if task.progress is not None:
        if task.progress < 0.0 or task.progress > 1.0:
            errors.append("progress must be in range 0.0-1.0")
    
    return errors
```

## Dependency Validation

### Reference Validation

All dependency IDs MUST reference existing tasks.

**Algorithm**:
```
function validateDependencyReferences(task, allTasks):
    errors = []
    
    for dependency in task.dependencies:
        dep_id = dependency.id
        
        // Check if dependency task exists
        if dep_id not in [t.id for t in allTasks]:
            errors.append(f"Dependency task '{dep_id}' not found")
        
        // Check self-reference
        if dep_id == task.id:
            errors.append("Task cannot depend on itself")
    
    return errors
```

**MUST**: Implementations MUST validate that all dependency IDs reference existing tasks.

**MUST**: Implementations MUST reject self-references (task depending on itself).

### Circular Dependency Detection

Dependencies MUST NOT form cycles.

**Algorithm** (Depth-First Search):
```
function hasCircularDependency(task, allTasks, visited=None, recStack=None):
    if visited is None:
        visited = set()
    if recStack is None:
        recStack = set()
    
    // Mark current task as visited and add to recursion stack
    visited.add(task.id)
    recStack.add(task.id)
    
    // Check all dependencies
    for dependency in task.dependencies:
        dep_id = dependency.id
        dep_task = findTask(dep_id, allTasks)
        
        if dep_task is None:
            continue  // Skip invalid references (handled separately)
        
        // If dependency not visited, recurse
        if dep_id not in visited:
            if hasCircularDependency(dep_task, allTasks, visited, recStack):
                return true
        
        // If dependency is in recursion stack, cycle detected
        elif dep_id in recStack:
            return true
    
    // Remove from recursion stack (backtrack)
    recStack.remove(task.id)
    return false
```

**MUST**: Implementations MUST detect circular dependencies.

**MUST**: Implementations MUST reject task definitions with circular dependencies.

**Example**:
```
Task A depends on Task B
Task B depends on Task C
Task C depends on Task A  // Cycle detected!
```

### Dependency Satisfaction Validation

When validating if a task can execute, dependencies MUST be checked.

**Algorithm**:
```
function validateDependencySatisfaction(task, allTasks):
    for dependency in task.dependencies:
        dep_id = dependency.id
        dep_task = findTask(dep_id, allTasks)
        
        if dep_task is None:
            return false  // Invalid reference
        
        // Check if dependency is ready
        if dep_task.status == "pending" or dep_task.status == "in_progress":
            return false  // Dependency not ready
        
        // Check required dependencies
        if dependency.required == true:
            if dep_task.status != "completed":
                return false  // Required dependency failed
    
    return true  // All dependencies satisfied
```

## Task Tree Validation

### Root Task Validation

A task tree MUST have exactly one root task.

**Algorithm**:
```
function validateRootTask(allTasks):
    roots = [task for task in allTasks if task.parent_id is None]
    
    if len(roots) == 0:
        return error("No root task found")
    
    if len(roots) > 1:
        return error(f"Multiple root tasks found: {[r.id for r in roots]}")
    
    return success
```

**MUST**: Implementations MUST validate that there is exactly one root task.

### Parent-Child Consistency Validation

All `parent_id` values MUST reference valid parent tasks.

**Algorithm**:
```
function validateParentChildConsistency(allTasks):
    errors = []
    taskIds = {task.id for task in allTasks}
    
    for task in allTasks:
        if task.parent_id is not None:
            if task.parent_id not in taskIds:
                errors.append(f"Task '{task.id}' has invalid parent_id: '{task.parent_id}'")
    
    return errors
```

**MUST**: Implementations MUST validate that all `parent_id` values reference existing tasks.

### Tree Acyclicity Validation

Parent-child relationships MUST NOT form cycles.

**Algorithm**:
```
function hasCircularParentChild(task, allTasks, visited=None):
    if visited is None:
        visited = set()
    
    if task.id in visited:
        return true  // Cycle detected
    
    visited.add(task.id)
    
    if task.parent_id is not None:
        parent = findTask(task.parent_id, allTasks)
        if parent and hasCircularParentChild(parent, allTasks, visited):
            return true
    
    visited.remove(task.id)
    return false
```

**MUST**: Implementations MUST detect circular parent-child relationships.

**MUST**: Implementations MUST reject task trees with circular parent-child relationships.

### Tree Completeness Validation

All referenced tasks MUST be present in the tree.

**Algorithm**:
```
function validateTreeCompleteness(rootTask, allTasks):
    errors = []
    taskIds = {task.id for task in allTasks}
    
    // Check all parent references
    for task in allTasks:
        if task.parent_id is not None and task.parent_id not in taskIds:
            errors.append(f"Task '{task.id}' references non-existent parent: '{task.parent_id}'")
    
    // Check all dependency references
    for task in allTasks:
        for dependency in task.dependencies:
            if dependency.id not in taskIds:
                errors.append(f"Task '{task.id}' references non-existent dependency: '{dependency.id}'")
    
    return errors
```

**MUST**: Implementations MUST validate that all referenced tasks exist in the tree.

## Input Validation

### Schema-Based Validation

If `schemas.input_schema` is present, `inputs` MUST conform to the schema.

**Algorithm**:
```
function validateInputsAgainstSchema(inputs, inputSchema):
    // Use JSON Schema validator
    validator = JSONSchemaValidator(inputSchema)
    
    try:
        validator.validate(inputs)
        return success
    except ValidationError as e:
        return error(f"Input validation failed: {e.message}")
```

**MUST**: Implementations MUST validate `inputs` against `schemas.input_schema` if present.

**SHOULD**: Implementations SHOULD use a JSON Schema validator (draft-07).

### Executor-Specific Validation

Executors MAY provide additional input validation.

**Algorithm**:
```
function validateExecutorInputs(task, executor):
    // 1. Check if executor exists
    if executor is None:
        return error("Executor not found")
    
    // 2. Validate against executor's input schema (if provided)
    if hasattr(executor, 'get_input_schema'):
        schema = executor.get_input_schema()
        if not validateJSONSchema(task.inputs, schema):
            return error("Inputs do not conform to executor's input schema")
    
    // 3. Executor-specific validation (if provided)
    if hasattr(executor, 'validate_inputs'):
        try:
            executor.validate_inputs(task.inputs)
        except ValidationError as e:
            return error(f"Executor validation failed: {e.message}")
    
    return success
```

**SHOULD**: Implementations SHOULD validate inputs using executor's validation if available.

## State Transition Validation

State transitions MUST follow the state machine rules.

**Algorithm**:
```
function validateStateTransition(currentStatus, newStatus):
    validTransitions = {
        "pending": ["in_progress", "cancelled"],
        "in_progress": ["completed", "failed", "cancelled"],
        "failed": ["pending"],  // Re-execution
        "completed": [],  // Terminal state
        "cancelled": []  // Terminal state
    }
    
    if newStatus not in validTransitions.get(currentStatus, []):
        return error(f"Invalid state transition: {currentStatus} -> {newStatus}")
    
    return success
```

**MUST**: Implementations MUST validate state transitions.

**MUST**: Implementations MUST reject invalid state transitions.

## UUID Validation

All UUID fields MUST be valid UUID v4 format.

**Algorithm**:
```
function isValidUUID(value):
    if not isinstance(value, str):
        return false
    
    // UUID v4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    return re.match(pattern, value.lower()) is not None
```

**MUST**: Implementations MUST validate UUID format for `id`, `parent_id`, and dependency IDs.

## Timestamp Validation

All timestamp fields MUST be valid ISO 8601 format.

**Algorithm**:
```
function isValidTimestamp(value):
    if value is None:
        return true  // Null is valid
    
    if not isinstance(value, str):
        return false
    
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return true
    except ValueError:
        return false
```

**MUST**: Implementations MUST validate timestamp format.

**SHOULD**: Implementations SHOULD use UTC timezone for timestamps.

## Validation Error Reporting

### Error Format

Validation errors MUST be reported in a structured format.

**Format**:
```json
{
  "field": "field_name",
  "reason": "Validation reason",
  "expected": "Expected value or format",
  "actual": "Actual value",
  "path": ["nested", "field", "path"]
}
```

### Error Aggregation

Multiple validation errors SHOULD be aggregated and returned together.

**Example**:
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "errors": [
        {
          "field": "priority",
          "reason": "Value out of range",
          "expected": "0-3",
          "actual": 5
        },
        {
          "field": "progress",
          "reason": "Value out of range",
          "expected": "0.0-1.0",
          "actual": 1.5
        }
      ]
    }
  },
  "id": "req-001"
}
```

## Implementation Requirements

**MUST**: Implementations MUST perform all validation checks defined in this document.

**MUST**: Implementations MUST reject invalid data with appropriate error codes.

**SHOULD**: Implementations SHOULD provide detailed validation error messages.

**SHOULD**: Implementations SHOULD aggregate multiple validation errors when possible.

## See Also

- [Data Model](03-data-model.md) - Task schema definitions
- [Execution Lifecycle](04-execution-lifecycle.md) - State machine rules
- [Error Handling](08-errors.md) - Error codes and handling
- [Conformance](07-conformance.md) - Validation requirements


### Complete Field Specification
| Field | Type | Required | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | String (UUID v4) | Yes | - | Must be valid UUID v4 | Unique identifier for the task. MUST be unique across all tasks. |
| `parent_id` | String (UUID v4) | No | `null` | Must be valid UUID v4 if present | ID of the parent task (if part of a hierarchy). Used for organizational purposes only, does not affect execution order. |
| `user_id` | String | No | `null` | Non-empty string if present | User identifier for multi-tenant scenarios. Used for access control and filtering. |
| `name` | String | Yes | - | Non-empty string, max 255 chars | Name or method identifier of the task. MUST match a registered executor's identifier when `schemas.method` is present. |
| `status` | String (enum) | Yes | `"pending"` | One of: `pending`, `in_progress`, `completed`, `failed`, `cancelled` | Current execution state. See [Execution Lifecycle](04-execution-lifecycle.md) for state machine details. |
| `priority` | Integer | No | `2` | Range: 0-3 (0=urgent, 1=high, 2=normal, 3=low) | Execution priority. Lower values = higher priority. Used for scheduling when multiple tasks are ready. |
| `inputs` | Object (JSON) | No | `{}` | Valid JSON object | **Runtime** input parameters for the executor. Contains the actual data to be processed. |
| `schemas` | Object (JSON) | No | `null` | Valid JSON object | **Configuration** and method definition. Defines *which* executor to use and *how* to validate inputs. |
| `params` | Object (JSON) | No | `null` | Valid JSON object | Additional executor-specific parameters. Used for executor configuration beyond `schemas`. |
| `result` | Object (JSON) | No | `null` | Valid JSON object | Execution result. MUST be `null` when status is not `completed`. SHOULD be populated when status is `completed`. |
| `error` | String | No | `null` | Non-empty string if present | Error message. MUST be `null` when status is not `failed` or `cancelled`. SHOULD be populated when status is `failed` or `cancelled`. |
| `dependencies` | Array | No | `[]` | Array of Dependency objects | List of dependencies that must be satisfied before execution. See [Dependency Schema](#dependency-schema) for structure. |
| `progress` | Number (float) | No | `0.0` | Range: 0.0-1.0 | Execution progress as a fraction (0.0 = not started, 1.0 = complete). SHOULD be updated during execution. |
| `created_at` | String (ISO 8601) | No | Current timestamp | Valid ISO 8601 datetime | Task creation timestamp. SHOULD be set when task is created. |
| `started_at` | String (ISO 8601) | No | `null` | Valid ISO 8601 datetime or null | Task execution start timestamp. MUST be `null` when status is `pending`. SHOULD be set when status transitions to `in_progress`. |
| `updated_at` | String (ISO 8601) | No | Current timestamp | Valid ISO 8601 datetime | Last update timestamp. SHOULD be updated whenever task is modified. |
| `completed_at` | String (ISO 8601) | No | `null` | Valid ISO 8601 datetime or null | Task completion timestamp. MUST be `null` when status is not terminal (`completed`, `failed`, `cancelled`). SHOULD be set when status transitions to terminal state. |
| `origin_type` | String (enum) | No | `null` | One of: `create`, `link`, `copy`, `archive` | Origin of the task definition. See below for meaning. |
| `original_task_id` | String (UUID v4) | No | `null` | Must be valid UUID v4 if present | Source task ID if this task was copied, linked, or snapshotted. |
| `has_references` | Boolean | No | `false` | - | Whether this task is referenced/copied by others. |
| `schedule_type` | String (enum) | No | `null` | One of: `once`, `interval`, `cron`, `daily`, `weekly`, `monthly` | Scheduling mode for recurring execution. See [Scheduling Fields](#scheduling-fields). |
| `schedule_expression` | String | No | `null` | Non-empty string if present | Schedule expression format depends on `schedule_type` (e.g., cron string, interval seconds). |
| `schedule_enabled` | Boolean | No | `false` | - | Whether scheduling is enabled for this task. |
| `schedule_start_at` | String (ISO 8601) | No | `null` | Valid ISO 8601 datetime or null | Earliest time the schedule can trigger. |
| `schedule_end_at` | String (ISO 8601) | No | `null` | Valid ISO 8601 datetime or null | Latest time the schedule can trigger (after this, scheduling is disabled). |
| `next_run_at` | String (ISO 8601) | No | `null` | Valid ISO 8601 datetime or null | Next scheduled execution time (computed). |
| `last_run_at` | String (ISO 8601) | No | `null` | Valid ISO 8601 datetime or null | Last time this scheduled task was executed. |
| `max_runs` | Integer | No | `null` | Non-negative integer if present | Maximum number of scheduled runs (null = unlimited). |
| `run_count` | Integer | No | `0` | Non-negative integer | Number of times this scheduled task has executed. |

### Auxiliary Fields (Database Optimization)

These fields are not required by the protocol, but are recommended for database implementations to optimize queries and tree operations:

| Field           | Type    | Description                                                        |
|-----------------|---------|--------------------------------------------------------------------|
| `task_tree_id`  | String  | Identifier for the task tree. Used to efficiently query all tasks in a tree. |
| `has_children`  | Boolean | Indicates if the task has child tasks. Used for fast child lookup. |

> **Note:** These fields are for implementation convenience and do not affect protocol behavior.

#### `origin_type` values

| Value      | Description                                                        |
|------------|--------------------------------------------------------------------|
| `create`   | Task created freshly                                               |
| `link`     | Task linked from another. **The source task MUST be in `completed` status (in principle).** |
| `copy`     | Task copied from another (can be modified)                         |
| `archive` | Task archive from another (cannot be modified). **The source task MUST be in `completed` status (in principle).** |

### Field Relationships and Constraints

**MUST**:
  - If `status` is `completed`, `result` SHOULD NOT be `null`.
  - If `status` is `failed` or `cancelled`, `error` SHOULD NOT be `null`.
  - If `status` is `pending`, `started_at` MUST be `null`.
  - If `status` is `in_progress`, `started_at` MUST NOT be `null`.
  - If `status` is terminal (`completed`, `failed`, `cancelled`), `completed_at` MUST NOT be `null`.
  - If `parent_id` is present, the referenced task MUST exist in the same flow.
  - All dependency IDs in `dependencies` MUST reference existing tasks in the same flow.
  - `progress` MUST be in range [0.0, 1.0].
  - If `origin_type` is `link` or `archive`, the `original_task_id` MUST reference a task in `completed` status (in principle).
  - If `schedule_enabled` is `true`, `schedule_type` and `schedule_expression` MUST NOT be `null`.
  - If `max_runs` is present, `run_count` MUST be less than or equal to `max_runs`.
  - If `schedule_end_at` is present, `next_run_at` MUST be `null` or not later than `schedule_end_at`.

### Scheduling Fields

Scheduling allows a task definition to trigger repeatedly. Scheduling fields do **not** alter dependency rules; they only determine when a task becomes ready to run.

**Schedule types**:
- `once`: Execute at a single specified time.
- `interval`: Execute every fixed number of seconds.
- `cron`: Execute using a cron expression.
- `daily`: Execute once per day at a specific time.
- `weekly`: Execute on specific weekdays at a specific time.
- `monthly`: Execute on specific dates each month.

**Schedule expressions**:
- `once`: ISO 8601 datetime (e.g., `2025-01-20T09:00:00Z`).
- `interval`: Integer seconds as a string (e.g., `"3600"`).
- `cron`: Standard 5-field cron (e.g., `"0 9 * * 1-5"`).
- `daily`: `HH:MM` in 24-hour format (e.g., `"09:30"`).
- `weekly`: `WEEKDAY@HH:MM` (e.g., `"mon,wed@09:30"`).
- `monthly`: `DAY@HH:MM` (e.g., `"1,15@09:30"`).

**Notes**:
- `next_run_at` is calculated by the scheduler and is read-only for clients.
- When `schedule_enabled` is `false`, scheduling fields MAY be present but are ignored.
- Scheduling scope is hierarchical: if the **root task** has scheduling enabled, the schedule applies to the **entire task tree**. If only a **child task** has scheduling enabled, the schedule applies **only to that child task and its dependency chain**.

### JSON Schema Definition

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "name", "status"],
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for the task (UUID v4)"
    },
    "parent_id": {
      "type": ["string", "null"],
      "format": "uuid",
      "description": "ID of the parent task (organizational only)"
    },
    "user_id": {
      "type": ["string", "null"],
      "minLength": 1,
      "description": "User identifier for multi-tenant scenarios"
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 255,
      "description": "Name or method identifier of the task"
    },
    "status": {
      "type": "string",
      "enum": ["pending", "in_progress", "completed", "failed", "cancelled"],
      "description": "Current execution state"
    },
    "priority": {
      "type": "integer",
      "minimum": 0,
      "maximum": 3,
      "default": 2,
      "description": "Execution priority (0=urgent, 1=high, 2=normal, 3=low)"
    },
    "inputs": {
      "type": "object",
      "default": {},
      "description": "Runtime input parameters for the executor"
    },
    "schemas": {
      "type": ["object", "null"],
      "description": "Configuration and method definition",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["local", "remote", "external"],
          "description": "Executor type"
        },
        "method": {
          "type": "string",
          "minLength": 1,
          "description": "Executor identifier (executor.id). MUST match a registered executor identifier in the ExecutorRegistry."
        },
        "input_schema": {
          "type": "object",
          "description": "JSON Schema (draft-07) defining valid inputs"
        },
        "model": {
          "type": "string",
          "description": "Model identifier (for LLM executors)"
        }
      },
      "required": ["method"],
      "additionalProperties": true
    },
    "params": {
      "type": ["object", "null"],
      "description": "Additional executor-specific parameters"
    },
    "result": {
      "type": ["object", "null"],
      "description": "Execution result (populated when status is completed)"
    },
    "error": {
      "type": "string",
      "description": "Error message (populated when status is failed or cancelled)"
    },
    "dependencies": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/dependency"
      },
      "default": [],
      "description": "List of dependencies that must be satisfied before execution"
    },
    "progress": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "default": 0.0,
      "description": "Execution progress as a fraction"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "Task creation timestamp (ISO 8601)"
    },
    "started_at": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": "Task execution start timestamp (ISO 8601)"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "Last update timestamp (ISO 8601)"
    },
    "completed_at": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": "Task completion timestamp (ISO 8601)"
    },
    "origin_type": {
      "type": ["string", "null"],
      "enum": ["create", "link", "copy", "archive", null],
      "description": "Origin of the task definition. One of: create, link, copy, archive. For link/archive, the source task MUST be completed."
    },
    "original_task_id": {
      "type": ["string", "null"],
      "format": "uuid",
      "description": "Source task ID if this task was copied, linked, or snapshotted."
    },
    "has_references": {
      "type": "boolean",
      "default": false,
      "description": "Whether this task is referenced/copied by others."
    },
    "schedule_type": {
      "type": ["string", "null"],
      "enum": ["once", "interval", "cron", "daily", "weekly", "monthly", null],
      "description": "Scheduling mode for recurring execution."
    },
    "schedule_expression": {
      "type": ["string", "null"],
      "description": "Schedule expression (format depends on schedule_type)."
    },
    "schedule_enabled": {
      "type": "boolean",
      "default": false,
      "description": "Whether scheduling is enabled for this task."
    },
    "schedule_start_at": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": "Earliest time the schedule can trigger (ISO 8601)."
    },
    "schedule_end_at": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": "Latest time the schedule can trigger (ISO 8601)."
    },
    "next_run_at": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": "Next scheduled execution time (computed)."
    },
    "last_run_at": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": "Last scheduled execution time (ISO 8601)."
    },
    "max_runs": {
      "type": ["integer", "null"],
      "minimum": 0,
      "description": "Maximum number of scheduled runs (null = unlimited)."
    },
    "run_count": {
      "type": "integer",
      "minimum": 0,
      "default": 0,
      "description": "Number of times this scheduled task has executed."
    }
  },
  "definitions": {
    "dependency": {
      "type": "object",
      "required": ["id"],
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid",
          "description": "ID of the task to depend on"
        },
        "required": {
          "type": "boolean",
          "default": true,
          "description": "If true, the dependent task must complete successfully"
        }
      }
    }
  }
}
```
### Complete Task Example

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "parent_id": "660e8400-e29b-41d4-a716-446655440001",
  "user_id": "user-123",
  "name": "Crawl Website",
  "status": "pending",
  "priority": 1,
  "inputs": {
    "url": "https://example.com",
    "timeout": 60
  },
  "schemas": {
    "type": "local",
    "method": "web_crawler",
    "input_schema": {
      "type": "object",
      "required": ["url"],
      "properties": {
        "url": {
          "type": "string",
          "format": "uri"
        },
        "timeout": {
          "type": "integer",
          "minimum": 1,
          "default": 30
        }
      }
    }
  },
  "params": {
    "retry_count": 3,
    "user_agent": "MyCrawler/1.0"
  },
  "result": null,
  "error": null,
  "dependencies": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "required": true
    }
  ],
  "progress": 0.0,
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": null,
  "updated_at": "2025-01-15T10:30:00Z",
  "completed_at": null,
  "origin_type": "copy",
  "original_task_id": "550e8400-e29b-41d4-a716-446655440003",
  "has_references": false,
  "schedule_type": "weekly",
  "schedule_expression": "mon,wed@09:30",
  "schedule_enabled": true,
  "schedule_start_at": "2025-01-20T00:00:00Z",
  "schedule_end_at": null,
  "next_run_at": "2025-01-22T09:30:00Z",
  "last_run_at": null,
  "max_runs": null,
  "run_count": 0
}
```


### Inputs vs Schemas

It is **critical** to distinguish between `inputs` and `schemas`:

#### `schemas` - Static Configuration

**Purpose**: Defines the **Method** and **Static Configuration**. It tells the system *which* executor to use and provides configuration that doesn't change between runs.

**Structure**:
```json
{
  "type": "local" | "remote" | "external",
  "method": "executor_identifier",
  "input_schema": {
    // JSON Schema defining valid inputs
  }
}
```

**Fields**:
- `type` (string, optional): Executor type. Values: `"local"` (same process), `"remote"` (different process), `"external"` (external service).
- `method` (string, **required**): The executor identifier. MUST be the executor.id (registered executor identifier) used to look up the executor in the `ExecutorRegistry`. MUST match a registered executor identifier.
- `input_schema` (object, optional): JSON Schema (draft-07) defining what `inputs` are valid. Used for validation before execution.

**Example**:
```json
{
  "schemas": {
    "type": "local",
    "method": "web_crawler",
    "input_schema": {
      "type": "object",
      "required": ["url"],
      "properties": {
        "url": {
          "type": "string",
          "format": "uri",
          "description": "URL to crawl"
        },
        "timeout": {
          "type": "integer",
          "minimum": 1,
          "default": 30,
          "description": "Timeout in seconds"
        }
      }
    }
  }
}
```

#### `inputs` - Runtime Data

**Purpose**: Defines the **Runtime Data**. It contains the actual data to be processed in this specific execution.

**Structure**: Any valid JSON object that conforms to `schemas.input_schema` (if present).

**Example**:
```json
{
  "inputs": {
    "url": "https://example.com",
    "timeout": 60
  }
}
```

**Validation Rules**:
- **MUST**: If `schemas.input_schema` is present, `inputs` MUST conform to the schema.
- **SHOULD**: Implementations SHOULD validate `inputs` against `schemas.input_schema` before execution.
- **MAY**: If `schemas.input_schema` is not present, `inputs` can be any valid JSON object.

### Complete Task Example

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "parent_id": "660e8400-e29b-41d4-a716-446655440001",
  "user_id": "user-123",
  "name": "Crawl Website",
  "status": "pending",
  "priority": 1,
  "inputs": {
    "url": "https://example.com",
    "timeout": 60
  },
  "schemas": {
    "type": "local",
    "method": "web_crawler",
    "input_schema": {
      "type": "object",
      "required": ["url"],
      "properties": {
        "url": {
          "type": "string",
          "format": "uri"
        },
        "timeout": {
          "type": "integer",
          "minimum": 1,
          "default": 30
        }
      }
    }
  },
  "params": {
    "retry_count": 3,
    "user_agent": "MyCrawler/1.0"
  },
  "result": null,
  "error": null,
  "dependencies": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "required": true
    }
  ],
  "progress": 0.0,
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": null,
  "updated_at": "2025-01-15T10:30:00Z",
  "completed_at": null,
  "schedule_type": "interval",
  "schedule_expression": "3600",
  "schedule_enabled": true,
  "schedule_start_at": "2025-01-15T10:30:00Z",
  "schedule_end_at": null,
  "next_run_at": "2025-01-15T11:30:00Z",
  "last_run_at": null,
  "max_runs": null,
  "run_count": 0
}
```

## Dependency Schema

Dependencies define the execution order. A task with dependencies will wait for those tasks to complete before executing.

### Dependency Object Specification

| Field | Type | Required | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | String (UUID v4) | Yes | - | Must be valid UUID v4, must reference existing task | ID of the task to depend on. MUST reference a task in the same flow. |
| `required` | Boolean | No | `true` | - | If `true`, the dependent task MUST complete successfully. If `false`, the task can execute even if the dependency fails. |

### Dependency Validation Rules

**MUST**:
- All dependency IDs MUST reference existing tasks in the same flow.
- A task MUST NOT depend on itself (self-reference).
- Dependencies MUST NOT create circular dependencies (see [Validation Rules](#validation-rules)).

**SHOULD**:
- Implementations SHOULD validate dependencies when a task is created or updated.
- Implementations SHOULD detect circular dependencies and reject invalid task definitions.

### Required vs Optional Dependencies

#### Required Dependencies (`required: true`)

**Behavior**:
- The task waits for the dependency to complete.
- If the dependency completes successfully (`status: "completed"`), the task can proceed.
- If the dependency fails (`status: "failed"`), the task MUST NOT execute (unless explicitly allowed by error handling).

**Example**:
```json
{
  "dependencies": [
    {
      "id": "task-123",
      "required": true
    }
  ]
}
```

#### Optional Dependencies (`required: false`)

**Behavior**:
- The task waits for the dependency to complete (or fail).
- The task can execute regardless of whether the dependency succeeds or fails.
- Useful for fallback scenarios or optional data sources.

**Example**:
```json
{
  "dependencies": [
    {
      "id": "primary-task",
      "required": false
    },
    {
      "id": "fallback-task",
      "required": false
    }
  ]
}
```

### Dependency Resolution Algorithm

When determining if a task can execute:

1. **Collect all dependencies**: Get all tasks referenced in the `dependencies` array.
2. **Check each dependency**:
   - If `required: true`:
     - Dependency MUST have `status: "completed"` for the task to proceed.
     - If dependency has `status: "failed"`, the task MUST NOT proceed.
   - If `required: false`:
     - Dependency MUST have a terminal status (`completed`, `failed`, or `cancelled`).
     - Task can proceed regardless of dependency outcome.
3. **All dependencies satisfied**: Task can transition from `pending` to `in_progress`.

See [Execution Lifecycle](04-execution-lifecycle.md) for detailed state machine behavior.

## Task Tree Structure

Tasks are organized in a hierarchical tree structure. The tree represents both organizational relationships (parent-child) and execution dependencies.

### TaskTreeNode Specification

A TaskTreeNode wraps a Task and its children in a recursive structure.

**Structure**:
```json
{
  "task": {
    // Complete Task object (see Task Schema above)
  },
  "children": [
    // Array of TaskTreeNode objects (recursive)
  ]
}
```

### Field Specification

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `task` | Task Object | Yes | The task object. MUST conform to Task Schema. |
| `children` | Array of TaskTreeNode | No | Child nodes. Empty array `[]` if no children. |

### Tree Validation Rules

**MUST**:
- The root task MUST have `parent_id: null`.
- All child tasks MUST have `parent_id` matching their parent's `id`.
- The tree MUST be acyclic (no circular parent-child relationships).
- All tasks in the tree MUST belong to the same flow (same root).

**SHOULD**:
- Implementations SHOULD validate tree structure when building or updating task trees.
- Implementations SHOULD detect and reject invalid tree structures.

### Parent-Child vs Dependencies

**Critical Distinction**:

- **`parent_id` (Parent-Child)**: Organizational relationship only. Used for grouping and visualization. Does NOT affect execution order.
- **`dependencies`**: Execution control. Determines when tasks run. Controls actual execution sequence.

**Example**:
```json
{
  "task": {
    "id": "task-a",
    "name": "Task A",
    "parent_id": "root-task"
  },
  "children": [
    {
      "task": {
        "id": "task-b",
        "name": "Task B",
        "parent_id": "task-a",  // Organizational: B is child of A
        "dependencies": [
          {
            "id": "task-c",  // Execution: B waits for C (not A!)
            "required": true
          }
        ]
      },
      "children": []
    }
  ]
}
```

In this example:
- Task B is **organizationally** a child of Task A.
- Task B **executionally** depends on Task C (not Task A).
- Execution order: Task C runs first, then Task B (regardless of parent-child relationship).

### Tree Serialization Format

When serializing a task tree for transmission:

**MUST**:
- Include complete Task objects (all fields).
- Preserve parent-child relationships.
- Preserve dependency relationships.
- Maintain tree structure integrity.

**SHOULD**:
- Use recursive JSON structure (TaskTreeNode with nested children).
- Include all tasks in the tree, not just the root.

**Example**:
```json
{
  "task": {
    "id": "root-task",
    "name": "Root Task",
    "status": "pending",
    "parent_id": null
  },
  "children": [
    {
      "task": {
        "id": "child-1",
        "name": "Child Task 1",
        "status": "pending",
        "parent_id": "root-task"
      },
      "children": []
    },
    {
      "task": {
        "id": "child-2",
        "name": "Child Task 2",
        "status": "pending",
        "parent_id": "root-task",
        "dependencies": [
          {
            "id": "child-1",
            "required": true
          }
        ]
      },
      "children": []
    }
  ]
}
```

## Result and Error Formats

### Result Format

When a task completes successfully (`status: "completed"`), the `result` field contains the execution result.

**Structure**: Any valid JSON object. The structure is executor-specific.

**MUST**:
- `result` MUST be a valid JSON object (not a primitive value).
- `result` MUST be `null` when status is not `completed`.
- `result` SHOULD be populated when status is `completed`.

**Example**:
```json
{
  "status": "completed",
  "result": {
    "output": "Processed data",
    "metadata": {
      "processing_time": 1.5,
      "items_processed": 100
    }
  }
}
```

### Error Format

When a task fails (`status: "failed"` or `status: "cancelled"`), the `error` field contains the error message.

**Structure**: String containing the error message.

**MUST**:
- `error` MUST be a non-empty string when status is `failed` or `cancelled`.
- `error` MUST be `null` when status is not `failed` or `cancelled`.

**SHOULD**:
- Error messages SHOULD be human-readable.
- Error messages SHOULD include context about what failed.

**Example**:
```json
{
  "status": "failed",
  "error": "Executor 'web_crawler' not found in registry"
}
```

### Progress Format

The `progress` field tracks execution progress as a fraction.

**Type**: Number (float)  
**Range**: 0.0 to 1.0  
**Default**: 0.0

**MUST**:
- `progress` MUST be in range [0.0, 1.0].
- `progress` SHOULD be updated during execution to reflect current progress.

**Example**:
```json
{
  "status": "in_progress",
  "progress": 0.65
}
```

## Executor Registration

The protocol supports extending functionality via custom executors. Executors are registered with an `ExecutorRegistry` using a unique identifier (the `method` name).

### Executor Categories

Executors can be categorized by their source and availability:

1. **Built-in Executors**: Provided by the framework implementation
   - System executors (e.g., `system_info_executor`, `command_executor`)
   - Data processing executors (e.g., `aggregate_results_executor`)
   - Tool executors (e.g., GitHub tools, web scraping tools)
   - These are available without additional dependencies

2. **Optional Executors**: Provided by optional extensions
   - LLM executors (e.g., `crew_manager` for CrewAI) - requires AI/LLM dependencies
   - HTTP executors - may require additional dependencies
   - Specialized executors for specific use cases

3. **Custom Executors**: Created by users
   - User-defined executors implementing the Executor interface
   - Registered with ExecutorRegistry using unique identifiers
   - Can implement any business logic or integration

**MUST**: Implementations MUST provide at least one executor type (built-in or custom).

**SHOULD**: Implementations SHOULD provide common built-in executors for system operations.

**MAY**: Implementations MAY provide optional executors for specialized use cases.

**Note**: The specific executor identifiers (e.g., `system_info_executor`, `command_executor`) are implementation-specific. The protocol only specifies the registration and lookup mechanism, not the specific executor names that must be provided.

### Executor Identifier

The `method` field in `schemas` is used to look up the executor in the registry. The value of `schemas.method` MUST be the executor.id (the registered executor identifier).

**MUST**:
- `method` MUST be a non-empty string.
- `method` MUST be the executor.id (registered executor identifier).
- `method` MUST match a registered executor identifier in the ExecutorRegistry.
- Executor identifiers MUST be unique within a registry.

**SHOULD**:
- Executor identifiers SHOULD be descriptive (e.g., `"web_crawler"` not `"exec1"`).
- Executor identifiers SHOULD follow a consistent naming convention.

### Registration Mechanism

**Language-Agnostic Specification**:

1. **Registry**: Implementations MUST provide an `ExecutorRegistry` that maps executor identifiers to executor instances.
2. **Registration**: Executors MUST be registered before they can be used in tasks.
3. **Lookup**: When a task is executed, the system MUST look up the executor using `schemas.method`.
4. **Error Handling**: If an executor is not found, the task MUST fail with an appropriate error.

**Implementation Note**: The specific registration mechanism (decorators, function calls, configuration files) is implementation-specific. The protocol only specifies that executors must be registered and accessible via the `method` identifier.

### Example Registration (Conceptual)

```python
# Python example (for reference only - protocol is language-agnostic)
@executor_registry.register("my_custom_analyzer")
class MyCustomAnalyzer:
    async def execute(self, inputs):
        # Implementation
        pass
```

In the Task JSON:
```json
{
  "schemas": {
    "method": "my_custom_analyzer"
  }
}
```

## Validation Rules

### Task Validation

When creating or updating a task, implementations MUST validate:

1. **Required Fields**: `id`, `name`, `status` are present.
2. **Field Types**: All fields match their specified types.
3. **Field Constraints**: All constraints are satisfied (e.g., `priority` in range 0-3).
4. **UUID Format**: `id`, `parent_id`, and dependency IDs are valid UUIDs.
5. **Status Consistency**: Status matches field values (e.g., `result` is null when status is not `completed`).
6. **Dependency References**: All dependency IDs reference existing tasks.
7. **Circular Dependencies**: No circular dependency chains exist.
8. **Input Schema**: If `schemas.input_schema` is present, `inputs` conforms to it.

### Dependency Validation

When validating dependencies:

1. **Reference Validation**: All dependency IDs MUST reference existing tasks.
2. **Self-Reference**: A task MUST NOT depend on itself.
3. **Circular Dependency Detection**: 
   - Build dependency graph.
   - Check for cycles using depth-first search (DFS).
   - Reject if cycles are detected.

**Algorithm for Circular Dependency Detection**:

```
function hasCircularDependency(task, visited, recStack):
    visited[task.id] = true
    recStack[task.id] = true
    
    for each dependency in task.dependencies:
        dep_task = getTask(dependency.id)
        if not visited[dep_task.id]:
            if hasCircularDependency(dep_task, visited, recStack):
                return true
        else if recStack[dep_task.id]:
            return true  // Cycle detected
    
    recStack[task.id] = false
    return false
```

### Tree Validation

When validating a task tree:

1. **Root Task**: Exactly one root task exists (`parent_id: null`).
2. **Parent-Child Consistency**: All `parent_id` values reference valid parent tasks in the tree.
3. **Acyclic Structure**: No circular parent-child relationships.
4. **Dependency References**: All dependency IDs reference tasks within the same tree.

## See Also

- [Execution Lifecycle](04-execution-lifecycle.md) - State machine and execution rules
- [Core Concepts](02-core-concepts.md) - Fundamental protocol concepts
- [Validation](09-validation.md) - Detailed validation algorithms
- [Error Handling](08-errors.md) - Error codes and handling

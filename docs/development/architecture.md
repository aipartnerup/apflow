# Architecture and Development Design Document (Focus on TaskManager)

This document is a focused summary. For the full architecture reference, see `docs/architecture/`.

## 1. Project Positioning and Overall Architecture

**Core Positioning**: apflow is a framework library centered on the **Task Orchestration & Execution Specification**. Its core capabilities focus on **task tree orchestration, dependency management, priority scheduling, and unified execution interfaces**. All other components—API, CLI, storage, and extensions—serve as peripheral support layers.

### Layered Architecture (Simplified View)

- **API / External Interface Layer**
  - Native API (JSON-RPC `POST /tasks`)
  - A2A Adapter (execute / generate / cancel)
  - MCP Adapter (15 auto-generated tools)
  - CLI

- **Orchestration Core Layer (Core)**
  - `TaskManager`: task tree orchestration, dependency checking, priority scheduling, lifecycle management
  - `TaskExecutor`: execution entrypoint, session management, concurrency protection, task tree distribution

- **Execution Layer (Extension Ecosystem)**
  - Various Executors (REST / WebSocket / gRPC / SSH / Docker / CrewAI / MCP / LLM, etc.)
  - Unified discovery and instantiation via Extension Registry

- **Support Layer**
  - Storage (DuckDB / PostgreSQL)
  - Streaming (real-time progress and result push)
  - Config / Hooks / Scheduler

> For detailed architecture, refer to: `docs/architecture/overview.md`.

## 2. Key Data Models and Core Concepts

### 2.1 TaskModel (Orchestration Definition)
- Task definition, dependencies, priority, task tree structure, latest execution result
- Stored in `apflow_tasks` (configurable via `APFLOW_TASK_TABLE_NAME`)

### 2.2 A2A Task (Execution Instance)
- LLM-oriented execution context (history / artifacts / status)
- Separated from TaskModel; TaskModel only retains the latest execution result

> For details, see: TaskModel and A2A Task mapping in `docs/architecture/overview.md`.

## 3. Core of Task Orchestration: TaskManager (Focus)

**File**: `src/apflow/core/execution/task_manager.py`

### 3.1 Core Responsibilities
- Recursive scheduling of task trees
- Dependency checking and input merging
- Task execution state transitions (pending → in_progress → completed/failed/cancelled)
- Pre/post hook execution and context management
- Streaming status push
- Task cancellation and executor cleanup
- Failed task retry and dependency re-execution

### 3.2 Task Tree Execution Flow (Summary)
1. **Set Hook Context** (`set_hook_context`)
2. Execute tree hooks: `on_tree_created` / `on_tree_started`
3. Recursively execute task tree:
   - Group by **priority**
   - Parallel execution of nodes with satisfied dependencies at the same priority
4. Task execution:
   - Dependency resolution → pre-hooks → executor → post-hooks
5. Aggregate tree status and trigger `on_tree_completed` / `on_tree_failed`
6. Clean up Hook Context

> For detailed lifecycle, refer to: `docs/architecture/task-tree-lifecycle.md`.

### 3.3 Re-execution and Failure Recovery Strategy
- `failed` tasks **are always re-executed**
- `completed` tasks are re-executed **only if marked for re-execution**
- `pending` tasks executed normally
- `in_progress` tasks skipped by default

`TaskExecutor` marks the "set of tasks requiring re-execution" at the tree level; `TaskManager` filters executable nodes based on this set during distribution.

### 3.4 Dependency Resolution and Input Merging
- Dependency checking handled by `are_dependencies_satisfied()`
- Dependency result merging:
  - Supports schema-based mapping (input/output schema)
  - Supports aggregate tasks (`aggregate_results_executor`)
  - Falls back to `dep_id` namespace by default for complex outputs

### 3.5 Executor Loading and Permission Control
- Executors retrieved by **executor_id** via `ExtensionRegistry`
- Supports restricting available executors via `APFLOW_EXTENSIONS` / `APFLOW_EXTENSIONS_IDS`
- Returns clear errors for unauthorized or missing executors

### 3.6 Hook System
- **Pre hooks**: Before execution; can modify `task.inputs` (auto-persisted)
- **Post hooks**: After execution; receive inputs + result
- **Task-tree hooks**: Tree lifecycle (created/started/completed/failed)
- Hooks share the same DB session at runtime (ContextVar)

### 3.7 Streaming & Cancellation
- Streaming: Progress and final status pushed via `StreamingCallbacks`
- Cancellation: Supports `executor.cancel()`, with merged `token_usage` / `partial_result`
- Executor instances stored in `_executor_instances` for cancellation and cleanup

### 3.8 Demo Mode
- Returns demo result directly when `use_demo=True`; supports simulated sleep (`APFLOW_DEMO_SLEEP_SCALE`)

## 4. Task Execution Entry: TaskExecutor

**File**: `src/apflow/core/execution/task_executor.py`

Main Responsibilities:
- Entrypoint for task tree execution (API/CLI invocation)
- Thread-safe "concurrency protection for same-root task trees" (TaskTracker)
- Distribution to TaskManager
- Task creation and task tree construction (TaskCreator)
- Task subtree execution (dependencies auto-resolved when task_id is specified)

## 5. Storage Layer and Repository

**File**: `src/apflow/core/storage/sqlalchemy/task_repository.py`

Key Features:
- Single access entry (TaskRepository)
- Supports custom TaskModel (`APFLOW_TASK_MODEL_CLASS`)
- Supports fast query of full tree by `task_tree_id`
- JSON field change detection (`flag_modified`)
- Support for scheduling-related fields (cron + next_run_at)

## 6. Extension Mechanism (Extension Registry)

**Files**: `src/apflow/core/extensions/registry.py` + `manager.py`

Core Capabilities:
- Extension registration and lookup (ID / category / type)
- **Lazy loading** of Executors (avoids slowing down CLI startup)
- Uses Protocol to avoid circular dependencies
- Supports override

Security Control:
- `APFLOW_EXTENSIONS` / `APFLOW_EXTENSIONS_IDS` allow restricting executor set

## 7. Dependencies and Optional Features

**Basic Dependencies (Core)**
- `sqlalchemy` / `duckdb-engine` / `alembic` / `pydantic`

**Optional Extensions** (Excerpt)
- `a2a`: FastAPI / Uvicorn / a2a-sdk / httpx / websockets
- `cli`: click / typer / rich / python-dotenv
- `postgres`: asyncpg / psycopg2-binary
- `crewai`: crewai / litellm / anthropic
- `docker` / `grpc` / `ssh` / `mcp` / `llm` / `email`

> For details, see `pyproject.toml`.

## 8. Functional Features (Summary)

- ✅ Task tree orchestration (parent-child structure + dependency control)
- ✅ Priority scheduling (parallel at same priority)
- ✅ Failure re-execution and dependency propagation
- ✅ Schema-based dependency result mapping
- ✅ Hooks + ContextVar (unified DB session)
- ✅ Streaming execution progress
- ✅ Cancelable tasks
- ✅ Extension mechanism (Executor / Hook / Storage)
- ✅ Multi-protocol API (A2A / MCP / JSON-RPC)
- ✅ Built-in scheduling and external scheduler support

## 9. Development Recommendations and Extension Points

- **New executor**: Register via extension decorator; ensure `execute()` and schema methods are available
- **Custom TaskModel**: Set `APFLOW_TASK_MODEL_CLASS`
- **Extend hooks**: Register pre/post/tree hooks; avoid long-running logic
- **Distributed extension (Future)**: Based on Distributed Core design in roadmap

---

### References
- `docs/architecture/overview.md`
- `docs/architecture/task-tree-lifecycle.md`
- `docs/architecture/directory-structure.md`
- `docs/architecture/extension-registry-design.md`
- `docs/guides/task-orchestration.md`
- `pyproject.toml`
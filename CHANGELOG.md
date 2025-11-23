# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Examples Module**
  - New `examples` module for initializing example task data to help beginners get started
  - CLI command `examples init` for initializing example tasks in the database
  - `--force` flag to re-initialize examples even if they already exist
  - Example tasks demonstrate various features:
    - Tasks with different statuses (completed, failed, pending, in_progress)
    - Task trees with parent-child relationships
    - Tasks with different priorities
    - Tasks with dependencies
    - CrewAI task example (requires LLM key)
  - Auto-initialization: API server automatically initializes examples if database is empty on startup
  - Example user ID: `example_user` for demo tasks

- **LLM API Key Management**
  - Request header support: `X-LLM-API-KEY` header for demo/one-time usage
    - Simple format: `X-LLM-API-KEY: <api-key>` (provider auto-detected from model name)
    - Provider-specific format: `X-LLM-API-KEY: <provider>:<api-key>` (e.g., `openai:sk-xxx`, `anthropic:sk-ant-xxx`)
  - User configuration support via `llm-key-config` extension for multi-user scenarios
    - In-memory storage of user-specific LLM keys (never stored in database)
    - Support for multiple providers per user (provider-specific keys)
    - `LLMKeyConfigManager` singleton for managing user keys
  - LLM Key Context Manager: Thread-local context for LLM keys during task execution
  - LLM Key Injector: Automatic provider detection from model names and works configuration
  - Priority order: Request header > User config > Environment variables
  - Supported providers: OpenAI, Anthropic, Google/Gemini, Mistral, Groq, Cohere, Together, and more
  - Automatic environment variable injection for CrewAI/LiteLLM compatibility
  - Keys are never stored in database, only used during task execution

- **Documentation Updates**
  - Added `examples` command documentation in CLI guide
  - Added LLM API key management documentation in API server guide
  - Added LLM key header documentation in HTTP API reference
  - Updated examples documentation with quick start guide and example task structure
  - Comprehensive examples for using LLM keys with CrewAI tasks

### Changed
- **CLI Command Improvements**
  - `serve` command now accepts options directly (e.g., `apflow serve --port 8000`) without requiring `start` subcommand
  - `serve start` subcommand still works for backward compatibility
  - Improved command structure and user experience

- **CORS Support**
  - Added CORS middleware to API server for cross-origin requests
  - Default configuration allows `localhost:3000`, `localhost:3001` and common development ports
  - Configurable via `AIPARTNERUPFLOW_CORS_ORIGINS` environment variable (comma-separated list)
  - Development mode: `AIPARTNERUPFLOW_CORS_ALLOW_ALL=true` to allow all origins
  - Supports credentials, all HTTP methods, and all headers

### Fixed
- **Documentation Corrections**
  - Fixed incorrect command examples in README.md and docs:
    - Corrected `run my_batch` to proper `run flow --tasks` or `run flow executor_id` format
    - Corrected `run flow example_flow` to proper executor ID format
    - Removed non-existent `list-flows` command from documentation
  - Ensured all command examples in documentation are accurate and testable

## [0.2.0] - 2025-11-21

### Added
- **Task Tree Validation**
  - Circular dependency detection using DFS algorithm in `TaskCreator.create_task_tree_from_array()`
  - Single task tree validation ensuring all tasks are in the same tree structure
  - Validation that only one root task exists
  - Verification that all tasks are reachable from root task via parent_id chain
  - Dependent task inclusion validation (ensures all tasks that depend on tasks in the tree are included)
  - Comprehensive test coverage for circular dependency scenarios

- **Task Copy Functionality**
  - `TaskCreator.create_task_copy()` method for creating executable copies of task trees
  - Automatic inclusion of dependent tasks (including transitive dependencies) when copying
  - Special handling for failed leaf nodes (filters out pending dependents)
  - Minimal subtree construction to include only required tasks
  - Task copy fields in `TaskModel`: `original_task_id` (links copy to original) and `has_copy` (indicates if task has copies)
  - API endpoint `tasks.copy` via JSON-RPC `/tasks` endpoint
  - CLI command `tasks copy <task_id>` for copying task trees
  - Comprehensive test coverage for task copy functionality

## [0.1.0] - 2025-11-19

### Added
- **Task Orchestration Engine**
  - `TaskManager`: Core task orchestration with dependency management and tree execution
  - `TaskRepository`: Data access layer for task CRUD operations
  - `TaskModel`: Task definition model with support for custom fields via inheritance
  - Task tree structure with parent-child relationships
  - Priority-based task execution
  - Dependency resolution and satisfaction checking

- **A2A Protocol Integration**
  - A2A Protocol as the standard communication protocol
  - Task definition (TaskModel) vs execution instance (A2A Task) separation
  - Context ID mapping: TaskModel.id → A2A Task.context_id
  - Uses A2A SDK's InMemoryTaskStore for task execution instances
  - TaskModel persistence handled by TaskRepository (separate from A2A TaskStore)

- **API Service Layer**
  - A2A server implementation with Starlette
  - Custom A2A Starlette application with system routes
  - Task management APIs: `/system/task_create`, `/system/task_get`, `/system/task_update`, `/system/task_delete`
  - Optional JWT authentication middleware
  - Support for custom TaskModel via `task_model_class` parameter
  - Environment variable support for custom TaskModel loading (`AIPARTNERUPFLOW_TASK_MODEL_CLASS`)

- **Storage Module**
  - SQLAlchemy-based storage with DuckDB (default) and PostgreSQL support
  - Automatic table creation on first use
  - Configurable table name via `AIPARTNERUPFLOW_TASK_TABLE_NAME` (default: `apflow_tasks`)
  - Session factory with sync/async support

- **Custom TaskModel Support**
  - Users can define custom TaskModel subclasses with additional fields
  - TaskRepository supports custom TaskModel classes
  - Custom fields automatically handled in task creation APIs
  - Example: `MyTaskModel(TaskModel)` with `project_id`, `department` fields

- **Event Queue Bridge**
  - Streaming callbacks integration with A2A Protocol EventQueue
  - Real-time task execution progress updates

- **Base Task Infrastructure**
  - `BaseTask`: Optional base class for executable tasks with common implementations
  - Input validation utilities (`get_input_schema`, `validate_input_schema`, `check_input_schema`)
  - Cancellation support via `cancellation_checker` callback
  - Streaming context support for progress updates
  - Support for Pydantic BaseModel or JSON schema dict for input validation

- **Executor Extension System**
  - Unified `ExtensionRegistry` for executor registration and discovery
  - `@executor_register()` decorator for automatic registration
  - Category and type-based executor discovery
  - Extension system supporting executors, storage, hooks, and tools
  - Globally unique ID-based extension lookup

- **Built-in Executors**
  - `AggregateResultsExecutor`: Aggregates dependency task results into structured format
  - `SystemInfoExecutor`: Safe system resource queries (CPU, memory, disk) with predefined commands
  - `CommandExecutor`: Shell command execution (stdio extension)
  - `CrewManager`: LLM-based agent crew execution via CrewAI with token usage tracking
  - `BatchManager`: Atomic batch execution of multiple crews with result merging

### Infrastructure
- Project structure with `src-layout`
- `pyproject.toml` with optional dependencies (`[a2a]`, `[crewai]`, `[cli]`, `[postgres]`, `[all]`)
- Comprehensive documentation in `docs/` directory
- Test suite with pytest fixtures
- Modular architecture separating core from optional features


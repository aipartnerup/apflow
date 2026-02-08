# Directory Structure

This document describes the directory structure of the `apflow` project.

## Core Framework (`core/`)

The core framework provides task orchestration and execution specifications. All core modules are always included when installing `apflow`.

```
core/
├── __init__.py
├── types.py                # Core type definitions (TaskStatus, TaskTreeNode, webhook types)
├── builders.py
├── config_manager.py
├── decorators.py
├── base/
│   └── base_task.py
├── config/
│   └── registry.py
├── dependency/
│   └── dependency_validator.py
├── execution/
│   ├── errors.py
│   ├── executor_registry.py
│   ├── streaming_callbacks.py
│   ├── task_creator.py
│   ├── task_executor.py
│   ├── task_manager.py
│   └── task_tracker.py
├── extensions/
│   ├── base.py
│   ├── decorators.py
│   ├── executor_metadata.py
│   ├── hook.py
│   ├── manager.py
│   ├── protocol.py
│   ├── registry.py
│   ├── scanner.py            # Extension auto-discovery
│   ├── storage.py
│   └── types.py
├── interfaces/
│   └── executable_task.py
├── storage/
│   ├── context.py
│   ├── factory.py
│   ├── migrate.py
│   ├── dialects/
│   │   ├── duckdb.py
│   │   ├── postgres.py
│   │   └── registry.py
│   ├── migrations/
│   │   ├── 001_add_task_tree_fields.py
│   │   └── 002_add_scheduling_fields.py
│   └── sqlalchemy/
│       ├── models.py
│       ├── schedule_calculator.py  # Schedule time calculation
│       └── task_repository.py
├── tools/
│   ├── base.py
│   ├── decorators.py
│   └── registry.py
├── utils/
│   ├── helpers.py
│   ├── llm_key_context.py
│   ├── llm_key_injector.py
│   ├── logger.py
│   └── project_detection.py
└── validator/
    ├── dependency_validator.py
    └── user_validator.py
```

## Scheduler (`scheduler/`)

Task scheduling subsystem with internal polling scheduler and external gateway integrations.

**Installation**: `pip install apflow[a2a]` (uses API for task execution)

```
scheduler/
├── __init__.py
├── base.py                 # Base scheduler interface
├── internal.py             # InternalScheduler - polls DB for due tasks
└── gateway/
    ├── __init__.py
    ├── ical.py             # iCalendar export for scheduled tasks
    └── webhook.py          # Webhook gateway for external schedulers
```

## Extensions (`extensions/`)

Framework extensions are optional features that require extra dependencies and are installed separately.

### [crewai] - CrewAI LLM Task Support

```
extensions/crewai/
├── __init__.py
├── crewai_executor.py     # CrewaiExecutor - CrewAI wrapper
├── batch_crewai_executor.py    # BatchCrewaiExecutor - batch execution of multiple crews
└── types.py            # CrewaiExecutorState, BatchState
```

**Installation**: `pip install apflow[crewai]`

### [stdio] - Stdio Executors

```
extensions/stdio/
├── __init__.py
├── command_executor.py      # CommandExecutor - local command execution
└── system_info_executor.py  # SystemInfoExecutor - system resource queries
```

**Installation**: Included in core (no extra required)

### [core] - Core Extensions

```
extensions/core/
├── __init__.py
└── aggregate_results_executor.py  # AggregateResultsExecutor - dependency result aggregation
```

**Installation**: Included in core (no extra required)

### [apflow] - APFlow API Executor

```
extensions/apflow/
├── __init__.py
└── api_executor.py          # ApiExecutor - execute tasks via APFlow API
```

**Installation**: Included in core (no extra required)

### [email] - Email Executor

```
extensions/email/
├── __init__.py
└── send_email_executor.py     # SendEmailExecutor - Resend API and SMTP
```

**Installation**: `pip install apflow[email]`

### [hooks] - Hook Extensions

```
extensions/hooks/
├── __init__.py
├── pre_execution_hook.py   # Pre-execution hook implementation
└── post_execution_hook.py  # Post-execution hook implementation
```

**Installation**: Included in core (no extra required)

### [storage] - Storage Extensions

```
extensions/storage/
├── __init__.py
├── duckdb_storage.py   # DuckDB storage implementation
└── postgres_storage.py # PostgreSQL storage implementation
```

**Installation**: Included in core (no extra required)

### [tools] - Tool Extensions

```
extensions/tools/
├── __init__.py
├── github_tools.py          # GitHub analysis tools
└── limited_scrape_tools.py   # Limited website scraping tools
```

**Installation**: Included in core (no extra required)

### [http] - HTTP Executor

```
extensions/http/
├── __init__.py
└── rest_executor.py         # RestExecutor - REST API calls
```

**Installation**: Included in core (no extra required)

### [docker] - Docker Executor

```
extensions/docker/
├── __init__.py
└── docker_executor.py       # DockerExecutor - Docker container execution
```

**Installation**: `pip install apflow[docker]`

### [grpc] - gRPC Executor

```
extensions/grpc/
├── __init__.py
└── grpc_executor.py         # GrpcExecutor - gRPC service calls
```

**Installation**: `pip install apflow[grpc]`

### [ssh] - SSH Executor

```
extensions/ssh/
├── __init__.py
└── ssh_executor.py          # SshExecutor - remote command execution via SSH
```

**Installation**: `pip install apflow[ssh]`

### [websocket] - WebSocket Executor

```
extensions/websocket/
├── __init__.py
└── websocket_executor.py    # WebSocketExecutor - WebSocket communication
```

**Installation**: `pip install apflow[websocket]`

### [mcp] - MCP Executor

```
extensions/mcp/
├── __init__.py
└── mcp_executor.py          # McpExecutor - Model Context Protocol execution
```

**Installation**: `pip install apflow[mcp]`

### [llm] - LLM Executor

```
extensions/llm/
├── __init__.py
└── llm_executor.py          # LlmExecutor - direct LLM API calls
```

**Installation**: `pip install apflow[llm]`

### [llm_key_config] - LLM Key Configuration

```
extensions/llm_key_config/
├── __init__.py
└── config_manager.py        # LLM API key configuration management
```

**Installation**: Included in core (no extra required)

### [scrape] - Web Scraping Executor

```
extensions/scrape/
├── __init__.py
└── scrape_executor.py       # ScrapeExecutor - web page scraping
```

**Installation**: `pip install apflow[scrape]`

### [generate] - Task Tree Generation

```
extensions/generate/
├── __init__.py
├── docs_loader.py           # Documentation loading for LLM context
├── executor_info.py         # Executor metadata extraction
├── generate_executor.py     # GenerateExecutor - LLM-based task tree generation
├── llm_client.py            # LLM API client
├── multi_phase_crew.py      # Multi-phase CrewAI generation
├── principles_extractor.py  # Design principles extraction
└── schema_formatter.py      # Schema formatting for LLM prompts
```

**Installation**: `pip install apflow[generate]`

## API Service (`api/`)

Unified external API service layer supporting multiple network protocols.

**Current Implementation**: A2A Protocol Server (Agent-to-Agent communication protocol)
- Supports HTTP, SSE, and WebSocket transport layers
- Implements A2A Protocol standard for agent-to-agent communication

**Future Extensions**: May include additional protocols such as REST API endpoints

**Installation**: `pip install apflow[a2a]`

```
api/
├── __init__.py            # API module exports
├── main.py                # CLI entry point (main() function and uvicorn server)
├── app.py                 # Application creation (create_app_by_protocol, create_a2a_server, create_mcp_server)
├── capabilities.py        # Server capability declarations
├── protocols.py           # Protocol management (get_protocol_from_env, check_protocol_dependency)
├── a2a/                   # A2A Protocol Server implementation
│   ├── __init__.py        # A2A module exports
│   ├── server.py          # A2A server creation
│   ├── agent_executor.py  # A2A agent executor
│   ├── custom_starlette_app.py  # Custom A2A Starlette application
│   ├── event_queue_bridge.py    # Event queue bridge
│   └── task_routes_adapter.py   # TaskRoutes adapter for A2A
├── docs/                  # API documentation
│   ├── __init__.py
│   ├── openapi.py         # OpenAPI schema generation
│   └── swagger_ui.py      # Swagger UI endpoint
├── mcp/                   # MCP (Model Context Protocol) Server implementation
│   ├── __init__.py        # MCP module exports
│   ├── server.py          # MCP server creation
│   ├── adapter.py         # TaskRoutes adapter for MCP
│   ├── tools.py           # MCP tools registry
│   ├── resources.py       # MCP resources registry
│   ├── transport_http.py  # HTTP transport
│   └── transport_stdio.py # Stdio transport
├── middleware/            # Middleware components
│   ├── __init__.py
│   └── db_session.py     # Database session middleware
└── routes/                # Protocol-agnostic route handlers
    ├── __init__.py        # Route handlers exports
    ├── base.py            # BaseRouteHandler - shared functionality
    ├── docs.py            # Documentation route handlers
    ├── tasks.py           # TaskRoutes - task management handlers
    └── system.py          # SystemRoutes - system operation handlers
```

**Route Handlers Architecture**:

The `api/routes/` directory contains protocol-agnostic route handlers that can be used by any protocol implementation (A2A, REST, GraphQL, etc.):

- **`base.py`**: Provides `BaseRouteHandler` class with shared functionality for permission checking, user information extraction, and common utilities
- **`tasks.py`**: Contains `TaskRoutes` class with handlers for task CRUD operations, execution, and monitoring
- **`system.py`**: Contains `SystemRoutes` class with handlers for system operations like health checks, LLM key configuration, and examples management

These handlers are designed to be protocol-agnostic, allowing them to be reused across different protocol implementations.

## CLI Tools (`cli/`)

Command-line interface for task management.

**Installation**: `pip install apflow[cli]`

```
cli/
├── __init__.py
├── main.py                # CLI entry point
├── api_client.py          # API client for remote operations
├── api_gateway_helper.py  # API vs direct DB mode helper
├── cli_config.py          # CLI configuration management
├── jwt_token.py           # JWT token generation
├── extension.py           # CLI extension management
├── decorators.py          # CLI decorators
└── commands/
    ├── __init__.py
    ├── config.py          # Configuration commands
    ├── daemon.py          # Daemon management commands
    ├── executors.py       # Executor management commands
    ├── generate.py        # Task tree generation commands
    ├── run.py             # Task execution commands
    ├── scheduler.py       # Scheduler commands (start, list, export-ical)
    ├── serve.py           # API server commands
    └── tasks.py           # Task management commands
```

## Test Suite (`tests/`)

Test suite organized to mirror the source code structure.

```
tests/
├── conftest.py                     # Shared fixtures and configuration
├── core/                           # Core framework tests
│   ├── execution/                  # Task orchestration tests
│   │   ├── test_task_manager.py
│   │   ├── test_task_creator.py
│   │   ├── test_task_executor_additional.py
│   │   ├── test_task_executor_concurrent.py
│   │   ├── test_task_executor_tools_integration.py
│   │   ├── test_task_failure_handling.py
│   │   └── test_task_reexecution.py
│   ├── storage/                    # Storage tests
│   │   ├── sqlalchemy/
│   │   │   ├── test_task_repository.py
│   │   │   ├── test_task_repository_additional.py
│   │   │   ├── test_custom_task_model.py
│   │   │   ├── test_flag_modified.py
│   │   │   ├── test_scheduling.py
│   │   │   └── test_session_pool.py
│   │   ├── test_context.py
│   │   ├── test_database_path_priority.py
│   │   ├── test_hook_context.py
│   │   ├── test_hook_modify_task_with_context.py
│   │   └── test_migration.py
│   ├── utils/
│   │   ├── test_llm_key_context.py
│   │   └── test_project_detection.py
│   ├── validator/
│   │   └── test_dependency_validator.py
│   ├── test_config_manager.py
│   ├── test_decorators.py
│   ├── test_demo_mode.py
│   ├── test_executor_hooks.py
│   ├── test_extension_scanner.py
│   ├── test_task_builder.py
│   ├── test_task_tree_hooks.py
│   └── test_user_id_extraction.py
├── extensions/                     # Extension tests
│   ├── apflow/
│   │   └── test_api_executor.py
│   ├── core/
│   │   └── test_aggregate_results_executor.py
│   ├── crewai/
│   │   ├── test_crewai_executor.py
│   │   └── test_batch_crewai_executor.py
│   ├── docker/
│   │   └── test_docker_executor.py
│   ├── email/
│   │   └── test_send_email_executor.py
│   ├── generate/
│   │   ├── test_crewai_dependency_fix.py
│   │   ├── test_crewai_schema_mapping.py
│   │   ├── test_docs_loader.py
│   │   ├── test_executor_info.py
│   │   ├── test_generate_crewai.py
│   │   ├── test_generate_executor.py
│   │   ├── test_generate_executor_enhanced.py
│   │   ├── test_generate_real_scenario.py
│   │   ├── test_integration.py
│   │   ├── test_llm_client.py
│   │   ├── test_llm_scrape_executor.py
│   │   ├── test_multi_phase_crew.py
│   │   ├── test_principles_extractor.py
│   │   └── test_schema_formatter.py
│   ├── grpc/
│   │   └── test_grpc_executor.py
│   ├── http/
│   │   └── test_rest_executor.py
│   ├── llm/
│   │   └── test_llm_executor.py
│   ├── mcp/
│   │   └── test_mcp_executor.py
│   ├── ssh/
│   │   └── test_ssh_executor.py
│   ├── stdio/
│   │   ├── test_command_executor.py
│   │   └── test_system_info_executor.py
│   ├── tools/
│   │   ├── test_tools_decorator.py
│   │   └── test_limited_scrape_tools.py
│   └── websocket/
│       └── test_websocket_executor.py
├── api/                            # API service tests
│   ├── a2a/
│   │   ├── test_a2a_client.py
│   │   ├── test_agent_executor.py
│   │   ├── test_docs_routes.py
│   │   └── test_http_json_rpc.py
│   ├── mcp/
│   │   ├── test_adapter.py
│   │   ├── test_resources.py
│   │   ├── test_server.py
│   │   ├── test_tools.py
│   │   └── test_transport_http.py
│   ├── test_executor_permissions.py
│   ├── test_executors_api.py
│   ├── test_main.py
│   ├── test_main_env_loading.py
│   ├── test_scheduler_routes.py
│   ├── test_system_executors_endpoint.py
│   ├── test_task_routes_extension.py
│   ├── test_task_update_validation.py
│   └── test_tasks_routes.py
├── cli/                            # CLI tests
│   ├── test_api_gateway.py
│   ├── test_api_server_fallback.py
│   ├── test_cli_api_gateway_integration.py
│   ├── test_cli_config.py
│   ├── test_cli_env_loading.py
│   ├── test_cli_extension.py
│   ├── test_config_command.py
│   ├── test_daemon_command.py
│   ├── test_decorators.py
│   ├── test_entry_point_function.py
│   ├── test_executors_command.py
│   ├── test_generate_command.py
│   ├── test_run_command.py
│   ├── test_scheduler_command.py
│   ├── test_serve_command.py
│   ├── test_tasks_command.py
│   └── test_tasks_command_api_mode.py
├── scheduler/                      # Scheduler tests
│   ├── test_scheduler.py
│   └── test_webhook_api.py
└── integration/                    # Integration tests
    ├── test_aggregate_results_integration.py
    ├── test_config_manager_integration.py
    └── test_schema_based_execution.py
```

**Note**: Test structure mirrors source code structure for easy navigation and maintenance.

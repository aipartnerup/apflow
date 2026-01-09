# Development Roadmap

## Core Philosophy

**apflow** = Pure orchestration library + Optional framework components

- **Core:** Zero framework dependencies, embeddable in any project
- **Optional:** A2A/MCP servers, CLI tools, protocol adapters
- **Goal:** Easy integration, easy extension, can coexist with competitors

---

## Completed Features ✅

### Core Infrastructure (Completed)

**Task Orchestration Engine** ✅
- TaskManager: Core task orchestration with dependency management and tree execution
- TaskRepository: Data access layer for task CRUD operations  
- TaskModel: Task definition model with support for custom fields
- Task tree structure with parent-child relationships
- Priority-based task execution and dependency resolution

**Storage Layer** ✅
- SQLAlchemy-based storage with DuckDB (default) and PostgreSQL support
- Automatic table creation and session management
- Configurable table names and database dialects

**Extension System** ✅
- Unified ExtensionRegistry for executor registration and discovery
- @executor_register() decorator for automatic registration
- Category and type-based executor discovery
- Support for executors, storage, hooks, and tools

**Base Task Infrastructure** ✅
- BaseTask: Optional base class for executable tasks
- Input validation utilities with JSON schema support
- Cancellation support and streaming context
- Pydantic BaseModel and JSON schema validation

### Built-in Executors (Completed)

**Core Executors** ✅
- AggregateResultsExecutor: Aggregates dependency task results
- SystemInfoExecutor: Safe system resource queries
- CommandExecutor: Shell command execution

**Network Executors** ✅
- RestExecutor: HTTP/REST API calls with authentication and retry
- WebSocketExecutor: Bidirectional WebSocket communication
- ApFlowApiExecutor: Inter-instance API calls for distributed execution

**Infrastructure Executors** ✅
- SshExecutor: Remote command execution via SSH
- DockerExecutor: Containerized command execution
- GrpcExecutor: gRPC service calls

**AI/ML Executors** ✅
- CrewaiExecutor: LLM-based agent crews via CrewAI
- BatchCrewaiExecutor: Atomic batch execution of multiple crews
- LlmExecutor: Direct LLM interaction via LiteLLM (100+ providers)
- McpExecutor: Model Context Protocol executor
- GenerateExecutor: Task tree generation from natural language

### API & Protocol Support (Completed)

**A2A Protocol Server** ✅
- Agent-to-Agent communication protocol implementation
- HTTP, SSE, and WebSocket transport layers
- JWT authentication and task management
- Real-time streaming support

**MCP (Model Context Protocol) Server** ✅
- Expose apflow capabilities as MCP tools and resources
- Support for stdio and HTTP/SSE transport modes
- 8 MCP tools for complete task management

**JSON-RPC API** ✅
- RESTful task management endpoints
- Webhook support for task execution callbacks
- Server-Sent Events (SSE) streaming
- Protocol identification in responses

### CLI Tools (Completed)

**Task Management Commands** ✅
- tasks list/status/get/create/update/delete/copy/tree/children
- tasks execute/cancel/watch/history/generate
- Support for JSON file input and filtering options

**Configuration Management** ✅
- apflow config commands: set/get/unset/list/reset/init/verify-token
- Multi-location configuration support (project-local, user-global)
- JWT token generation and validation
- API server connectivity testing

**Server Commands** ✅
- apflow serve: Start API server with protocol selection
- apflow daemon: Background server management
- Protocol selection (--protocol a2a/mcp)

### Advanced Features (Completed)

**Task Lifecycle Management** ✅
- Task tree validation with circular dependency detection
- Task copy functionality with dependency preservation
- Task re-execution support for failed tasks
- Enhanced task deletion with validation
- Task update with critical field protection

**Configuration Management** ✅
- ConfigManager singleton for unified configuration
- Multi-location config support (project/global)
- Environment variable integration
- Type-safe configuration access

**LLM Key Management** ✅
- Multi-provider LLM key support (OpenAI, Anthropic, etc.)
- Request header and user configuration support
- Thread-local context for secure key handling
- Automatic provider detection

**Demo Mode Support** ✅
- Built-in demo execution for all executors
- Realistic timing simulation
- Fallback for missing dependencies
- Global demo sleep scale configuration

**Hook System** ✅
- Pre/post execution hooks for executors
- Task tree lifecycle hooks (created/started/completed/failed)
- Hook context sharing with database access
- Thread-safe context isolation

**Streaming & Real-time Updates** ✅
- Real-time progress updates via SSE and webhooks
- A2A Protocol event-driven updates
- Streaming context for progress tracking
- Protocol-agnostic streaming support

### Testing & Quality (Completed)

**Test Infrastructure** ✅
- Comprehensive test suite (800+ tests)
- Isolated test databases and fixtures
- Async test support with proper event loop handling
- Test coverage for all major components

**Code Quality** ✅
- Type annotations and mypy compliance
- Ruff linting and formatting
- Pre-commit hooks and CI/CD integration
- Comprehensive error handling and logging

---

## Development Priorities

### Priority 1: Fluent API (TaskBuilder) ✅

**Goal:** Type-safe, chainable task creation API

**Implementation:**
```python
# New file: src/apflow/core/builders.py
result = await (
    TaskBuilder(manager, "rest_executor")
    .with_name("fetch_data")
    .with_input("url", "https://api.example.com")
    .depends_on("task_auth")
    .execute()
)
```

**Deliverables:**
- Type-safe builder with generics
- Support for all task properties
- Documentation with examples
- Integration with existing TaskManager

**Why:**
- Zero breaking changes
- Immediate DX improvement
- Competitive advantage over Dagster/Prefect
- Foundation for future enhancements

---

### Priority 2: CLI → API Gateway Architecture ✅

**Goal:** Enable CLI commands to access API-managed data, ensuring data consistency and supporting concurrent access patterns.

**Problem Statement:**
- CLI currently queries database directly, causing data inconsistency when API is running
- DuckDB doesn't support concurrent writes, creating conflicts between CLI and API
- No support for remote API servers or multi-instance deployments

**Implementation:**
```python
# New module: src/apflow/cli/api_client.py
# HTTP client for CLI to communicate with API
class APIClient:
    def __init__(self, server_url: str, auth_token: Optional[str] = None):
        self.server_url = server_url
        self.auth_token = auth_token
    
    async def execute_task(self, task_id: str) -> dict: ...
    async def get_task_status(self, task_id: str) -> dict: ...
    async def list_tasks(self, **filters) -> list: ...
    async def cancel_task(self, task_id: str) -> dict: ...

# ConfigManager extended with:
# - api_server_url (address, port)
# - api_auth_token (optional, for auth with running API)
# - use_local_db (bool, bypass API for direct local queries if needed)
# - api_timeout (seconds)
# - api_retry_policy (exponential backoff)
```

**CLI Integration:**
```bash
# Configure API server
apflow config set api_server_url http://localhost:8000
apflow config set api_auth_token <token>

# CLI commands automatically use API when configured
apflow tasks list  # Routes to API instead of local DB
apflow tasks execute task-123
apflow tasks cancel task-456

# Fallback behavior: if API unreachable, use local DB (configurable)
apflow tasks list --local-only  # Force local database access
```

**Deliverables:**
- HTTP client layer (`src/apflow/cli/api_client.py`) with request/response handling
- ConfigManager extension for API configuration (URL, auth, timeouts, retry policy)
- CLI command layer refactored to use APIClient by default when configured
- Graceful fallback to local DB if API unavailable (with warning)
- Request middleware for auth token injection
- Error handling for network timeouts and API errors
- Documentation on API + CLI co-deployment patterns
- Integration tests for CLI → API workflows

**Why:**
- Solves data consistency problem between API and CLI (single source of truth)
- Unblocks DuckDB concurrent write limitations (all writes go through API)
- Foundation for all future protocol adapters (CLI, GraphQL, MQTT, WebSocket all use same HTTP layer)
- Enterprise requirement (API gateway pattern for multi-instance deployments)
- Prerequisite for distributed deployments and remote API servers
- Enables CLI to work with centralized API without direct database access

---

### Priority 3: Distributed Core Enablement ⭐⭐⭐

**Goal:** Multi-node/instance orchestration with centralized coordination

**Problem Statement:**
- Current single-node limitation: only one API or CLI instance can safely write to DuckDB
- No distributed task assignment across nodes
- Cannot leverage multiple machines for horizontal scaling
- No support for high availability and fault tolerance
- Tasks must run on the same machine as TaskManager instance

For detailed design rationale and architecture decisions, see [Distributed Orchestration Design](distributed-orchestration-design.md).

**Implementation:**

**Node Registry & Management** (`src/apflow/core/distributed/`)
```python
class NodeRegistry:
    async def register_node(
        self, 
        node_id: str, 
        capabilities: dict,  # CPU/GPU/memory/labels/executor_types
        executor_types: list[str]
    ) -> None: ...
    
    async def heartbeat(self, node_id: str) -> None: ...
    
    async def deregister_node(self, node_id: str) -> None: ...
    
    async def list_healthy_nodes(self) -> list[NodeInfo]: ...

@dataclass
class PlacementConstraints:
    requires_executors: list[str]  # Must have one of these
    requires_capabilities: dict  # e.g., {"gpu": "nvidia", "memory_gb": 16}
    forbidden_nodes: set[str]  # Blacklist specific nodes
    max_parallel_per_node: int = 1
```

**Task Leasing & Idempotency** (`src/apflow/core/distributed/leasing.py`)
```python
class TaskLease:
    task_id: str
    node_id: str
    lease_token: str
    acquired_at: datetime
    expires_at: datetime
    
    async def renew(self, duration: timedelta) -> None: ...
    async def release(self) -> None: ...

@dataclass
class ExecutionIdempotency:
    idempotency_key: str  # Unique per (task_id, execution_attempt)
    result_cache: dict  # Store result to return on retry
```

**Distributed TaskManager** (`src/apflow/core/distributed/manager.py`)
```python
class DistributedTaskManager(TaskManager):
    async def acquire_lease(
        self, 
        task_id: str, 
        node_id: str,
        constraints: PlacementConstraints
    ) -> TaskLease: ...
    
    async def find_executable_tasks(
        self, 
        node_id: str
    ) -> list[Task]: ...
    
    async def renew_lease(self, lease: TaskLease) -> None: ...
    
    async def report_completion(
        self, 
        task_id: str,
        node_id: str,
        result: dict,
        idempotency_key: str
    ) -> None: ...
```

**Storage Layer Extensions**
```python
# Extend task model with:
- lease_id: Optional[str]
- lease_expires_at: Optional[datetime]
- placement_constraints: dict
- idempotency_key: Optional[str]
- last_heartbeat_from: Optional[str]

# New database operations:
- acquire_lease(task_id, node_id, lease_duration)
- release_lease(task_id)
- find_tasks_by_placement(node_id, constraints)
- record_completion(task_id, idempotency_key, result)
```

**Deployment Configuration**
```bash
# Mode 1: Single-node (default, no distributed)
apflow serve --port 8000

# Mode 2: Distributed coordinator (central write authority)
apflow serve --port 8000 --distributed-mode coordinator --database-url postgresql://...

# Mode 3: Distributed worker (executes tasks from coordinator)
apflow serve --node-id worker-1 --coordinator-url http://coordinator:8000
```

**Deliverables:**
- Node registry with health checks and capability tracking
- Task leasing mechanism with automatic expiry and cleanup
- Idempotent task execution with result caching
- Placement constraints (executor type, labels, resource requirements)
- Distributed TaskManager with task assignment APIs
- PostgreSQL-based distributed locking (DuckDB remains read-only in distributed mode)
- Heartbeat/health check system with stale lease detection
- Task recovery on node failure (automatic reassignment)
- Comprehensive test suite (25+ distributed scenarios)
- Deployment documentation: topology, node setup, failover patterns
- Migration guide: single-node to distributed mode

**Key Decisions:**
- Single writer (API/central coordinator) with optional read replicas
- Lease-based (not lock-based) for graceful node failure handling
- Optional feature (backward compatible single-node mode)
- PostgreSQL support (existing dependency)
- Coordinator can run in same process as API or standalone

**Why:**
- Unlocks multi-node deployments without architectural rework
- Foundation for all protocol adapters (each can run on distributed node)
- Prerequisite for horizontal scaling and high availability
- Enables load distribution across machines/containers
- Competitive with Celery/Prefect distributed capabilities
- Enterprise requirement for production deployments
- Solves DuckDB concurrency limitations definitively

---

### Priority 4: Protocol Adapter Abstraction Layer ⭐⭐⭐

**Goal:** Unified protocol interface, framework-agnostic

**Implementation:**
```python
# New module: src/apflow/core/protocols/
class ProtocolAdapter(Protocol):
    async def handle_execute_request(self, request: dict) -> dict: ...
    async def handle_status_request(self, request: dict) -> dict: ...
```

**Deliverables:**
- Base protocol adapter interface
- Refactor existing A2A/MCP adapters to use abstraction
- Protocol adapter documentation
- Testing framework for protocol adapters

**Why:**
- Foundation for multi-protocol support (built on distributed core)
- Enables GraphQL/MQTT/WebSocket additions
- Improves testability
- Each protocol can run on distributed nodes
- No competitor has this abstraction

---

### Priority 5: GraphQL Protocol Adapter ⭐⭐⭐

**Goal:** GraphQL query interface for complex task trees

**Implementation:**
```python
# New: src/apflow/core/protocols/graphql.py
# Optional dependency: strawberry-graphql
schema = create_graphql_schema()
# Users integrate with any GraphQL server
```

**Deliverables:**
- GraphQL schema for tasks, task trees, execution
- Strawberry-based implementation
- Examples for FastAPI, Starlette integration
- GraphQL Playground documentation

**Why:**
- Competitors don't have GraphQL support
- Natural fit for task tree relationships
- Developer-friendly (great tooling ecosystem)
- Library-level (no HTTP server required)

**Update pyproject.toml:**
```toml
[project.optional-dependencies]
graphql = ["strawberry-graphql>=0.219.0"]
```

---

### Priority 6: MQTT Protocol Adapter ⭐⭐

**Goal:** IoT/Edge AI agent communication

**Implementation:**
```python
# New: src/apflow/core/protocols/mqtt.py
mqtt_adapter = MQTTProtocolAdapter(task_manager)
result = await mqtt_adapter.handle_mqtt_message(topic, payload)
```

**Deliverables:**
- MQTT message handler (library function)
- Topic routing (tasks/execute/*, tasks/status/*)
- Examples with paho-mqtt and aiomqtt
- IoT agent orchestration guide

**Why:**
- Unique capability (no competitor has this)
- Growing IoT/edge AI market
- Lightweight implementation
- Complements existing protocols

**Update pyproject.toml:**
```toml
[project.optional-dependencies]
mqtt = ["paho-mqtt>=1.6.1"]
```

---

### Priority 7: Observability Hook System ⭐⭐

**Goal:** Pluggable metrics collection, user-chosen backends

**Implementation:**
```python
# New: src/apflow/core/observability/
class MetricsCollector(Protocol):
    async def record_task_start(self, task_id: str) -> None: ...
    async def record_task_complete(self, task_id: str, duration: float) -> None: ...

tracer = TaskTracer()
tracer.register_collector(PrometheusCollector())  # User provides
```

**Deliverables:**
- Metrics collector protocol
- TaskTracer with plugin system
- Examples: Prometheus, Datadog, OpenTelemetry
- Performance impact documentation

**Why:**
- Close gap with Dagster's observability
- Maintains library purity (no forced backend)
- Enterprise requirement
- Foundation for dashboard/UI

---

### Priority 8: Workflow Patterns Library ⭐⭐

**Goal:** Common orchestration patterns as reusable functions

**Implementation:**
```python
# New: src/apflow/patterns/
result = await map_reduce(
    items=urls,
    map_executor="rest_executor",
    reduce_executor="aggregate_results_executor",
)
```

**Deliverables:**
- Map-Reduce pattern
- Fan-Out/Fan-In pattern
- Circuit Breaker pattern
- Retry with exponential backoff
- Pattern documentation with real-world examples

**Why:**
- Improves ease of use
- Built on existing core (no new infrastructure)
- Competitive with Prefect/Dagster patterns
- Demonstrates library power

---

### Priority 9: VS Code Extension ⭐

**Goal:** Task tree visualization in editor

**Deliverables:**
- Task tree graph view
- Real-time execution status
- Jump to task definition
- Debug console integration

**Why:**
- Significant DX improvement
- Competitive advantage
- Separate project (no core impact)
- Community contribution opportunity

---

### Priority 10: Testing Utilities ⭐

**Goal:** Make workflow testing easy

**Implementation:**
```python
# New: src/apflow/testing/
mocker = TaskMocker()
mocker.mock_executor("rest_executor", return_value={"status": "ok"})
result = await simulate_workflow(task_tree, speed_factor=10.0)
```

**Deliverables:**
- TaskMocker for unit tests
- Workflow simulation with time compression
- Assertion helpers
- Testing best practices guide

**Why:**
- Developer confidence
- Test-friendly library design
- Competitive requirement
- Enables better community contributions

---

### Priority 11: Hot Reload Development Mode ⭐

**Goal:** Auto-reload on code changes

**Implementation:**
```python
# New: src/apflow/dev/
apflow dev --watch src/tasks/
# Auto-reloads when task files change
```

**Deliverables:**
- File watcher for task/executor files
- Automatic registry refresh
- Development mode CLI command
- Error reporting on reload failures

**Why:**
- Faster development iteration
- Competitive with modern frameworks
- Small implementation scope
- High developer satisfaction impact

---

### Priority 12: Bidirectional WebSocket Server ⭐

**Goal:** Real-time agent-to-agent collaboration

**Implementation:**
```python
# New: src/apflow/core/protocols/websocket_server.py
# Enables peer-to-peer agent networks
```

**Deliverables:**
- WebSocket server adapter
- Agent registry and discovery
- Bidirectional message routing
- Real-time collaboration examples

**Why:**
- Advanced use case
- Complements existing websocket_executor (client)
- Unique capability
- Foundation for agent marketplace

**Update pyproject.toml:**
```toml
[project.optional-dependencies]
websocket-server = ["websockets>=12.0"]
protocols = ["apflow[graphql,mqtt,websocket-server]"]
```

---

## Unified Configuration Management (ConfigManager)

**Goal:**  
Introduce a project-wide ConfigManager as the single source of truth for all configuration (CLI, daemon, business logic, testing, etc.), replacing scattered config file access and .env reliance.

**Motivation:**  
- Eliminate configuration pollution and inconsistency between CLI, daemon, and tests.
- Support dynamic configuration reload, project/global scope, and future API-based config management.
- Enable type-safe, maintainable, and testable configuration access across the entire codebase.

**Key Steps:**
1. Implement a ConfigManager singleton with type-safe get/set/reload methods.
2. Refactor all code (CLI, daemon, business logic, tests) to access configuration exclusively via ConfigManager.
3. Remove direct reads/writes to config files and .env for business parameters (except for secrets).
4. Ensure all configuration changes (including duckdb_read_only and future options) are managed through ConfigManager.
5. For daemon mode, expose configuration management APIs; CLI config commands interact with the daemon via HTTP API when running.
6. Add unit tests for ConfigManager and all configuration-dependent logic.
7. Document configuration conventions and migration steps for contributors.

**Benefits:**
- Consistent configuration state across all entrypoints.
- Easy support for project/global profiles, plugin configs, and hot-reload.
- Simplifies testing and avoids cross-test pollution.
- Lays the foundation for future features like multi-profile, plugin, and remote config management.

---

## Success Metrics

### Library-First Success Criteria
- ✅ Core has zero HTTP/CLI dependencies
- ✅ Can embed in any Python project without `[a2a]` or `[cli]`
- ✅ Protocol adapters are pure functions (no server coupling)
- ✅ All "batteries" are optional extensions

### Developer Experience Success Criteria
- ✅ Fluent API reduces boilerplate by 50% (TaskBuilder implemented)
- ⏳ GraphQL queries 30% faster than REST for complex trees (not yet implemented)
- ⏳ Hot reload reduces iteration time by 70% (not yet implemented)
- ✅ Testing utilities enable 90%+ test coverage (comprehensive test suite with 800+ tests)

### Competitive Success Criteria
- ✅ Multi-protocol support (A2A, MCP, JSON-RPC, WebSocket - GraphQL/MQTT pending)
- ⏳ Observable (like Dagster, but for agents) (basic hooks implemented, full observability pending)
- ✅ Lightweight (DuckDB → PostgreSQL)
- ✅ Can coexist with Dagster, Prefect, Celery

### Implementation Status Summary
- **Completed Features**: 15+ major components implemented
- **Test Coverage**: 800+ tests passing
- **Documentation**: Comprehensive guides and API references
- **CLI Tools**: Full-featured command-line interface
- **API Protocols**: A2A, MCP, JSON-RPC support
- **Executors**: 12+ built-in executors for various use cases
- **Storage**: DuckDB + PostgreSQL support
- **Extensions**: Plugin system with 50+ extensions

---

## Package Structure Updates

```toml
[project.optional-dependencies]
# New protocols
graphql = ["strawberry-graphql>=0.219.0"]
mqtt = ["paho-mqtt>=1.6.1"]
websocket-server = ["websockets>=12.0"]

# Protocol development bundle
protocols = ["apflow[graphql,mqtt,websocket-server]"]

# Observability (user chooses backend)
observability = [
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
]

# Updated all
all = [
    "apflow[crewai,a2a,cli,postgres,llm-key-config,ssh,docker,grpc,mcp,llm,protocols,observability]",
]
```

---

## Explicitly NOT Planned

The following are **NOT core features** and will **NOT be implemented in the library**:

- ❌ **User Management** - Application-level concern
- ❌ **Authentication/Authorization** - Application-level concern  
- ❌ **Multi-Tenancy** - Application-level concern
- ❌ **RBAC** - Application-level concern
- ❌ **Audit Logging** - Application-level concern (observability hooks enable this)
- ✅ **Dashboard UI** - Separate project (apflow-webapp)
- ❌ **Secret Management** - Use external solutions (Vault, AWS Secrets Manager)

**Rationale:** These are application/business concerns, not orchestration concerns. Users should implement these in their own projects (like `apflow-demo`) using the extension system.

**How Users Add These:**
- Extend TaskRoutes naturally (demo project shows pattern)
- Use hook system for audit logging
- Implement custom middleware for auth
- Examples provided in `examples/extensions/` (reference only)

---

## Documentation Priorities

### Core Library Documentation
1. **"Library-First Architecture"** - Philosophy and design principles
2. **"Protocol Adapter Guide"** - Building custom protocol adapters
3. **"Fluent API Reference"** - TaskBuilder complete guide
4. **"Embedding Guide"** - Using apflow in your project

### Protocol Documentation
5. **"GraphQL Integration"** - Schema reference and examples
6. **"MQTT for Edge AI"** - IoT agent orchestration guide
7. **"Multi-Protocol Comparison"** - When to use which protocol
8. **"Observability Best Practices"** - Metrics, tracing, logging

### Advanced Guides
9. **"Testing Agent Workflows"** - Comprehensive testing guide
10. **"Coexistence Patterns"** - Using with Dagster, Prefect, Celery
11. **"VS Code Extension Guide"** - Developer tooling
12. **"Production Deployment"** - Scaling and operations

---

## Competitive Positioning

### Unique Value Proposition

**"The Protocol-First AI Agent Orchestration Library"**

- ✅ A2A Protocol (agent-to-agent communication)
- ✅ Multi-Protocol (GraphQL, MQTT, MCP, JSON-RPC, WebSocket)
- ✅ Library-First (embed anywhere, no framework lock-in)
- ✅ Observable (pluggable metrics, like Dagster)
- ✅ Lightweight (DuckDB → PostgreSQL)
- ✅ Developer-Friendly (fluent API, hot reload, VS Code)

### Key Differentiators

**vs. Dagster/Prefect:**
- AI agent-first design (not retrofitted from data pipelines)
- Multi-protocol support (they only have HTTP)
- Library-first (they're frameworks)
- Lightweight embedded mode (DuckDB)

**vs. LangGraph:**
- Less opinionated, more flexible
- Multi-protocol support
- A2A protocol for agent communication
- Can integrate with LangGraph workflows

**vs. Task Queues (Celery/Dramatiq/Taskiq):**
- Full orchestration (DAG support, dependencies)
- State persistence
- AI agent native features
- Multi-executor types

---

This roadmap focuses on what makes apflow unique: **protocol-first, library-first AI agent orchestration** that can be embedded anywhere and extended naturally.

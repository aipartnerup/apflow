# Development Roadmap

## Core Philosophy

**apflow** = Pure orchestration library + Optional framework components

- **Core:** Zero framework dependencies, embeddable in any project
- **Optional:** A2A/MCP servers, CLI tools, protocol adapters
- **Goal:** Easy integration, easy extension, can coexist with competitors

---

## Development Priorities

### Priority 1: Fluent API (TaskBuilder) ⭐⭐⭐

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

### Priority 2: Protocol Adapter Abstraction Layer ⭐⭐⭐

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
- Foundation for multi-protocol support
- Enables GraphQL/MQTT/WebSocket additions
- Improves testability
- No competitor has this abstraction

---

### Priority 3: GraphQL Protocol Adapter ⭐⭐⭐

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

### Priority 4: MQTT Protocol Adapter ⭐⭐

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

### Priority 5: Observability Hook System ⭐⭐

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

### Priority 6: Workflow Patterns Library ⭐⭐

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

### Priority 7: VS Code Extension ⭐

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

### Priority 8: Testing Utilities ⭐

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

### Priority 9: Hot Reload Development Mode ⭐

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

### Priority 10: Bidirectional WebSocket Server ⭐

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
- ✅ Fluent API reduces boilerplate by 50%
- ✅ GraphQL queries 30% faster than REST for complex trees
- ✅ Hot reload reduces iteration time by 70%
- ✅ Testing utilities enable 90%+ test coverage

### Competitive Success Criteria
- ✅ Multi-protocol support (A2A, MCP, GraphQL, MQTT, WebSocket)
- ✅ Observable (like Dagster, but for agents)
- ✅ Lightweight (DuckDB → PostgreSQL)
- ✅ Can coexist with Dagster, Prefect, Celery

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

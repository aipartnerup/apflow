# Roadmap

> Pure orchestration library + Optional framework components

## Current Status (v1.x)

Core orchestration is stable with 800+ tests. Key capabilities:
- Task orchestration with dependency trees and priority execution
- 12+ executors (REST, WebSocket, gRPC, SSH, Docker, CrewAI, LiteLLM, MCP)
- Multi-protocol API (A2A, MCP, JSON-RPC)
- CLI and ConfigManager
- DuckDB + PostgreSQL storage

---

## Near-term

| Feature | Status | Description |
|---------|--------|-------------|
| Distributed Core | Planned | Multi-node orchestration with task leasing |
| Protocol Abstraction | Planned | Unified adapter interface for all protocols |
| GraphQL Adapter | Planned | Query interface for complex task trees |

### Distributed Core

Enable multi-node deployments with centralized coordination. See [design doc](distributed-orchestration-design.md) for details.

- Node registry with health checks
- Task leasing with automatic expiry
- Placement constraints (executor type, resources)
- PostgreSQL-based coordination

### Protocol Abstraction

Unified interface for protocol adapters:

```python
class ProtocolAdapter(Protocol):
    async def handle_execute_request(self, request: dict) -> dict: ...
    async def handle_status_request(self, request: dict) -> dict: ...
```

### GraphQL Adapter

Optional `strawberry-graphql` based adapter for querying task trees.

---

## Mid-term

| Feature | Status | Description |
|---------|--------|-------------|
| MQTT Adapter | Planned | IoT/Edge AI agent communication |
| Observability Hooks | Planned | Pluggable metrics (Prometheus, OpenTelemetry) |
| Workflow Patterns | Planned | Map-Reduce, Fan-Out/Fan-In, Circuit Breaker |
| Testing Utilities | Planned | TaskMocker, workflow simulation |

---

## Future

| Feature | Status | Description |
|---------|--------|-------------|
| VS Code Extension | Idea | Task tree visualization |
| Hot Reload | Idea | Auto-reload on code changes |
| WebSocket Server | Idea | Bidirectional agent collaboration |

---

## Not Planned

These are application-level concerns, not orchestration:

- User Management / Auth / RBAC
- Multi-Tenancy
- Audit Logging (use observability hooks)
- Secret Management (use Vault, AWS Secrets Manager)
- Dashboard UI (separate project: apflow-webapp)

---

## Completed

| Feature | Version | Notes |
|---------|---------|-------|
| Fluent API (TaskBuilder) | v1.x | Type-safe chainable task creation |
| CLI → API Gateway | v1.x | CLI routes through API when configured |
| ConfigManager | v1.x | Unified configuration management |
| Task Model Extensions | v1.x | task_tree_id, origin_type, migrations |
| Executor Access Control | v1.x | Environment-based filtering |

# Protocol Abstraction Phase 2

> Formal ProtocolAdapter interface for unified protocol handling

## Overview

Phase 1 of Protocol Abstraction is complete: capabilities registry, A2A adapter, MCP adapter, and native API. Phase 2 formalizes the `ProtocolAdapter` interface to make adding new protocols (GraphQL, REST, MQTT, etc.) a standardized process.

## Current State (Phase 1 - Complete)

- `api/capabilities.py`: `OperationDef` and registry as single source of truth for all 15 operations
- `api/routes/tasks.py`: `TaskRoutes` - protocol-agnostic core handler methods
- `api/a2a/`: A2A protocol adapter (agent-level actions: execute, generate, cancel)
- `api/mcp/`: MCP protocol adapter (all 15 operations as MCP tools)
- `api/protocols.py`: Protocol selection, dependency checking
- Native API: `POST /tasks` with JSON-RPC, `GET /tasks/methods` discovery

## Phase 2 Requirements

### 1. Formal ProtocolAdapter Protocol

Define a `ProtocolAdapter` Protocol (PEP 544) that all protocol adapters must implement:

```python
class ProtocolAdapter(Protocol):
    """Protocol interface for all protocol adapters."""

    @property
    def protocol_name(self) -> str: ...

    @property
    def supported_operations(self) -> list[str]: ...

    async def handle_request(self, operation_id: str, params: dict) -> dict: ...

    async def handle_streaming_request(self, operation_id: str, params: dict) -> AsyncIterator[dict]: ...

    def create_app(self, task_routes: TaskRoutes) -> Any: ...

    def get_discovery_info(self) -> dict: ...
```

### 2. Refactor Existing Adapters

Refactor A2A and MCP adapters to implement the `ProtocolAdapter` interface:
- `A2AProtocolAdapter(ProtocolAdapter)`
- `MCPProtocolAdapter(ProtocolAdapter)`

### 3. Protocol Registry

Create a protocol registry that:
- Discovers available protocol adapters
- Validates protocol dependencies
- Creates protocol instances
- Provides unified server creation

### 4. Unified Server Factory

Update `api/app.py` to use the protocol registry:
```python
def create_app(protocol: str, **kwargs) -> Any:
    adapter = protocol_registry.get_adapter(protocol)
    return adapter.create_app(task_routes)
```

### 5. Multi-Protocol Support

Enable running multiple protocols simultaneously:
- A2A on port 8000
- MCP on port 8001
- Native API always available at POST /tasks

### 6. Protocol Discovery Endpoint

Enhance `GET /tasks/methods` to include per-protocol availability:
```json
{
  "protocols": {
    "a2a": {"status": "active", "operations": ["execute", "generate", "cancel"]},
    "mcp": {"status": "available", "operations": ["all 15"]},
    "graphql": {"status": "not_installed", "install": "pip install apflow[graphql]"}
  }
}
```

## Technology Stack

- **Language**: Python 3.11+
- **Typing**: Protocol (PEP 544) from typing
- **Web Framework**: Starlette/FastAPI (existing)
- **Pattern**: Strategy pattern with protocol registry

## Dependencies

- No new external dependencies required
- Refactoring of existing `api/` modules

## Testing Requirements

- Unit tests for ProtocolAdapter interface compliance
- Tests for protocol registry
- Tests for server factory
- Integration tests for each adapter
- Backward compatibility tests (existing A2A/MCP behavior unchanged)

## Acceptance Criteria

- [ ] `ProtocolAdapter` Protocol defined and documented
- [ ] A2A adapter implements ProtocolAdapter
- [ ] MCP adapter implements ProtocolAdapter
- [ ] Protocol registry discovers and manages adapters
- [ ] Unified server factory works with any adapter
- [ ] All existing API tests pass unchanged
- [ ] New protocol can be added by implementing ProtocolAdapter only

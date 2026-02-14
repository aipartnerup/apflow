# Distributed Core

> Multi-node task orchestration with centralized coordination

## Overview

Enable multi-node deployments for apflow with centralized coordination via PostgreSQL. Workers can execute tasks distributed across multiple nodes, with lease-based task assignment and automatic failover.

## Detailed Design Reference

See `docs/development/distributed-development.md` for the full architecture design document (1050+ lines).

## Core Requirements

### Single Codebase, Dynamic Roles
- All nodes run the same code; role determined at runtime
- **Leader**: Single writer, handles lease acquisition/renewal, serves read/write API
- **Worker**: Polls for tasks, acquires lease, executes, reports results
- **Observer**: Read-only endpoints for CLI/dashboard
- Role selection via `APFLOW_NODE_ROLE` env var or automatic leader election

### Data Model Extensions (PostgreSQL-only)
- Extend `TaskModel` with distributed fields: `lease_id`, `lease_expires_at`, `placement_constraints`, `attempt_id`, `idempotency_key`, `last_assigned_node`
- New tables: `apflow_distributed_nodes`, `apflow_task_leases`, `apflow_execution_idempotency`, `apflow_cluster_leader`, `apflow_task_events`
- Dialect-aware migrations (PostgreSQL gets full tables, DuckDB gets nullable columns only)

### Leader Election (SQL-based)
- Atomic INSERT with ON CONFLICT DO NOTHING
- Lease renewal every 10s (30s TTL)
- Automatic re-election on leader failure

### Node Registry
- Register/deregister nodes with executor types and capabilities
- Heartbeat mechanism with stale/dead detection
- Query by executor types and capabilities

### Lease Manager
- Atomic lease acquisition (INSERT WHERE NOT EXISTS)
- Token-based renewal
- Expired lease cleanup

### Placement Constraints
- `requires_executors`, `requires_capabilities`, `allowed_nodes`, `forbidden_nodes`, `max_parallel_per_node`

### Idempotency
- Key: `hash(task_id + attempt_id + inputs)`
- Cache results to prevent duplicate execution on retries

### Worker Runtime
- Poll → Acquire lease → Execute → Renew lease → Report completion
- Background lease renewal loop during execution
- Heartbeat to keep node alive

### Integration
- Wire distributed services into TaskExecutor/TaskManager
- Role-aware entrypoints
- API layer leader-only write enforcement
- Backward compatibility: single-node mode unchanged

## Technology Stack

- **Language**: Python 3.11+
- **Database**: PostgreSQL (required for distributed mode)
- **ORM**: SQLAlchemy (existing)
- **Async**: asyncio (existing)
- **Migration**: Alembic (existing)

## Implementation Phases

1. **Phase 0**: Preparation (ensure PostgreSQL tests pass, refactor TaskExecutor)
2. **Phase 1**: Storage & Schema (new tables, migrations, config)
3. **Phase 2**: Leader Services (NodeRegistry, LeaseManager, LeaderElection, PlacementEngine, IdempotencyManager)
4. **Phase 3**: Worker Runtime (polling, lease renewal, execution)
5. **Phase 4**: Integration (wire into TaskExecutor/TaskManager, role selection)
6. **Phase 5**: Observability (task events, metrics, integration tests)

## Testing Requirements

- Unit tests >= 90% coverage for all distributed modules
- Integration tests: leader + 2 workers end-to-end
- Failure scenarios: worker crash, long tasks, leader failover
- Concurrent lease acquisition
- Backward compatibility tests

## Acceptance Criteria

- [ ] Multi-node task execution works end-to-end
- [ ] Lease-based assignment with automatic expiry
- [ ] Leader election and failover
- [ ] Placement constraints enforced
- [ ] Idempotent execution on retries
- [ ] Single-node mode unchanged (both PostgreSQL and DuckDB)
- [ ] All existing tests still pass
- [ ] Code quality: ruff, black, pyright zero errors

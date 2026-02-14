# Distributed Core - Feature Overview

## Overview

Enable multi-node task orchestration with centralized coordination via PostgreSQL. Implements lease-based task assignment, leader election, and role-based execution (leader/worker/observer) using a single codebase with runtime role selection.

## Scope

**Included:**
- Database schema extensions (5 new tables + TaskModel fields)
- Leader election (SQL-based, automatic)
- Node registry with heartbeat mechanism
- Lease manager (atomic acquisition, renewal, cleanup)
- Placement engine and idempotency manager
- Worker runtime (polling, execution, lease renewal)
- Integration with TaskExecutor/TaskManager
- Dialect-aware migrations (PostgreSQL full, DuckDB columns only)

**Excluded:**
- Fully decentralized consensus (Raft/Paxos)
- Multi-tenancy or RBAC
- Cross-region orchestration
- Distributed streaming (deferred to future)

## Technology Stack

- **Language**: Python 3.11+
- **Database**: PostgreSQL (required for distributed mode)
- **ORM**: SQLAlchemy
- **Async**: asyncio
- **Migration**: Alembic
- **Testing**: pytest, Strict TDD

## Task Execution Order

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | [storage-schema](./tasks/storage-schema.md) | Storage Schema, Data Models & Configuration | pending |
| 2 | [leader-services](./tasks/leader-services.md) | Leader Services (NodeRegistry, LeaseManager, LeaderElection, PlacementEngine, IdempotencyManager) | pending |
| 3 | [worker-runtime](./tasks/worker-runtime.md) | Worker Runtime | pending |
| 4 | [integration](./tasks/integration.md) | Integration, Role Selection & End-to-End Validation | pending |

## Progress

- **Total**: 4
- **Completed**: 0
- **In Progress**: 0
- **Pending**: 4

## Reference Documents

- [Feature Document](../../features/distributed-core.md)
- [Detailed Design](../../../docs/development/distributed-development.md)

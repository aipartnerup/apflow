# T2: Leader Services (NodeRegistry, LeaseManager, LeaderElection, PlacementEngine, IdempotencyManager)

## Goal

Implement five independently testable leader-side coordination services under `src/apflow/core/distributed/`. Each service receives a session factory via dependency injection, uses full type annotations, and has >= 90% unit test coverage. No changes to the existing execution path.

## Files Involved

### New Files
- `src/apflow/core/distributed/node_registry.py` -- Node registration, heartbeat, stale/dead detection
- `src/apflow/core/distributed/lease_manager.py` -- Atomic lease acquisition, renewal, cleanup
- `src/apflow/core/distributed/leader_election.py` -- SQL-based leader election with lease TTL
- `src/apflow/core/distributed/placement.py` -- Placement constraint evaluation and node filtering
- `src/apflow/core/distributed/idempotency.py` -- Idempotency key generation and result caching
- `tests/unit/distributed/test_node_registry.py`
- `tests/unit/distributed/test_lease_manager.py`
- `tests/unit/distributed/test_leader_election.py`
- `tests/unit/distributed/test_placement.py`
- `tests/unit/distributed/test_idempotency.py`
- `tests/unit/distributed/conftest.py` -- Shared fixtures (session factory, test nodes, etc.)

### Modified Files
- `src/apflow/core/distributed/__init__.py` -- Export public service classes

## Steps

### 1. Create shared test fixtures

Create `tests/unit/distributed/conftest.py` with:

```python
@pytest.fixture
def session_factory(pg_engine):
    """Provide a SQLAlchemy session factory connected to test PostgreSQL."""

@pytest.fixture
def sample_node() -> DistributedNode:
    """A healthy node with executor_types=['a2a'] and capabilities={'gpu': False}."""

@pytest.fixture
def sample_task(session_factory) -> TaskModel:
    """A pending task with no lease, persisted to DB."""
```

### 2. Implement NodeRegistry (test first)

Write `tests/unit/distributed/test_node_registry.py`:

```python
class TestNodeRegistry:
    async def test_register_node_creates_entry(self):
        """register_node inserts a DistributedNode with status='healthy'."""

    async def test_register_node_idempotent(self):
        """Registering the same node_id twice updates rather than duplicates."""

    async def test_heartbeat_updates_timestamp(self):
        """heartbeat(node_id) sets heartbeat_at to current time and status to 'healthy'."""

    async def test_heartbeat_nonexistent_node_raises(self):
        """heartbeat for unknown node_id raises NodeNotFoundError."""

    async def test_detect_stale_nodes(self):
        """Nodes with heartbeat older than stale_threshold are marked 'stale'."""

    async def test_detect_dead_nodes(self):
        """Nodes with heartbeat older than dead_threshold are marked 'dead'."""

    async def test_status_transitions_healthy_to_stale_to_dead(self):
        """Status transitions follow healthy -> stale -> dead lifecycle."""

    async def test_deregister_node_removes_entry(self):
        """deregister_node deletes the node and its leases."""

    async def test_query_by_executor_types(self):
        """get_nodes(executor_types=['a2a']) returns only matching healthy nodes."""

    async def test_query_by_capabilities(self):
        """get_nodes(capabilities={'gpu': True}) filters correctly."""
```

Implement `src/apflow/core/distributed/node_registry.py`:

```python
class NodeRegistry:
    def __init__(self, session_factory: SessionFactory, config: DistributedConfig) -> None: ...

    async def register_node(self, node_id: str, executor_types: list[str], capabilities: dict) -> DistributedNode: ...
    async def deregister_node(self, node_id: str) -> None: ...
    async def heartbeat(self, node_id: str) -> None: ...
    async def detect_stale_nodes(self) -> list[DistributedNode]: ...
    async def detect_dead_nodes(self) -> list[DistributedNode]: ...
    async def get_healthy_nodes(self, executor_types: list[str] | None = None, capabilities: dict | None = None) -> list[DistributedNode]: ...
```

### 3. Implement LeaseManager (test first)

Write `tests/unit/distributed/test_lease_manager.py`:

```python
class TestLeaseManager:
    async def test_acquire_lease_success(self):
        """acquire_lease for unleased task returns TaskLease with valid token."""

    async def test_acquire_lease_already_leased(self):
        """acquire_lease for task with active lease returns None."""

    async def test_concurrent_acquisition_only_one_wins(self):
        """Two concurrent acquire_lease calls for same task: exactly one succeeds."""

    async def test_renew_lease_extends_expiry(self):
        """renew_lease with valid token extends expires_at."""

    async def test_renew_lease_invalid_token_fails(self):
        """renew_lease with wrong token returns False."""

    async def test_renew_lease_expired_fails(self):
        """renew_lease on already-expired lease returns False."""

    async def test_cleanup_expired_leases(self):
        """cleanup_expired_leases deletes leases past expires_at and reverts tasks to pending."""

    async def test_release_lease_removes_entry(self):
        """release_lease deletes the lease row and clears task.lease_id."""

    async def test_select_for_update_skip_locked(self):
        """Lease acquisition uses SELECT FOR UPDATE SKIP LOCKED to avoid contention."""
```

Implement `src/apflow/core/distributed/lease_manager.py`:

```python
class LeaseManager:
    def __init__(self, session_factory: SessionFactory, config: DistributedConfig) -> None: ...

    async def acquire_lease(self, task_id: str, node_id: str) -> TaskLease | None:
        """Atomic lease acquisition using INSERT ... WHERE NOT EXISTS."""

    async def renew_lease(self, lease_token: str) -> bool:
        """Extend lease expiry. Returns False if token invalid or lease expired."""

    async def release_lease(self, task_id: str, lease_token: str) -> None:
        """Release a lease (graceful completion or shutdown)."""

    async def cleanup_expired_leases(self) -> list[str]:
        """Delete expired leases, revert tasks to pending, increment attempt_id. Returns affected task_ids."""
```

Key SQL pattern for acquisition:
```sql
INSERT INTO apflow_task_leases (task_id, node_id, lease_token, acquired_at, expires_at, attempt_id)
SELECT :task_id, :node_id, :lease_token, NOW(), NOW() + INTERVAL ':duration seconds', :attempt_id
WHERE NOT EXISTS (
    SELECT 1 FROM apflow_task_leases WHERE task_id = :task_id
);
```

### 4. Implement LeaderElection (test first)

Write `tests/unit/distributed/test_leader_election.py`:

```python
class TestLeaderElection:
    async def test_first_node_wins_leadership(self):
        """First try_acquire returns True and inserts leader row."""

    async def test_second_node_fails_gracefully(self):
        """Second try_acquire returns False when leader exists with valid lease."""

    async def test_renew_extends_ttl(self):
        """renew_leadership extends expires_at by leader_lease_seconds."""

    async def test_renew_wrong_token_fails(self):
        """renew_leadership with invalid token returns False."""

    async def test_stale_leader_replaced(self):
        """After leader lease expires, cleanup_stale + try_acquire succeeds for new node."""

    async def test_graceful_release(self):
        """release_leadership deletes leader row."""

    async def test_get_current_leader(self):
        """get_current_leader returns node_id of active leader or None."""

    async def test_is_leader_true_for_holder(self):
        """is_leader returns True only for the node holding the lease."""
```

Implement `src/apflow/core/distributed/leader_election.py`:

```python
class LeaderElection:
    def __init__(self, session_factory: SessionFactory, config: DistributedConfig) -> None: ...

    async def try_acquire(self, node_id: str) -> bool:
        """Attempt to acquire leadership via INSERT ... ON CONFLICT DO NOTHING."""

    async def renew_leadership(self, node_id: str, lease_token: str) -> bool:
        """Renew leader lease. Returns False if not the current leader."""

    async def release_leadership(self, node_id: str, lease_token: str) -> None:
        """Gracefully release leadership."""

    async def cleanup_stale_leader(self) -> bool:
        """Delete leader row if expired. Returns True if cleaned up."""

    async def get_current_leader(self) -> str | None:
        """Return node_id of current leader, or None."""

    async def is_leader(self, node_id: str) -> bool:
        """Check if node_id is the current leader."""
```

Key SQL for acquisition:
```sql
INSERT INTO apflow_cluster_leader (leader_id, node_id, lease_token, acquired_at, expires_at)
VALUES ('singleton', :node_id, :lease_token, NOW(), NOW() + INTERVAL '30 seconds')
ON CONFLICT (leader_id) DO NOTHING;
```

### 5. Implement PlacementEngine (test first)

Write `tests/unit/distributed/test_placement.py`:

```python
class TestPlacementEngine:
    def test_no_constraints_returns_all_healthy_nodes(self):
        """Tasks without placement_constraints match all healthy nodes."""

    def test_requires_executors_filters_nodes(self):
        """Only nodes with matching executor_types are eligible."""

    def test_requires_capabilities_filters_nodes(self):
        """Only nodes with matching capabilities dict entries are eligible."""

    def test_allowed_nodes_whitelist(self):
        """Only nodes in allowed_nodes list are eligible."""

    def test_forbidden_nodes_blacklist(self):
        """Nodes in forbidden_nodes list are excluded."""

    def test_allowed_and_forbidden_combined(self):
        """forbidden_nodes takes precedence over allowed_nodes."""

    def test_max_parallel_per_node_enforcement(self):
        """Nodes at max_parallel_per_node active leases are excluded."""

    def test_empty_eligible_nodes_returns_empty_list(self):
        """When no nodes match, returns empty list (not an error)."""
```

Implement `src/apflow/core/distributed/placement.py`:

```python
class PlacementEngine:
    def __init__(self, session_factory: SessionFactory) -> None: ...

    async def find_eligible_nodes(
        self,
        placement_constraints: dict | None,
        healthy_nodes: list[DistributedNode],
        active_leases_by_node: dict[str, int],
    ) -> list[DistributedNode]:
        """Evaluate constraints and return eligible nodes."""
```

### 6. Implement IdempotencyManager (test first)

Write `tests/unit/distributed/test_idempotency.py`:

```python
class TestIdempotencyManager:
    def test_generate_key_deterministic(self):
        """Same (task_id, attempt_id, inputs) produces same key."""

    def test_generate_key_different_inputs_differ(self):
        """Different inputs produce different keys."""

    async def test_check_cached_result_miss(self):
        """check_cached_result returns (False, None) for unknown key."""

    async def test_check_cached_result_hit(self):
        """check_cached_result returns (True, result) for completed key."""

    async def test_store_result_creates_entry(self):
        """store_result inserts ExecutionIdempotency row."""

    async def test_status_transitions_pending_to_completed(self):
        """Status changes from 'pending' to 'completed' after store_result."""

    async def test_status_transitions_pending_to_failed(self):
        """Status changes from 'pending' to 'failed' after store_failure."""
```

Implement `src/apflow/core/distributed/idempotency.py`:

```python
class IdempotencyManager:
    def __init__(self, session_factory: SessionFactory) -> None: ...

    @staticmethod
    def generate_key(task_id: str, attempt_id: int, inputs: dict | None) -> str:
        """Generate idempotency key: hash(task_id + attempt_id + json(inputs))."""

    async def check_cached_result(self, idempotency_key: str) -> tuple[bool, dict | None]:
        """Return (is_cached, result). is_cached=True if status='completed'."""

    async def store_result(self, task_id: str, attempt_id: int, idempotency_key: str, result: dict, status: str) -> None:
        """Store or update execution result."""
```

### 7. Update `__init__.py` exports

Update `src/apflow/core/distributed/__init__.py` to export all five services.

### 8. Run tests and quality checks

```bash
pytest tests/unit/distributed/ -v --cov=src/apflow/core/distributed --cov-report=term-missing
pytest tests/ -v  # Full suite for backward compatibility
ruff check --fix .
black .
pyright .
```

Verify coverage >= 90% on each service module.

## Acceptance Criteria

- [ ] `NodeRegistry`: registration, heartbeat updates, status transitions (healthy -> stale -> dead), query by executor_types and capabilities, deregistration
- [ ] `LeaseManager`: atomic acquisition (INSERT ... WHERE NOT EXISTS), concurrent acquisition (only one wins), token-based renewal, expired lease cleanup, lease release, SELECT FOR UPDATE SKIP LOCKED
- [ ] `LeaderElection`: first node wins, second fails gracefully, renewal extends TTL, stale leader replaced, graceful release, get_current_leader
- [ ] `PlacementEngine`: constraint matching (executor types, capabilities), node filtering (allowed/forbidden), max_parallel_per_node enforcement
- [ ] `IdempotencyManager`: deterministic key generation, cache hit returns stored result, cache miss returns None, status transitions (pending -> completed/failed)
- [ ] All services instantiable independently with injected session factory
- [ ] Full type annotations on all public methods (no `Any` except external data)
- [ ] Functions <= 50 lines, single responsibility
- [ ] Logging via `logging` module (no `print()`)
- [ ] Unit test coverage >= 90% on `src/apflow/core/distributed/`
- [ ] All existing tests still pass (backward compatibility)
- [ ] Zero errors from `ruff check --fix .`, `black .`, `pyright .`

## Dependencies

- **Depends on**: T1 (Storage Schema, Data Models & Configuration)
- **Required by**: T3 (Worker Runtime)

## Estimated Time

~5 days

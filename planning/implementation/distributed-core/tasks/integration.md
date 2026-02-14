# T4: Integration, Role Selection & End-to-End Validation

## Goal

Wire distributed services into the existing `TaskExecutor` and `TaskManager`, implement the `DistributedRuntime` coordinator with role selection state machine, enforce leader-only writes at the API layer, emit task lifecycle events, and validate the full system end-to-end. Backward compatibility with single-node mode on both PostgreSQL and DuckDB must be verified.

## Files Involved

### New Files
- `src/apflow/core/distributed/runtime.py` -- `DistributedRuntime` coordinator with role selection state machine
- `tests/unit/distributed/test_runtime.py` -- Unit tests for role selection and lifecycle
- `tests/integration/distributed/test_end_to_end.py` -- Full end-to-end multi-node tests
- `tests/integration/distributed/conftest.py` -- `distributed_cluster` fixture

### Modified Files
- `src/apflow/core/execution/task_executor.py` -- Conditional `DistributedRuntime` initialization
- `src/apflow/core/execution/task_manager.py` -- Route execution through distributed or local path
- `src/apflow/core/distributed/__init__.py` -- Export `DistributedRuntime`

## Steps

### 1. Write tests first (TDD)

Create `tests/unit/distributed/test_runtime.py`:

```python
class TestDistributedRuntime:
    # --- Role Selection ---
    async def test_auto_role_attempts_leader_first(self):
        """node_role='auto': try_acquire is called; on success, role becomes 'leader'."""

    async def test_auto_role_falls_back_to_worker(self):
        """node_role='auto': if try_acquire fails, role becomes 'worker'."""

    async def test_leader_role_fails_if_cannot_acquire(self):
        """node_role='leader': raises RuntimeError if leadership acquisition fails."""

    async def test_worker_role_never_attempts_leadership(self):
        """node_role='worker': try_acquire is never called."""

    async def test_observer_role_read_only(self):
        """node_role='observer': no leader election, no worker polling, read-only."""

    # --- Lifecycle ---
    async def test_start_initializes_services(self):
        """start() registers node, selects role, launches background tasks."""

    async def test_shutdown_stops_all_background_tasks(self):
        """shutdown() cancels renewal/cleanup loops and worker runtime."""

    # --- Leader Background Tasks ---
    async def test_leader_runs_lease_cleanup_loop(self):
        """Leader runs cleanup_expired_leases at lease_cleanup_interval_seconds."""

    async def test_leader_runs_node_cleanup_loop(self):
        """Leader runs detect_stale_nodes + detect_dead_nodes periodically."""

    async def test_leader_renewal_loop(self):
        """Leader renews its own leadership lease every leader_renew_seconds."""

    async def test_leader_renewal_failure_demotes_to_worker(self):
        """If leader lease renewal fails, runtime transitions to worker role."""

    # --- Validation ---
    async def test_rejects_duckdb_dialect(self):
        """DistributedRuntime raises ValueError if dialect is 'duckdb'."""

    async def test_rejects_non_postgresql_dialect(self):
        """DistributedRuntime raises ValueError if dialect is not 'postgresql'."""

    # --- Properties ---
    async def test_is_leader_property(self):
        """is_leader returns True only when role is 'leader'."""

    async def test_current_role_property(self):
        """current_role returns the active role string."""
```

### 2. Implement DistributedRuntime

Create `src/apflow/core/distributed/runtime.py`:

```python
class DistributedRuntime:
    """Distributed runtime coordinator: role selection, lifecycle, background tasks."""

    def __init__(
        self,
        config: DistributedConfig,
        session_factory: SessionFactory,
    ) -> None:
        # Validate dialect
        dialect = self._get_dialect(session_factory)
        if dialect == "duckdb":
            raise ValueError(
                "Distributed mode requires PostgreSQL. "
                "DuckDB is single-writer and does not support multi-node coordination."
            )
        if dialect != "postgresql":
            raise ValueError(f"Distributed mode requires PostgreSQL, got: {dialect}")

        self._config = config
        self._session_factory = session_factory
        self._role: str = "initializing"
        self._lease_token: str | None = None

        # Initialize services
        self._node_registry = NodeRegistry(session_factory, config)
        self._lease_manager = LeaseManager(session_factory, config)
        self._leader_election = LeaderElection(session_factory, config)
        self._placement_engine = PlacementEngine(session_factory)
        self._idempotency = IdempotencyManager(session_factory)
        self._worker_runtime: WorkerRuntime | None = None
        self._background_tasks: list[asyncio.Task] = []

    @property
    def is_leader(self) -> bool: ...

    @property
    def current_role(self) -> str: ...

    async def start(self) -> None:
        """Register node, select role, launch background tasks."""

    async def shutdown(self) -> None:
        """Cancel background tasks, shutdown worker, release leadership, deregister."""

    async def _select_role(self) -> None:
        """Role selection state machine based on config.node_role."""

    async def _leader_renewal_loop(self) -> None:
        """Renew leader lease every leader_renew_seconds."""

    async def _lease_cleanup_loop(self) -> None:
        """Clean expired leases every lease_cleanup_interval_seconds."""

    async def _node_cleanup_loop(self) -> None:
        """Detect stale/dead nodes periodically."""
```

Role selection logic:

```python
async def _select_role(self) -> None:
    role_config = self._config.node_role

    if role_config == "observer":
        self._role = "observer"
        return

    if role_config == "worker":
        self._role = "worker"
        return

    if role_config in ("auto", "leader"):
        acquired = await self._leader_election.try_acquire(self._config.node_id)
        if acquired:
            self._role = "leader"
            # Start leader background tasks
            self._background_tasks.append(
                asyncio.create_task(self._leader_renewal_loop())
            )
            self._background_tasks.append(
                asyncio.create_task(self._lease_cleanup_loop())
            )
            self._background_tasks.append(
                asyncio.create_task(self._node_cleanup_loop())
            )
            return

        if role_config == "leader":
            raise RuntimeError(
                f"Node {self._config.node_id} configured as leader but "
                "could not acquire leadership. Another leader is active."
            )

        # auto: fall back to worker
        self._role = "worker"
```

### 3. Integrate into TaskExecutor

Modify `src/apflow/core/execution/task_executor.py`:

```python
# In __init__ or initialization method:
from apflow.core.distributed.config import get_distributed_config

distributed_config = get_distributed_config()
if distributed_config.enabled:
    from apflow.core.distributed.runtime import DistributedRuntime
    self._distributed_runtime = DistributedRuntime(
        distributed_config, self._session_factory
    )
else:
    self._distributed_runtime = None

# In start/initialization:
if self._distributed_runtime:
    await self._distributed_runtime.start()
```

Add leader-only check for task execution routing:

```python
async def execute_task_tree(self, ...):
    if self._distributed_runtime:
        if self._distributed_runtime.is_leader:
            return await self._execute_task_tree_local(...)
        else:
            raise RuntimeError("Non-leader nodes cannot initiate task tree execution directly")
    return await self._execute_task_tree_local(...)
```

### 4. Add leader-only write enforcement

Add to API layer (routes or middleware):

```python
def _require_leader(self) -> None:
    """Raise 503 if this node is not the leader."""
    if self._distributed_runtime and not self._distributed_runtime.is_leader:
        current_leader = await self._distributed_runtime._leader_election.get_current_leader()
        raise HTTPException(
            status_code=503,
            detail=f"Write operations require leader node. Current leader: {current_leader}"
        )
```

Apply `_require_leader()` to all mutating endpoints (create task, update task, delete task, execute task tree).

### 5. Add task event emission

Add event logging to key lifecycle points:

```python
async def _emit_event(
    self,
    session_factory: SessionFactory,
    task_id: str,
    event_type: str,
    node_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Insert a TaskEvent row."""
    event = TaskEvent(
        task_id=task_id,
        event_type=event_type,
        node_id=node_id,
        details=details or {},
    )
    # persist via session
```

Event types to emit:
- `created` -- when task is created
- `assigned` -- when lease is acquired
- `started` -- when execution begins
- `completed` -- when execution succeeds
- `failed` -- when execution fails
- `reassigned` -- when expired lease is cleaned up and task reverts to pending
- `cancelled` -- when task is cancelled

### 6. Write end-to-end integration tests

Create `tests/integration/distributed/conftest.py`:

```python
@pytest.fixture
async def distributed_cluster(pg_engine):
    """Start leader + N workers in-process for integration testing."""
    leader_config = DistributedConfig(enabled=True, node_id="leader-1", node_role="leader")
    worker_configs = [
        DistributedConfig(enabled=True, node_id=f"worker-{i}", node_role="worker")
        for i in range(1, 3)
    ]
    # ... start runtimes, yield, teardown
```

Create `tests/integration/distributed/test_end_to_end.py`:

```python
class TestEndToEnd:
    async def test_leader_plus_two_workers_execute_tasks(self, distributed_cluster):
        """Create 5 tasks, verify all complete across 2 workers."""

    async def test_worker_crash_lease_expiry_reassignment(self, distributed_cluster):
        """Stop a worker mid-execution -> lease expires -> task reassigned -> completes."""

    async def test_leader_failure_reelection(self, distributed_cluster):
        """Shutdown leader -> worker detects stale leader -> re-election -> new leader."""

    async def test_leader_failure_stale_lease_cleanup(self, distributed_cluster):
        """After re-election, new leader cleans up expired leases from old leader."""

    async def test_placement_constraints_filter_workers(self, distributed_cluster):
        """Task with requires_executors=['gpu'] only assigned to GPU-capable worker."""

    async def test_concurrent_lease_acquisition_five_workers_one_task(self, distributed_cluster):
        """5 workers race for 1 task: exactly 1 acquires lease, 4 get None."""

    async def test_idempotent_reexecution(self, distributed_cluster):
        """Task with cached result (from crashed worker) returns cached result on retry."""

    async def test_backward_compat_distributed_disabled(self, duckdb_engine):
        """With APFLOW_CLUSTER_ENABLED=false, TaskExecutor works exactly as before."""

    async def test_backward_compat_postgresql_single_node(self, pg_engine):
        """With APFLOW_CLUSTER_ENABLED=false on PostgreSQL, no distributed behavior."""

    async def test_task_events_emitted(self, distributed_cluster):
        """Verify task_events table has created, assigned, started, completed entries."""
```

### 7. Run full validation

```bash
# Unit tests
pytest tests/unit/distributed/ -v --cov=src/apflow/core/distributed --cov-report=term-missing

# Integration tests
pytest tests/integration/distributed/ -v

# Full backward compatibility
pytest tests/ -v

# Code quality
ruff check --fix .
black .
pyright .
```

## Acceptance Criteria

- [ ] `DistributedRuntime` implements role selection state machine: `auto` attempts leader then falls back to worker; `leader` fails if cannot acquire; `worker` never attempts leadership; `observer` is read-only
- [ ] `DistributedRuntime` validates dialect and rejects non-PostgreSQL
- [ ] `DistributedRuntime` manages background tasks: leader lease renewal, expired lease cleanup, stale/dead node detection
- [ ] Leader lease renewal failure triggers demotion to worker role
- [ ] `TaskExecutor` conditionally initializes `DistributedRuntime` only when `APFLOW_CLUSTER_ENABLED=true`
- [ ] `TaskExecutor` routes execution through distributed or local path based on role
- [ ] Leader-only write enforcement returns 503 with current leader info on non-leader nodes
- [ ] Task events emitted for all lifecycle transitions (created, assigned, started, completed, failed, reassigned, cancelled)
- [ ] End-to-end: leader + 2 workers execute tasks correctly
- [ ] End-to-end: worker crash -> lease expiry -> reassignment -> idempotent re-execution
- [ ] End-to-end: leader failure -> re-election -> stale lease cleanup
- [ ] End-to-end: placement constraints filter eligible workers
- [ ] End-to-end: concurrent lease acquisition (5 workers, 1 task) -- exactly 1 wins
- [ ] Backward compatibility: all existing tests pass with distributed mode disabled
- [ ] Backward compatibility: single-node DuckDB and PostgreSQL unchanged
- [ ] Unit test coverage >= 90% on `src/apflow/core/distributed/runtime.py`
- [ ] Full type annotations on all public methods
- [ ] Functions <= 50 lines, single responsibility
- [ ] Logging via `logging` module (no `print()`)
- [ ] Zero errors from `ruff check --fix .`, `black .`, `pyright .`

## Dependencies

- **Depends on**: T3 (Worker Runtime)
- **Required by**: None (final task)

## Estimated Time

~4 days

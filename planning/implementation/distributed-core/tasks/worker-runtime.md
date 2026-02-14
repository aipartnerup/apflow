# T3: Worker Runtime

## Goal

Implement the complete worker execution loop: async polling for executable tasks, atomic lease acquisition, local task execution via existing `TaskManager.distribute_task_tree()`, background lease renewal, heartbeat, idempotency checking, result reporting, concurrency control, and graceful shutdown. The worker runtime uses the leader services from T2 as building blocks.

## Files Involved

### New Files
- `src/apflow/core/distributed/worker.py` -- `WorkerRuntime` class with async polling/execution loop
- `tests/unit/distributed/test_worker.py` -- Unit tests for worker runtime
- `tests/integration/distributed/__init__.py`
- `tests/integration/distributed/test_worker_integration.py` -- Integration tests with real DB

### Modified Files
- `src/apflow/core/distributed/__init__.py` -- Export `WorkerRuntime`

## Steps

### 1. Write tests first (TDD)

Create `tests/unit/distributed/test_worker.py`:

```python
class TestWorkerRuntime:
    async def test_poll_receives_executable_tasks(self):
        """Worker polling returns tasks with status=pending, dependencies satisfied, no active lease."""

    async def test_acquire_lease_atomically(self):
        """Worker acquires lease via LeaseManager; second worker for same task gets None."""

    async def test_lease_renewal_extends_expiry(self):
        """Background renewal loop extends lease expiry during long-running tasks."""

    async def test_lease_renewal_failure_stops_execution(self):
        """If lease renewal returns False (e.g., expired), worker cancels the running task."""

    async def test_idempotency_cache_hit_skips_execution(self):
        """When IdempotencyManager.check_cached_result returns (True, result), worker skips execution."""

    async def test_idempotency_cache_miss_executes_task(self):
        """When check_cached_result returns (False, None), worker executes and stores result."""

    async def test_heartbeat_keeps_node_healthy(self):
        """Background heartbeat loop calls NodeRegistry.heartbeat periodically."""

    async def test_graceful_shutdown_releases_leases(self):
        """shutdown() cancels running tasks, releases all leases, deregisters node."""

    async def test_graceful_shutdown_deregisters_node(self):
        """After shutdown(), NodeRegistry no longer lists this node."""

    async def test_max_parallel_tasks_enforced(self):
        """Semaphore limits concurrent task execution to max_parallel_tasks_per_node."""

    async def test_max_parallel_blocks_additional(self):
        """When semaphore is full, worker waits instead of acquiring more leases."""

    async def test_worker_crash_lease_expires(self):
        """When worker stops without shutdown, lease expires and task becomes re-assignable."""

    async def test_completion_reporting_persists_result(self):
        """After execution, worker updates task status to 'completed' and stores result."""

    async def test_failure_reporting_persists_error(self):
        """On execution failure, worker updates task status to 'failed' and stores error."""

    async def test_execution_uses_task_manager(self):
        """Worker delegates to TaskManager.distribute_task_tree() for local execution."""
```

### 2. Implement WorkerRuntime

Create `src/apflow/core/distributed/worker.py`:

```python
class WorkerRuntime:
    """Worker execution loop with lease lifecycle management."""

    def __init__(
        self,
        node_id: str,
        config: DistributedConfig,
        session_factory: SessionFactory,
        node_registry: NodeRegistry,
        lease_manager: LeaseManager,
        idempotency_manager: IdempotencyManager,
        task_manager: TaskManager,
    ) -> None:
        self._node_id = node_id
        self._config = config
        self._node_registry = node_registry
        self._lease_manager = lease_manager
        self._idempotency = idempotency_manager
        self._task_manager = task_manager
        self._semaphore = asyncio.Semaphore(config.max_parallel_tasks_per_node)
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start worker: register node, launch polling + heartbeat loops."""

    async def shutdown(self) -> None:
        """Graceful shutdown: cancel tasks, release leases, deregister."""

    async def _poll_loop(self) -> None:
        """Poll for executable tasks at config.poll_interval_seconds."""

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat at config.heartbeat_interval_seconds."""

    async def _execute_task(self, task: TaskModel) -> None:
        """Full task lifecycle: acquire -> renew -> check idempotency -> execute -> report."""

    async def _renew_lease_loop(self, task_id: str, lease_token: str) -> None:
        """Renew lease every leader_renew_seconds. Cancel task if renewal fails."""

    async def _report_completion(self, task_id: str, lease_token: str, result: dict) -> None:
        """Update task status, store result, release lease."""

    async def _report_failure(self, task_id: str, lease_token: str, error: str) -> None:
        """Update task status to failed, store error, release lease."""
```

### 3. Implement the polling loop

The polling loop should:
1. Wait on `_shutdown_event` with timeout of `poll_interval_seconds`
2. If shutdown signaled, break
3. Query for executable tasks (status=pending, dependencies met, no active lease)
4. For each task, try to acquire the semaphore (non-blocking check)
5. If semaphore available, spawn `_execute_task` as asyncio.Task
6. Track in `_running_tasks[task_id]`

```python
async def _poll_loop(self) -> None:
    while not self._shutdown_event.is_set():
        try:
            tasks = await self._find_executable_tasks()
            for task in tasks:
                if self._semaphore.locked():
                    break  # At capacity
                asyncio.create_task(self._execute_task_wrapper(task))
        except Exception:
            logger.error("Error in poll loop", exc_info=True)
        await asyncio.wait_for(
            self._shutdown_event.wait(),
            timeout=self._config.poll_interval_seconds,
        )
```

### 4. Implement the task execution lifecycle

```python
async def _execute_task(self, task: TaskModel) -> None:
    async with self._semaphore:
        # 1. Acquire lease
        lease = await self._lease_manager.acquire_lease(task.id, self._node_id)
        if not lease:
            return  # Already leased by another worker

        # 2. Start lease renewal (background)
        renewal = asyncio.create_task(
            self._renew_lease_loop(task.id, lease.lease_token)
        )

        try:
            # 3. Check idempotency cache
            key = IdempotencyManager.generate_key(task.id, task.attempt_id, task.inputs)
            is_cached, cached_result = await self._idempotency.check_cached_result(key)

            if is_cached and cached_result is not None:
                result = cached_result
            else:
                # 4. Execute via TaskManager
                result = await self._task_manager.distribute_task_tree(task)
                await self._idempotency.store_result(
                    task.id, task.attempt_id, key, result, "completed"
                )

            # 5. Report completion
            await self._report_completion(task.id, lease.lease_token, result)
        except asyncio.CancelledError:
            logger.warning(f"Task {task.id} cancelled (lease renewal failed or shutdown)")
            raise
        except Exception as exc:
            await self._report_failure(task.id, lease.lease_token, str(exc))
        finally:
            renewal.cancel()
            self._running_tasks.pop(task.id, None)
```

### 5. Implement lease renewal loop

```python
async def _renew_lease_loop(self, task_id: str, lease_token: str) -> None:
    interval = self._config.leader_renew_seconds
    while not self._shutdown_event.is_set():
        await asyncio.sleep(interval)
        success = await self._lease_manager.renew_lease(lease_token)
        if not success:
            logger.error(f"Lease renewal failed for task {task_id}, cancelling execution")
            running = self._running_tasks.get(task_id)
            if running:
                running.cancel()
            return
```

### 6. Implement graceful shutdown

```python
async def shutdown(self) -> None:
    self._shutdown_event.set()

    # Cancel all running tasks
    for task_id, task in self._running_tasks.items():
        task.cancel()
        logger.info(f"Cancelled running task: {task_id}")

    # Wait for cancellations to complete
    if self._running_tasks:
        await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)

    # Release all held leases
    # (LeaseManager.cleanup_expired_leases will handle any that remain)

    # Deregister node
    await self._node_registry.deregister_node(self._node_id)
    logger.info(f"Worker {self._node_id} shut down gracefully")
```

### 7. Write integration tests

Create `tests/integration/distributed/test_worker_integration.py`:

```python
class TestWorkerIntegration:
    async def test_worker_polls_and_executes_task(self, pg_session, worker_runtime):
        """End-to-end: insert pending task -> worker polls -> acquires lease -> executes -> completes."""

    async def test_two_workers_one_task(self, pg_session):
        """Two WorkerRuntimes polling same DB: only one acquires the lease."""

    async def test_long_task_lease_renewal(self, pg_session, worker_runtime):
        """Task taking >lease_duration completes because renewal extends expiry."""

    async def test_worker_crash_recovery(self, pg_session):
        """Worker stops mid-execution -> lease expires -> task becomes re-assignable."""
```

### 8. Run tests and quality checks

```bash
pytest tests/unit/distributed/test_worker.py -v
pytest tests/integration/distributed/ -v
pytest tests/ -v  # Full suite
ruff check --fix .
black .
pyright .
```

## Acceptance Criteria

- [ ] Worker polls for executable tasks (pending, dependencies met, no active lease)
- [ ] Worker acquires lease atomically (concurrent workers, only one succeeds)
- [ ] Background lease renewal extends expiry during long-running tasks
- [ ] Lease renewal failure cancels the running task gracefully
- [ ] Idempotency cache hit skips execution and returns cached result
- [ ] Idempotency cache miss executes task and stores result
- [ ] Background heartbeat keeps node status healthy in NodeRegistry
- [ ] Graceful shutdown cancels running tasks, releases leases, deregisters node
- [ ] Max parallel tasks enforced via asyncio.Semaphore (blocks additional acquisitions)
- [ ] Worker crash scenario: lease expires, task becomes re-assignable
- [ ] Completion/failure reporting updates task status and persists result/error
- [ ] Worker delegates to `TaskManager.distribute_task_tree()` for local execution
- [ ] Full type annotations on all public methods
- [ ] Functions <= 50 lines, single responsibility
- [ ] Logging via `logging` module (no `print()`)
- [ ] Unit test coverage >= 90% on `src/apflow/core/distributed/worker.py`
- [ ] All existing tests still pass
- [ ] Zero errors from `ruff check --fix .`, `black .`, `pyright .`

## Dependencies

- **Depends on**: T2 (Leader Services -- NodeRegistry, LeaseManager, IdempotencyManager)
- **Required by**: T4 (Integration, Role Selection & End-to-End Validation)

## Estimated Time

~4 days

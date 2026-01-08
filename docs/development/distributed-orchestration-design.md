# Distributed Orchestration Design

## Architecture Philosophy

**apflow distributed orchestration** is built on the principle of **centralised coordination with decentralised execution**. Unlike fully peer-to-peer systems, we adopt a pragmatic approach:

- **Single writer authority**: One centralized API instance holds write permission to the task state database
- **Multiple readers**: CLI, replicas, and external tools read state via API (no direct DB access)
- **Stateless executors**: Worker nodes fetch tasks, execute, and report results (can be horizontally scaled)
- **Graceful failure handling**: Automatic task reassignment on node/lease expiry

This design eliminates the complexity of distributed consensus (Raft/Paxos) while maintaining data consistency and fault tolerance for typical orchestration workloads.

---

## Core Design Decisions

### 1. Why NOT Fully Distributed Consensus?

**Distributed consensus (Raft, Paxos) adds complexity without commensurate benefit for task orchestration:**

| Aspect | Consensus Required? | apflow Approach |
|--------|-------------------|-------------------|
| **Data Consistency** | ✓ Yes, but... | Single writer satisfies this |
| **Availability** | ✓ Partially | External HA tools (k8s, haproxy) handle coordinator failover |
| **Fault Tolerance** | ✓ Yes, but... | Lease-based recovery is sufficient |
| **Complexity** | ✗ High cost | Minimal (PostgreSQL locking) |

**Conclusion:** Orchestration is not a financial ledger. A coordinated failover (managed externally) is acceptable. Users deploying apflow can:
- Use k8s or Docker Swarm for coordinator HA (restart + virtual IP)
- Or accept single-instance architecture (sufficient for 80%+ of use cases)

### 2. Why Lease-Based, Not Lock-Based?

**Leases** are superior for distributed task assignment:

```
Lock-Based (Problems):
  - Lock must be explicitly released → task crash = permanent deadlock
  - Requires heartbeat monitoring anyway
  
Lease-Based (Solution):
  - Lease auto-expires → stale tasks are automatically reassigned
  - Heartbeat renewal is voluntary, not blocking
  - Simple cleanup: dead tasks just timeout
```

**Example:**

```python
# Node acquires lease for task_123
lease = await manager.acquire_lease("task_123", "node-1", duration=30s)

# If node-1 crashes without renewal, lease expires after 30s
# Coordinator detects expiry, marks task as "pending", another node picks it up

# If node-1 is healthy, it renews:
await lease.renew(duration=30s)  # Non-blocking
```

### 3. PostgreSQL as Distributed Lease Authority

**PostgreSQL provides sufficient distributed locking primitives:**

```sql
-- Distributed lease table
CREATE TABLE task_leases (
  task_id TEXT PRIMARY KEY,
  node_id TEXT,
  lease_token TEXT UNIQUE,
  acquired_at TIMESTAMP,
  expires_at TIMESTAMP,
  
  CONSTRAINT only_one_active_lease
    CHECK ((expires_at IS NULL) OR (expires_at > NOW()))
);

-- Atomic lease acquisition (PostgreSQL advisory lock or UNIQUE constraint)
INSERT INTO task_leases (task_id, node_id, lease_token, expires_at)
VALUES (?, ?, ?, NOW() + INTERVAL '30 seconds')
ON CONFLICT(task_id) DO NOTHING
RETURNING lease_token;  -- Returns NULL if task already leased
```

**DuckDB:** Cannot support this (no multi-writer transactions). Hence, **distributed mode requires PostgreSQL**.

### 4. Idempotency as First-Class Concern

Tasks can fail and be retried. Idempotency ensures safe re-execution:

```python
@dataclass
class ExecutionRecord:
    task_id: str
    attempt_id: str  # Unique per retry
    idempotency_key: str  # Deterministic, e.g., hash(task_id + attempt + input)
    result: Optional[dict]
    status: Literal["pending", "completed", "failed"]
    
async def execute_with_idempotency(task_id, attempt_id):
    idempotency_key = hash_combine(task_id, attempt_id, task.input)
    
    # Check if already executed
    cached = await db.get_idempotency_record(idempotency_key)
    if cached and cached.status == "completed":
        return cached.result  # Safe re-execution: return cached result
    
    # Execute
    result = await executor.execute(task)
    
    # Record execution
    await db.record_execution(idempotency_key, result, "completed")
    return result
```

**Benefits:**
- Retries are safe (idempotent)
- No duplicate side effects
- Transparent to users (executor doesn't need to know)

---

## System Components

### Node Registration & Discovery

```python
# 1. Node registers itself with capabilities
await registry.register_node(
    node_id="worker-1",
    capabilities={
        "cpu_cores": 8,
        "memory_gb": 32,
        "gpu": "nvidia",
        "labels": ["high-compute", "ml-optimized"],
    },
    executor_types=["rest_executor", "docker_executor"],
)

# 2. Coordinator tracks node health
async def health_check_loop():
    while True:
        nodes = await registry.list_nodes()
        for node in nodes:
            if not await ping(node.url):
                await registry.mark_stale(node.node_id)
        await asyncio.sleep(10)

# 3. Worker renews heartbeat
async def heartbeat_loop():
    while True:
        await registry.heartbeat(node_id)
        await asyncio.sleep(5)
```

### Task Placement & Scheduling

```python
@dataclass
class PlacementConstraints:
    requires_executors: list[str]  # Task needs one of these
    requires_capabilities: dict  # Task needs {"gpu": "nvidia"}
    max_parallel_per_node: int = 1  # Concurrency limit
    allowed_nodes: Optional[list[str]] = None  # Whitelist
    forbidden_nodes: Optional[list[str]] = None  # Blacklist

# Scheduler finds executable tasks
async def find_executable_tasks(node_id: str) -> list[Task]:
    """Find tasks this node can execute."""
    node = await registry.get_node(node_id)
    
    # Find tasks in "runnable" state
    tasks = await db.get_tasks(status="pending")
    
    # Filter by placement constraints
    executable = [
        t for t in tasks
        if satisfies_placement(t.placement_constraints, node)
           and not t.lease_id  # Not already leased
           and within_parallelism_limit(t, node)
    ]
    return executable

def satisfies_placement(constraints, node):
    # Check executor compatibility
    if constraints.requires_executors:
        if not any(e in node.executor_types for e in constraints.requires_executors):
            return False
    
    # Check capability requirements
    if constraints.requires_capabilities:
        for key, required_value in constraints.requires_capabilities.items():
            if key not in node.capabilities or node.capabilities[key] != required_value:
                return False
    
    # Check node whitelist/blacklist
    if constraints.allowed_nodes and node.node_id not in constraints.allowed_nodes:
        return False
    if constraints.forbidden_nodes and node.node_id in constraints.forbidden_nodes:
        return False
    
    return True
```

### Task Execution Flow

```
Coordinator (API)          Worker Node
         |
         |-- create task with placement constraints
         |-- mark task as "pending"
         |
         |<-- worker polls: find_executable_tasks(node_id)
         |
         |-- returns [task_123, task_124, ...]
         |
         |<-- worker attempts: acquire_lease(task_123, node_id)
         |
         |-- atomic: check no existing lease, insert lease row
         |-- returns lease_token or NULL
         |
         | (lease acquired for task_123)
         |
         |<-- worker: execute(task_123) with lease_token
         |
         | ... execution happens ...
         |
         |<-- worker: report_completion(task_123, result, idempotency_key)
         |
         |-- update task status, release lease, record result
         |
         |-- heartbeat: renew_lease(lease_token) [during long tasks]
         |
    [Failure: node crashes without renewal]
         |
         |-- lease expires after 30s
         |-- coordinator detects expiry
         |-- marks task as "pending" again
         |-- next healthy worker picks it up
```

### Replica & Read-Only Nodes

For CLI and external monitoring without direct database access:

```python
# Replica mode (read-only, no writes)
api_replica = create_a2a_server(
    mode="distributed_replica",
    coordinator_url="http://coordinator:8000",
)

# CLI uses replica
client = APIClient(coordinator_url="http://replica:8001")
tasks = await client.list_tasks()  # Reads from replica cache (synced from coordinator)
```

Replicas maintain a local cache of task state, synced asynchronously from the coordinator. Good for:
- Reducing load on coordinator
- Supporting offline queries (stale-read acceptable for dashboards)
- HA patterns where failover is external (k8s, haproxy)

---

## Failure Scenarios & Recovery

### Scenario 1: Worker Node Crashes During Execution

```
State Before:     task_123 has lease from node-1, expires at 10:05:30
Node-1 crashes at 10:05:00 (no graceful shutdown)

Timeline:
10:05:30 - Coordinator lease cleanup job runs
         - Detects expired lease for task_123
         - Marks task as "pending"
         - Increments attempt_id (1 → 2)

10:05:31 - Worker node-2 pulls executable tasks
         - Sees task_123 in "pending" state
         - Acquires lease for task_123
         - Executes (idempotency key includes attempt_id, so safe retry)

Result: Task completes on node-2 without user intervention
```

### Scenario 2: Long-Running Task (Heartbeat Renewal)

```python
async def execute_long_task(task_id, lease):
    """Long task that may take hours."""
    
    async def renew_periodically():
        while True:
            await asyncio.sleep(20)  # Renew every 20s, expire in 30s
            await lease.renew(duration=30)
    
    renew_task = asyncio.create_task(renew_periodically())
    
    try:
        result = await some_long_operation()
    finally:
        renew_task.cancel()
    
    return result
```

Worker maintains lease alive during execution. If renewal fails, node is unhealthy → lease expires → task reassigned.

### Scenario 3: Coordinator Failure

```
Coordinator API is down.

For Workers:
  - Cannot acquire new leases
  - Continue executing current tasks (with renewal if possible)
  - Wait for coordinator recovery

For CLI/Replicas:
  - Cannot reach coordinator directly
  - Use cached state from last sync
  - Or connect to a replica (if available)

Recovery (External HA):
  - k8s: restart Pod, remap virtual IP
  - haproxy: switch to backup coordinator
  - Manual: operator restarts API, resumes state from database
```

**Note:** Distributed mode does NOT require distributed consensus. Coordinator failover is a deployment concern, not a core requirement.

---

## API Extensions for Distribution

### TaskManager API

```python
class DistributedTaskManager(TaskManager):
    # Node management
    async def register_node(self, node_id: str, capabilities: dict) -> NodeInfo: ...
    async def heartbeat(self, node_id: str) -> None: ...
    async def deregister_node(self, node_id: str) -> None: ...
    
    # Task assignment
    async def find_executable_tasks(self, node_id: str) -> list[Task]: ...
    async def acquire_lease(
        self, 
        task_id: str, 
        node_id: str,
        constraints: PlacementConstraints
    ) -> TaskLease: ...
    async def renew_lease(self, lease: TaskLease) -> None: ...
    
    # Execution completion
    async def report_completion(
        self,
        task_id: str,
        node_id: str,
        result: dict,
        idempotency_key: str
    ) -> None: ...
    
    # Recovery
    async def recover_stale_leases(self) -> list[str]: ...  # Reassign expired tasks
```

### Storage Layer Extension

```python
# Existing Task model extended with:
class Task(BaseModel):
    id: str
    # ... existing fields ...
    
    # Distributed fields (optional, used only in distributed mode)
    lease_id: Optional[str] = None  # Current lease holder
    lease_expires_at: Optional[datetime] = None
    placement_constraints: Optional[dict] = None
    idempotency_key: Optional[str] = None
    attempt_id: int = 0  # Increments on retry
    last_assigned_node: Optional[str] = None
```

---

## Database Schema

```sql
-- Nodes
CREATE TABLE distributed_nodes (
  node_id TEXT PRIMARY KEY,
  executor_types TEXT[],
  capabilities JSONB,
  status ENUM ('healthy', 'stale', 'dead'),
  heartbeat_at TIMESTAMP,
  registered_at TIMESTAMP
);

-- Task leases (distributed lock)
CREATE TABLE task_leases (
  task_id TEXT PRIMARY KEY REFERENCES tasks(id),
  node_id TEXT REFERENCES distributed_nodes(node_id),
  lease_token TEXT UNIQUE,
  acquired_at TIMESTAMP,
  expires_at TIMESTAMP,
  
  CONSTRAINT valid_expiry CHECK (expires_at > acquired_at)
);
CREATE INDEX idx_task_leases_expires_at ON task_leases(expires_at);

-- Idempotency cache (prevent duplicate execution)
CREATE TABLE execution_idempotency (
  task_id TEXT,
  attempt_id INT,
  idempotency_key TEXT UNIQUE,
  result JSONB,
  status ENUM ('pending', 'completed', 'failed'),
  created_at TIMESTAMP,
  
  PRIMARY KEY (task_id, attempt_id),
  FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Task state events (audit/observability)
CREATE TABLE task_events (
  event_id UUID PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  event_type ENUM (
    'created', 'pending', 'assigned', 'started', 
    'completed', 'failed', 'reassigned', 'cancelled'
  ),
  node_id TEXT,
  details JSONB,
  timestamp TIMESTAMP DEFAULT NOW()
);
```

---

## Configuration

### Single-Node Mode (Default)

```python
manager = TaskManager(
    storage=DuckDBStorage(path="apflow.db"),
    distributed=None,  # Disabled
)
```

### Distributed Coordinator Mode

```python
manager = TaskManager(
    storage=PostgreSQLStorage(url="postgresql://..."),
    distributed=DistributedConfig(
        mode="coordinator",
        node_id="api-main",
        heartbeat_timeout_seconds=30,
        lease_duration_seconds=30,
        cleanup_interval_seconds=10,
    ),
)
```

### Distributed Worker Mode

```python
manager = TaskManager(
    storage=PostgreSQLStorage(url="postgresql://..."),
    distributed=DistributedConfig(
        mode="worker",
        node_id="worker-1",
        coordinator_url="http://coordinator:8000",
        capabilities={
            "cpu_cores": 8,
            "memory_gb": 32,
            "gpu": "nvidia",
            "labels": ["high-compute"],
        },
        executor_types=["rest_executor", "docker_executor"],
        poll_interval_seconds=5,
    ),
)
```

---

## Deployment Patterns

### Pattern 1: Single Coordinator + Multiple Workers (Recommended)

```
┌────────────────────────────────────────────┐
│  apflow Coordinator (API)                  │
│  - Writes task state to PostgreSQL         │
│  - Accepts execute/status/cancel requests  │
│  - Manages node heartbeats                 │
│  - Runs lease cleanup job                  │
└────────────┬─────────────────────────────┬─┘
             │                             │
     ┌───────▼────────┐          ┌────────▼────────┐
     │  Worker Node 1 │          │  Worker Node 2  │
     │ - Polls tasks  │          │  - Polls tasks  │
     │ - Executes     │          │  - Executes     │
     │ - Reports back │          │  - Reports back │
     └────────────────┘          └─────────────────┘
             │                             │
             └──────────────┬──────────────┘
                            │
                    ┌───────▼────────┐
                    │  PostgreSQL    │
                    │ (task state)   │
                    └────────────────┘
```

**CLI/Monitoring:**
```
┌──────────────────┐
│  CLI / Dashboard │
│  (read replica)  │
│  - No DB access  │
│  - Queries API   │
└────────┬─────────┘
         │
    Query API (read-only)
         │
    ┌────▼────────────────────────────┐
    │  apflow API Replica (optional)   │
    │  - Caches task state from main   │
    │  - Serves read requests          │
    └─────────────────────────────────┘
```

### Pattern 2: HA Coordinator (k8s + External Loadbalancer)

```
┌─────────────────────────────────────────┐
│  Kubernetes Deployment                  │
│                                         │
│  Coordinator Replica 1 (Primary)        │
│  Coordinator Replica 2 (Standby)        │
│  Coordinator Replica 3 (Standby)        │
│                                         │
│  (k8s ensures exactly 1 is healthy)     │
└──────────┬────────────────────────────┬─┘
           │                            │
      (virtual IP via k8s Service)     │
           │                      ┌─────▼──────────┐
      Workers connect here       │  PostgreSQL    │
      (automatic failover)        │  (shared state)│
                                  └────────────────┘
```

**How it works:**
- k8s Service provides stable endpoint + automatic failover
- All Coordinator replicas share same PostgreSQL database
- Workers connect to Service (transparent failover)
- Only **one Coordinator writes** at a time (leader election via DB lock or external tool)

---

## Performance Considerations

### Lease Acquisition Latency

```
acquire_lease() involves:
1. Check: SELECT ... WHERE task_id = ? AND expires_at > NOW()
2. Insert: INSERT ... ON CONFLICT DO NOTHING
3. Return: lease_token or NULL

Expected latency: 1-5ms on healthy PostgreSQL
With 100 workers polling every 5s:
- Peak: ~20 lease acquisitions/sec
- PostgreSQL easily handles 1000+/sec
```

### Scaling Limits

| Component | Scaling Limit | Notes |
|-----------|---------------|-------|
| Workers | 1000+ | Each has independent task queue |
| Tasks/Second | 10,000+ | Depends on PostgreSQL performance |
| Task Tree Depth | Arbitrary | Scheduler is O(n) per poll |
| Concurrent Leases | Unlimited | One row per task in DB |

### Optimization Opportunities

1. **Batch Lease Acquisition**: Workers ask for 10 tasks at once
2. **Caching**: Worker caches task definitions locally
3. **Sharding**: Multiple coordinators per shard (by task_type or tenant)
4. **Async Lease Renewal**: Batch renew multiple leases in one DB round-trip

---

## Testing Strategy

### Unit Tests (25+ scenarios)

```python
# tests/core/distributed/test_leasing.py
async def test_acquire_lease_success()
async def test_acquire_lease_already_held()
async def test_lease_expiry_detection()
async def test_lease_renewal()
async def test_idempotent_execution_cached_result()
async def test_idempotent_execution_retry_with_new_attempt()

# tests/core/distributed/test_placement.py
async def test_placement_executor_constraint()
async def test_placement_capability_constraint()
async def test_placement_whitelist()
async def test_placement_blacklist()
async def test_placement_concurrency_limit()

# tests/core/distributed/test_node_registry.py
async def test_node_registration()
async def test_node_heartbeat()
async def test_node_stale_detection()
async def test_node_deregistration()

# tests/core/distributed/test_recovery.py
async def test_recover_expired_leases()
async def test_recover_on_node_crash()
async def test_reassign_to_healthy_node()
```

### Integration Tests

```python
# tests/integration/distributed/
async def test_end_to_end_task_execution()
async def test_multiple_workers_same_tree()
async def test_coordinator_failure_and_recovery()
async def test_worker_failure_during_execution()
async def test_long_running_task_with_heartbeat()
```

---

## Migration Path: Single-Node to Distributed

### Step 1: Switch Storage (Non-Breaking)

```python
# Before: DuckDB
manager = TaskManager(storage=DuckDBStorage(path="apflow.db"))

# After: PostgreSQL (still single-node)
manager = TaskManager(storage=PostgreSQLStorage(url="postgresql://..."))
```

All existing APIs remain unchanged. This is a pure storage upgrade.

### Step 2: Enable Distributed Mode

```python
# Before: Single-node
manager = TaskManager(
    storage=PostgreSQLStorage(url="postgresql://..."),
    distributed=None,
)

# After: Distributed coordinator
manager = TaskManager(
    storage=PostgreSQLStorage(url="postgresql://..."),
    distributed=DistributedConfig(mode="coordinator"),
)
```

All task definitions, executors, and APIs remain unchanged. Workers are added separately.

### Step 3: Deploy Workers

```python
# New worker processes
manager = TaskManager(
    storage=PostgreSQLStorage(url="postgresql://..."),
    distributed=DistributedConfig(
        mode="worker",
        node_id="worker-1",
        coordinator_url="http://coordinator:8000",
    ),
)
```

---

## FAQ

### Q: Do I need distributed mode?

**A:** Only if you need:
- Multiple machines for execution
- High availability (node failure tolerance)
- Horizontal scaling of workers

Single-node (PostgreSQL) is sufficient for 80% of use cases.

### Q: What if PostgreSQL is overkill? Can I use SQLite?

**A:** Not for distributed mode. SQLite lacks:
- ACID guarantees for multi-writer scenarios (we use single-writer, but...)
- Advisory locks for lease management
- Full transaction isolation levels

Use DuckDB (single-node, fast) or PostgreSQL (distributed-ready).

### Q: Can I run a distributed system without a coordinator?

**A:** Theoretically, you could implement peer-to-peer task discovery (e.g., via etcd or Consul), but:
- Complexity increases 10x
- No clear winner in architecture design
- apflow's coordinator is simple: just PostgreSQL + HTTP

If you need fully decentralized, consider Celery or Dask.

### Q: How do I handle secrets in distributed mode?

**A:** Secrets are **not** part of apflow. Use:
- Environment variables (injected per node)
- External secret manager (Vault, AWS Secrets Manager)
- Custom executor that fetches secrets at runtime

### Q: What about network failures between coordinator and workers?

**A:** Workers use leases as heartbeats:
- If network fails, lease expires → task reassigned
- Workers don't need continuous connectivity
- Eventual consistency is acceptable for orchestration

---

## Future Enhancements

1. **Raft-Based Coordinator** (Optional): If users demand true distributed consensus
2. **Task Sharding**: Split large task trees across multiple coordinators
3. **Workload Affinity**: Schedule tasks near data
4. **Advanced Placement**: Spot instances, heterogeneous resources, cost optimization
5. **Multi-Tenancy**: Isolated task namespaces per tenant

All above are additive features, not breaking changes to the core design.


# T1: Storage Schema, Data Models & Configuration

## Goal

Establish the database foundation for all distributed features: extend `TaskModel` with distributed fields, create five new PostgreSQL tables, implement a dialect-aware migration, and add `DistributedConfig` for cluster settings. Single-node mode on both PostgreSQL and DuckDB must remain unchanged.

## Files Involved

### New Files
- `src/apflow/core/storage/migrations/003_add_distributed_support.py` -- Dialect-aware migration
- `src/apflow/core/distributed/__init__.py` -- Package init (minimal)
- `src/apflow/core/distributed/config.py` -- `DistributedConfig` dataclass
- `tests/unit/distributed/__init__.py`
- `tests/unit/distributed/test_distributed_config.py`
- `tests/unit/distributed/test_distributed_models.py`
- `tests/unit/distributed/test_distributed_migration.py`

### Modified Files
- `src/apflow/core/storage/sqlalchemy/models.py` -- Add 5 new models + 6 nullable fields on `TaskModel`
- `src/apflow/core/config/registry.py` -- Register `DistributedConfig` accessors

## Steps

### 1. Write tests first (TDD)

Create `tests/unit/distributed/test_distributed_models.py`:

```python
def test_distributed_node_model_fields():
    """DistributedNode has required columns: node_id, executor_types, capabilities, status, heartbeat_at, registered_at."""

def test_task_lease_model_fields():
    """TaskLease has required columns: task_id, node_id, lease_token, acquired_at, expires_at, attempt_id."""

def test_execution_idempotency_model_fields():
    """ExecutionIdempotency has composite PK (task_id, attempt_id) and unique idempotency_key."""

def test_cluster_leader_model_fields():
    """ClusterLeader has leader_id PK and unique lease_token."""

def test_task_event_model_fields():
    """TaskEvent has event_id PK, task_id FK, event_type, node_id, details, timestamp."""

def test_task_model_distributed_fields_nullable():
    """TaskModel distributed fields (lease_id, lease_expires_at, etc.) are all nullable."""
```

Create `tests/unit/distributed/test_distributed_config.py`:

```python
def test_distributed_config_defaults():
    """DistributedConfig has correct defaults: enabled=False, node_role='auto', etc."""

def test_distributed_config_from_env(monkeypatch):
    """DistributedConfig loads from APFLOW_CLUSTER_ENABLED, APFLOW_NODE_ID, etc."""

def test_distributed_config_rejects_invalid_role():
    """DistributedConfig raises ValueError for invalid node_role."""

def test_get_set_distributed_config():
    """get_distributed_config / set_distributed_config round-trip works."""
```

Create `tests/unit/distributed/test_distributed_migration.py`:

```python
def test_migration_postgresql_creates_all_tables(pg_engine):
    """Migration creates 5 distributed tables on PostgreSQL."""

def test_migration_postgresql_adds_task_model_columns(pg_engine):
    """Migration adds 6 nullable columns to apflow_tasks on PostgreSQL."""

def test_migration_duckdb_skips_distributed_tables(duckdb_engine):
    """Migration only adds nullable columns on DuckDB, no distributed tables."""

def test_migration_rollback_postgresql(pg_engine):
    """Rollback drops all distributed tables and columns on PostgreSQL."""

def test_migration_rollback_duckdb(duckdb_engine):
    """Rollback drops only the added columns on DuckDB."""

def test_migration_on_existing_tasks(pg_engine_with_tasks):
    """Migration succeeds on a database with existing tasks; data is preserved."""

def test_existing_tests_pass_after_migration():
    """All pre-existing test suite passes after migration (backward compatibility)."""
```

### 2. Add new SQLAlchemy models to `models.py`

Add five new model classes after `TaskModel`:

```python
class DistributedNode(Base):
    __tablename__ = "apflow_distributed_nodes"
    node_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    executor_types: Mapped[list[str]] = mapped_column(JSON)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20))  # healthy, stale, dead
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

class TaskLease(Base):
    __tablename__ = "apflow_task_leases"
    task_id: Mapped[str] = mapped_column(String(100), ForeignKey("apflow_tasks.id"), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(100), ForeignKey("apflow_distributed_nodes.node_id"))
    lease_token: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempt_id: Mapped[int] = mapped_column(Integer, default=0)

class ExecutionIdempotency(Base):
    __tablename__ = "apflow_execution_idempotency"
    task_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    attempt_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # pending, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

class ClusterLeader(Base):
    __tablename__ = "apflow_cluster_leader"
    leader_id: Mapped[str] = mapped_column(String(100), primary_key=True, default="singleton")
    node_id: Mapped[str] = mapped_column(String(100), ForeignKey("apflow_distributed_nodes.node_id"))
    lease_token: Mapped[str] = mapped_column(String(100), unique=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

class TaskEvent(Base):
    __tablename__ = "apflow_task_events"
    event_id: Mapped[str] = mapped_column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(100), ForeignKey("apflow_tasks.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    node_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)
```

### 3. Extend `TaskModel` with 6 nullable distributed fields

Add to the `TaskModel` class body (after existing fields, before `to_dict`):

```python
# === Distributed Execution Fields (nullable, backward compatible) ===
lease_id = Column(String(100), nullable=True)
lease_expires_at = Column(DateTime(timezone=True), nullable=True)
placement_constraints = Column(JSON, nullable=True)
attempt_id = Column(Integer, default=0)
idempotency_key = Column(String(255), nullable=True)
last_assigned_node = Column(String(100), nullable=True)
```

Update `to_dict()` and `default_values()` to include the new fields.

### 4. Create dialect-aware migration

Create `src/apflow/core/storage/migrations/003_add_distributed_support.py` following the pattern in `002_add_scheduling_fields.py`:

- Detect dialect via `engine.dialect.name`
- **PostgreSQL**: Create all 5 distributed tables + add 6 columns to `apflow_tasks` + create indexes
- **DuckDB**: Only add 6 nullable columns to `apflow_tasks`, skip distributed tables
- **Downgrade**: Drop columns from both dialects; drop tables only on PostgreSQL

Key indexes to create on PostgreSQL:
```sql
CREATE INDEX idx_task_leases_expires_at ON apflow_task_leases(expires_at);
CREATE INDEX idx_task_leases_node_id ON apflow_task_leases(node_id);
CREATE INDEX idx_distributed_nodes_status ON apflow_distributed_nodes(status);
CREATE INDEX idx_distributed_nodes_heartbeat ON apflow_distributed_nodes(heartbeat_at);
CREATE INDEX idx_task_events_task_id_timestamp ON apflow_task_events(task_id, timestamp);
```

### 5. Create `DistributedConfig` dataclass

Create `src/apflow/core/distributed/config.py`:

```python
@dataclass
class DistributedConfig:
    enabled: bool = False
    node_id: str | None = None
    node_role: str = "auto"  # auto | leader | worker | observer

    leader_lease_seconds: int = 30
    leader_renew_seconds: int = 10

    lease_duration_seconds: int = 30
    lease_cleanup_interval_seconds: int = 10

    poll_interval_seconds: int = 5
    max_parallel_tasks_per_node: int = 4

    heartbeat_interval_seconds: int = 10
    node_stale_threshold_seconds: int = 30
    node_dead_threshold_seconds: int = 120

    @classmethod
    def from_env(cls) -> "DistributedConfig":
        """Load configuration from environment variables (APFLOW_CLUSTER_ENABLED, etc.)."""

    def validate(self) -> None:
        """Validate config values (e.g., node_role in allowed set, intervals > 0)."""
```

### 6. Register config accessors in `ConfigRegistry`

Add `set_distributed_config()` / `get_distributed_config()` to `src/apflow/core/config/registry.py`, following the existing pattern (module-level functions delegating to `_get_registry()`).

### 7. Run tests and quality checks

```bash
pytest tests/unit/distributed/ -v
pytest tests/ -v  # Full suite for backward compatibility
ruff check --fix .
black .
pyright .
```

## Acceptance Criteria

- [ ] 5 new SQLAlchemy models created: `DistributedNode`, `TaskLease`, `ExecutionIdempotency`, `ClusterLeader`, `TaskEvent`
- [ ] `TaskModel` extended with 6 nullable fields: `lease_id`, `lease_expires_at`, `placement_constraints`, `attempt_id`, `idempotency_key`, `last_assigned_node`
- [ ] `to_dict()` and `default_values()` updated to include distributed fields
- [ ] Migration `003_add_distributed_support.py` succeeds on PostgreSQL (empty DB and DB with existing tasks)
- [ ] Migration succeeds on DuckDB (only adds columns, skips distributed tables)
- [ ] Rollback works correctly on both PostgreSQL and DuckDB
- [ ] Database indexes created for lease expiry, node status, and event queries (PostgreSQL only)
- [ ] `DistributedConfig` dataclass with `from_env()` classmethod and `validate()` method
- [ ] `get_distributed_config()` / `set_distributed_config()` registered in `ConfigRegistry`
- [ ] Runtime validation rejects distributed mode on non-PostgreSQL dialects
- [ ] All existing tests still pass (backward compatibility)
- [ ] Single-node mode unchanged on both PostgreSQL and DuckDB
- [ ] Unit test coverage >= 90% on new code
- [ ] Zero errors from `ruff check --fix .`, `black .`, `pyright .`

## Dependencies

- **Depends on**: None
- **Required by**: T2 (Leader Services)

## Estimated Time

~3 days

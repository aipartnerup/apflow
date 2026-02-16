# Code Review: distributed-core

**Date:** 2026-02-15 (re-review)
**Reviewer:** code-forge
**Overall Rating:** pass_with_notes
**Previous Review Issues Fixed:** 0/7
**Total Issues:** 18 (5 warnings, 4 suggestions, 9 coverage/consistency gaps)

## Summary

Re-review confirms all findings from the previous review. No issues have been addressed since the last review. The Distributed Core implementation delivers a clean, well-organized architecture with all 7 planned source modules, 5 new SQLAlchemy models, 6 TaskModel extensions, dialect-aware migration, and a DistributedRuntime coordinator with role selection state machine. Code quality is high with no `print()` statements, proper logging throughout, good use of `secrets.compare_digest()` for timing-safe token comparison, and all functions within the 50-line limit. The 119 unit tests pass with zero flakiness.

Key concerns: test coverage is 89% (1% under the 90% target), several T4 integration deliverables are incomplete (TaskExecutor integration, API layer enforcement, task event emission), SQL patterns deviate from the planned PostgreSQL primitives (`SELECT FOR UPDATE SKIP LOCKED`, `INSERT ... ON CONFLICT DO NOTHING`), and all tests run against SQLite in-memory rather than PostgreSQL.

## Code Quality

**Rating:** good

| Severity | File | Line | Description | Suggestion |
|----------|------|------|-------------|------------|
| warning | `distributed/worker.py` | 23 | `TaskExecutorFn` type alias duplicated in both `worker.py` and `runtime.py` | Define once in a shared location and import |
| warning | `distributed/worker.py` | 134-142, 200-232 | Manual session lifecycle (try/finally) instead of context managers, inconsistent with rest of codebase | Use `with self._session_factory() as session:` |
| warning | `distributed/leader_election.py` | 30-73 | Uses read-then-delete-then-insert pattern instead of plan's `INSERT ... ON CONFLICT DO NOTHING` | Consider dialect-aware path using PostgreSQL primitives |
| warning | `distributed/lease_manager.py` | 28-76 | Uses read-delete-insert pattern instead of plan's `SELECT FOR UPDATE SKIP LOCKED` | Consider dialect-aware path for production PostgreSQL |
| warning | `storage/migrations/003_add_distributed_support.py` | 59-60, 80-81, 105 | SQL DDL via f-string interpolation with `TASK_TABLE_NAME` env var | Add regex validation on table names before interpolation |
| suggestion | `distributed/node_registry.py` | 7 | `Any` used for `capabilities`; could benefit from a type alias | Define `Capabilities = dict[str, Any]` in shared types |
| suggestion | `distributed/config.py` | 28-29 | `utcnow()` strips timezone info without clear documentation | Add module-level comment explaining naive UTC strategy |
| suggestion | `distributed/runtime.py` | 44-59 | Services instantiated inside constructor rather than injected | Accept service instances as optional constructor parameters |
| suggestion | `distributed/worker.py` | 100-106 | `Semaphore.locked()` pre-check is not reliable for concurrency control | Remove pre-check; rely solely on `async with self._semaphore` |

## Test Coverage

**Rating:** acceptable

119 unit tests pass. Overall coverage is ~89%, slightly under the 90% acceptance criterion. Specific gaps:

- `leader_election.py` at 81%: Input validation error paths (`ValueError` on empty strings) untested
- `lease_manager.py` at 87%: Similar missing validation path coverage
- `runtime.py` at 82%: Constructor bypassed in tests via `__new__`; `_start_worker_runtime` None-guard untested
- No integration/end-to-end tests for multi-node scenarios (leader + 2 workers)
- No migration test coverage (upgrade/downgrade on PostgreSQL or DuckDB)
- No test validates rejection of distributed mode on non-PostgreSQL dialects
- **All tests use SQLite in-memory** — no PostgreSQL-specific features tested

## Security

**Rating:** pass

- `secrets.compare_digest()` correctly used for timing-safe token validation in `leader_election.py` and `lease_manager.py`
- No hardcoded secrets or credentials
- Input validation present at service boundaries (empty string checks with `ValueError`)
- Low-risk SQL injection vector in migration f-strings (internal config, not user input)

## Plan Consistency

**Criteria Met:** 9/15

Met:
- All 7 planned source modules created with correct responsibilities
- 5 new SQLAlchemy models + 6 TaskModel extensions
- DistributedConfig with `from_env()` and validation
- Config registry integration
- Dialect-aware migration structure
- Role selection state machine (auto/leader/worker/observer)
- PlacementEngine with constraint evaluation (100% coverage)
- IdempotencyManager with hash-based key generation
- Zero errors from ruff, black, pyright

Unmet:
- Coverage 89% vs 90% target
- No multi-node end-to-end tests
- No migration tests on PostgreSQL or DuckDB
- SQL patterns deviate from plan (`SKIP LOCKED`, `ON CONFLICT DO NOTHING`)
- No performance benchmark measured
- TaskExecutor integration not implemented (T4 deliverable)

Missing T4 scope items:
- **TaskExecutor integration**: No conditional initialization of `DistributedRuntime` when `APFLOW_CLUSTER_ENABLED=true`
- **API layer enforcement**: No `_require_leader` check on mutating endpoints, no 503 response
- **Task event emission**: `TaskEvent` model exists but no code writes lifecycle events to it
- **Dialect rejection**: No runtime validation rejecting distributed mode on non-PostgreSQL

## Database Testing

**Uses Real PostgreSQL:** No
**Uses TEST_DATABASE_URL:** No

The test conftest at `tests/unit/distributed/conftest.py` uses `sqlite:///:memory:` with `StaticPool` for all tests. It does **not** read `TEST_DATABASE_URL` or any other environment variable. No PostgreSQL connection is used in any test. This means PostgreSQL-specific features (`SELECT FOR UPDATE SKIP LOCKED`, `INSERT ... ON CONFLICT DO NOTHING`, foreign key constraints between distributed tables) are completely untested.

## Recommendations

**Must fix before merge:**
1. **Complete T4 integration**: Wire DistributedRuntime into TaskExecutor, add API enforcement, implement task event emission
2. **Add TEST_DATABASE_URL support to conftest.py**: Read `TEST_DATABASE_URL` env var and use it when available, falling back to SQLite for CI
3. **Implement dialect-aware SQL**: Add PostgreSQL-specific paths using `SELECT FOR UPDATE SKIP LOCKED` and `INSERT ... ON CONFLICT DO NOTHING`
4. **Fix session management in worker.py**: Use context managers consistently

**Should fix before merge:**
5. **Reach 90% coverage**: Add tests for input validation error paths and the DistributedRuntime constructor
6. **Add migration tests**: Verify upgrade/downgrade on both PostgreSQL and DuckDB
7. **Eliminate duplicated `TaskExecutorFn`**: Define once, import everywhere
8. **Add SQL injection protection**: Table name validation in migration f-strings

**Can defer to follow-up:**
9. Add integration tests for multi-node scenarios
10. Add performance benchmarks
11. Inject services into DistributedRuntime constructor
12. Add module-level documentation for naive UTC datetime strategy
13. Define `Capabilities` type alias

## Verdict

**Pass with notes.** The core distributed architecture is well-designed and implemented with high code quality. All previous issues remain unaddressed. The main gaps are in T4 integration (TaskExecutor, API enforcement, event emission), the absence of PostgreSQL-based testing, and SQL pattern deviations from the plan. The session management inconsistency in `worker.py` and the slightly-under-target test coverage should be addressed. Recommended: fix items 1-4 before merging, address items 5-8 as should-fix.

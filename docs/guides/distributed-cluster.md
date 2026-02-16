# Distributed Cluster Guide

This guide explains how to run apflow as a distributed cluster for high availability and horizontal scaling of task execution.

## Overview

By default, apflow runs as a single process using DuckDB for storage. The distributed cluster mode enables **multi-node task execution** with centralized coordination:

- **Lease-based task assignment** with automatic expiry and reassignment
- **Automatic leader election** via PostgreSQL (no external coordination service)
- **Horizontal scaling** by adding worker nodes without code changes
- **Failure recovery** through lease expiry and automatic task reassignment

Use distributed mode when you need:
- High availability for task execution
- Parallel execution across multiple machines
- Automatic failover when nodes go down
- Scaling beyond a single process

## Prerequisites

- **PostgreSQL** is required for distributed mode (DuckDB does not support multi-node coordination)
- All nodes must connect to the **same PostgreSQL database**
- Network connectivity between nodes is not required (coordination is database-driven)

```bash
# Install with PostgreSQL support
pip install apflow[postgres]
```

Set the database URL for all nodes:

```bash
export APFLOW_DATABASE_URL=postgresql+asyncpg://user:pass@db-host/apflow
```

## Quick Start

### 1. Start a leader node

```bash
export APFLOW_CLUSTER_ENABLED=true
export APFLOW_DATABASE_URL=postgresql+asyncpg://user:pass@db-host/apflow
export APFLOW_NODE_ROLE=auto
export APFLOW_NODE_ID=node-leader-1

apflow serve --host 0.0.0.0 --port 8000
```

### 2. Start a worker node

On a second machine (or process):

```bash
export APFLOW_CLUSTER_ENABLED=true
export APFLOW_DATABASE_URL=postgresql+asyncpg://user:pass@db-host/apflow
export APFLOW_NODE_ROLE=worker
export APFLOW_NODE_ID=node-worker-1

apflow serve --host 0.0.0.0 --port 8001
```

The worker will automatically register, start heartbeating, and begin polling for tasks.

### 3. Submit tasks

Submit tasks to the leader node. The cluster distributes execution across available workers:

```bash
curl -X POST http://leader-host:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.execute",
    "params": {
      "tasks": [
        {"id": "task-1", "name": "my_task", "inputs": {"key": "value"}}
      ]
    },
    "id": "1"
  }'
```

## Configuration Reference

All distributed configuration is loaded from environment variables. Set `APFLOW_CLUSTER_ENABLED=true` to activate distributed mode.

### Cluster Identity

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_CLUSTER_ENABLED` | boolean | `false` | Enable distributed cluster mode |
| `APFLOW_NODE_ID` | string | auto-generated | Unique identifier for this node. Auto-generated as `node-<random>` if not set |
| `APFLOW_NODE_ROLE` | string | `auto` | Node role: `auto`, `leader`, `worker`, or `observer` |

### Leader Election

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_LEADER_LEASE` | integer | `30` | Leader lease duration in seconds. If the leader fails to renew within this window, another node can claim leadership |
| `APFLOW_LEADER_RENEW` | integer | `10` | How often the leader renews its lease (seconds). Must be less than `APFLOW_LEADER_LEASE` |

### Task Lease Management

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_LEASE_DURATION` | integer | `30` | Task lease duration in seconds. Workers must complete or renew within this window |
| `APFLOW_LEASE_CLEANUP_INTERVAL` | integer | `10` | How often the leader checks for expired task leases (seconds) |

### Worker Polling

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_POLL_INTERVAL` | integer | `5` | How often workers poll for new tasks (seconds) |
| `APFLOW_MAX_PARALLEL_TASKS` | integer | `4` | Maximum concurrent tasks per worker node |

### Node Health Monitoring

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_HEARTBEAT_INTERVAL` | integer | `10` | How often nodes send heartbeat signals (seconds) |
| `APFLOW_NODE_STALE_THRESHOLD` | integer | `30` | Seconds without heartbeat before a node is marked `stale` |
| `APFLOW_NODE_DEAD_THRESHOLD` | integer | `120` | Seconds without heartbeat before a node is marked `dead` and its tasks are reassigned |

## Node Roles

All nodes run the **same codebase**. The role determines behavior at runtime.

### `auto` (default)

The node attempts leader election on startup. If another leader already holds the lease, it falls back to worker mode. This is the recommended setting for most deployments.

### `leader`

Forces the node to act as the cluster leader. Fails on startup if leadership cannot be acquired.

**Responsibilities:**
- Owns task state writes in PostgreSQL
- Handles lease acquisition, renewal, and reassignment
- Runs cleanup for expired leases
- Serves read/write API endpoints

### `worker`

The node never attempts to become leader. It only executes tasks.

**Responsibilities:**
- Polls for executable tasks
- Acquires a task lease, executes the task, and reports the result
- Renews lease during long-running tasks
- Sends periodic heartbeats

### `observer`

Read-only mode. Useful for dashboards, CLI access, or monitoring endpoints.

**Responsibilities:**
- Serves read-only API endpoints
- Does not execute tasks or participate in leader election

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────┐
│                  PostgreSQL                      │
│  ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │  Tasks   │ │  Nodes   │ │ Leader Lease     │  │
│  │  Table   │ │ Registry │ │ Table            │  │
│  └──────────┘ └──────────┘ └─────────────────┘  │
└────────┬────────────┬────────────┬──────────────┘
         │            │            │
    ┌────┴────┐  ┌────┴────┐  ┌───┴─────┐
    │ Leader  │  │ Worker  │  │ Worker  │
    │ Node    │  │ Node 1  │  │ Node 2  │
    └─────────┘  └─────────┘  └─────────┘
```

### Execution Flow

1. **Task submitted** to the leader via API
2. **Leader writes** the task to PostgreSQL with status `pending`
3. **Workers poll** for pending tasks matching their capabilities
4. **Worker acquires lease** on a task (atomic database operation)
5. **Worker executes** the task, renewing the lease periodically
6. **Worker reports result** back to PostgreSQL
7. **Leader cleans up** expired leases and reassigns failed tasks

### Leader Election

Leader election uses a SQL-based lease mechanism (no external coordination needed):

1. On startup, nodes with role `auto` or `leader` attempt to insert a row into `cluster_leader`
2. The first successful insert wins leadership
3. The leader renews its lease every `APFLOW_LEADER_RENEW` seconds
4. If the lease expires (leader crash), any node can claim leadership
5. On graceful shutdown, the leader releases its lease

## Deployment Patterns

### Simple High Availability (2 nodes)

Both nodes set `APFLOW_NODE_ROLE=auto`. One becomes leader, the other becomes worker. If the leader fails, the worker promotes itself.

```bash
# Node A
APFLOW_CLUSTER_ENABLED=true
APFLOW_NODE_ROLE=auto
APFLOW_NODE_ID=node-a

# Node B
APFLOW_CLUSTER_ENABLED=true
APFLOW_NODE_ROLE=auto
APFLOW_NODE_ID=node-b
```

### Auto-Scaling Workers

One dedicated leader with auto-scaling workers. Add workers dynamically without configuration changes.

```bash
# Leader (fixed)
APFLOW_CLUSTER_ENABLED=true
APFLOW_NODE_ROLE=leader
APFLOW_NODE_ID=leader-1

# Workers (auto-scaled, e.g., in Kubernetes)
APFLOW_CLUSTER_ENABLED=true
APFLOW_NODE_ROLE=worker
# APFLOW_NODE_ID auto-generated per instance
APFLOW_MAX_PARALLEL_TASKS=8
```

### Leader + Workers + Observers

Full deployment with dedicated roles for separation of concerns.

```bash
# Leader: handles coordination
APFLOW_NODE_ROLE=leader

# Workers: execute tasks
APFLOW_NODE_ROLE=worker
APFLOW_MAX_PARALLEL_TASKS=4

# Observers: serve dashboard/CLI
APFLOW_NODE_ROLE=observer
```

## Failure Handling

### Worker Crash

1. The worker stops sending heartbeats
2. After `APFLOW_NODE_STALE_THRESHOLD` seconds (default: 30), the node is marked `stale`
3. After `APFLOW_NODE_DEAD_THRESHOLD` seconds (default: 120), the node is marked `dead`
4. Task leases held by the dead node expire automatically
5. The leader's cleanup loop detects expired leases and marks those tasks as `pending`
6. Another worker picks up the task on its next poll

### Leader Failover

1. The leader stops renewing its lease (crash or network partition)
2. After `APFLOW_LEADER_LEASE` seconds (default: 30), the lease expires
3. A node with role `auto` detects the expired lease and claims leadership
4. The new leader resumes lease cleanup and task coordination

### Task Lease Expiry

If a worker takes longer than `APFLOW_LEASE_DURATION` to complete a task without renewing:

1. The lease expires
2. The leader's cleanup loop marks the task for reassignment
3. Another worker can acquire the task

Workers automatically renew leases for long-running tasks. Increase `APFLOW_LEASE_DURATION` if tasks routinely take longer than 30 seconds.

## Troubleshooting

### No leader elected

**Symptoms:** All nodes are workers, no task coordination happening.

**Possible causes:**
- All nodes have `APFLOW_NODE_ROLE=worker` (no node is attempting leader election)
- Database connectivity issues preventing lease table writes

**Fix:** Set at least one node to `APFLOW_NODE_ROLE=auto` or `APFLOW_NODE_ROLE=leader`.

### Tasks stuck in pending

**Symptoms:** Tasks remain in `pending` status indefinitely.

**Possible causes:**
- No worker nodes are running
- Workers don't have the required executor installed
- `APFLOW_MAX_PARALLEL_TASKS` is reached on all workers

**Fix:** Check worker logs, verify executors are registered, or add more workers.

### Frequent task reassignment

**Symptoms:** Tasks are being reassigned repeatedly.

**Possible causes:**
- `APFLOW_LEASE_DURATION` is too short for the task execution time
- Worker nodes are overloaded and failing to renew leases

**Fix:** Increase `APFLOW_LEASE_DURATION` or reduce `APFLOW_MAX_PARALLEL_TASKS`.

### Node marked as dead but still running

**Symptoms:** A node is functional but marked `dead` in the node registry.

**Possible causes:**
- Network partition between the node and PostgreSQL
- Database connection pool exhausted

**Fix:** Check database connectivity. The node will re-register on its next successful heartbeat.

## See Also

- [Environment Variables Reference](./environment-variables.md) - All configuration variables
- [API Server Guide](./api-server.md) - Running the API server
- [Installation](../getting-started/installation.md) - Installing PostgreSQL support

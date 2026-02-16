# GraphQL API Reference

This document provides a complete reference for the apflow GraphQL API, built on [Strawberry GraphQL](https://strawberry.rocks/).

## Overview

The GraphQL API provides:
- **Typed schema** with full introspection support
- **Queries** for reading tasks and task trees
- **Mutations** for creating, updating, cancelling, and deleting tasks
- **Subscriptions** for real-time task status updates via WebSocket
- **GraphiQL** interactive playground for exploring the schema

## Installation

Install apflow with the GraphQL extra:

```bash
pip install apflow[graphql]
```

## Configuration

Set the API protocol to `graphql`:

```bash
export APFLOW_API_PROTOCOL=graphql
```

Start the server:

```bash
apflow serve
# Or: python -m apflow.api.main
```

The GraphQL endpoint is available at `http://localhost:8000/graphql`.

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_API_PROTOCOL` | string | `a2a` | Set to `graphql` to enable the GraphQL adapter |
| `APFLOW_ENABLE_DOCS` | boolean | `true` | Enable GraphiQL interactive playground |
| `APFLOW_ENABLE_SYSTEM_ROUTES` | boolean | `true` | Enable system info endpoint at `/system` |
| `APFLOW_API_HOST` | string | `0.0.0.0` | Server host |
| `APFLOW_API_PORT` | integer | `8000` | Server port |

## Schema Reference

### Types

#### `TaskType`

The primary task representation:

```graphql
type TaskType {
  id: String!
  name: String!
  status: TaskStatusEnum!
  priority: Int!
  progress: Float!
  result: String
  error: String
  createdAt: DateTime
  updatedAt: DateTime
  parentId: String
  description: String
  children: [TaskType!]
}
```

#### `TaskStatusEnum`

```graphql
enum TaskStatusEnum {
  PENDING
  IN_PROGRESS
  COMPLETED
  FAILED
  CANCELLED
}
```

### Input Types

#### `CreateTaskInput`

```graphql
input CreateTaskInput {
  name: String!
  description: String
  executor: String
  priority: Int
  inputs: JSON
  parentId: String
}
```

#### `UpdateTaskInput`

```graphql
input UpdateTaskInput {
  name: String
  description: String
  status: TaskStatusEnum
  inputs: JSON
}
```

### Queries

#### `task`

Fetch a single task by ID.

```graphql
query {
  task(taskId: "task-123") {
    id
    name
    status
    progress
    result
    error
    createdAt
  }
}
```

#### `tasks`

Fetch a list of tasks with optional filters.

```graphql
query {
  tasks(status: PENDING, limit: 10, offset: 0) {
    id
    name
    status
    priority
    createdAt
  }
}
```

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `status` | `TaskStatusEnum` | Filter by task status |
| `limit` | `Int` | Maximum number of tasks to return |
| `offset` | `Int` | Number of tasks to skip |

#### `taskChildren`

Fetch all child tasks of a parent task.

```graphql
query {
  taskChildren(parentId: "parent-task-123") {
    id
    name
    status
    priority
  }
}
```

### Mutations

#### `createTask`

Create a new task.

```graphql
mutation {
  createTask(taskInput: {
    name: "my_task"
    description: "A sample task"
    executor: "rest_executor"
    priority: 5
    inputs: { url: "https://api.example.com/data" }
  }) {
    id
    name
    status
  }
}
```

#### `updateTask`

Update an existing task.

```graphql
mutation {
  updateTask(
    taskId: "task-123"
    taskInput: {
      name: "updated_name"
      status: CANCELLED
    }
  ) {
    id
    name
    status
    updatedAt
  }
}
```

#### `cancelTask`

Cancel a running task. Returns `true` on success.

```graphql
mutation {
  cancelTask(taskId: "task-123")
}
```

#### `deleteTask`

Delete a task. Returns `true` on success.

```graphql
mutation {
  deleteTask(taskId: "task-123")
}
```

### Subscriptions

#### `taskStatusChanged`

Subscribe to real-time status updates for a specific task. Emits a `TaskType` each time the task's status changes. The subscription ends automatically when the task reaches a terminal status (`COMPLETED`, `FAILED`, or `CANCELLED`).

```graphql
subscription {
  taskStatusChanged(taskId: "task-123") {
    id
    name
    status
    progress
    result
    error
  }
}
```

The subscription uses the `graphql-transport-ws` protocol over WebSocket.

## Client Examples

### Python (httpx)

```python
import httpx

# Query a task
query = """
query GetTask($taskId: String!) {
  task(taskId: $taskId) {
    id
    name
    status
    progress
    result
  }
}
"""

response = httpx.post(
    "http://localhost:8000/graphql",
    json={"query": query, "variables": {"taskId": "task-123"}},
)
print(response.json())
```

### Python (create task)

```python
import httpx

mutation = """
mutation CreateTask($input: CreateTaskInput!) {
  createTask(taskInput: $input) {
    id
    name
    status
  }
}
"""

variables = {
    "input": {
        "name": "my_executor",
        "description": "Run a data pipeline",
        "priority": 5,
        "inputs": {"source": "s3://bucket/data.csv"},
    }
}

response = httpx.post(
    "http://localhost:8000/graphql",
    json={"query": mutation, "variables": variables},
)
print(response.json())
```

### cURL

```bash
# Query tasks
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ tasks(status: PENDING, limit: 5) { id name status priority } }"
  }'

# Create a task
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createTask(taskInput: { name: \"my_task\" }) { id name status } }"
  }'
```

## Authentication

The GraphQL adapter supports the same JWT authentication as the A2A and MCP adapters. Include the token in the `Authorization` header:

```bash
curl -X POST http://localhost:8000/graphql \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ tasks { id name status } }"}'
```

See the [API Server Guide](../guides/api-server.md#authentication) for token generation details.

## GraphiQL Playground

When `APFLOW_ENABLE_DOCS=true` (the default), opening `http://localhost:8000/graphql` in a browser loads the GraphiQL interactive playground. Use it to:

- Explore the schema with auto-complete
- Run queries and mutations interactively
- View type documentation inline
- Test subscriptions

To disable GraphiQL in production:

```bash
export APFLOW_ENABLE_DOCS=false
```

## Protocol Comparison

| Feature | A2A (HTTP) | MCP | GraphQL |
|---------|-----------|-----|---------|
| Protocol | JSON-RPC over HTTP | JSON-RPC (HTTP/stdio) | GraphQL over HTTP/WS |
| Schema | Agent Card discovery | Tool/Resource listing | Full introspection |
| Streaming | SSE / WebSocket | N/A | Subscriptions (WS) |
| Best for | Agent-to-agent communication | LLM tool integration | Frontend apps, typed APIs |
| Install extra | `apflow[a2a]` | `apflow[a2a]` | `apflow[graphql]` |

## See Also

- [API Server Guide](../guides/api-server.md) - Server setup and protocol selection
- [HTTP API Reference](./http.md) - A2A Protocol HTTP API
- [Python API Reference](./python.md) - Python library API
- [Environment Variables](../guides/environment-variables.md) - All configuration options

# GraphQL Adapter

> Query interface for complex task trees using strawberry-graphql

## Overview

Add a GraphQL protocol adapter for querying and managing task trees. GraphQL is particularly well-suited for apflow's hierarchical task tree structure, where clients need to query nested task data with flexible field selection.

## Dependencies

- **Requires**: Protocol Abstraction Phase 2 (ProtocolAdapter interface)
- **Library**: `strawberry-graphql[asgi]` (Python-first GraphQL library with type safety)

## Core Requirements

### 1. GraphQL Schema

Define GraphQL types that map to apflow's data model:

```graphql
type Task {
  id: ID!
  name: String!
  status: TaskStatus!
  priority: Int
  progress: Float
  result: JSON
  error: String
  children: [Task!]!
  dependencies: [Task!]!
  parent: Task
  createdAt: DateTime!
  updatedAt: DateTime
}

enum TaskStatus {
  PENDING
  IN_PROGRESS
  COMPLETED
  FAILED
  CANCELLED
}

type TaskTree {
  root: Task!
  totalTasks: Int!
  completedTasks: Int!
  failedTasks: Int!
}

type Query {
  task(id: ID!): Task
  tasks(status: TaskStatus, limit: Int, offset: Int): [Task!]!
  taskTree(rootId: ID!): TaskTree
  taskChildren(parentId: ID!): [Task!]!
  runningTasks: [Task!]!
  executors: [Executor!]!
}

type Mutation {
  createTask(input: CreateTaskInput!): Task!
  updateTask(id: ID!, input: UpdateTaskInput!): Task!
  cancelTask(id: ID!): Task!
  deleteTask(id: ID!): Boolean!
  executeTask(id: ID!, inputs: JSON): Task!
}

type Subscription {
  taskStatusChanged(taskId: ID!): Task!
  taskProgress(taskId: ID!): Task!
}
```

### 2. GraphQL Protocol Adapter

Implement `GraphQLProtocolAdapter` following the `ProtocolAdapter` interface:

```python
class GraphQLProtocolAdapter:
    protocol_name = "graphql"

    def create_app(self, task_routes: TaskRoutes) -> Any:
        schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
        return GraphQL(schema)
```

### 3. Resolver Implementation

Resolvers should delegate to existing `TaskRoutes` handler methods:
- `task(id)` -> `TaskRoutes.get_task()`
- `tasks(...)` -> `TaskRoutes.list_tasks()`
- `taskTree(rootId)` -> `TaskRoutes.get_task_tree()`
- `createTask(input)` -> `TaskRoutes.create_task()`
- `cancelTask(id)` -> `TaskRoutes.cancel_task()`
- `executeTask(id, inputs)` -> `TaskRoutes.execute_task()`

### 4. DataLoader for N+1 Prevention

Use strawberry's DataLoader to prevent N+1 queries for nested task trees:
```python
@strawberry.type
class Task:
    @strawberry.field
    async def children(self, info: Info) -> list["Task"]:
        return await info.context["task_loader"].load(self.id)
```

### 5. Subscription Support

WebSocket-based subscriptions for real-time task updates:
- Task status changes
- Task progress updates
- Uses existing EventQueue/streaming infrastructure

## Module Structure

```
src/apflow/api/graphql/
├── __init__.py
├── server.py          # GraphQL server creation
├── schema.py          # Strawberry schema definition
├── types.py           # GraphQL types (Task, TaskTree, Executor, etc.)
├── resolvers/
│   ├── __init__.py
│   ├── queries.py     # Query resolvers
│   ├── mutations.py   # Mutation resolvers
│   └── subscriptions.py  # Subscription resolvers
└── loaders.py         # DataLoaders for N+1 prevention
```

## Technology Stack

- **Language**: Python 3.11+
- **GraphQL**: strawberry-graphql[asgi]
- **ASGI**: Starlette (existing)
- **WebSocket**: For subscriptions

## Installation

```bash
pip install apflow[graphql]
```

## Testing Requirements

- Unit tests for each resolver
- Schema validation tests
- DataLoader tests (verify N+1 prevention)
- Integration tests with real database
- Subscription tests via WebSocket
- Performance tests for deep task trees

## Acceptance Criteria

- [ ] GraphQL schema covers all task operations
- [ ] Queries resolve task trees efficiently (no N+1)
- [ ] Mutations delegate to TaskRoutes correctly
- [ ] Subscriptions provide real-time updates
- [ ] Implements ProtocolAdapter interface
- [ ] Available via `pip install apflow[graphql]`
- [ ] GraphiQL/playground available in development mode
- [ ] All existing API tests pass unchanged

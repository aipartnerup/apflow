# GraphQL Adapter - Feature Overview

## Overview

Add a GraphQL protocol adapter for querying and managing task trees using strawberry-graphql. Provides queries, mutations, and WebSocket subscriptions, delegating all operations to existing TaskRoutes handlers.

## Scope

**Included:**
- GraphQL schema (types, queries, mutations, subscriptions)
- GraphQLProtocolAdapter implementing ProtocolAdapter interface
- Query/mutation resolvers delegating to TaskRoutes
- DataLoaders for N+1 prevention on nested task trees
- WebSocket subscriptions for real-time updates
- GraphiQL playground in development mode

**Excluded:**
- Custom business logic (all delegated to TaskRoutes)
- Authentication/authorization (handled at API layer)
- Schema stitching or federation

## Technology Stack

- **Language**: Python 3.11+
- **GraphQL**: strawberry-graphql[asgi]
- **ASGI**: Starlette (existing)
- **WebSocket**: For subscriptions
- **Testing**: pytest, Strict TDD

## Task Execution Order

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | [schema-types](./tasks/schema-types.md) | Define GraphQL Types and Schema | pending |
| 2 | [resolvers](./tasks/resolvers.md) | Implement Query and Mutation Resolvers with DataLoaders | pending |
| 3 | [subscriptions](./tasks/subscriptions.md) | Implement Subscription Resolvers | pending |
| 4 | [adapter-integration](./tasks/adapter-integration.md) | Protocol Adapter, Server Integration, and End-to-End Tests | pending |

## Progress

- **Total**: 4
- **Completed**: 0
- **In Progress**: 0
- **Pending**: 4

## Reference Documents

- [Feature Document](../../features/graphql-adapter.md)
- **Dependency**: [Protocol Abstraction Phase 2](../protocol-abstraction-phase2/overview.md) (must be completed first)

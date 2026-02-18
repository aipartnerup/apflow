"""GraphQL schema assembly for apflow."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import strawberry
from strawberry.extensions import QueryDepthLimiter
from strawberry.types import Info

from apflow.api.graphql.resolvers.mutations import (
    resolve_cancel_task,
    resolve_create_task,
    resolve_delete_task,
    resolve_execute_task,
    resolve_update_task,
)
from apflow.api.graphql.resolvers.queries import (
    resolve_running_tasks,
    resolve_task,
    resolve_task_children,
    resolve_task_tree,
    resolve_tasks,
)
from apflow.api.graphql.resolvers.subscriptions import (
    subscribe_task_progress,
    subscribe_task_status_changed,
)
from apflow.api.graphql.types import TaskProgressEvent, TaskTreeType, TaskType

MAX_QUERY_DEPTH = 10


@strawberry.type
class Query:
    """GraphQL query root type."""

    task: TaskType = strawberry.field(resolver=resolve_task)
    tasks: list[TaskType] = strawberry.field(resolver=resolve_tasks)
    task_children: list[TaskType] = strawberry.field(resolver=resolve_task_children)
    task_tree: TaskTreeType = strawberry.field(resolver=resolve_task_tree)
    running_tasks: list[TaskType] = strawberry.field(resolver=resolve_running_tasks)


@strawberry.type
class Mutation:
    """GraphQL mutation root type."""

    create_task: TaskType = strawberry.mutation(resolver=resolve_create_task)
    update_task: TaskType = strawberry.mutation(resolver=resolve_update_task)
    cancel_task: bool = strawberry.mutation(resolver=resolve_cancel_task)
    delete_task: bool = strawberry.mutation(resolver=resolve_delete_task)
    execute_task: TaskType = strawberry.mutation(resolver=resolve_execute_task)


@strawberry.type
class Subscription:
    """GraphQL subscription root type."""

    @strawberry.subscription
    async def task_status_changed(self, info: Info, task_id: str) -> AsyncGenerator[TaskType, None]:
        """Subscribe to status changes for a specific task."""
        async for update in subscribe_task_status_changed(info, task_id):
            yield update

    @strawberry.subscription
    async def task_progress(
        self, info: Info, task_id: str
    ) -> AsyncGenerator[TaskProgressEvent, None]:
        """Subscribe to progress events for a task execution."""
        async for event in subscribe_task_progress(info, task_id):
            yield event


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    extensions=[QueryDepthLimiter(max_depth=MAX_QUERY_DEPTH)],
)

"""
Protocol-agnostic route handlers for apflow API

This module contains route handlers that can be used by any protocol
(A2A, REST, GraphQL, etc.) to provide task management, system operations,
and API documentation.
"""

from apflow.api.routes.base import BaseRouteHandler
from apflow.api.routes.tasks import TaskRoutes
from apflow.api.routes.system import SystemRoutes
from apflow.api.routes.docs import DocsRoutes

__all__ = [
    "BaseRouteHandler",
    "TaskRoutes",
    "SystemRoutes",
    "DocsRoutes",
]


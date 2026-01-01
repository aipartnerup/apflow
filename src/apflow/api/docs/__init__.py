"""
API Documentation Module

Provides interactive API documentation using Swagger UI and OpenAPI schema.
"""

from apflow.api.docs.openapi import generate_openapi_schema
from apflow.api.docs.swagger_ui import (
    get_swagger_ui_route_handler,
    get_openapi_json_route_handler,
)

__all__ = [
    "generate_openapi_schema",
    "get_swagger_ui_route_handler",
    "get_openapi_json_route_handler",
]


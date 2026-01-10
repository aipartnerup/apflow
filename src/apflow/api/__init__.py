"""
apflow API module

This module provides functions for creating and configuring API applications.
"""

from apflow.api.app import create_app_by_protocol
from apflow.api.main import create_runnable_app, main

__all__ = [
    "create_app_by_protocol",
    "create_runnable_app",
    "main",
    "setup_app",
]


def setup_app(
    protocol: str = "a2a",
    custom_routes=None,
    custom_middleware=None,
    task_routes_class=None,
    **kwargs
):
    """
    Setup and create API application with all necessary initialization
    
    This is a convenience function that handles all the initialization steps
    that main.py does, making it easy to use apflow as a library.
    
    Args:
        protocol: Protocol type ("a2a", "mcp", etc.). Default: "a2a"
        custom_routes: Optional list of custom Starlette Route objects
        custom_middleware: Optional list of custom Starlette BaseHTTPMiddleware classes
        task_routes_class: Optional custom TaskRoutes class
        **kwargs: Additional arguments passed to create_app_by_protocol
    
    Returns:
        Configured Starlette/FastAPI application instance
    
    Examples:
        # Basic usage
        from apflow.api import setup_app
        
        app = setup_app()
        
        # With custom routes and middleware
        from starlette.routing import Route
        from starlette.middleware.base import BaseHTTPMiddleware
        
        custom_routes = [Route("/health", health_handler, methods=["GET"])]
        custom_middleware = [LoggingMiddleware]
        
        app = setup_app(
            custom_routes=custom_routes,
            custom_middleware=custom_middleware
        )
    """
    
    # Create and return app
    return create_app_by_protocol(
        protocol=protocol,
        task_routes_class=task_routes_class,
        custom_routes=custom_routes,
        custom_middleware=custom_middleware,
        **kwargs
    )

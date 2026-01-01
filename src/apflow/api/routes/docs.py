"""
Documentation routes handler

Provides route handlers for interactive API documentation (Swagger UI and OpenAPI schema).
"""

import os
from typing import Optional, Dict, Any, Callable
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from apflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class DocsRoutes:
    """
    Route handler for API documentation endpoints
    
    Provides handlers for:
    - /docs: Swagger UI interactive documentation
    - /openapi.json: OpenAPI schema JSON
    
    Also handles OpenAPI schema generation from agent_card or base_url.
    """
    
    def __init__(
        self,
        enable_docs: bool = True,
        openapi_schema: Optional[Dict[str, Any]] = None,
        agent_card: Optional[Any] = None,
        base_url: Optional[str] = None,
        get_base_url_func: Optional[Callable[[], str]] = None,
    ):
        """
        Initialize documentation routes handler
        
        Args:
            enable_docs: Whether to enable documentation. If False, schema will not be generated.
            openapi_schema: Pre-generated OpenAPI schema dictionary. If None, will be generated.
            agent_card: Agent card object with url attribute (optional, for base_url detection).
            base_url: Base URL for API (optional, used if agent_card is not available).
            get_base_url_func: Function to get base URL (optional, highest priority).
        """
        self.enable_docs = enable_docs
        self.openapi_schema = openapi_schema
        
        # Generate schema if enabled and not provided
        if self.enable_docs and self.openapi_schema is None:
            self.openapi_schema = self._generate_schema(
                agent_card=agent_card,
                base_url=base_url,
                get_base_url_func=get_base_url_func
            )
    
    def _generate_schema(
        self,
        agent_card: Optional[Any] = None,
        base_url: Optional[str] = None,
        get_base_url_func: Optional[Callable[[], str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate OpenAPI schema for documentation
        
        Args:
            agent_card: Agent card object with url attribute (optional).
            base_url: Base URL for API (optional).
            get_base_url_func: Function to get base URL (optional, highest priority).
            
        Returns:
            OpenAPI schema dictionary, or None if generation failed.
        """
        try:
            from apflow.api.docs import generate_openapi_schema
            
            # Determine base URL (priority: get_base_url_func > agent_card > base_url > default)
            if get_base_url_func:
                resolved_base_url = get_base_url_func()
            elif agent_card and hasattr(agent_card, "url"):
                resolved_base_url = agent_card.url
            elif base_url:
                resolved_base_url = base_url
            else:
                # Fallback to default
                resolved_base_url = f"http://localhost:{os.getenv('APFLOW_PORT', '8000')}"
            
            logger.debug(f"Generating OpenAPI schema with base_url: {resolved_base_url}")
            return generate_openapi_schema(base_url=resolved_base_url)
        except Exception as e:
            logger.warning(f"Failed to generate OpenAPI schema: {e}. Documentation will not be available.")
            return None
    
    def handle_swagger_ui(self, request: Request) -> HTMLResponse:
        """
        Handle Swagger UI documentation route (/docs)
        
        Args:
            request: Starlette request object
            
        Returns:
            HTMLResponse with Swagger UI page
        """
        if not self.openapi_schema:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Documentation is not available",
                    "message": "OpenAPI schema is not configured"
                }
            )
        
        try:
            from apflow.api.docs.swagger_ui import get_swagger_ui_route_handler
            return get_swagger_ui_route_handler(self.openapi_schema)
        except Exception as e:
            logger.error(f"Error serving Swagger UI: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Failed to serve documentation",
                    "message": str(e)
                }
            )
    
    def handle_openapi_json(self, request: Request) -> JSONResponse:
        """
        Handle OpenAPI schema JSON route (/openapi.json)
        
        Args:
            request: Starlette request object
            
        Returns:
            JSONResponse with OpenAPI schema
        """
        if not self.openapi_schema:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "OpenAPI schema is not available",
                    "message": "OpenAPI schema is not configured"
                }
            )
        
        try:
            from apflow.api.docs.swagger_ui import get_openapi_json_route_handler
            return get_openapi_json_route_handler(self.openapi_schema)
        except Exception as e:
            logger.error(f"Error serving OpenAPI schema: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Failed to serve OpenAPI schema",
                    "message": str(e)
                }
            )


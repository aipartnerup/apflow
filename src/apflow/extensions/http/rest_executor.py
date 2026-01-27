"""
REST API Executor for calling REST API endpoints.

This executor is designed to make HTTP requests to third-party REST API services, webhooks, and HTTP-based endpoints.
It supports authentication, custom headers, query parameters, and request bodies, making it suitable for integrating with external APIs such as SaaS platforms, cloud services, or any HTTP-based API provider.
"""

import httpx
from typing import Dict, Any, Optional
from apflow.core.base import BaseTask
from apflow.core.extensions.decorators import executor_register
from apflow.core.execution.errors import ValidationError
from apflow.logger import get_logger

logger = get_logger(__name__)


@executor_register()
class RestExecutor(BaseTask):
    """
    Executor for calling REST API endpoints, typically provided by third-party services.
    Supports GET, POST, PUT, DELETE, PATCH methods with authentication, custom headers, query parameters, and request bodies.
    This is ideal for integrating with external APIs, SaaS platforms, cloud services, or any HTTP-based API provider.

    Example usage in task schemas:
    {
        "schemas": {
            "method": "rest_executor"  # Executor id
        },
        "inputs": {
            "url": "https://api.example.com/users",
            "method": "GET",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 30
        }
    }
    """

    id = "rest_executor"
    name = "REST API Executor"
    description = "Execute HTTP/REST API requests with authentication and custom headers"
    tags = ["http", "rest", "api", "webhook"]
    examples = [
        "Call external REST API",
        "Send webhook notification",
        "Fetch data from HTTP service",
    ]

    # Cancellation support: Can be cancelled by closing the HTTP client
    cancelable: bool = True

    def __init__(self, headers=None, auth=None, verify=True, follow_redirects=True, **kwargs):
        super().__init__(**kwargs)
        self.default_headers = headers or {}
        self.default_auth = auth
        self.default_verify = verify
        self.default_follow_redirects = follow_redirects

    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "http"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an HTTP request

        Args:
            inputs: Dictionary containing:
                - url: Target URL (required)
                - method: HTTP method (GET, POST, PUT, DELETE, PATCH, default: GET)
                - headers: Optional HTTP headers dict (merged with default)
                - params: Optional query parameters dict
                - json: Optional JSON body (dict)
                - data: Optional form data (dict)
                - timeout: Optional timeout in seconds (default: 30.0)

        Returns:
            Dictionary with response data (json or body).
        """
        url = inputs.get("url")
        if not url:
            raise ValidationError(f"[{self.id}] url is required in inputs")

        method = inputs.get("method", "GET").upper()
        headers = {**self.default_headers, **inputs.get("headers", {})}
        params = inputs.get("params")
        json_data = inputs.get("json")
        data = inputs.get("data")
        timeout = inputs.get("timeout", 30.0)

        # Handle authentication from inputs or defaults
        auth_config = inputs.get("auth") or self.default_auth
        auth = None
        if auth_config:
            auth_type = auth_config.get("type", "").lower()
            if auth_type == "bearer":
                token = auth_config.get("token")
                if token:
                    headers.setdefault("Authorization", f"Bearer {token}")
            elif auth_type == "basic":
                username = auth_config.get("username")
                password = auth_config.get("password")
                if username and password:
                    auth = httpx.BasicAuth(username, password)
            elif auth_type == "apikey":
                key = auth_config.get("key")
                value = auth_config.get("value")
                location = auth_config.get("location", "header").lower()
                if key and value:
                    if location == "header":
                        headers[key] = value
                    elif location == "query":
                        if params is None:
                            params = {}
                        params[key] = value

        # Prepare request kwargs
        request_kwargs = {
            "method": method,
            "url": url,
            "headers": headers,
            "follow_redirects": self.default_follow_redirects,
        }

        if params:
            request_kwargs["params"] = params
        if json_data is not None:
            request_kwargs["json"] = json_data
        elif data is not None:
            request_kwargs["data"] = data
        if auth:
            request_kwargs["auth"] = auth

        logger.info(f"Executing HTTP {method} request to {url}")

        async with httpx.AsyncClient(
            verify=inputs.get("verify", self.default_verify), timeout=timeout
        ) as client:
            # Check for cancellation before making request
            if self.cancellation_checker and self.cancellation_checker():
                return {"success": False, "error": "Request was cancelled", "method": method}

            response = await client.request(**request_kwargs)

            # Check for cancellation after request
            if self.cancellation_checker and self.cancellation_checker():
                return {"success": False, "error": "Request was cancelled", "method": method}

            if not (200 <= response.status_code < 300):
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "url": str(response.url),
                    "headers": dict(response.headers),
                    "text": response.text,
                    "method": method,
                }

            # Try to parse JSON response
            json_response = None
            try:
                json_response = response.json()
            except Exception:
                pass

            if json_response is not None:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "url": str(response.url),
                    "headers": dict(response.headers),
                    "json": json_response,
                    "method": method,
                }
            else:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "url": str(response.url),
                    "headers": dict(response.headers),
                    "text": response.text,
                    "method": method,
                }

    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo HTTP response data"""
        method = inputs.get("method", "GET").upper()

        # Generate appropriate demo response based on method
        if method == "GET":
            demo_json = {
                "status": "success",
                "data": {"id": "demo-123", "name": "Demo Resource", "value": 42},
            }
        elif method == "POST":
            demo_json = {
                "status": "created",
                "id": "new-resource-456",
                "message": "Resource created successfully",
            }
        else:
            demo_json = {"status": "success", "message": f"{method} operation completed"}

        return {
            "success": True,
            "status_code": 200,
            "url": inputs.get("url", "https://api.example.com/demo"),
            "headers": {"Content-Type": "application/json"},
            "json": demo_json,
            "method": method,
        }

    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL for the HTTP request"},
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "description": "HTTP method (default: GET)",
                },
                "headers": {
                    "type": "object",
                    "description": "Additional HTTP headers as key-value pairs (merged with defaults)",
                },
                "params": {"type": "object", "description": "Query parameters as key-value pairs"},
                "json": {"type": "object", "description": "JSON request body"},
                "data": {"type": "object", "description": "Form data as key-value pairs"},
                "auth": {
                    "type": "object",
                    "description": "Authentication configuration",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["bearer", "basic", "apikey"],
                            "description": "Authentication type",
                        },
                        "token": {
                            "type": "string",
                            "description": "Bearer token (for bearer auth)",
                        },
                        "username": {"type": "string", "description": "Username (for basic auth)"},
                        "password": {"type": "string", "description": "Password (for basic auth)"},
                        "key": {"type": "string", "description": "API key name (for apikey auth)"},
                        "value": {
                            "type": "string",
                            "description": "API key value (for apikey auth)",
                        },
                        "location": {
                            "type": "string",
                            "enum": ["header", "query"],
                            "description": "Where to place the API key (default: header)",
                        },
                    },
                    "required": ["type"],
                },
                "timeout": {
                    "type": "number",
                    "description": "Request timeout in seconds (default: 30.0)",
                },
                "verify": {
                    "type": "boolean",
                    "description": "Whether to verify SSL certificates (default: true)",
                },
            },
            "required": ["url"],
        }

    def get_output_schema(self) -> Dict[str, Any]:
        """
        Return the output result schema for this executor.
        """
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "description": "Whether the request was successful"},
                "status_code": {"type": "integer", "description": "HTTP status code"},
                "url": {"type": "string", "description": "Final URL after redirects"},
                "headers": {"type": "object", "description": "Response headers"},
                "method": {"type": "string", "description": "HTTP method used"},
                "json": {"type": "object", "description": "JSON response body (if applicable)"},
                "text": {"type": "string", "description": "Text response body (if applicable)"},
                "error": {"type": "string", "description": "Error message (if applicable)"},
            },
            "required": ["success", "method"],
        }

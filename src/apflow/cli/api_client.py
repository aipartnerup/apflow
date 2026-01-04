"""
HTTP client for CLI to communicate with API server.

Provides a unified interface for CLI commands to access API-managed data,
ensuring data consistency between CLI and API when both are running.
"""

from typing import Any, Dict, List, Optional

import httpx

from apflow.logger import get_logger

logger = get_logger(__name__)


class APIClientError(Exception):
    """Base exception for API client errors."""

    pass


class APIConnectionError(APIClientError):
    """Raised when unable to connect to API server."""

    pass


class APITimeoutError(APIClientError):
    """Raised when API request times out."""

    pass


class APIResponseError(APIClientError):
    """Raised when API returns an error response."""

    pass


class APIClient:
    """
    HTTP client for CLI to communicate with API server.

    Supports exponential backoff retry, auth tokens, and configurable timeouts.

    Usage:
        client = APIClient(
            server_url="http://localhost:8000",
            auth_token="optional-token",
            timeout=30.0,
            retry_attempts=3,
            retry_backoff=1.0,
        )
        result = await client.execute_task("task-123")
    """

    def __init__(
        self,
        server_url: str,
        auth_token: Optional[str] = None,
        timeout: float = 30.0,
        retry_attempts: int = 3,
        retry_backoff: float = 1.0,
    ):
        """
        Initialize APIClient.

        Args:
            server_url: Base URL of API server (e.g., http://localhost:8000)
            auth_token: Optional auth token for request headers
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts on failure
            retry_backoff: Initial backoff for exponential retry (seconds)
        """
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "APIClient":
        """Context manager entry."""
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Make HTTP request with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path (without server URL)
            **kwargs: Additional arguments for httpx.AsyncClient.request()

        Returns:
            JSON response as dictionary

        Raises:
            APIConnectionError: If unable to connect
            APITimeoutError: If request times out
            APIResponseError: If API returns error response
        """
        url = f"{self.server_url}{path}"
        headers = kwargs.pop("headers", {})

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        if not self._client:
            self._client = httpx.AsyncClient()

        last_error = None
        backoff = self.retry_backoff

        for attempt in range(self.retry_attempts):
            try:
                logger.debug(
                    f"API request (attempt {attempt + 1}/{self.retry_attempts}): "
                    f"{method} {path}"
                )

                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    **kwargs,
                )

                if response.status_code >= 400:
                    raise APIResponseError(
                        f"API error {response.status_code}: {response.text}"
                    )

                return response.json()

            except httpx.TimeoutException as e:
                last_error = APITimeoutError(f"Request timeout after {self.timeout}s: {e}")
                logger.warning(f"{last_error} (attempt {attempt + 1})")

            except (httpx.ConnectError, httpx.NetworkError) as e:
                last_error = APIConnectionError(f"Failed to connect to {url}: {e}")
                logger.warning(f"{last_error} (attempt {attempt + 1})")

            except APIResponseError as e:
                # Don't retry on API errors
                logger.error(f"API error: {e}")
                raise

            except httpx.HTTPError as e:
                last_error = APIClientError(f"HTTP error: {e}")
                logger.warning(f"{last_error} (attempt {attempt + 1})")

            # Exponential backoff before retry
            if attempt < self.retry_attempts - 1:
                import asyncio

                await asyncio.sleep(backoff)
                backoff *= 2  # Double the backoff

        # All retries exhausted
        if last_error:
            raise last_error

        raise APIClientError("Unknown error in API request")

    async def execute_task(self, task_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute a task by ID."""
        return await self._request("POST", f"/tasks/{task_id}/execute", **kwargs)

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status by ID."""
        return await self._request("GET", f"/tasks/{task_id}")

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get full task details by ID."""
        return await self._request("GET", f"/tasks/{task_id}")

    async def list_tasks(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List tasks with optional filtering and pagination."""
        import uuid
        
        params = {}
        if status:
            params["status"] = status
        if user_id:
            params["user_id"] = user_id
        params["limit"] = limit
        params["offset"] = offset

        # Use JSON-RPC format for /tasks endpoint
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "method": "tasks.list",
            "params": params,
            "id": str(uuid.uuid4()),
        }

        response = await self._request("POST", "/tasks", json=jsonrpc_request)

        # Handle JSON-RPC response format
        if isinstance(response, dict):
            if "result" in response:
                result = response["result"]
                if isinstance(result, list):
                    return result
                if isinstance(result, dict) and "tasks" in result:
                    return result["tasks"]
            elif "error" in response:
                error = response["error"]
                raise APIResponseError(
                    f"API error {error.get('code', 'unknown')}: {error.get('message', 'Unknown error')}"
                )

        # Fallback: handle direct array response (backward compatibility)
        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "tasks" in response:
            return response["tasks"]

        logger.warning(f"Unexpected response format: {type(response)}")
        return []

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a running task."""
        return await self._request("POST", f"/tasks/{task_id}/cancel")

    async def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task."""
        return await self._request("DELETE", f"/tasks/{task_id}")

    async def create_task(
        self, name: str, executor_id: str, inputs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new task."""
        payload = {
            "name": name,
            "schemas": {"method": executor_id},
        }
        if inputs:
            payload["inputs"] = inputs

        return await self._request("POST", "/tasks", json=payload)

    async def update_task(
        self, task_id: str, **updates: Any
    ) -> Dict[str, Any]:
        """Update task fields."""
        return await self._request("PATCH", f"/tasks/{task_id}", json=updates)


__all__ = [
    "APIClient",
    "APIClientError",
    "APIConnectionError",
    "APITimeoutError",
    "APIResponseError",
]

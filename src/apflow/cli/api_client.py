"""
HTTP client for CLI to communicate with API server.

Provides a unified interface for CLI commands to access API-managed data,
ensuring data consistency between CLI and API when both are running.
"""

import uuid
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
        proxies: Optional[str] = None,
    ):
        """
        Initialize APIClient.

        Args:
            server_url: Base URL of API server (e.g., http://localhost:8000)
            auth_token: Optional auth token for request headers
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts on failure
            retry_backoff: Initial backoff for exponential retry (seconds)
            proxies: Proxy URL (e.g., http://127.0.0.1:7890). 
                     If None, disables automatic proxy detection from environment.
                     Use empty string "" to use environment proxy settings.
        """
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self.proxies = proxies
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "APIClient":
        """Context manager entry."""
        # Proxy configuration:
        # - None: explicitly disable proxy (ignore environment variables)
        # - "": use environment proxy (httpx default behavior)
        # - "http://...": use specific proxy URL
        if self.proxies is None:
            # Explicitly disable proxy to avoid environment variable interference
            self._client = httpx.AsyncClient(proxy=None, trust_env=False)
        elif self.proxies == "":
            # Use environment proxy (httpx default behavior)
            self._client = httpx.AsyncClient(trust_env=True)
        else:
            # Use specific proxy URL
            self._client = httpx.AsyncClient(proxy=self.proxies, trust_env=False)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _tasks_rpc(self, method: str, params: Any) -> Any:
        """Call the /tasks JSON-RPC endpoint."""
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": str(uuid.uuid4()),
        }

        response = await self._request("POST", "/tasks", json=jsonrpc_request)

        if isinstance(response, dict):
            if "result" in response:
                return response["result"]
            if "error" in response:
                error = response["error"]
                raise APIResponseError(
                    f"API error {error.get('code', 'unknown')}: {error.get('message', 'Unknown error')}"
                )

        return response

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
            logger.debug("Using auth token for API request")
            headers["Authorization"] = f"Bearer {self.auth_token}"
        else:
            logger.debug("No auth token provided for API request")

        if not self._client:
            # Use same proxy configuration logic as __aenter__
            if self.proxies is None:
                self._client = httpx.AsyncClient(proxy=None, trust_env=False)
            elif self.proxies == "":
                self._client = httpx.AsyncClient(trust_env=True)
            else:
                self._client = httpx.AsyncClient(proxy=self.proxies, trust_env=False)

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
        statuses = await self.get_tasks_status([task_id])
        if statuses:
            return statuses[0]
        return {"task_id": task_id, "status": "not_found"}

    async def get_tasks_status(self, task_ids: List[str]) -> List[Dict[str, Any]]:
        """Get status for multiple tasks."""
        if not task_ids:
            return []
        return await self._tasks_rpc("tasks.running.status", {"task_ids": task_ids})

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get full task details by ID."""
        return await self._tasks_rpc("tasks.get", {"task_id": task_id})

    async def list_tasks(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        root_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """List tasks with optional filtering and pagination."""
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "root_only": root_only,
        }
        if status:
            params["status"] = status
        if user_id:
            params["user_id"] = user_id

        response = await self._tasks_rpc("tasks.list", params)

        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "tasks" in response:
            return response["tasks"]

        logger.warning(f"Unexpected response format: {type(response)}")
        return []

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a running task."""
        results = await self.cancel_tasks([task_id])
        return results[0] if results else {"task_id": task_id, "status": "not_found"}

    async def cancel_tasks(
        self,
        task_ids: List[str],
        force: bool = False,
        error_message: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Cancel multiple tasks."""
        params: Dict[str, Any] = {"task_ids": task_ids, "force": force}
        if error_message:
            params["error_message"] = error_message
        return await self._tasks_rpc("tasks.cancel", params)

    async def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task."""
        return await self._tasks_rpc("tasks.delete", {"task_id": task_id})

    async def create_task(
        self, name: str, executor_id: str, inputs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new task."""
        payload: Dict[str, Any] = {
            "name": name,
            "schemas": {"method": executor_id},
        }
        if inputs:
            payload["inputs"] = inputs

        return await self._tasks_rpc("tasks.create", payload)

    async def create_tasks(self, tasks: List[Dict[str, Any]] | Dict[str, Any]) -> Dict[str, Any]:
        """Create tasks from a task array or single task dict."""
        return await self._tasks_rpc("tasks.create", tasks)

    async def update_task(
        self, task_id: str, **updates: Any
    ) -> Dict[str, Any]:
        """Update task fields."""
        return await self._tasks_rpc("tasks.update", {"task_id": task_id, **updates})

    async def copy_task(self, **params: Any) -> Dict[str, Any]:
        """Copy a task tree."""
        return await self._tasks_rpc("tasks.copy", params)

    async def get_task_tree(self, task_id: str) -> Dict[str, Any]:
        """Get task tree structure."""
        return await self._tasks_rpc("tasks.tree", {"task_id": task_id})

    async def get_task_children(self, parent_id: str) -> List[Dict[str, Any]]:
        """Get child tasks for a parent."""
        response = await self._tasks_rpc("tasks.children", {"parent_id": parent_id})
        return response if isinstance(response, list) else []

    async def count_tasks(
        self,
        user_id: Optional[str] = None,
        root_only: bool = False,
        statuses: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Count tasks grouped by status."""
        params: Dict[str, Any] = {"root_only": root_only}
        if user_id:
            params["user_id"] = user_id
        if statuses:
            params["statuses"] = statuses

        return await self._tasks_rpc("tasks.count", params)


__all__ = [
    "APIClient",
    "APIClientError",
    "APIConnectionError",
    "APITimeoutError",
    "APIResponseError",
]

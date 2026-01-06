"""
CLI helper utilities for API Gateway integration.

This module provides helper functions and context managers to transparently
use API when configured, with graceful fallback to local database.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Coroutine, Optional

from apflow.cli.api_client import APIClient, APIClientError
from apflow.core.config_manager import get_config_manager
from apflow.logger import get_logger

logger = get_logger(__name__)

# Flag to track if API URL has been validated in this session
_api_validated = False
_api_accessible = False


def should_use_api() -> bool:
    """
    Check if CLI should use API gateway based on configuration.
    
    Loads configuration from CLI config file if not already loaded.
    Validates API server URL accessibility (only once per session).
    Falls back to local database if server is not accessible.
    
    Returns:
        True if api_server_url is configured and accessible, False otherwise
    """
    global _api_validated, _api_accessible
    
    cm = get_config_manager()
    
    # If already validated in this session, use cached result
    if _api_validated:
        return _api_accessible
    
    # Mark as validated (even if loading fails, we only try once per session)
    _api_validated = True
    
    # Try to load from CLI config file if not already loaded
    if not cm.is_api_configured():
        try:
            cm.load_cli_config()
        except Exception as e:
            logger.debug(f"Failed to load API config: {e}")
            _api_accessible = False
            return False

    if not cm.is_api_configured():
        # Try a sensible default once (developer UX): localhost:8000
        default_url = "http://localhost:8000"
        try:
            is_accessible = run_async_safe(
                cm.check_api_server_accessible(default_url, timeout=1.0)
            )
            if is_accessible:
                cm.set_api_server_url(default_url)
                logger.info("Auto-configured API server URL: %s", default_url)
                _api_accessible = True
                return True
        except Exception as discover_exc:  # pragma: no cover - defensive
            logger.debug(
                "Default API auto-check failed for %s: %s", default_url, discover_exc
            )
        
        # logger.warning(
        #     "API server URL is not configured; using local database. "
        #     "Set it via 'apflow config set api_server_url <url>' (aliases: "
        #     "api-server, api-url) or by exporting APFLOW_BASE_URL or "
        #     "APFLOW_API_HOST/APFLOW_API_PORT."
        # )
        _api_accessible = False
        return False
    
    # If URL is configured, verify it's accessible
    if cm.is_api_configured():
        url = cm.get_api_server_url()
        try:
            is_accessible = run_async_safe(
                cm.check_api_server_accessible(url, timeout=3.0)
            )
            if not is_accessible:
                logger.warning(
                    f"API server at {url} is not accessible. "
                    "Will use local database for this session."
                )
                # Clear URL to fall back to local DB
                cm.set_api_server_url(None)
                _api_accessible = False
                return False
        except Exception as e:
            logger.warning(
                f"Failed to validate API server accessibility: {e}. "
                "Will use local database for this session."
            )
            # Clear URL to fall back to local DB
            cm.set_api_server_url(None)
            _api_accessible = False
            return False
    
    _api_accessible = cm.is_api_configured()
    return _api_accessible


@asynccontextmanager
async def get_api_client_if_configured() -> Optional[APIClient]:
    """
    Context manager that yields APIClient if configured, None otherwise.
    
    Usage:
        async with get_api_client_if_configured() as client:
            if client:
                # Use API
                result = await client.list_tasks()
            else:
                # Use local database
                result = query_local_db()
    
    Yields:
        APIClient instance if configured, None otherwise
    """
    if not should_use_api():
        yield None
        return
    
    cm = get_config_manager()
    server_url = cm.api_server_url
    auth_token = cm.admin_auth_token
    timeout = cm.api_timeout
    retry_attempts = cm.api_retry_attempts
    retry_backoff = cm.api_retry_backoff
    
    # Disable proxy by default to avoid environment variable interference
    # Users can configure proxy via environment variables if needed
    client = APIClient(
        server_url=server_url,
        auth_token=auth_token,
        timeout=timeout,
        retry_attempts=retry_attempts,
        retry_backoff=retry_backoff,
        proxies=None,  # Disable proxy to avoid environment variable issues
    )
    
    async with client:
        yield client


def run_async_safe(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Safely run async coroutine in CLI context.
    
    Handles the case where asyncpg connections need to be created and destroyed
    within the same event loop. This ensures database connections don't get
    bound to closed event loops.
    
    Args:
        coro: Coroutine to run
        
    Returns:
        Result of the coroutine
    """
    try:
        # Check if event loop is already running
        loop = asyncio.get_running_loop()
        # Event loop is running (e.g., in test environment), use nest_asyncio
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop running, safe to use asyncio.run()
        # This creates and closes an event loop for the entire coroutine operation
        return asyncio.run(coro)


async def api_with_fallback_decorator(
    api_func: Coroutine[Any, Any, Any],
    fallback_func: Coroutine[Any, Any, Any],
) -> Any:
    """
    Try API first, fall back to local database if API unavailable.
    
    Args:
        api_func: Async function to execute via API
        fallback_func: Async function to execute if API unavailable
        
    Returns:
        Result from either API or fallback function
    """
    if not should_use_api():
        return await fallback_func
    
    try:
        return await api_func
    except APIClientError as e:
        cm = get_config_manager()
        if cm.use_local_db:
            logger.warning(
                f"API call failed, falling back to local DB: {e}"
            )
            return await fallback_func
        else:
            logger.error(f"API call failed and no fallback configured: {e}")
            raise


def log_api_usage(command_name: str, using_api: bool) -> None:
    """
    Log whether a command is using API or local database.
    
    Args:
        command_name: Name of the CLI command
        using_api: True if using API, False if using local DB
    """
    if using_api:
        cm = get_config_manager()
        logger.debug(
            f"Command '{command_name}' using API gateway: "
            f"{cm.api_server_url}"
        )
    else:
        logger.debug(f"Command '{command_name}' using local database")


def reset_api_validation() -> None:
    """
    Reset API validation state.
    
    Useful for testing or when you want to re-validate the API server
    on the next should_use_api() call.
    """
    global _api_validated, _api_accessible
    _api_validated = False
    _api_accessible = False

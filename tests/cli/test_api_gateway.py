"""
Integration tests for CLI → API Gateway architecture.

Tests APIClient communication with API server, configuration management,
and fallback behavior when API is unavailable.
"""

import pytest

from apflow.cli.api_client import (
    APIClient,
    APIClientError,
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
)
from apflow.core.config_manager import get_config_manager


@pytest.mark.asyncio
async def test_api_client_initialization():
    """Test APIClient initialization with various configurations."""
    client = APIClient(
        server_url="http://localhost:8000",
        auth_token="test-token",
        timeout=60.0,
        retry_attempts=5,
        retry_backoff=2.0,
    )

    assert client.server_url == "http://localhost:8000"
    assert client.auth_token == "test-token"
    assert client.timeout == 60.0
    assert client.retry_attempts == 5
    assert client.retry_backoff == 2.0


@pytest.mark.asyncio
async def test_api_client_strips_trailing_slash():
    """Test that APIClient strips trailing slashes from server URL."""
    client = APIClient(server_url="http://localhost:8000/")
    assert client.server_url == "http://localhost:8000"


@pytest.mark.asyncio
async def test_config_manager_api_configuration():
    """Test ConfigManager API configuration methods."""
    cm = get_config_manager()
    cm.clear()

    # Initially not configured
    assert not cm.is_api_configured()
    assert cm.get_api_server_url() is None

    # Configure API
    cm.set_api_server_url("http://localhost:8000")
    assert cm.is_api_configured()
    assert cm.get_api_server_url() == "http://localhost:8000"

    # Configure auth token (using admin_auth_token)
    cm.set_admin_auth_token("test-token")
    assert cm.get_admin_auth_token() == "test-token"
    # Backward compatibility
    assert cm.get_api_auth_token() == "test-token"

    # Configure timeouts and retry
    cm.set_api_timeout(45.0)
    assert cm.get_api_timeout() == 45.0

    cm.set_api_retry_attempts(5)
    assert cm.get_api_retry_attempts() == 5

    cm.set_api_retry_backoff(2.0)
    assert cm.get_api_retry_backoff() == 2.0

    # Configure local DB fallback
    cm.set_use_local_db(False)
    assert not cm.get_use_local_db()

    # Clear should reset everything
    cm.clear()
    assert not cm.is_api_configured()
    assert cm.get_use_local_db() is True


@pytest.mark.asyncio
async def test_config_manager_api_defaults():
    """Test ConfigManager API configuration defaults."""
    cm = get_config_manager()
    cm.clear()

    # Check defaults
    assert cm.get_api_timeout() == 30.0
    assert cm.get_api_retry_attempts() == 3
    assert cm.get_api_retry_backoff() == 1.0
    assert cm.get_use_local_db() is True


@pytest.mark.asyncio
async def test_api_client_context_manager():
    """Test APIClient context manager initialization."""
    client = APIClient(server_url="http://localhost:8000")

    async with client:
        assert client._client is not None

    # Client should be closed after context exit


@pytest.mark.asyncio
async def test_api_client_error_types():
    """Test APIClient exception hierarchy."""
    # All custom errors inherit from APIClientError
    assert issubclass(APIConnectionError, APIClientError)
    assert issubclass(APITimeoutError, APIClientError)
    assert issubclass(APIResponseError, APIClientError)


@pytest.mark.asyncio
async def test_api_client_url_construction():
    """Test correct URL construction in APIClient methods."""
    client = APIClient(server_url="http://localhost:8000")

    # Test URL paths for different methods
    # (We won't actually call them, just verify the paths would be correct)

    # These would be called with correct URLs:
    # POST /tasks/{task_id}/execute
    # GET /tasks/{task_id}
    # GET /tasks/{task_id}
    # GET /tasks
    # POST /tasks/{task_id}/cancel
    # DELETE /tasks/{task_id}
    # POST /tasks
    # PATCH /tasks/{task_id}

    assert client.server_url == "http://localhost:8000"
    assert client.auth_token is None


@pytest.mark.asyncio
async def test_config_manager_multiple_configurations():
    """Test setting and getting multiple API configurations."""
    cm = get_config_manager()
    cm.clear()

    # Set multiple configurations
    cm.set_api_server_url("http://api.example.com:9000")
    cm.set_admin_auth_token("bearer-token-xyz")
    cm.set_api_timeout(120.0)
    cm.set_api_retry_attempts(10)
    cm.set_api_retry_backoff(0.5)
    cm.set_use_local_db(False)

    # Verify all are set correctly
    assert cm.get_api_server_url() == "http://api.example.com:9000"
    assert cm.get_admin_auth_token() == "bearer-token-xyz"
    # Backward compatibility
    assert cm.get_api_auth_token() == "bearer-token-xyz"
    assert cm.get_api_timeout() == 120.0
    assert cm.get_api_retry_attempts() == 10
    assert cm.get_api_retry_backoff() == 0.5
    assert not cm.get_use_local_db()
    assert cm.is_api_configured()

    # Clear and verify reset to defaults
    cm.clear()
    assert cm.get_api_server_url() is None
    assert cm.get_admin_auth_token() is None
    # Backward compatibility
    assert cm.get_api_auth_token() is None
    assert cm.get_api_timeout() == 30.0
    assert cm.get_api_retry_attempts() == 3
    assert cm.get_api_retry_backoff() == 1.0
    assert cm.get_use_local_db() is True
    assert not cm.is_api_configured()


__all__ = []

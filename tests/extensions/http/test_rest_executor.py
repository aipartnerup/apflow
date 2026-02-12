"""
Test RestExecutor

Tests for HTTP/REST API executor functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from apflow.core.execution.errors import ValidationError
from apflow.extensions.http.rest_executor import RestExecutor


class TestRestExecutor:
    """Test RestExecutor functionality"""

    @pytest.fixture(autouse=True)
    def _mock_dns_resolution(self):
        """Mock DNS resolution to return a public IP for test URLs.

        This prevents the SSRF validation from failing on fictional hostnames
        like api.example.com used in existing tests.
        """
        with patch(
            "socket.getaddrinfo",
            return_value=[(None, None, None, None, ("93.184.216.34", 0))],
        ):
            yield

    @pytest.mark.asyncio
    async def test_execute_get_request(self):
        """Test executing a GET request"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = '{"result": "success"}'
        mock_response.json.return_value = {"result": "success"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {"url": "https://api.example.com/test", "method": "GET"}
            )

            assert result["success"] is True
            assert result["status_code"] == 200
            assert result["json"] == {"result": "success"}
            mock_client_instance.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_post_request_with_json(self):
        """Test executing a POST request with JSON body"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.url = "https://api.example.com/create"
        mock_response.headers = {}
        mock_response.text = '{"id": "123"}'
        mock_response.json.return_value = {"id": "123"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {
                    "url": "https://api.example.com/create",
                    "method": "POST",
                    "json": {"name": "test"},
                }
            )

            assert result["success"] is True
            assert result["status_code"] == 201
            call_kwargs = mock_client_instance.request.call_args[1]
            assert call_kwargs["json"] == {"name": "test"}

    @pytest.mark.asyncio
    async def test_execute_with_bearer_auth(self):
        """Test executing request with Bearer authentication"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {
                    "url": "https://api.example.com/test",
                    "auth": {"type": "bearer", "token": "test-token"},
                }
            )

            assert result["success"] is True
            call_kwargs = mock_client_instance.request.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_execute_with_basic_auth(self):
        """Test executing request with Basic authentication"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {
                    "url": "https://api.example.com/test",
                    "auth": {"type": "basic", "username": "user", "password": "pass"},
                }
            )

            assert result["success"] is True
            call_kwargs = mock_client_instance.request.call_args[1]
            assert call_kwargs["auth"] is not None

    @pytest.mark.asyncio
    async def test_execute_timeout_error(self):
        """Test handling timeout errors"""
        from apflow.core.execution.errors import NetworkError

        executor = RestExecutor()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

            # TimeoutException should be wrapped in NetworkError with helpful context
            with pytest.raises(NetworkError, match="HTTP request timed out"):
                await executor.execute({"url": "https://api.example.com/test", "timeout": 5.0})

    @pytest.mark.asyncio
    async def test_execute_missing_url(self):
        """Test error when URL is missing"""
        from apflow.core.execution.errors import ValidationError

        executor = RestExecutor()

        with pytest.raises(ValidationError, match="url is required"):
            await executor.execute({})

    @pytest.mark.asyncio
    async def test_execute_with_apikey_auth_header(self):
        """Test executing request with API key in header"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {
                    "url": "https://api.example.com/test",
                    "auth": {
                        "type": "apikey",
                        "key": "X-API-Key",
                        "value": "secret-key",
                        "location": "header",
                    },
                }
            )

            assert result["success"] is True
            call_kwargs = mock_client_instance.request.call_args[1]
            assert call_kwargs["headers"]["X-API-Key"] == "secret-key"

    @pytest.mark.asyncio
    async def test_execute_with_apikey_auth_query(self):
        """Test executing request with API key in query parameters"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {
                    "url": "https://api.example.com/test",
                    "auth": {
                        "type": "apikey",
                        "key": "api_key",
                        "value": "secret-key",
                        "location": "query",
                    },
                }
            )

            assert result["success"] is True
            call_kwargs = mock_client_instance.request.call_args[1]
            assert call_kwargs["params"]["api_key"] == "secret-key"

    @pytest.mark.asyncio
    async def test_execute_with_query_params(self):
        """Test executing request with query parameters"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {"url": "https://api.example.com/test", "params": {"page": "1", "limit": "10"}}
            )

            assert result["success"] is True
            call_kwargs = mock_client_instance.request.call_args[1]
            assert call_kwargs["params"] == {"page": "1", "limit": "10"}

    @pytest.mark.asyncio
    async def test_execute_with_form_data(self):
        """Test executing POST request with form data"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {
                    "url": "https://api.example.com/test",
                    "method": "POST",
                    "data": {"name": "test", "value": "123"},
                }
            )

            assert result["success"] is True
            call_kwargs = mock_client_instance.request.call_args[1]
            assert call_kwargs["data"] == {"name": "test", "value": "123"}

    @pytest.mark.asyncio
    async def test_execute_non_success_status(self):
        """Test handling non-success HTTP status codes"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "Not Found"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute({"url": "https://api.example.com/test"})

            assert result["success"] is False
            assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_execute_request_error(self):
        """Test handling request errors"""
        from apflow.core.execution.errors import NetworkError

        executor = RestExecutor()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(
                side_effect=httpx.RequestError("Connection error")
            )

            # RequestError should be wrapped in NetworkError with helpful context
            with pytest.raises(NetworkError, match="HTTP request failed"):
                await executor.execute({"url": "https://api.example.com/test"})

    @pytest.mark.asyncio
    async def test_execute_cancellation_before_request(self):
        """Test cancellation before making request"""
        executor = RestExecutor()
        executor.cancellation_checker = lambda: True

        result = await executor.execute({"url": "https://api.example.com/test"})

        assert result["success"] is False
        assert "cancelled" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_cancellation_after_request(self):
        """Test cancellation after making request"""
        executor = RestExecutor()
        cancelled = [False]

        def check_cancellation():
            if not cancelled[0]:
                cancelled[0] = True
                return False
            return True

        executor.cancellation_checker = check_cancellation

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute({"url": "https://api.example.com/test"})

            assert result["success"] is False
            assert "cancelled" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_all_http_methods(self):
        """Test all supported HTTP methods"""
        executor = RestExecutor()

        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]

        for method in methods:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.url = f"https://api.example.com/{method.lower()}"
            mock_response.headers = {}
            mock_response.text = "OK"
            mock_response.json.side_effect = Exception("Not JSON")

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request = AsyncMock(return_value=mock_response)

                result = await executor.execute(
                    {"url": f"https://api.example.com/{method.lower()}", "method": method}
                )

                assert result["success"] is True
                assert result["method"] == method

    @pytest.mark.asyncio
    async def test_execute_with_custom_timeout(self):
        """Test executing request with custom timeout"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {"url": "https://api.example.com/test", "timeout": 60.0}
            )

            assert result["success"] is True
            # timeout is passed to AsyncClient constructor, not request method
            client_call_kwargs = mock_client.call_args[1]
            assert client_call_kwargs["timeout"] == 60.0

    @pytest.mark.asyncio
    async def test_execute_with_ssl_verification_disabled(self):
        """Test executing request with SSL verification disabled"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                {"url": "https://api.example.com/test", "verify": False}
            )

            assert result["success"] is True
            # verify is passed to AsyncClient constructor, not request method
            client_call_kwargs = mock_client.call_args[1]
            assert client_call_kwargs["verify"] is False

    @pytest.mark.asyncio
    async def test_execute_rejects_private_ip(self):
        """Test that requests to private IP addresses are rejected"""
        executor = RestExecutor()

        with patch(
            "socket.getaddrinfo", return_value=[(None, None, None, None, ("192.168.1.1", 0))]
        ):
            with pytest.raises(ValidationError, match="private/reserved address"):
                await executor.execute({"url": "http://internal.corp/api"})

    @pytest.mark.asyncio
    async def test_execute_rejects_localhost(self):
        """Test that requests to localhost are rejected"""
        executor = RestExecutor()

        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
            with pytest.raises(ValidationError, match="private/reserved address"):
                await executor.execute({"url": "http://localhost.localdomain/admin"})

    @pytest.mark.asyncio
    async def test_execute_rejects_metadata_endpoint(self):
        """Test that requests to cloud metadata endpoints are rejected"""
        executor = RestExecutor()

        with patch(
            "socket.getaddrinfo", return_value=[(None, None, None, None, ("169.254.169.254", 0))]
        ):
            with pytest.raises(ValidationError, match="private/reserved address"):
                await executor.execute({"url": "http://metadata.google.internal/latest/meta-data/"})

    @pytest.mark.asyncio
    async def test_execute_allows_private_when_env_set(self):
        """Test that private URLs are allowed when APFLOW_REST_ALLOW_PRIVATE_URLS=1"""
        executor = RestExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "http://192.168.1.1/api"
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.json.side_effect = Exception("Not JSON")

        with (
            patch.dict("os.environ", {"APFLOW_REST_ALLOW_PRIVATE_URLS": "1"}),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await executor.execute({"url": "http://192.168.1.1/api"})

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_input_schema(self):
        """Test input schema generation"""
        executor = RestExecutor()
        schema = executor.get_input_schema()

        assert schema["type"] == "object"
        assert "url" in schema["required"]
        assert "properties" in schema
        assert "method" in schema["properties"]
        assert "auth" in schema["properties"]

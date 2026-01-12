"""
Tests for executor listing API and functionality
"""

import os
from unittest.mock import patch
from apflow.core.extensions.manager import get_available_executors
import pytest


class TestGetAvailableExecutors:
    """Test get_available_executors function"""

    def test_get_available_executors_no_restrictions(self):
        """Test getting executors with no APFLOW_EXTENSIONS restrictions"""

        with patch.dict(os.environ, {}, clear=True):
            result = get_available_executors()

            assert "executors" in result
            assert "count" in result
            assert "restricted" in result
            assert result["restricted"] is False
            assert "allowed_ids" not in result
            assert result["count"] > 0
            assert len(result["executors"]) == result["count"]

    def test_get_available_executors_with_restrictions(self):
        """Test getting executors with APFLOW_EXTENSIONS restrictions"""

        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio"}):
            result = get_available_executors()

            assert result["restricted"] is True
            assert "allowed_ids" in result
            assert "system_info_executor" in result["allowed_ids"]
            assert "command_executor" in result["allowed_ids"]

            # Verify only stdio executors are returned
            executor_ids = [e["id"] for e in result["executors"]]
            assert "system_info_executor" in executor_ids
            assert "command_executor" in executor_ids

    def test_get_available_executors_multiple_extensions(self):
        """Test getting executors with multiple extensions"""

        import sys
        from unittest.mock import MagicMock
        from apflow.core.extensions.manager import _is_package_installed, _loaded_extensions

        # Mock httpx as installed so http extension can load
        def mock_is_package_installed(package_name: str) -> bool:
            if package_name == "httpx":
                return True
            return _is_package_installed(package_name)

        # Create a mock httpx module so the import succeeds
        mock_httpx = MagicMock()
        mock_httpx.AsyncClient = MagicMock()
        
        # Store original httpx if it exists
        original_httpx = sys.modules.get("httpx")
        sys.modules["httpx"] = mock_httpx

        try:
            # Remove http extension module from cache if it was already imported (and failed)
            http_modules = [
                "apflow.extensions.http",
                "apflow.extensions.http.rest_executor",
            ]
            for module_name in http_modules:
                if module_name in sys.modules:
                    del sys.modules[module_name]

            with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio,http"}):
                with patch("apflow.core.extensions.manager._is_package_installed", side_effect=mock_is_package_installed):
                    # Reset loaded extensions state to ensure http extension is loaded
                    # Remove http from loaded extensions if it was previously skipped
                    if "http" in _loaded_extensions:
                        del _loaded_extensions["http"]

                    result = get_available_executors()

                    assert result["restricted"] is True
                    executor_ids = [e["id"] for e in result["executors"]]
                    assert "system_info_executor" in executor_ids
                    assert "rest_executor" in executor_ids
        finally:
            # Restore original httpx module
            if original_httpx is not None:
                sys.modules["httpx"] = original_httpx
            elif "httpx" in sys.modules and sys.modules["httpx"] is mock_httpx:
                del sys.modules["httpx"]

    def test_executor_metadata_structure(self):
        """Test that returned executor metadata has expected structure"""

        with patch.dict(os.environ, {}, clear=True):
            result = get_available_executors()

            assert len(result["executors"]) > 0
            executor = result["executors"][0]

            # Check required fields
            assert "id" in executor
            assert "name" in executor
            assert "description" in executor

            # Optional fields may exist
            # input_schema, tags, examples, etc.


@pytest.mark.asyncio
class TestSystemExecutorsEndpoint:
    """Test system.executors API endpoint"""

    async def test_system_executors_endpoint(self):
        """Test that system.executors endpoint returns executor list"""
        from apflow.api.routes.system import SystemRoutes
        from apflow.core.storage.sqlalchemy.models import TaskModel
        from starlette.datastructures import Headers
        import json

        # Create SystemRoutes instance
        system_routes = SystemRoutes(task_model_class=TaskModel)

        # Mock request
        class MockRequest:
            def __init__(self):
                self.headers = Headers({})

            async def json(self):
                return {
                    "jsonrpc": "2.0",
                    "id": "test-123",
                    "method": "system.executors",
                    "params": {},
                }

        request = MockRequest()

        # Call handler
        response = await system_routes.handle_system_requests(request)

        # Verify response
        assert response.status_code == 200
        content = json.loads(response.body.decode())

        assert content["jsonrpc"] == "2.0"
        assert content["id"] == "test-123"
        assert "result" in content

        result = content["result"]
        assert "executors" in result
        assert "count" in result
        assert "restricted" in result

    async def test_system_executors_with_restrictions(self):
        """Test system.executors endpoint with APFLOW_EXTENSIONS set"""
        from apflow.api.routes.system import SystemRoutes
        from apflow.core.storage.sqlalchemy.models import TaskModel
        import json

        system_routes = SystemRoutes(task_model_class=TaskModel)

        class MockRequest:
            def __init__(self):
                from starlette.datastructures import Headers

                self.headers = Headers({})

            async def json(self):
                return {
                    "jsonrpc": "2.0",
                    "id": "test-456",
                    "method": "system.executors",
                    "params": {},
                }

        with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio"}):
            request = MockRequest()
            response = await system_routes.handle_system_requests(request)

            assert response.status_code == 200
            content = json.loads(response.body.decode())
            result = content["result"]

            assert result["restricted"] is True
            assert "allowed_ids" in result
            assert "system_info_executor" in result["allowed_ids"]

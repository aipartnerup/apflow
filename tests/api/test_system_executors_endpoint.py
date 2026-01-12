"""
Test API endpoint for listing available executors
"""

import os
from unittest.mock import patch
from apflow.core.extensions.manager import initialize_extensions
import pytest


@pytest.mark.asyncio
async def test_system_executors_api_no_restrictions():
    """Test system.executors API endpoint with no APFLOW_EXTENSIONS restrictions"""
    from apflow.api.routes.system import SystemRoutes
    from apflow.core.storage.sqlalchemy.models import TaskModel
    from starlette.datastructures import Headers
    import json

    # Initialize extensions first
    with patch.dict(os.environ, {}, clear=True):
        initialize_extensions()

        # Create SystemRoutes instance with TaskModel
        system_routes = SystemRoutes(task_model_class=TaskModel)

        # Mock request
        class MockRequest:
            def __init__(self):
                self.headers = Headers({})

            async def json(self):
                return {
                    "jsonrpc": "2.0",
                    "id": "test-no-restrictions",
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
        assert content["id"] == "test-no-restrictions"
        assert "result" in content

        result = content["result"]
        assert "executors" in result
        assert "count" in result
        assert "restricted" in result

        # No restrictions, so should show all executors
        assert result["restricted"] is False
        assert "allowed_ids" not in result
        assert result["count"] > 0

        # Verify executor structure
        assert len(result["executors"]) > 0
        executor = result["executors"][0]
        assert "id" in executor
        assert "name" in executor
        assert "description" in executor

        print(f"\n✅ API Test (No Restrictions): Found {result['count']} executors")
        print(f"   Sample executor: {executor['id']}")


@pytest.mark.asyncio
async def test_system_executors_api_with_restrictions():
    """Test system.executors API endpoint with APFLOW_EXTENSIONS=stdio (no http)"""
    from apflow.api.routes.system import SystemRoutes
    from apflow.core.storage.sqlalchemy.models import TaskModel
    from starlette.datastructures import Headers
    import json

    # Initialize extensions with restrictions (no http)
    with patch.dict(os.environ, {"APFLOW_EXTENSIONS": "stdio"}):
        initialize_extensions()

        system_routes = SystemRoutes(task_model_class=TaskModel)

        class MockRequest:
            def __init__(self):
                self.headers = Headers({})

            async def json(self):
                return {
                    "jsonrpc": "2.0",
                    "id": "test-with-restrictions",
                    "method": "system.executors",
                    "params": {},
                }

        request = MockRequest()
        response = await system_routes.handle_system_requests(request)

        assert response.status_code == 200
        content = json.loads(response.body.decode())
        result = content["result"]

        # With restrictions
        assert result["restricted"] is True
        assert "allowed_ids" in result

        # Verify only stdio and http executors
        executor_ids = [e["id"] for e in result["executors"]]
        assert "system_info_executor" in executor_ids
        assert "command_executor" in executor_ids
        assert "rest_executor" not in executor_ids

        # Verify crewai is NOT in the list (not in stdio,http)
        assert "crewai_executor" not in executor_ids

        print(f"\n✅ API Test (With Restrictions): Found {result['count']} executors")
        print(f"   Allowed IDs: {result['allowed_ids']}")
        print(f"   Executor IDs: {executor_ids}")


if __name__ == "__main__":
    import asyncio
    print("\n" + "=" * 80)
    print("Testing API endpoint: system.executors")
    print("=" * 80)
    
    asyncio.run(test_system_executors_api_no_restrictions())
    asyncio.run(test_system_executors_api_with_restrictions())
    
    print("\n" + "=" * 80)
    print("All API tests passed! ✅")
    print("=" * 80 + "\n")

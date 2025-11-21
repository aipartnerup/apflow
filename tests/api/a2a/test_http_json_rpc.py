"""
Test HTTP JSON-RPC client integration

This module tests the A2A Protocol Server using direct HTTP JSON-RPC calls.
Tests the /tasks and /system endpoints for task management.
"""

import pytest
import json
import uuid
from starlette.testclient import TestClient
from aipartnerupflow.api.a2a.server import create_a2a_server
from aipartnerupflow.core.storage import get_default_session, set_default_session, reset_default_session
from tests.conftest import sync_db_session


@pytest.fixture(scope="function")
def use_test_db_session(sync_db_session):
    """Fixture to set and reset default session for tests"""
    set_default_session(sync_db_session)
    yield sync_db_session
    reset_default_session()


@pytest.fixture(scope="function")
def json_rpc_client(use_test_db_session):
    """Create HTTP JSON-RPC test client"""
    # Create A2A server instance
    server_instance = create_a2a_server(
        verify_token_secret_key=None,  # No JWT for testing
        base_url="http://localhost:8000",
        enable_system_routes=True,
    )
    
    # Build the app
    app = server_instance.build()
    
    # Create test client
    client = TestClient(app)
    
    yield client
    
    # Cleanup
    client.close()


def test_jsonrpc_tasks_create(json_rpc_client):
    """Test creating tasks via JSON-RPC /tasks endpoint"""
    # Prepare task data
    task_data = {
        "id": f"test-task-{uuid.uuid4().hex[:8]}",
        "name": "Test Task via JSON-RPC",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # JSON-RPC request format
    request_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tasks.create",
        "params": [task_data]  # Tasks array as direct parameter
    }
    
    # Send request to /tasks endpoint
    response = json_rpc_client.post(
        "/tasks",
        json=request_payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "id" in result
    assert result["id"] == 1
    assert "result" in result
    
    # Verify task was created
    created_task = result["result"]
    assert "id" in created_task
    assert created_task["name"] == task_data["name"]


def test_jsonrpc_tasks_create_multiple(json_rpc_client):
    """Test creating multiple tasks via JSON-RPC"""
    # Prepare task tree
    tasks = [
        {
            "id": f"root-{uuid.uuid4().hex[:8]}",
            "name": "Root Task",
            "user_id": "test-user",
            "status": "pending",
            "priority": 2,
            "has_children": True,
            "dependencies": [
                {"id": f"child-{uuid.uuid4().hex[:8]}", "required": True}
            ],
            "schemas": {
                "method": "aggregate_results_executor",
                "type": "core"
            },
            "inputs": {}
        },
        {
            "id": f"child-{uuid.uuid4().hex[:8]}",
            "name": "Child Task",
            "parent_id": f"root-{uuid.uuid4().hex[:8]}",
            "user_id": "test-user",
            "status": "pending",
            "priority": 1,
            "has_children": False,
            "dependencies": [],
            "schemas": {
                "method": "system_info",
                "type": "stdio"
            },
            "inputs": {}
        }
    ]
    
    # Fix parent_id reference
    tasks[1]["parent_id"] = tasks[0]["id"]
    tasks[0]["dependencies"][0]["id"] = tasks[1]["id"]
    
    request_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tasks.create",
        "params": tasks
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=request_payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    # Verify task tree was created
    created_tree = result["result"]
    assert "id" in created_tree
    assert "children" in created_tree or "name" in created_tree


def test_jsonrpc_tasks_get(json_rpc_client):
    """Test getting a task via JSON-RPC"""
    # First create a task
    task_data = {
        "id": f"get-test-{uuid.uuid4().hex[:8]}",
        "name": "Task to Get",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Create task
    create_request = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Get task
    get_request = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tasks.get",
        "params": {
            "task_id": task_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=get_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    # Verify task data
    task = result["result"]
    assert task["id"] == task_id
    assert task["name"] == task_data["name"]


def test_jsonrpc_tasks_detail(json_rpc_client):
    """Test getting task detail via JSON-RPC"""
    # Create a task first
    task_data = {
        "id": f"detail-test-{uuid.uuid4().hex[:8]}",
        "name": "Task for Detail",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 20,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Get task detail
    detail_request = {
        "jsonrpc": "2.0",
        "id": 21,
        "method": "tasks.detail",
        "params": {
            "task_id": task_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=detail_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert "result" in result
    task = result["result"]
    assert task["id"] == task_id


def test_jsonrpc_tasks_tree(json_rpc_client):
    """Test getting task tree via JSON-RPC"""
    # Create a task tree
    tasks = [
        {
            "id": f"tree-root-{uuid.uuid4().hex[:8]}",
            "name": "Tree Root",
            "user_id": "test-user",
            "status": "pending",
            "priority": 2,
            "has_children": True,
            "dependencies": [
                {"id": f"tree-child-{uuid.uuid4().hex[:8]}", "required": True}
            ],
            "schemas": {
                "method": "aggregate_results_executor",
                "type": "core"
            },
            "inputs": {}
        },
        {
            "id": f"tree-child-{uuid.uuid4().hex[:8]}",
            "name": "Tree Child",
            "parent_id": f"tree-root-{uuid.uuid4().hex[:8]}",
            "user_id": "test-user",
            "status": "pending",
            "priority": 1,
            "has_children": False,
            "dependencies": [],
            "schemas": {
                "method": "system_info",
                "type": "stdio"
            },
            "inputs": {}
        }
    ]
    
    # Fix references
    tasks[1]["parent_id"] = tasks[0]["id"]
    tasks[0]["dependencies"][0]["id"] = tasks[1]["id"]
    
    # Create tree
    create_request = {
        "jsonrpc": "2.0",
        "id": 30,
        "method": "tasks.create",
        "params": tasks
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    created_result = create_response.json()
    root_id = created_result["result"]["id"]
    
    # Get tree
    tree_request = {
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tasks.tree",
        "params": {
            "task_id": root_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=tree_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert "result" in result
    tree = result["result"]
    assert tree["id"] == root_id
    assert "children" in tree


def test_jsonrpc_tasks_update(json_rpc_client):
    """Test updating a task via JSON-RPC"""
    # Create a task
    task_data = {
        "id": f"update-test-{uuid.uuid4().hex[:8]}",
        "name": "Task to Update",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 40,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Update task
    update_request = {
        "jsonrpc": "2.0",
        "id": 41,
        "method": "tasks.update",
        "params": {
            "task_id": task_id,
            "status": "in_progress",
            "progress": 0.5
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=update_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert "result" in result
    updated_task = result["result"]
    assert updated_task["status"] == "in_progress"
    assert float(updated_task["progress"]) == 0.5


def test_jsonrpc_system_health(json_rpc_client):
    """Test system health check via JSON-RPC"""
    health_request = {
        "jsonrpc": "2.0",
        "id": 50,
        "method": "system.health",
        "params": {}
    }
    
    response = json_rpc_client.post(
        "/system",
        json=health_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    health = result["result"]
    assert "status" in health
    assert health["status"] == "healthy"


def test_jsonrpc_error_handling(json_rpc_client):
    """Test JSON-RPC error handling"""
    # Invalid method
    invalid_request = {
        "jsonrpc": "2.0",
        "id": 60,
        "method": "tasks.invalid_method",
        "params": {}
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=invalid_request,
        headers={"Content-Type": "application/json"}
    )
    
    # Our implementation returns 400 for method not found, but still includes JSON-RPC error format
    assert response.status_code in [200, 400]  # May return 400 or 200 with error
    result = response.json()
    
    assert "jsonrpc" in result
    assert "error" in result
    assert result["error"]["code"] == -32601  # Method not found


def test_jsonrpc_running_tasks_list(json_rpc_client):
    """Test listing running tasks via JSON-RPC"""
    list_request = {
        "jsonrpc": "2.0",
        "id": 70,
        "method": "tasks.running.list",
        "params": {
            "limit": 10
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=list_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert "jsonrpc" in result
    assert "result" in result
    # Result should be a list
    assert isinstance(result["result"], list)


@pytest.mark.integration
def test_jsonrpc_full_workflow(json_rpc_client):
    """Integration test: Full JSON-RPC workflow"""
    # Step 1: Create task
    task_data = {
        "id": f"workflow-{uuid.uuid4().hex[:8]}",
        "name": "Workflow Test Task",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    create_request = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tasks.create",
        "params": [task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    task_id = created_result["result"]["id"]
    
    # Step 2: Get task
    get_request = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tasks.get",
        "params": {"task_id": task_id}
    }
    
    get_response = json_rpc_client.post("/tasks", json=get_request)
    assert get_response.status_code == 200
    get_result = get_response.json()
    print(f"result:\n {json.dumps(get_result, indent=2)}")
    assert get_result["result"]["id"] == task_id
    
    # Step 3: Update task
    update_request = {
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tasks.update",
        "params": {
            "task_id": task_id,
            "status": "completed",
            "progress": 1.0
        }
    }
    
    update_response = json_rpc_client.post("/tasks", json=update_request)
    assert update_response.status_code == 200
    update_result = update_response.json()
    assert update_result["result"]["status"] == "completed"


def test_jsonrpc_tasks_copy(json_rpc_client):
    """Test copying a task via JSON-RPC"""
    # First create a task tree
    root_task_data = {
        "id": f"copy-root-{uuid.uuid4().hex[:8]}",
        "name": "Root Task to Copy",
        "user_id": "test-user",
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    child_task_data = {
        "id": f"copy-child-{uuid.uuid4().hex[:8]}",
        "name": "Child Task to Copy",
        "user_id": "test-user",
        "parent_id": root_task_data["id"],
        "status": "pending",
        "priority": 1,
        "has_children": False,
        "dependencies": [],
        "schemas": {
            "method": "system_info",
            "type": "stdio"
        },
        "inputs": {}
    }
    
    # Create task tree
    create_request = {
        "jsonrpc": "2.0",
        "id": 200,
        "method": "tasks.create",
        "params": [root_task_data, child_task_data]
    }
    
    create_response = json_rpc_client.post("/tasks", json=create_request)
    assert create_response.status_code == 200
    created_result = create_response.json()
    root_task_id = created_result["result"]["id"]
    
    # Copy task
    copy_request = {
        "jsonrpc": "2.0",
        "id": 201,
        "method": "tasks.copy",
        "params": {
            "task_id": root_task_id
        }
    }
    
    response = json_rpc_client.post(
        "/tasks",
        json=copy_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify JSON-RPC response structure
    assert "jsonrpc" in result
    assert result["jsonrpc"] == "2.0"
    assert "result" in result
    
    # Verify copied task
    copied_task = result["result"]
    assert "id" in copied_task
    assert copied_task["id"] != root_task_id  # New task ID
    assert copied_task["name"] == root_task_data["name"]
    assert copied_task["original_task_id"] == root_task_id  # Linked to original
    assert copied_task["status"] == "pending"  # Reset to pending
    assert copied_task["progress"] == 0.0  # Reset progress
    
    # Verify original task has_copy flag is set
    get_request = {
        "jsonrpc": "2.0",
        "id": 202,
        "method": "tasks.get",
        "params": {"task_id": root_task_id}
    }
    get_response = json_rpc_client.post("/tasks", json=get_request)
    assert get_response.status_code == 200
    original_task = get_response.json()["result"]
    assert original_task.get("has_copy") is True


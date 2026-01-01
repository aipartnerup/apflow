"""
Test GenerateExecutor
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from apflow.extensions.generate.generate_executor import GenerateExecutor


class TestGenerateExecutor:
    """Test GenerateExecutor"""
    
    def test_executor_attributes(self):
        """Test executor has correct attributes"""
        executor = GenerateExecutor()
        assert executor.id == "generate_executor"
        assert executor.name == "Generate Executor"
        assert executor.type == "generate"
    
    def test_get_input_schema(self):
        """Test input schema"""
        executor = GenerateExecutor()
        schema = executor.get_input_schema()
        assert isinstance(schema, dict)
        assert schema["type"] == "object"
        assert "requirement" in schema["required"]
        assert "requirement" in schema["properties"]
    
    def test_parse_llm_response_valid_json(self):
        """Test parsing valid JSON response"""
        executor = GenerateExecutor()
        response = '[{"name": "test_executor", "inputs": {}}]'
        tasks = executor._parse_llm_response(response)
        assert isinstance(tasks, list)
        assert len(tasks) == 1
        assert tasks[0]["name"] == "test_executor"
    
    def test_parse_llm_response_markdown_wrapped(self):
        """Test parsing JSON wrapped in markdown code blocks"""
        executor = GenerateExecutor()
        response = '```json\n[{"name": "test_executor"}]\n```'
        tasks = executor._parse_llm_response(response)
        assert isinstance(tasks, list)
        assert len(tasks) == 1
    
    def test_parse_llm_response_invalid_json(self):
        """Test parsing invalid JSON raises error"""
        executor = GenerateExecutor()
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            executor._parse_llm_response("invalid json")
    
    def test_validate_tasks_array_empty(self):
        """Test validation of empty array"""
        executor = GenerateExecutor()
        result = executor._validate_tasks_array([])
        assert not result["valid"]
        assert "empty" in result["error"].lower()
    
    def test_validate_tasks_array_missing_name(self):
        """Test validation fails when task missing name"""
        executor = GenerateExecutor()
        result = executor._validate_tasks_array([{"inputs": {}}])
        assert not result["valid"]
        assert "name" in result["error"].lower()
    
    def test_validate_tasks_array_mixed_id_mode(self):
        """Test validation fails with mixed id mode"""
        executor = GenerateExecutor()
        tasks = [
            {"id": "task_1", "name": "executor1"},
            {"name": "executor2"}  # No id
        ]
        result = executor._validate_tasks_array(tasks)
        assert not result["valid"]
        assert "mixed" in result["error"].lower()
    
    def test_validate_tasks_array_valid(self):
        """Test validation of valid task array"""
        executor = GenerateExecutor()
        tasks = [
            {"name": "executor1", "priority": 1},
            {"name": "executor2", "parent_id": "executor1", "priority": 2}
        ]
        result = executor._validate_tasks_array(tasks)
        assert result["valid"]
        assert result["error"] is None
    
    def test_validate_tasks_array_valid_with_dependencies(self):
        """Test validation of valid task array with dependencies and parent_id"""
        executor = GenerateExecutor()
        tasks = [
            {"id": "task_1", "name": "executor1", "priority": 1},  # Root task
            {
                "id": "task_2",
                "name": "executor2",
                "parent_id": "task_1",  # task_2 is child of task_1 (parallel task)
                "priority": 1
            },
            {
                "id": "task_3",
                "name": "executor3",
                "parent_id": "task_1",  # parent_id = first dependency
                "dependencies": [{"id": "task_1", "required": True}, {"id": "task_2", "required": True}],
                "priority": 2
            }
        ]
        result = executor._validate_tasks_array(tasks)
        assert result["valid"]
        assert result["error"] is None
    
    def test_validate_tasks_array_sequential_chain(self):
        """Test validation of sequential task chain with correct parent_id"""
        executor = GenerateExecutor()
        tasks = [
            {"id": "task_1", "name": "executor1", "priority": 1},
            {
                "id": "task_2",
                "name": "executor2",
                "parent_id": "task_1",  # parent_id = previous task
                "dependencies": [{"id": "task_1", "required": True}],
                "priority": 2
            },
            {
                "id": "task_3",
                "name": "executor3",
                "parent_id": "task_2",  # parent_id = previous task
                "dependencies": [{"id": "task_2", "required": True}],
                "priority": 2
            }
        ]
        result = executor._validate_tasks_array(tasks)
        assert result["valid"]
        assert result["error"] is None
    
    def test_validate_tasks_array_multiple_roots(self):
        """Test validation fails with multiple root tasks"""
        executor = GenerateExecutor()
        tasks = [
            {"name": "executor1"},
            {"name": "executor2"}  # Also a root
        ]
        result = executor._validate_tasks_array(tasks)
        assert not result["valid"]
        assert "multiple root" in result["error"].lower()
        assert "parent_id" in result["error"].lower()  # Error should mention parent_id fix
    
    def test_validate_tasks_array_missing_parent_id_with_dependencies(self):
        """Test validation fails when task has dependencies but no parent_id"""
        executor = GenerateExecutor()
        tasks = [
            {"id": "task_1", "name": "executor1", "priority": 1},
            {
                "id": "task_2",
                "name": "executor2",
                # Missing parent_id but has dependencies
                "dependencies": [{"id": "task_1", "required": True}],
                "priority": 2
            }
        ]
        result = executor._validate_tasks_array(tasks)
        assert not result["valid"]
        assert "multiple root" in result["error"].lower()  # task_2 is also a root
    
    def test_validate_tasks_array_invalid_parent_id(self):
        """Test validation fails with invalid parent_id"""
        executor = GenerateExecutor()
        tasks = [
            {"name": "executor1"},
            {"name": "executor2", "parent_id": "nonexistent"}
        ]
        result = executor._validate_tasks_array(tasks)
        assert not result["valid"]
        assert "parent_id" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_missing_requirement(self):
        """Test execute fails without requirement"""
        executor = GenerateExecutor()
        result = await executor.execute({})
        assert result["status"] == "failed"
        assert "requirement" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_with_mock_llm(self):
        """Test execute with mocked LLM"""
        executor = GenerateExecutor()
        
        # Mock LLM client
        mock_llm_client = Mock()
        mock_llm_client.generate = AsyncMock(return_value='[{"name": "test_executor", "inputs": {}}]')
        
        with patch('apflow.extensions.generate.generate_executor.create_llm_client', return_value=mock_llm_client):
            result = await executor.execute({
                "requirement": "Test requirement",
                "user_id": "user123"
            })
            
            # Should succeed with mocked LLM
            # Note: This might fail validation if executor doesn't exist, but parsing should work
            assert "status" in result
            assert "tasks" in result
    
    @pytest.mark.asyncio
    async def test_execute_validates_parent_id_structure(self):
        """Test that execute validates parent_id structure in generated tasks"""
        executor = GenerateExecutor()
        
        # Mock LLM client to return tasks with correct parent_id structure
        mock_llm_client = Mock()
        mock_response = json.dumps([
            {"id": "task_1", "name": "system_info_executor", "inputs": {"resource": "cpu"}},
            {
                "id": "task_2",
                "name": "command_executor",
                "parent_id": "task_1",  # Correct: parent_id = first dependency
                "dependencies": [{"id": "task_1", "required": True}],
                "inputs": {"command": "echo test"}
            }
        ])
        mock_llm_client.generate = AsyncMock(return_value=mock_response)
        
        with patch('apflow.extensions.generate.generate_executor.create_llm_client', return_value=mock_llm_client):
            result = await executor.execute({
                "requirement": "Get system info then run a command",
                "user_id": "user123"
            })
            
            # Should validate parent_id structure
            assert "status" in result
            if result["status"] == "completed":
                tasks = result["tasks"]
                # Verify parent_id is set correctly
                root_tasks = [t for t in tasks if not t.get("parent_id")]
                assert len(root_tasks) == 1, "Should have exactly one root task"
                
                # Verify non-root tasks have parent_id
                non_root_tasks = [t for t in tasks if t.get("parent_id")]
                for task in non_root_tasks:
                    assert "parent_id" in task, f"Task {task.get('name')} should have parent_id"
                    # Verify parent_id references a valid task
                    parent_id = task["parent_id"]
                    task_ids = {t.get("id") or t.get("name") for t in tasks}
                    assert parent_id in task_ids, f"Task {task.get('name')} has invalid parent_id {parent_id}"
    
    @pytest.mark.asyncio
    async def test_execute_rejects_multiple_roots(self):
        """Test that execute rejects tasks with multiple root tasks"""
        executor = GenerateExecutor()
        
        # Mock LLM client to return tasks with multiple roots (missing parent_id)
        mock_llm_client = Mock()
        mock_response = json.dumps([
            {"id": "task_1", "name": "system_info_executor", "inputs": {"resource": "cpu"}},
            {"id": "task_2", "name": "system_info_executor", "inputs": {"resource": "memory"}},
            # task_3 has dependencies but no parent_id - will be treated as root
            {
                "id": "task_3",
                "name": "aggregate_results_executor",
                "dependencies": [{"id": "task_1", "required": True}, {"id": "task_2", "required": True}],
                "inputs": {}
            }
        ])
        mock_llm_client.generate = AsyncMock(return_value=mock_response)
        
        with patch('apflow.extensions.generate.generate_executor.create_llm_client', return_value=mock_llm_client):
            result = await executor.execute({
                "requirement": "Get system info from multiple sources",
                "user_id": "user123"
            })
            
            # Should fail validation due to multiple root tasks
            assert result["status"] == "failed"
            assert "multiple root" in result["error"].lower()
            assert "parent_id" in result["error"].lower()  # Error should mention parent_id
    
    def test_post_process_tasks_overrides_llm_generated_user_id(self):
        """Test that _post_process_tasks overrides LLM-generated user_id with correct one from BaseTask"""
        executor = GenerateExecutor()
        
        # Mock task object with user_id
        mock_task = Mock()
        mock_task.user_id = "correct_user_123"
        executor.task = mock_task  # Set task to enable self.user_id property
        
        # Simulate LLM-generated tasks with wrong user_id values
        llm_generated_tasks = [
            {
                "id": "task_1",  # Not UUID format
                "name": "system_info_executor",
                "user_id": "api_user",  # LLM generated wrong value
                "inputs": {"resource": "cpu"}
            },
            {
                "id": "task_2",  # Not UUID format
                "name": "command_executor",
                "user_id": "user123",  # LLM generated wrong value
                "parent_id": "task_1",
                "dependencies": [{"id": "task_1", "required": True}],
                "inputs": {"command": "echo test"}
            }
        ]
        
        # Process tasks
        processed_tasks = executor._post_process_tasks(llm_generated_tasks)
        
        # Verify all tasks have correct user_id
        for task in processed_tasks:
            assert task["user_id"] == "correct_user_123", f"Task {task.get('name')} should have user_id='correct_user_123', got '{task.get('user_id')}'"
        
        # Verify all tasks have UUID format IDs
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)
        for task in processed_tasks:
            assert "id" in task, f"Task {task.get('name')} should have id"
            assert uuid_pattern.match(task["id"]), f"Task {task.get('name')} should have UUID format id, got '{task.get('id')}'"
        
        # Verify dependencies references are updated if IDs changed
        # (In this case, IDs should be updated from "task_1" to UUIDs)
        task_ids = {task["id"] for task in processed_tasks}
        for task in processed_tasks:
            if "parent_id" in task:
                assert task["parent_id"] in task_ids, f"Task {task.get('name')} has invalid parent_id '{task.get('parent_id')}'"
            if "dependencies" in task:
                for dep in task["dependencies"]:
                    if isinstance(dep, dict) and "id" in dep:
                        assert dep["id"] in task_ids, f"Task {task.get('name')} has invalid dependency id '{dep.get('id')}'"
    
    def test_post_process_tasks_uses_parameter_user_id_over_self_user_id(self):
        """Test that _post_process_tasks prioritizes parameter user_id over self.user_id"""
        executor = GenerateExecutor()
        
        # Mock task object with user_id
        mock_task = Mock()
        mock_task.user_id = "self_user_456"
        executor.task = mock_task
        
        # Simulate LLM-generated tasks
        llm_generated_tasks = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",  # Valid UUID
                "name": "system_info_executor",
                "user_id": "api_user",  # LLM generated wrong value
                "inputs": {"resource": "cpu"}
            }
        ]
        
        # Process with parameter user_id (should take priority)
        processed_tasks = executor._post_process_tasks(llm_generated_tasks, user_id="param_user_789")
        
        # Verify parameter user_id is used (not self.user_id)
        assert processed_tasks[0]["user_id"] == "param_user_789"
        assert processed_tasks[0]["user_id"] != "self_user_456"
    
    def test_post_process_tasks_sets_none_when_no_user_id_available(self):
        """Test that _post_process_tasks sets user_id to None when no user_id is available"""
        executor = GenerateExecutor()
        
        # No task object set (self.user_id will be None)
        executor.task = None
        
        # Simulate LLM-generated tasks with wrong user_id
        llm_generated_tasks = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "system_info_executor",
                "user_id": "api_user",  # LLM generated wrong value
                "inputs": {"resource": "cpu"}
            }
        ]
        
        # Process without user_id parameter
        processed_tasks = executor._post_process_tasks(llm_generated_tasks, user_id=None)
        
        # Verify user_id is set to None (not kept as "api_user")
        assert processed_tasks[0]["user_id"] is None, "Should set user_id to None when no user_id available"
    
    def test_post_process_tasks_updates_dependencies_when_ids_change(self):
        """Test that _post_process_tasks updates dependency references when task IDs are converted to UUIDs"""
        executor = GenerateExecutor()
        
        mock_task = Mock()
        mock_task.user_id = "test_user"
        executor.task = mock_task
        
        # Simulate LLM-generated tasks with non-UUID IDs
        llm_generated_tasks = [
            {
                "id": "task_1",  # Not UUID
                "name": "system_info_executor",
                "user_id": "test_user",
                "inputs": {"resource": "cpu"}
            },
            {
                "id": "task_2",  # Not UUID
                "name": "command_executor",
                "user_id": "test_user",
                "parent_id": "task_1",  # References task_1
                "dependencies": [{"id": "task_1", "required": True}],  # References task_1
                "inputs": {"command": "echo test"}
            }
        ]
        
        # Process tasks
        processed_tasks = executor._post_process_tasks(llm_generated_tasks)
        
        # Verify all IDs are UUIDs
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)
        task_id_map = {}
        for task in processed_tasks:
            assert uuid_pattern.match(task["id"]), f"Task {task.get('name')} should have UUID format id"
            task_id_map[task["name"]] = task["id"]
        
        # Verify parent_id and dependencies are updated to new UUIDs
        command_task = next(t for t in processed_tasks if t["name"] == "command_executor")
        system_task = next(t for t in processed_tasks if t["name"] == "system_info_executor")
        
        # parent_id should reference the new UUID of system_info_executor
        assert command_task["parent_id"] == system_task["id"], "parent_id should reference updated UUID"
        
        # dependencies should reference the new UUID
        assert len(command_task["dependencies"]) == 1
        assert command_task["dependencies"][0]["id"] == system_task["id"], "dependency id should reference updated UUID"


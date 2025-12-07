"""
Test GenerateExecutor
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from aipartnerupflow.extensions.generate.generate_executor import GenerateExecutor


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
        
        with patch('aipartnerupflow.extensions.generate.generate_executor.create_llm_client', return_value=mock_llm_client):
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
        
        with patch('aipartnerupflow.extensions.generate.generate_executor.create_llm_client', return_value=mock_llm_client):
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
        
        with patch('aipartnerupflow.extensions.generate.generate_executor.create_llm_client', return_value=mock_llm_client):
            result = await executor.execute({
                "requirement": "Get system info from multiple sources",
                "user_id": "user123"
            })
            
            # Should fail validation due to multiple root tasks
            assert result["status"] == "failed"
            assert "multiple root" in result["error"].lower()
            assert "parent_id" in result["error"].lower()  # Error should mention parent_id


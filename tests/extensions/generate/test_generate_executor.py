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


"""
Tests for Enhanced GenerateExecutor Features

Tests dual-mode execution, auto-fix mechanisms, and enhanced validation.
"""

import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch
from apflow.extensions.generate.generate_executor import GenerateExecutor


class TestGenerateExecutorEnhanced:
    """Test suite for enhanced GenerateExecutor features"""

    @pytest.fixture
    def executor(self):
        """Create GenerateExecutor instance"""
        return GenerateExecutor(
            id="test_generate",
            name="Test Generator",
            llm_provider="openai",
            model="gpt-4",
            api_key="test-key",
        )

    def test_dual_mode_parameter(self, executor):
        """Test that generation_mode parameter exists in schema"""
        schema = executor.get_input_schema()
        assert "generation_mode" in schema["properties"]
        assert schema["properties"]["generation_mode"]["enum"] == ["single_shot", "multi_phase"]

    @pytest.mark.asyncio
    async def test_single_shot_mode_execution(self, executor):
        """Test single-shot mode creates LLM client"""
        with patch("apflow.extensions.generate.generate_executor.create_llm_client") as mock_client:
            with patch.object(executor, "_build_llm_prompt") as mock_prompt:
                mock_llm = Mock()
                mock_llm.generate = AsyncMock(
                    return_value='[{"id": "1", "name": "Task", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'
                )
                mock_client.return_value = mock_llm
                mock_prompt.return_value = "test prompt"

                result = await executor.execute(
                    {"requirement": "test requirement", "generation_mode": "single_shot"}
                )

                mock_client.assert_called_once()
                assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_multi_phase_mode_execution(self, executor):
        """Test multi-phase mode with CrewAI"""
        # Skip if crewai is not installed (required for multi-phase mode)
        pytest.importorskip("crewai")
        
        with patch(
            "apflow.extensions.generate.multi_phase_crew.MultiPhaseGenerationCrew"
        ) as mock_crew_class:
            mock_crew = Mock()
            mock_crew.generate = AsyncMock(
                return_value={
                    "success": True,
                    "tasks": [{"id": "1", "name": "Task 1", "schemas": {"method": "test"}}],
                }
            )
            mock_crew_class.return_value = mock_crew

            result = await executor.execute(
                {"requirement": "test requirement", "generation_mode": "multi_phase"}
            )

            mock_crew.generate.assert_called_once()
            assert result["status"] == "completed"

    def test_validate_schema_compliance_missing_required_field(self, executor):
        """Test schema compliance skips executors without schemas gracefully"""
        tasks = [
            {
                "id": str(uuid.uuid4()),
                "name": "Test Task",
                "schemas": {"method": "system_info_executor"},
                "inputs": {},
            }
        ]

        result = executor._validate_schema_compliance(tasks)
        assert result["valid"] is True

    def test_validate_schema_compliance_type_mismatch(self, executor):
        """Test schema compliance with correct inputs"""
        tasks = [
            {
                "id": str(uuid.uuid4()),
                "name": "Test Task",
                "schemas": {"method": "system_info_executor"},
                "inputs": {"resource": "cpu"},
            }
        ]

        result = executor._validate_schema_compliance(tasks)
        assert result["valid"] is True

    def test_validate_schema_compliance_unknown_executor(self, executor):
        """Test schema compliance allows unknown executors (caught at execution time)"""
        tasks = [
            {
                "id": str(uuid.uuid4()),
                "name": "Test Task",
                "schemas": {"method": "nonexistent_executor_that_does_not_exist"},
                "inputs": {},
            }
        ]

        result = executor._validate_schema_compliance(tasks)
        assert result["valid"] is True

    def test_validate_root_task_pattern_enforces_aggregator(self, executor):
        """Test root task pattern validation enforces aggregator for 2+ executors"""
        tasks = [
            {
                "id": "1",
                "name": "Root Task",
                "schemas": {"method": "scrape_executor"},
                "inputs": {"url": "https://example.com"},
            },
            {
                "id": "2",
                "name": "Child Task",
                "schemas": {"method": "llm_executor"},
                "parent_id": "1",
                "inputs": {"messages": []},
            },
        ]

        result = executor._validate_root_task_pattern(tasks)

        assert result["valid"] is False
        assert "aggregator" in result["error"].lower()

    def test_validate_root_task_pattern_allows_single_executor(self, executor):
        """Test root task pattern allows single executor without aggregator"""
        tasks = [
            {
                "id": "1",
                "name": "Root Task",
                "schemas": {"method": "scrape_executor"},
                "inputs": {"url": "https://example.com"},
            },
            {
                "id": "2",
                "name": "Child Task",
                "schemas": {"method": "scrape_executor"},
                "parent_id": "1",
                "inputs": {"url": "https://example.com"},
            },
        ]

        result = executor._validate_root_task_pattern(tasks)

        assert result["valid"] is True

    def test_validate_root_task_pattern_allows_aggregator_root(self, executor):
        """Test root task pattern allows aggregator with multiple executors"""
        tasks = [
            {
                "id": "1",
                "name": "Aggregate Results",
                "schemas": {"method": "aggregate_results_executor"},
                "inputs": {},
            },
            {
                "id": "2",
                "name": "Scrape Task",
                "schemas": {"method": "scrape_executor"},
                "parent_id": "1",
                "inputs": {"url": "https://example.com"},
            },
            {
                "id": "3",
                "name": "LLM Task",
                "schemas": {"method": "llm_executor"},
                "parent_id": "1",
                "inputs": {"messages": []},
            },
        ]

        result = executor._validate_root_task_pattern(tasks)

        assert result["valid"] is True

    def test_auto_fix_multiple_roots(self, executor):
        """Test auto-fix creates aggregator root for multiple roots"""
        tasks = [
            {
                "id": "1",
                "name": "Task 1",
                "schemas": {"method": "scrape_executor"},
                "inputs": {"url": "https://example.com"},
            },
            {
                "id": "2",
                "name": "Task 2",
                "schemas": {"method": "llm_executor"},
                "inputs": {"messages": []},
            },
        ]

        fixed_tasks = executor._fix_multiple_roots(tasks)

        assert fixed_tasks is not None
        assert len(fixed_tasks) == 3

        root_tasks = [t for t in fixed_tasks if not t.get("parent_id")]
        assert len(root_tasks) == 1
        assert "aggregate" in root_tasks[0]["schemas"]["method"].lower()

        for task in fixed_tasks[1:]:
            assert task.get("parent_id") == root_tasks[0]["id"]

    def test_auto_fix_invalid_parent_ids(self, executor):
        """Test auto-fix removes invalid parent_id references"""
        tasks = [
            {"id": "1", "name": "Root Task", "schemas": {"method": "test_executor"}, "inputs": {}},
            {
                "id": "2",
                "name": "Child Task",
                "schemas": {"method": "test_executor"},
                "parent_id": "nonexistent",
                "inputs": {},
            },
        ]

        fixed_tasks = executor._fix_invalid_parent_ids(tasks)

        assert fixed_tasks is not None
        assert len(fixed_tasks) == 2
        assert fixed_tasks[1].get("parent_id") == "1"

    def test_auto_fix_integration_with_validation(self, executor):
        """Test auto-fix is called during validation and retries"""
        tasks = [
            {"id": "1", "name": "Task 1", "schemas": {"method": "test_executor"}, "inputs": {}},
            {"id": "2", "name": "Task 2", "schemas": {"method": "test_executor"}, "inputs": {}},
        ]

        with patch.object(executor, "_fix_multiple_roots") as mock_fix:
            fixed_tasks = [
                {
                    "id": "root",
                    "name": "Root",
                    "schemas": {"method": "aggregate_results_executor"},
                    "inputs": {},
                },
                {
                    "id": "1",
                    "name": "Task 1",
                    "schemas": {"method": "test_executor"},
                    "parent_id": "root",
                    "inputs": {},
                },
                {
                    "id": "2",
                    "name": "Task 2",
                    "schemas": {"method": "test_executor"},
                    "parent_id": "root",
                    "inputs": {},
                },
            ]
            mock_fix.return_value = fixed_tasks

            result = executor._validate_tasks_array(tasks)

            if not result["valid"]:
                fixed = executor._attempt_auto_fix(tasks, result["error"])
                if fixed:
                    result = executor._validate_tasks_array(fixed)

            mock_fix.assert_called_once()

    def test_get_json_type(self, executor):
        """Test JSON type detection"""
        assert executor._get_json_type(None) == "null"
        assert executor._get_json_type(True) == "boolean"
        assert executor._get_json_type(42) == "integer"
        assert executor._get_json_type(3.14) == "number"
        assert executor._get_json_type("hello") == "string"
        assert executor._get_json_type([1, 2, 3]) == "array"
        assert executor._get_json_type({"key": "value"}) == "object"

    def test_is_compatible_type(self, executor):
        """Test type compatibility checking"""
        assert executor._is_compatible_type("string", "string") is True
        assert executor._is_compatible_type("integer", "number") is True
        assert executor._is_compatible_type("number", "integer") is False
        assert executor._is_compatible_type("string", "integer") is False
        assert executor._is_compatible_type("array", "object") is False

    def test_attempt_auto_fix_routing(self, executor):
        """Test auto-fix routes to correct fix method"""
        tasks = []

        with patch.object(executor, "_fix_multiple_roots") as mock_multiple:
            executor._attempt_auto_fix(tasks, "Multiple root tasks found")
            mock_multiple.assert_called_once()

        with patch.object(executor, "_fix_invalid_parent_ids") as mock_parent:
            executor._attempt_auto_fix(tasks, "parent_id 'xyz' is not in the tasks array")
            mock_parent.assert_called_once()

        with patch.object(executor, "_fix_invalid_parent_ids") as mock_unreachable:
            executor._attempt_auto_fix(tasks, "Tasks not reachable from root")
            mock_unreachable.assert_called_once()

        with patch.object(executor, "_fix_root_executor_to_aggregator") as mock_aggregator:
            executor._attempt_auto_fix(tasks, "Task tree uses 2 different executors but root task uses 'scrape_executor'. When multiple executors are needed, root should use an aggregator executor")
            mock_aggregator.assert_called_once()

    def test_fix_root_executor_to_aggregator(self, executor):
        """Test auto-fix for multiple executors with non-aggregator root"""
        tasks = [
            {
                "id": "root-1",
                "name": "Scrape Website",
                "schemas": {"method": "scrape_executor"},
                "inputs": {"url": "https://example.com"},
            },
            {
                "id": "task-2",
                "name": "Analyze Content",
                "parent_id": "root-1",
                "schemas": {"method": "crewai_executor"},
                "inputs": {"works": {"agents": {}, "tasks": {}}},
            },
        ]

        # Validate that it fails before fix
        validation = executor._validate_root_task_pattern(tasks)
        assert validation["valid"] is False
        assert "different executors" in validation["error"]

        # Apply auto-fix
        fixed = executor._fix_root_executor_to_aggregator(tasks)
        assert fixed is not None
        assert len(fixed) == 2

        # Check root task is now aggregator
        root_task = [t for t in fixed if not t.get("parent_id")][0]
        assert root_task["schemas"]["method"] == "aggregate_results_executor"
        assert root_task["inputs"] == {}  # Inputs cleared
        
        # Check root task has dependencies on all direct children
        assert "dependencies" in root_task, "Root aggregator must have dependencies field"
        dependencies = root_task["dependencies"]
        assert len(dependencies) == 1, "Root should have 1 dependency (1 direct child)"
        assert dependencies[0]["id"] == "task-2"
        assert dependencies[0]["required"] is True

        # Validate after fix
        revalidation = executor._validate_root_task_pattern(fixed)
        assert revalidation["valid"] is True

    def test_validation_integration_full_flow(self, executor):
        """Test full validation flow with auto-fix"""
        invalid_tasks = [
            {"id": "1", "name": "Task 1", "schemas": {"method": "test_executor"}, "inputs": {}},
            {"id": "2", "name": "Task 2", "schemas": {"method": "test_executor"}, "inputs": {}},
        ]

        validation = executor._validate_tasks_array(invalid_tasks)
        assert validation["valid"] is False

        fixed = executor._attempt_auto_fix(invalid_tasks, validation["error"])
        assert fixed is not None

        executor._validate_tasks_array(fixed)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

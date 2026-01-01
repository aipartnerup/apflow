"""
Unit tests for AggregateResultsExecutor

Tests the aggregate_results_executor functionality in isolation and with real executors.
"""

import pytest
from apflow.extensions.core.aggregate_results_executor import AggregateResultsExecutor


class TestAggregateResultsExecutor:
    """Test cases for AggregateResultsExecutor"""
    
    @pytest.fixture
    def executor(self):
        """Create AggregateResultsExecutor instance"""
        return AggregateResultsExecutor()
    
    @pytest.mark.asyncio
    async def test_execute_with_dependency_results(self, executor):
        """Test aggregating dependency results from inputs"""
        # Simulate inputs with dependency results (as merged by TaskManager)
        inputs = {
            "task-1": {
                "system": "Darwin",
                "cores": 8,
                "threads": 8
            },
            "task-2": {
                "total_gb": 64.0,
                "system": "Darwin"
            },
            "task-3": {
                "total": "926Gi",
                "used": "15Gi",
                "available": "319Gi"
            },
            # Pre-hook markers are filtered out (internal implementation details)
            "_pre_hook_executed": True,
            "_pre_hook_timestamp": "test-timestamp"
        }
        
        result = await executor.execute(inputs)
        
        # Verify result structure
        assert result is not None
        assert "summary" in result
        assert "timestamp" in result
        assert "results" in result
        assert "result_count" in result
        
        # Verify aggregated results (pre-hook markers are filtered out)
        assert result["result_count"] == 3  # Only 3 task results (pre-hook markers filtered)
        assert "task-1" in result["results"]
        assert "task-2" in result["results"]
        assert "task-3" in result["results"]
        # Pre-hook markers are filtered out (internal implementation details)
        assert "_pre_hook_executed" not in result["results"]
        assert "_pre_hook_timestamp" not in result["results"]
        
        # Verify result values
        assert result["results"]["task-1"]["cores"] == 8
        assert result["results"]["task-2"]["total_gb"] == 64.0
        assert result["results"]["task-3"]["total"] == "926Gi"
    
    @pytest.mark.asyncio
    async def test_execute_with_empty_inputs(self, executor):
        """Test aggregating with empty inputs"""
        inputs = {}
        
        result = await executor.execute(inputs)
        
        assert result is not None
        assert result["result_count"] == 0
        assert result["results"] == {}
    
    @pytest.mark.asyncio
    async def test_execute_with_only_internal_keys(self, executor):
        """Test that pre-hook markers are filtered out, but other keys are included
        
        Note: Pre-hook markers (_pre_hook_executed, _pre_hook_timestamp) are filtered
        as they are internal implementation details. Other keys are included.
        """
        inputs = {
            "_pre_hook_executed": True,
            "_pre_hook_timestamp": "test-timestamp",
            "_hook_timestamp": "2024-01-01T00:00:00Z",
            "_project_id": "project-123"
        }
        
        result = await executor.execute(inputs)
        
        assert result is not None
        # Pre-hook markers are filtered, but other keys are included
        assert result["result_count"] == 2
        assert len(result["results"]) == 2
        # Pre-hook markers are filtered out
        assert "_pre_hook_executed" not in result["results"]
        assert "_pre_hook_timestamp" not in result["results"]
        # Other keys are included
        assert "_hook_timestamp" in result["results"]
        assert "_project_id" in result["results"]
    
    @pytest.mark.asyncio
    async def test_execute_with_mixed_types(self, executor):
        """Test aggregating results with different types"""
        inputs = {
            "task-1": {"status": "completed", "value": 100},
            "task-2": "simple string result",
            "task-3": 42,  # numeric result
            "task-4": ["list", "result"],
            "_pre_hook_executed": True  # Pre-hook marker (filtered out)
        }
        
        result = await executor.execute(inputs)
        
        assert result is not None
        assert result["result_count"] == 4  # Only 4 task results (pre-hook marker filtered)
        assert "task-1" in result["results"]
        assert "task-2" in result["results"]
        assert "task-3" in result["results"]
        assert "task-4" in result["results"]
        # Pre-hook marker is filtered out
        assert "_pre_hook_executed" not in result["results"]
        
        # Verify values are preserved
        assert result["results"]["task-1"]["value"] == 100
        assert result["results"]["task-2"] == "simple string result"
        assert result["results"]["task-3"] == 42
        assert result["results"]["task-4"] == ["list", "result"]
    
    @pytest.mark.asyncio
    async def test_execute_with_nested_results(self, executor):
        """Test aggregating nested result structures"""
        inputs = {
            "task-1": {
                "result": {
                    "nested": {
                        "data": "value"
                    }
                }
            },
            "task-2": {
                "metadata": {
                    "timestamp": "2024-01-01",
                    "version": "1.0"
                }
            }
        }
        
        result = await executor.execute(inputs)
        
        assert result is not None
        assert result["result_count"] == 2
        assert "task-1" in result["results"]
        assert "task-2" in result["results"]
        
        # Verify nested structures are preserved
        assert result["results"]["task-1"]["result"]["nested"]["data"] == "value"
        assert result["results"]["task-2"]["metadata"]["version"] == "1.0"
    
    def test_get_input_schema(self, executor):
        """Test input schema definition"""
        schema = executor.get_input_schema()
        
        assert schema is not None
        assert "type" in schema
        assert schema["type"] == "object"
        assert "description" in schema
    
    def test_executor_properties(self, executor):
        """Test executor metadata properties"""
        assert executor.id == "aggregate_results_executor"
        assert executor.name == "Aggregate Results Executor"
        assert executor.type == "core"
        assert executor.cancelable is False
        assert "aggregation" in executor.tags
        assert "core" in executor.tags
    
    @pytest.mark.asyncio
    async def test_execute_with_real_system_info_executor(self, executor):
        """
        Integration test: Use real system_info_executor to get actual system data,
        then aggregate the results using aggregate_results_executor.
        
        This test demonstrates the real-world usage pattern:
        1. Execute system_info_executor for different resources (CPU, memory, disk)
        2. Simulate TaskManager merging results into inputs (as it would in production)
        3. Use aggregate_results_executor to aggregate all results
        """
        # Import system_info_executor
        try:
            from apflow.extensions.stdio import SystemInfoExecutor
        except ImportError:
            pytest.skip("SystemInfoExecutor not available")
        
        # Step 1: Execute system_info_executor for different resources
        cpu_executor = SystemInfoExecutor()
        memory_executor = SystemInfoExecutor()
        disk_executor = SystemInfoExecutor()
        
        # Get real system information
        cpu_result = await cpu_executor.execute({"resource": "cpu"})
        memory_result = await memory_executor.execute({"resource": "memory"})
        disk_result = await disk_executor.execute({"resource": "disk"})
        
        # Verify we got real results
        assert cpu_result is not None
        assert memory_result is not None
        assert disk_result is not None
        
        # Step 2: Simulate TaskManager's _resolve_task_dependencies() behavior
        # In production, TaskManager would merge these results into inputs like this:
        inputs = {
            "cpu-info": cpu_result,      # Dependency result from cpu-info task
            "memory-info": memory_result,  # Dependency result from memory-info task
            "disk-info": disk_result,     # Dependency result from disk-info task
            # Pre-hook markers are filtered out (internal implementation details)
            "_pre_hook_executed": True,
            "_pre_hook_timestamp": "2024-01-01T00:00:00Z"
        }
        
        # Step 3: Use aggregate_results_executor to aggregate the real results
        aggregated_result = await executor.execute(inputs)
        
        # Verify aggregated result structure
        assert aggregated_result is not None
        assert "summary" in aggregated_result
        assert "timestamp" in aggregated_result
        assert "results" in aggregated_result
        assert "result_count" in aggregated_result
        
        # Verify we aggregated only dependency results (pre-hook markers filtered)
        assert aggregated_result["result_count"] == 3
        assert "cpu-info" in aggregated_result["results"]
        assert "memory-info" in aggregated_result["results"]
        assert "disk-info" in aggregated_result["results"]
        # Pre-hook markers are filtered out (internal implementation details)
        assert "_pre_hook_executed" not in aggregated_result["results"]
        assert "_pre_hook_timestamp" not in aggregated_result["results"]
        
        # Verify real system data is preserved in aggregated results
        cpu_aggregated = aggregated_result["results"]["cpu-info"]
        memory_aggregated = aggregated_result["results"]["memory-info"]
        disk_aggregated = aggregated_result["results"]["disk-info"]
        
        # CPU result should have system info
        assert isinstance(cpu_aggregated, dict)
        assert "system" in cpu_aggregated or "cores" in cpu_aggregated or "brand" in cpu_aggregated
        
        # Memory result should have memory info
        assert isinstance(memory_aggregated, dict)
        assert "total_gb" in memory_aggregated or "system" in memory_aggregated
        
        # Disk result should have disk info
        assert isinstance(disk_aggregated, dict)
        assert "total" in disk_aggregated or "available" in disk_aggregated or "system" in disk_aggregated
        
        # Verify the aggregated results match the original results
        assert cpu_aggregated == cpu_result
        assert memory_aggregated == memory_result
        assert disk_aggregated == disk_result


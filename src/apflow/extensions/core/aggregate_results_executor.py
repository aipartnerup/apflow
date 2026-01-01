"""
Aggregate Results Executor - Aggregates dependency task results

This executor aggregates results from dependency tasks into a single result.
It's a built-in executor that provides a common aggregation pattern.

Users can create custom aggregator executors for more complex aggregation logic.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from apflow.core.base import BaseTask
from apflow.core.extensions.decorators import executor_register
from apflow.core.utils.logger import get_logger

logger = get_logger(__name__)


@executor_register()
class AggregateResultsExecutor(BaseTask):
    """
    Executor for aggregating dependency task results
    
       **How aggregation works:**
       
       1. **Dependency Resolution (by TaskManager):**
          Before this executor runs, TaskManager's _resolve_task_dependencies() merges
          dependency task results into the task's inputs dictionary:
          
          - For each dependency in task.dependencies, it adds: inputs[dep_id] = dep_task.result
          - Example: If task depends on ["cpu-info", "memory-info"], and those tasks completed
            with results {"cores": 8} and {"total_gb": 64.0}, then inputs becomes:
            {
                "cpu-info": {"cores": 8, "system": "Darwin"},
                "memory-info": {"total_gb": 64.0, "system": "Darwin"}
            }
       
       2. **Result Extraction (by this executor):**
          This executor receives the inputs dictionary and:
          - Treats all keys in inputs as dependency task IDs
          - Extracts their values as dependency results
          - No filtering is applied - all keys are included
          - If you need to filter certain keys, implement a custom executor
    
    3. **Aggregation (by this executor):**
       Builds a structured result containing all dependency results:
       {
           "summary": "Task Results Aggregation",
           "timestamp": "2024-01-01T00:00:00Z",
           "results": {
               "cpu-info": {"cores": 8, "system": "Darwin"},
               "memory-info": {"total_gb": 64.0, "system": "Darwin"}
           },
           "result_count": 2
       }
    
    **Example usage:**
    ```python
    {
        "schemas": {
            "input_schema": {}  # Optional
        },
        "params": {
            "executor_id": "aggregate_results_executor"
        },
        "dependencies": [
            {"id": "cpu-info", "required": True},
            {"id": "memory-info", "required": True}
        ],
        "inputs": {}  # Will be populated by TaskManager with dependency results
    }
    ```
    
    **Result structure:**
    The executor returns:
    ```python
    {
        "summary": "Task Results Aggregation",
        "timestamp": "2024-01-01T00:00:00Z",
        "results": {
            "cpu-info": {...},      # Result from cpu-info task
            "memory-info": {...}     # Result from memory-info task
        },
        "result_count": 2
    }
    ```
    """
    
    id = "aggregate_results_executor"
    name = "Aggregate Results Executor"
    description = "Aggregates dependency task results into a single result"
    tags = ["aggregation", "core", "built-in"]
    examples = [
        "Aggregate system resource monitoring results",
        "Merge multiple task outputs",
        "Combine dependency results"
    ]
    
    # Cancellation support: No-op (aggregation is instant)
    cancelable: bool = False
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "core"
    
    def __init__(
        self,
        name: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ):
        """
        Initialize AggregateResultsExecutor
        
        Args:
            name: Optional executor name
            inputs: Input parameters (will contain dependency results)
            **kwargs: Additional configuration
        """
        super().__init__(inputs=inputs, **kwargs)
        if name:
            self.name = name
    
    async def execute(self, inputs: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Aggregate dependency results from inputs
        
        **How it works:**
        1. TaskManager's _resolve_task_dependencies() merges dependency task results into inputs
           - For each dependency in task.dependencies, it adds: inputs[dep_id] = dep_task.result
           - Example: If task depends on ["cpu-info", "memory-info"], inputs will contain:
             {
                 "cpu-info": {"cores": 8, "system": "Darwin"},
                 "memory-info": {"total_gb": 64.0}
             }
        
        2. This executor aggregates all keys in inputs as dependency results
           - All keys in inputs are treated as dependency task IDs
           - Their values are the results from those dependency tasks
           - No filtering is applied - if you need filtering, implement a custom executor
        
        3. Builds aggregated result structure:
           {
               "summary": "Task Results Aggregation",
               "timestamp": "ISO timestamp",
               "results": {
                   "cpu-info": {...},      # Result from cpu-info task
                   "memory-info": {...}     # Result from memory-info task
               },
               "result_count": 2
           }
        
        Args:
            inputs: Input parameters containing dependency results
                   Format: {
                       "dependency-task-id-1": <result from task 1>,
                       "dependency-task-id-2": <result from task 2>,
                       ...
                   }
                   All keys in inputs will be included in aggregated results.
                   If you need to filter certain keys, implement a custom executor.
        
        Returns:
            Aggregated result dictionary with structure:
            {
                "summary": "Task Results Aggregation",
                "timestamp": "ISO timestamp",
                "results": {
                    "task-id-1": {...},  # Result from dependency task 1
                    "task-id-2": {...}   # Result from dependency task 2
                },
                "result_count": 2
            }
        """
        logger.info(f"Aggregating dependency results for {self.name}")
        
        # Validate inputs if input_schema is defined (from BaseTask)
        try:
            self.check_input_schema(inputs)
            logger.debug(f"Input validation passed for {self.name}")
        except ValueError as e:
            error_msg = f"Input validation failed for {self.name}: {str(e)}"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "validation_error": str(e)
            }
        
        # ============================================================
        # Step 1: Extract dependency results from inputs
        # ============================================================
        # TaskManager's _resolve_task_dependencies() has already merged dependency results
        # into inputs with keys matching dependency task IDs.
        # 
        # Example inputs structure:
        # {
        #     "cpu-info": {"cores": 8, "system": "Darwin"},      # Dependency result (task ID = "cpu-info")
        #     "memory-info": {"total_gb": 64.0},                  # Dependency result (task ID = "memory-info")
        #     "_pre_hook_executed": True,                          # Pre-hook marker (should be filtered)
        #     "_pre_hook_timestamp": "..."                        # Pre-hook marker (should be filtered)
        # }
        #
        # Filter out pre-hook markers and other internal fields that are not dependency results.
        # Only keys that match dependency task IDs should be included.
        pre_hook_markers = {"_pre_hook_executed", "_pre_hook_timestamp"}
        dependency_results = {
            key: value
            for key, value in inputs.items()
            if key not in pre_hook_markers
        }
        logger.debug(f"Extracted {len(dependency_results)} dependency results: {list(dependency_results.keys())}")
        
        # ============================================================
        # Step 3: Build aggregated result structure
        # ============================================================
        # Organize all dependency results into a structured format
        aggregated = {
            "summary": "Task Results Aggregation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": dependency_results,  # All dependency results keyed by task ID
            "result_count": len(dependency_results)
        }
        
        logger.info(
            f"Aggregated {aggregated['result_count']} dependency results: "
            f"{list(dependency_results.keys())}"
        )
        
        return aggregated
    
    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo aggregated results"""
        from datetime import datetime, timezone
        
        # Create demo dependency results based on inputs
        # Filter out internal markers
        pre_hook_markers = {"_pre_hook_executed", "_pre_hook_timestamp", "use_demo"}
        dependency_results = {
            key: value
            for key, value in inputs.items()
            if key not in pre_hook_markers
        }
        
        # If no dependency results, create some demo ones
        if not dependency_results:
            dependency_results = {
                "demo-task-1": {"status": "completed", "result": "Demo result 1"},
                "demo-task-2": {"status": "completed", "result": "Demo result 2"}
            }
        
        return {
            "summary": "Task Results Aggregation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": dependency_results,
            "result_count": len(dependency_results),
            "_demo_sleep": 0.05  # Simulate quick data aggregation (local operation)
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Get input parameter schema
        
        Note: Dependency results are automatically merged into inputs by TaskManager,
        so this schema is mainly for documentation.
        """
        return {
            "type": "object",
            "properties": {
                "_dependencies": {
                    "type": "array",
                    "description": "List of dependency task IDs (optional, auto-populated by TaskManager)"
                }
            },
            "description": "Inputs will contain dependency results merged by TaskManager"
        }


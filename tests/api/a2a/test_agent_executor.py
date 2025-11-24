"""
Test AgentExecutor functionality

This module contains both unit tests (with mocks) and integration tests (with real database).
Integration tests are marked with @pytest.mark.integration and can be run separately:
    pytest tests/api/a2a/test_agent_executor.py -m integration  # Run only integration tests
    pytest tests/api/a2a/test_agent_executor.py -m "not integration"  # Run only unit tests
"""
import pytest
import uuid
import json
from unittest.mock import Mock, AsyncMock, patch
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, DataPart

from aipartnerupflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.utils.logger import get_logger

# Import executors to trigger @executor_register decorator
# This ensures the executors are registered before tests run
try:
    from aipartnerupflow.extensions.stdio import SystemInfoExecutor, CommandExecutor  # noqa: F401
except ImportError:
    # If stdio extension is not available, tests will fail appropriately
    SystemInfoExecutor = None
    CommandExecutor = None

logger = get_logger(__name__)


class TestAgentExecutor:
    """Test cases for AIPartnerUpFlowAgentExecutor"""
    
    @pytest.fixture
    def executor(self):
        """Create AIPartnerUpFlowAgentExecutor instance"""
        return AIPartnerUpFlowAgentExecutor()
    
    @pytest.fixture
    def mock_event_queue(self):
        """Create mock event queue"""
        event_queue = AsyncMock(spec=EventQueue)
        event_queue.enqueue_event = AsyncMock()
        return event_queue
    
    def _create_request_context(self, tasks: list, metadata: dict = None) -> RequestContext:
        """Helper to create RequestContext with tasks array"""
        if metadata is None:
            metadata = {}
        
        # Create message with DataPart containing tasks
        message = Mock(spec=Message)
        message.parts = []
        
        # Option 1: Wrapped format (tasks array in first part)
        if len(tasks) == 1:
            data_part = Mock()
            data_part.root = DataPart(data={"tasks": tasks})
            message.parts.append(data_part)
        else:
            # Option 2: Direct format (each part is a task)
            for task in tasks:
                data_part = Mock()
                data_part.root = DataPart(data=task)
                message.parts.append(data_part)
        
        context = Mock(spec=RequestContext)
        context.task_id = str(uuid.uuid4())
        context.context_id = str(uuid.uuid4())
        context.metadata = metadata
        context.message = message
        context.configuration = {}
        
        return context
    
    @pytest.mark.asyncio
    async def test_extract_tasks_wrapped_format(self, executor):
        """Test extracting tasks from wrapped format"""
        tasks = [
            {
                "id": "task-1",
                "user_id": "test-user",
                "name": "Task 1",
                "status": "pending"
            },
            {
                "id": "task-2",
                "user_id": "test-user",
                "name": "Task 2",
                "status": "pending"
            }
        ]
        
        context = self._create_request_context(tasks)
        
        extracted = executor._extract_tasks_from_context(context)
        assert len(extracted) == 2
        assert extracted[0]["id"] == "task-1"
        assert extracted[1]["id"] == "task-2"
    
    @pytest.mark.asyncio
    async def test_extract_tasks_direct_format(self, executor):
        """Test extracting tasks from direct format"""
        tasks = [
            {
                "id": "task-1",
                "user_id": "test-user",
                "name": "Task 1"
            },
            {
                "id": "task-2",
                "user_id": "test-user",
                "name": "Task 2"
            }
        ]
        
        # Create context with direct format (multiple parts)
        message = Mock(spec=Message)
        message.parts = []
        for task in tasks:
            data_part = Mock()
            data_part.root = DataPart(data=task)
            message.parts.append(data_part)
        
        context = Mock(spec=RequestContext)
        context.message = message
        
        extracted = executor._extract_tasks_from_context(context)
        assert len(extracted) == 2
    
    @pytest.mark.asyncio
    async def test_extract_tasks_empty(self, executor):
        """Test extracting tasks with empty context"""
        message = Mock(spec=Message)
        message.parts = []
        
        context = Mock(spec=RequestContext)
        context.message = message
        
        with pytest.raises(ValueError, match="No tasks found"):
            executor._extract_tasks_from_context(context)
    
    @pytest.mark.asyncio
    async def test_build_task_tree_from_tasks(self, executor):
        """Test building task tree from tasks array"""
        tasks = [
            {
                "id": "root-task",
                "parent_id": None,
                "user_id": "test-user",
                "name": "Root Task",
                "dependencies": []
            },
            {
                "id": "child-1",
                "parent_id": "root-task",
                "user_id": "test-user",
                "name": "Child 1",
                "dependencies": []
            },
            {
                "id": "child-2",
                "parent_id": "root-task",
                "user_id": "test-user",
                "name": "Child 2",
                "dependencies": [{"id": "child-1", "required": True}]
            }
        ]
        
        # Use task_executor's _build_task_tree_from_tasks method
        task_tree = executor.task_executor._build_task_tree_from_tasks(tasks)
        
        assert task_tree is not None
        assert task_tree.task.id == "root-task"
        assert len(task_tree.children) == 2
        assert task_tree.children[0].task.id == "child-1"
        assert task_tree.children[1].task.id == "child-2"
    
    @pytest.mark.asyncio
    async def test_should_use_streaming_mode(self, executor):
        """Test streaming mode detection"""
        # Test with stream metadata
        metadata = {"stream": True}
        context = Mock()
        context.metadata = metadata
        
        assert executor._should_use_streaming_mode(context) is True
        
        # Test without stream metadata
        metadata = {}
        context.metadata = metadata
        
        assert executor._should_use_streaming_mode(context) is False
    
    @pytest.mark.asyncio
    async def test_should_use_callback(self, executor):
        """Test callback detection"""
        # Test with push notification config (needs url attribute)
        context = Mock()
        push_config = Mock()
        push_config.url = "https://example.com/callback"
        context.configuration = Mock()
        context.configuration.push_notification_config = push_config
        
        assert executor._should_use_callback(context) is True
        
        # Test with metadata.use_callback (backward compatibility)
        context = Mock()
        context.configuration = None
        context.metadata = {"use_callback": True}
        
        assert executor._should_use_callback(context) is True
        
        # Test without push notification config
        context = Mock()
        context.configuration = None
        context.metadata = {}
        
        assert executor._should_use_callback(context) is False
    
    @pytest.mark.asyncio
    async def test_execute_simple_mode(self, executor, mock_event_queue):
        """Test simple mode execution"""
        tasks = [
            {
                "id": "task-1",
                "user_id": "test-user",
                "name": "Test Task",
                "status": "pending",
                "schemas": {
                    "method": "crewai_executor"
                }
            }
        ]
        
        context = self._create_request_context(tasks)
        
        # Mock TaskExecutor and get_default_session
        # Use patch to ensure mock is properly cleaned up after test
        # This is important because TaskExecutor is a singleton, and mocks can leak to other tests
        with patch('aipartnerupflow.api.a2a.agent_executor.get_default_session') as mock_get_session, \
             patch.object(executor.task_executor, 'execute_tasks') as mock_execute_tasks:
            mock_get_session.return_value = Mock()
            
            # Mock TaskExecutor.execute_tasks (which handles building tree, saving, and execution)
            mock_execution_result = {
                "status": "completed",
                "progress": 1.0,
                "root_task_id": "task-1"
            }
            mock_execute_tasks.return_value = mock_execution_result
            
            result = await executor._execute_simple_mode(context, mock_event_queue)
            
            # Should have executed
            assert mock_execute_tasks.called
            assert result is not None
            # Result is now a Task object, not a dict
            from a2a.types import Task
            assert isinstance(result, Task)
            assert result.id is not None
            # Extract data from artifacts if needed
            if result.artifacts and len(result.artifacts) > 0:
                artifact_data = result.artifacts[0].parts[0].root.data if result.artifacts[0].parts else None
                if artifact_data:
                    assert artifact_data.get("status") == "completed"
                    assert artifact_data.get("root_task_id") == "task-1"
    
    # ============================================================================
    # Integration Tests (Real Database)
    # ============================================================================
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_execute_system_resource_monitoring_with_executor(self, use_test_db_session, sync_db_session, mock_event_queue):
        """
        Integration test: Real task tree execution using aggregate_results_executor
        
        This test demonstrates the new executor-based approach for aggregating results.
        Uses params.executor_id="aggregate_results_executor" instead of deprecated method.
        
        Task structure:
        - Parent task: Aggregate system resources using executor (depends on cpu, memory, disk)
        - Child task 1: Get CPU info
        - Child task 2: Get Memory info
        - Child task 3: Get Disk info
        
        Parent task uses aggregate_results_executor to merge all child results.
        """
        # Clear any existing hooks from previous tests
        from aipartnerupflow import clear_config
        clear_config()
        
        # Track hook calls for verification
        pre_hook_calls = []
        post_hook_calls = []
        
        # Register pre-hook using decorator
        from aipartnerupflow import register_pre_hook
        
        @register_pre_hook
        async def test_pre_hook(task):
            """Pre-hook that modifies task inputs and tracks calls"""
            pre_hook_calls.append({
                "task_id": task.id,
                "task_name": task.name,
                "original_input": dict(task.inputs) if task.inputs else {},
            })
            if task.inputs is None:
                task.inputs = {}
            task.inputs["_pre_hook_executed"] = True
            task.inputs["_pre_hook_timestamp"] = "test-timestamp"
        
        # Register post-hook using decorator
        from aipartnerupflow import register_post_hook
        
        @register_post_hook
        async def test_post_hook(task, inputs, result):
            """Post-hook that tracks task completion and results"""
            post_hook_calls.append({
                "task_id": task.id,
                "task_name": task.name,
                "task_status": task.status,
                "inputs": inputs,
                "result": result,
            })
        
        # Create executor AFTER registering hooks
        from aipartnerupflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
        from aipartnerupflow.core.execution.task_executor import TaskExecutor
        executor = AIPartnerUpFlowAgentExecutor()
        TaskExecutor().refresh_config()
        
        user_id = "test-user-executor"
        
        # Create task tree structure using new executor approach
        tasks = [
            {
                "id": "system-resources-root-executor",
                "user_id": user_id,
                "name": "System Resources Monitor (Executor)",
                "status": "pending",
                "priority": 3,
                "has_children": True,
                "dependencies": [
                    {"id": "cpu-info-executor", "required": True},
                    {"id": "memory-info-executor", "required": True},
                    {"id": "disk-info-executor", "required": True}
                ],
                "schemas": {
                    "input_schema": {}  # Optional: can define input schema
                },
                "params": {
                    "executor_id": "aggregate_results_executor"  # New executor-based approach
                },
                "inputs": {}
            },
            {
                "id": "cpu-info-executor",
                "parent_id": "system-resources-root-executor",
                "user_id": user_id,
                "name": "Get CPU Information",
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "dependencies": [],
                "schemas": {
                    "method": "system_info_executor"  # Executor id
                },
                "inputs": {
                    "resource": "cpu"
                }
            },
            {
                "id": "memory-info-executor",
                "parent_id": "system-resources-root-executor",
                "user_id": user_id,
                "name": "Get Memory Information",
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "dependencies": [],
                "schemas": {
                    "method": "system_info_executor"  # Executor id
                },
                "inputs": {
                    "resource": "memory"
                }
            },
            {
                "id": "disk-info-executor",
                "parent_id": "system-resources-root-executor",
                "user_id": user_id,
                "name": "Get Disk Information",
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "dependencies": [],
                "schemas": {
                    "method": "system_info_executor"  # Executor id
                },
                "inputs": {
                    "resource": "disk"
                }
            }
        ]
        
        context = self._create_request_context(tasks)
        
        # Execute in simple mode with real database
        with patch('aipartnerupflow.api.a2a.agent_executor.get_default_session') as mock_get_session_agent, \
             patch('aipartnerupflow.core.execution.task_executor.get_default_session') as mock_get_session_executor:
            mock_get_session_agent.return_value = sync_db_session
            mock_get_session_executor.return_value = sync_db_session
            
            # Execute using executor
            result = await executor.execute(context, mock_event_queue)
            # Result is now a Task object, convert to dict for logging
            from a2a.types import Task
            if isinstance(result, Task):
                result_dict = result.model_dump(mode='json', exclude_none=True)
                logger.info(f"==result (executor)==\n {json.dumps(result_dict, indent=4)}")
            else:
                logger.info(f"==result (executor)==\n {json.dumps(result, indent=4)}")
            
            # Verify result structure - result is now a Task object
            assert result is not None
            assert isinstance(result, Task)
            assert result.id is not None
            # Extract execution status from artifacts
            if result.artifacts and len(result.artifacts) > 0:
                artifact_data = result.artifacts[0].parts[0].root.data if result.artifacts[0].parts else None
                if artifact_data:
                    assert artifact_data.get("status") == "completed"
                    assert "root_task_id" in artifact_data
            
            # Verify all tasks were created and executed
            repo = TaskRepository(sync_db_session)
            
            # Check root task
            root_task = await repo.get_task_by_id("system-resources-root-executor")
            assert root_task is not None
            assert root_task.status == "completed"
            assert root_task.result is not None
            
            # Verify aggregated result structure (from executor)
            root_result = root_task.result
            assert isinstance(root_result, dict)
            assert "summary" in root_result
            assert "results" in root_result
            assert "result_count" in root_result
            assert root_result["result_count"] == 3  # cpu, memory, disk
            
            # Verify each resource is in the aggregated result
            results = root_result["results"]
            assert "cpu-info-executor" in results
            assert "memory-info-executor" in results
            assert "disk-info-executor" in results
            
            # Check child tasks
            cpu_task = await repo.get_task_by_id("cpu-info-executor")
            assert cpu_task is not None
            assert cpu_task.status == "completed"
            
            memory_task = await repo.get_task_by_id("memory-info-executor")
            assert memory_task is not None
            assert memory_task.status == "completed"
            
            disk_task = await repo.get_task_by_id("disk-info-executor")
            assert disk_task is not None
            assert disk_task.status == "completed"
            
            # Verify hooks were called
            assert len(pre_hook_calls) == 4  # root + 3 children
            assert len(post_hook_calls) >= 4
            
            logger.info(f"✅ Executor-based aggregation test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_execute_system_resource_monitoring(self, use_test_db_session, sync_db_session, mock_event_queue):
        """
        Integration test: Real task tree execution for system resource monitoring
        
        This test uses real TaskManager and database to execute a task tree
        that monitors system resources (CPU, memory, disk) and merges results.
        
        Also tests decorator-based hooks (@register_pre_hook, @register_post_hook)
        in a real execution environment to verify they work correctly in practice.
        
        Task structure:
        - Parent task: Aggregate system resources using aggregate_results_executor (depends on cpu, memory, disk)
        - Child task 1: Get CPU info
        - Child task 2: Get Memory info
        - Child task 3: Get Disk info
        
        Parent task uses aggregate_results_executor to merge all child results.
        """
        # Clear any existing hooks from previous tests
        from aipartnerupflow import clear_config
        clear_config()
        
        # Track hook calls for verification
        pre_hook_calls = []
        post_hook_calls = []
        
        # Register pre-hook using decorator (real usage pattern)
        from aipartnerupflow import register_pre_hook
        
        @register_pre_hook
        async def test_pre_hook(task):
            """Pre-hook that modifies task inputs and tracks calls"""
            pre_hook_calls.append({
                "task_id": task.id,
                "task_name": task.name,
                "original_input": dict(task.inputs) if task.inputs else {},
            })
            # Modify inputs to demonstrate hook can transform data
            if task.inputs is None:
                task.inputs = {}
            task.inputs["_pre_hook_executed"] = True
            task.inputs["_pre_hook_timestamp"] = "test-timestamp"
        
        # Register post-hook using decorator (real usage pattern)
        from aipartnerupflow import register_post_hook
        
        @register_post_hook
        async def test_post_hook(task, inputs, result):
            """Post-hook that tracks task completion and results"""
            post_hook_calls.append({
                "task_id": task.id,
                "task_name": task.name,
                "task_status": task.status,
                "inputs": inputs,
                "result": result,
            })
        
        # Create executor AFTER registering hooks
        # In production, hooks are registered at application startup before executor creation
        # For testing, we register hooks first, then create executor to match production pattern
        # Since TaskExecutor is singleton, we need to refresh its config to pick up newly registered hooks
        from aipartnerupflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
        from aipartnerupflow.core.execution.task_executor import TaskExecutor
        executor = AIPartnerUpFlowAgentExecutor()
        # Refresh TaskExecutor singleton's hooks to pick up newly registered hooks
        # This is only needed for testing; in production, hooks are registered before executor creation
        TaskExecutor().refresh_config()
        
        user_id = "test-user-real"
        
        # Create task tree structure
        tasks = [
            {
                "id": "system-resources-root",
                "user_id": user_id,
                "name": "System Resources Monitor",
                "status": "pending",
                "priority": 3,
                "has_children": True,
                "dependencies": [
                    {"id": "cpu-info", "required": True},
                    {"id": "memory-info", "required": True},
                    {"id": "disk-info", "required": True}
                ],
                "schemas": {
                    "input_schema": {}  # Optional: can define input schema
                },
                "params": {
                    "executor_id": "aggregate_results_executor"  # Use executor-based approach
                },
                "inputs": {}
            },
            {
                "id": "cpu-info",
                "parent_id": "system-resources-root",
                "user_id": user_id,
                "name": "Get CPU Information",
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "dependencies": [],
                "schemas": {
                    "method": "system_info_executor"  # Executor id
                },
                "inputs": {
                    "resource": "cpu"
                }
            },
            {
                "id": "memory-info",
                "parent_id": "system-resources-root",
                "user_id": user_id,
                "name": "Get Memory Information",
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "dependencies": [],
                "schemas": {
                    "method": "system_info_executor"  # Executor id
                },
                "inputs": {
                    "resource": "memory"
                }
            },
            {
                "id": "disk-info",
                "parent_id": "system-resources-root",
                "user_id": user_id,
                "name": "Get Disk Information",
                "status": "pending",
                "priority": 1,
                "has_children": False,
                "dependencies": [],
                "schemas": {
                    "method": "system_info_executor"  # Executor id
                },
                "inputs": {
                    "resource": "disk"
                }
            }
        ]
        
        context = self._create_request_context(tasks)
        
        # Execute in simple mode with real database
        # Mock get_default_session in both agent_executor and task_executor modules
        with patch('aipartnerupflow.api.a2a.agent_executor.get_default_session') as mock_get_session_agent, \
             patch('aipartnerupflow.core.execution.task_executor.get_default_session') as mock_get_session_executor:
            mock_get_session_agent.return_value = sync_db_session
            mock_get_session_executor.return_value = sync_db_session
            
            # Execute using executor with hooks
            result = await executor.execute(context, mock_event_queue)
            # Result is now a Task object, convert to dict for logging
            from a2a.types import Task
            if isinstance(result, Task):
                result_dict = result.model_dump(mode='json', exclude_none=True)
                logger.info(f"==result==\n {json.dumps(result_dict, indent=4)}")
            else:
                logger.info(f"==result==\n {json.dumps(result, indent=4)}")
            # Verify result structure - result is now a Task object
            assert result is not None
            assert isinstance(result, Task)
            assert result.id is not None
            # Extract execution status from artifacts
            if result.artifacts and len(result.artifacts) > 0:
                artifact_data = result.artifacts[0].parts[0].root.data if result.artifacts[0].parts else None
                if artifact_data:
                    assert artifact_data.get("status") == "completed"
                    assert "root_task_id" in artifact_data

            
            # Verify all tasks were created and executed
            repo = TaskRepository(sync_db_session)
            
            # Check root task
            root_task = await repo.get_task_by_id("system-resources-root")
            assert root_task is not None
            assert root_task.status == "completed"
            assert root_task.result is not None
            
            # Check child tasks
            cpu_task = await repo.get_task_by_id("cpu-info")
            assert cpu_task is not None
            assert cpu_task.status == "completed"
            assert cpu_task.result is not None
            # Verify CPU info is in result
            cpu_result = cpu_task.result
            assert isinstance(cpu_result, dict)
            assert "system" in cpu_result or "cores" in cpu_result
            
            memory_task = await repo.get_task_by_id("memory-info")
            assert memory_task is not None
            assert memory_task.status == "completed"
            assert memory_task.result is not None
            
            disk_task = await repo.get_task_by_id("disk-info")
            assert disk_task is not None
            assert disk_task.status == "completed"
            assert disk_task.result is not None
            
            # Verify parent task merged results (using aggregate_results_executor)
            root_result = root_task.result
            assert isinstance(root_result, dict)
            
            # Check aggregated result structure (from executor)
            assert "summary" in root_result
            assert "results" in root_result
            assert "result_count" in root_result
            assert root_result["result_count"] == 3  # cpu, memory, disk
            
            # Verify each resource is in the aggregated result
            results = root_result["results"]
            assert "cpu-info" in results
            assert "memory-info" in results
            assert "disk-info" in results
            
            # Verify event queue was called
            assert mock_event_queue.enqueue_event.called
            
            # ========================================================================
            # Verify decorator-based hooks were called correctly
            # ========================================================================
            
            # Verify pre-hooks were called for all tasks (root + 3 children)
            assert len(pre_hook_calls) == 4, f"Expected 4 pre-hook calls, got {len(pre_hook_calls)}"
            
            # Verify pre-hook was called for each task
            task_ids_called = [call["task_id"] for call in pre_hook_calls]
            assert "system-resources-root" in task_ids_called
            assert "cpu-info" in task_ids_called
            assert "memory-info" in task_ids_called
            assert "disk-info" in task_ids_called
            
            # Verify pre-hook modified inputs (check in database)
            cpu_task_after = await repo.get_task_by_id("cpu-info")
            # Note: inputs modification happens in memory, but we can verify
            # the hook was called and had access to the task
            
            # Verify post-hooks were called for all completed tasks
            assert len(post_hook_calls) >= 4, f"Expected at least 4 post-hook calls, got {len(post_hook_calls)}"
            
            # Verify post-hook received correct data
            post_hook_task_ids = [call["task_id"] for call in post_hook_calls]
            assert "system-resources-root" in post_hook_task_ids
            assert "cpu-info" in post_hook_task_ids
            assert "memory-info" in post_hook_task_ids
            assert "disk-info" in post_hook_task_ids
            
            # Verify post-hook received task status and results
            for call in post_hook_calls:
                assert call["task_status"] == "completed", f"Task {call['task_id']} should be completed"
                assert call["result"] is not None, f"Task {call['task_id']} should have result"
            
            # Verify post-hook received correct inputs (with pre-hook modifications)
            cpu_post_hook = next(call for call in post_hook_calls if call["task_id"] == "cpu-info")
            assert cpu_post_hook["inputs"] is not None
            # The inputs should have been modified by pre-hook (if it was accessible)
            
            logger.info(f"==Pre-hook calls: {len(pre_hook_calls)}==\n{json.dumps(pre_hook_calls, indent=2)}")
            logger.info(f"==Post-hook calls: {len(post_hook_calls)}==\n{json.dumps(post_hook_calls, indent=2)}")
            
            # Query and display complete task tree data
            task_tree = await repo.build_task_tree(root_task)
            
            # Convert TaskTreeNode to dictionary format for JSON display
            def tree_node_to_dict(node):
                """Convert TaskTreeNode to dictionary"""
                task_dict = node.task.to_dict()
                if node.children:
                    task_dict["children"] = [tree_node_to_dict(child) for child in node.children]
                return task_dict
            
            task_tree_dict = tree_node_to_dict(task_tree)
            
            # Display task tree as JSON
            logger.info("==Task Tree Data (JSON)==\n" + json.dumps(task_tree_dict, indent=2, ensure_ascii=False))
            
            # Verify task tree structure
            assert "children" in task_tree_dict
            assert len(task_tree_dict["children"]) == 3  # cpu-info, memory-info, disk-info
            
            # Verify each child task has result
            child_ids = [child["id"] for child in task_tree_dict["children"]]
            assert "cpu-info" in child_ids
            assert "memory-info" in child_ids
            assert "disk-info" in child_ids
            
            for child in task_tree_dict["children"]:
                assert child["status"] == "completed"
                assert child["result"] is not None
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_execute_with_custom_task_model_and_hooks(self, use_test_db_session, sync_db_session, mock_event_queue):
        """
        Integration test: Real task execution with custom TaskModel and decorator-based hooks
        
        This test demonstrates the complete decorator workflow:
        1. Custom TaskModel with additional fields (project_id)
        2. set_task_model_class() to configure custom model
        3. @register_pre_hook to modify task data before execution
        4. @register_post_hook to process results after execution
        
        This verifies that all decorator features work together in a real execution environment.
        """
        # Clear any existing configuration
        from aipartnerupflow import clear_config, set_task_model_class
        clear_config()
        
        # ========================================================================
        # Step 1: Define and set custom TaskModel with additional field
        # ========================================================================
        from sqlalchemy import Column, String, text
        from aipartnerupflow.core.storage.sqlalchemy.models import TASK_TABLE_NAME, TaskModel
        
        # Add project_id column to existing table (if not exists)
        # In production, this would be done via Alembic migrations
        try:
            sync_db_session.execute(text(f"ALTER TABLE {TASK_TABLE_NAME} ADD COLUMN project_id VARCHAR(100)"))
            sync_db_session.commit()
        except Exception:
            # Column might already exist, ignore
            sync_db_session.rollback()
        
        # Inherit from TaskModel to satisfy registry check
        # Define custom TaskModel that inherits from TaskModel
        # This satisfies the registry's issubclass check
        class CustomTaskModel(TaskModel):
            """Custom TaskModel with project_id field"""
            __tablename__ = TASK_TABLE_NAME
            __table_args__ = {'extend_existing': True}  # Allow extending existing table
            
            # Custom field
            project_id = Column(String(100), nullable=True, comment="Project ID for task grouping")
            
            def to_dict(self):
                """Convert to dictionary including custom field"""
                base_dict = super().to_dict()
                base_dict["project_id"] = self.project_id
                return base_dict
        
        # ========================================================================
        # Step 2: Register hooks using decorators
        # ========================================================================
        pre_hook_calls = []
        post_hook_calls = []
        
        from aipartnerupflow import register_pre_hook, register_post_hook
        
        @register_pre_hook
        async def custom_pre_hook(task):
            """Pre-hook that adds project context and modifies inputs"""
            pre_hook_calls.append({
                "task_id": task.id,
                "task_name": task.name,
                "has_project_id": hasattr(task, "project_id"),
                "project_id": getattr(task, "project_id", None),
                "original_input": dict(task.inputs) if task.inputs else {},
            })
            
            # Modify inputs to add hook-generated data
            if task.inputs is None:
                task.inputs = {}
            task.inputs["_pre_hook_executed"] = True
            task.inputs["_hook_timestamp"] = "2024-01-01T00:00:00Z"
            
            # If project_id is set, add it to inputs for executor
            if hasattr(task, "project_id") and task.project_id:
                task.inputs["_project_id"] = task.project_id
        
        @register_post_hook
        async def custom_post_hook(task, inputs, result):
            """Post-hook that validates custom fields and processes results"""
            post_hook_calls.append({
                "task_id": task.id,
                "task_name": task.name,
                "task_status": task.status,
                "has_project_id": hasattr(task, "project_id"),
                "project_id": getattr(task, "project_id", None),
                "inputs_keys": list(inputs.keys()) if inputs else [],
                "has_pre_hook_marker": inputs.get("_pre_hook_executed", False) if inputs else False,
                "result_type": type(result).__name__,
                "result_keys": list(result.keys()) if isinstance(result, dict) else None,
            })
        
        # Set custom TaskModel using decorator API (after hooks are registered)
        set_task_model_class(CustomTaskModel)
        
        # Create executor AFTER registering hooks and setting custom TaskModel
        # In production, hooks and TaskModel are registered at application startup before executor creation
        # For testing, we register hooks and set TaskModel first, then create executor to match production pattern
        # Since TaskExecutor is singleton, we need to refresh its config to pick up newly registered hooks and model
        from aipartnerupflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
        from aipartnerupflow.core.execution.task_executor import TaskExecutor
        executor = AIPartnerUpFlowAgentExecutor()
        # Refresh TaskExecutor singleton's hooks and model to pick up newly registered values
        # This is only needed for testing; in production, hooks and model are registered before executor creation
        TaskExecutor().refresh_config()
        
        # ========================================================================
        # Step 3: Create and execute task with custom model
        # ========================================================================
        user_id = "test-user-custom"
        project_id = "test-project-123"
        
        # Create task using repository with custom model (to set project_id)
        # Then execute via executor using require_existing_tasks=True mode
        repo = TaskRepository(sync_db_session, task_model_class=CustomTaskModel)
        
        # Create task with custom field first (using kwargs for id)
        task = await repo.create_task(
            name="Custom Task with Project",
            user_id=user_id,
            priority=1,
            schemas={
                "method": "system_info_executor"  # Executor id
            },
            inputs={
                "resource": "cpu"
            },
            id="custom-task-1",  # Custom field via kwargs
            project_id=project_id  # Custom field
        )
        
        # Verify task was created with custom field
        assert task.id == "custom-task-1"
        assert task.project_id == project_id
        
        # Now execute the task via executor using require_existing_tasks=True
        # This mode loads existing tasks from database instead of creating new ones
        tasks = [
            {
                "id": "custom-task-1",  # Use same ID as created task
                # Only need id for require_existing_tasks=True mode
            }
        ]
        
        # Set require_existing_tasks=True in metadata to use existing task mode
        context = self._create_request_context(tasks, metadata={"require_existing_tasks": True})
        
        # Execute with real database and custom model
        # Mock get_default_session in both agent_executor and task_executor modules
        with patch('aipartnerupflow.api.a2a.agent_executor.get_default_session') as mock_get_session_agent, \
             patch('aipartnerupflow.core.execution.task_executor.get_default_session') as mock_get_session_executor:
            mock_get_session_agent.return_value = sync_db_session
            mock_get_session_executor.return_value = sync_db_session
            
            # Execute using executor with custom config
            result = await executor.execute(context, mock_event_queue)
            
            # ========================================================================
            # Step 4: Verify execution results
            # ========================================================================
            assert result is not None
            # Result format depends on execution mode, check if it's a dict with status
            if isinstance(result, dict) and "status" in result:
                assert result["status"] == "completed", f"Expected completed, got {result.get('status')}"
            # Also verify via database
            
            # Reload task from database to verify custom field persisted
            repo = TaskRepository(sync_db_session, task_model_class=CustomTaskModel)
            task_after = await repo.get_task_by_id("custom-task-1")
            assert task_after is not None
            assert task_after.status == "completed"
            assert task_after.result is not None
            
            # Verify custom field was saved and persisted
            assert hasattr(task_after, "project_id"), "Custom TaskModel should have project_id field"
            assert task_after.project_id == project_id, f"Expected project_id={project_id}, got {task_after.project_id}"
            
            # ========================================================================
            # Step 5: Verify hooks were called correctly
            # ========================================================================
            # Verify pre-hook was called
            assert len(pre_hook_calls) == 1, f"Expected 1 pre-hook call, got {len(pre_hook_calls)}"
            pre_call = pre_hook_calls[0]
            assert pre_call["task_id"] == "custom-task-1"
            assert pre_call["has_project_id"] is True, "Pre-hook should see custom field"
            assert pre_call["project_id"] == project_id
            
            # Verify pre-hook modified inputs
            assert pre_call["original_input"].get("resource") == "cpu"
            
            # Verify post-hook was called
            assert len(post_hook_calls) == 1, f"Expected 1 post-hook call, got {len(post_hook_calls)}"
            post_call = post_hook_calls[0]
            assert post_call["task_id"] == "custom-task-1"
            assert post_call["task_status"] == "completed"
            assert post_call["has_project_id"] is True, "Post-hook should see custom field"
            assert post_call["project_id"] == project_id
            
            # Verify post-hook received modified inputs from pre-hook
            assert post_call["has_pre_hook_marker"] is True, "Post-hook should see pre-hook modifications"
            assert "_pre_hook_executed" in post_call["inputs_keys"]
            assert "_hook_timestamp" in post_call["inputs_keys"]
            
            # Verify post-hook received result
            assert post_call["result_type"] == "dict"
            assert post_call["result_keys"] is not None
            assert len(post_call["result_keys"]) > 0
            
            # ========================================================================
            # Step 6: Verify data flow: inputs -> pre-hook -> execution -> post-hook
            # ========================================================================
            # The inputs should have been modified by pre-hook before execution
            # We can verify this by checking the task's inputs (if persisted)
            # or by checking what post-hook received
            
            logger.info(f"==Custom TaskModel Test Results==")
            logger.info(f"Pre-hook calls: {json.dumps(pre_hook_calls, indent=2)}")
            logger.info(f"Post-hook calls: {json.dumps(post_hook_calls, indent=2)}")
            logger.info(f"Task project_id: {task_after.project_id}")
            logger.info(f"Task result keys: {list(task_after.result.keys()) if isinstance(task_after.result, dict) else 'N/A'}")
            
            # Final verification: All decorator features work together
            assert task_after.project_id == project_id, "Custom TaskModel field should be preserved"
            assert pre_call["has_project_id"] is True, "Pre-hook should access custom field"
            assert post_call["has_project_id"] is True, "Post-hook should access custom field"
            assert post_call["has_pre_hook_marker"] is True, "Pre-hook modifications should be visible to post-hook"
            
            logger.info("✅ All decorator features verified: custom TaskModel, pre-hook, post-hook")


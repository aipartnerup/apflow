"""
Integration tests for schema-based task tree execution and generation

Tests the following scenarios:
1. scrape_executor + llm_executor (schema-based dependency mapping)
2. scrape_executor + crewai_executor (if available)
3. generate_executor creating and executing task trees
"""

import pytest
from unittest.mock import AsyncMock, patch

from apflow.core.execution.task_manager import TaskManager
from apflow.core.types import TaskTreeNode
from apflow.extensions.llm.llm_executor import LLMExecutor
from apflow.extensions.generate.generate_executor import GenerateExecutor


@pytest.mark.asyncio
class TestSchemaBasedTaskExecution:
    """Test schema-based task tree execution"""

    async def test_scrape_llm_chain_schema_based(self, sync_db_session):
        """Test scrape_executor -> llm_executor with schema-based dependency mapping"""
        task_manager = TaskManager(sync_db_session)
        task_repo = task_manager.task_repository

        # Create actual database tasks with the same task_tree_id
        task_tree_id = "test-tree-123"
        scrape_task = await task_repo.create_task(
            name="scrape_content",
            user_id="test_user",
            schemas={"method": "scrape_executor"},
            result={"result": "Scraped content from example.com"},
            status="completed",
            task_tree_id=task_tree_id,
        )

        llm_task = await task_repo.create_task(
            name="analyze_content",
            user_id="test_user",
            schemas={"method": "llm_executor"},
            dependencies=[{"id": scrape_task.id, "required": True}],
            task_tree_id=task_tree_id,
        )

        # Mock the _get_executor_for_task to return mock executors
        class MockScrapeExecutor:
            def get_input_schema(self):
                return {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                }

            def get_output_schema(self):
                return {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                }

        class MockLLMExecutor:
            def get_input_schema(self):
                return {
                    "type": "object",
                    "properties": {"messages": {"type": "array"}},
                }

            def get_output_schema(self):
                return {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                }

        with patch.object(task_manager, "_get_executor_for_task") as mock_get_executor:
            mock_get_executor.side_effect = lambda task: (
                MockScrapeExecutor() if task.id == scrape_task.id else MockLLMExecutor()
            )

            # Test resolve_task_dependencies for llm_task
            resolved_inputs = await task_manager.resolve_task_dependencies(llm_task)

            # Since actual_result is string 'Scraped content from example.com', it should be stored under scrape_task.id
            assert scrape_task.id in resolved_inputs
            assert resolved_inputs[scrape_task.id] == "Scraped content from example.com"

    async def test_scrape_crewai_chain_schema_based(self, sync_db_session):
        """Test scrape_executor -> crewai_executor with schema-based dependency mapping"""
        # Check if scrape_executor is available
        try:
            from apflow.extensions.scrape.scrape_executor import ScrapeExecutor
        except ImportError:
            pytest.skip("ScrapeExecutor not available")

        # Only run if crewai is available
        try:
            from apflow.core.extensions.registry import get_registry

            registry = get_registry()

            # Ensure crewai executor is registered (workaround for test isolation)
            if not registry.is_registered("crewai_executor"):
                try:
                    from apflow.extensions.crewai.crewai_executor import CrewaiExecutor
                    from apflow.core.extensions.decorators import executor_register

                    executor_register()(CrewaiExecutor)
                except ImportError:
                    pytest.skip("CrewAI executor not available")

            if not registry.is_registered("crewai_executor"):
                pytest.skip("CrewAI executor not available")
        except ImportError:
            pytest.skip("Extension registry not available")

        # Import the class for patching
        try:
            from apflow.extensions.crewai.crewai_executor import CrewaiExecutor

            crewai_executor_class = CrewaiExecutor
        except ImportError:
            pytest.skip("CrewAI not installed")

        # Create task manager
        task_manager = TaskManager(sync_db_session)
        task_repo = task_manager.task_repository

        # Create scrape task
        scrape_task = await task_repo.create_task(
            name="scrape_content",
            user_id="test_user",
            schemas={"method": "scrape_executor"},
            inputs={"url": "https://example.com", "max_chars": 1000, "extract_metadata": False},
        )

        # Create CrewAI task that depends on scrape
        crewai_task = await task_repo.create_task(
            name="analyze_with_crew",
            user_id="test_user",
            schemas={"method": "crewai_executor"},
            inputs={
                "works": {
                    "agents": {
                        "Analyst": {
                            "role": "Analyst",
                            "goal": "Analyze content",
                            "backstory": "You are a content analyst",
                        }
                    },
                    "tasks": {
                        "analyze_task": {
                            "description": "Analyze the provided content",
                            "agent": "Analyst",
                            "expected_output": "Analysis of the content",
                        }
                    },
                }
                # "content" should be populated by schema-based mapping
            },
            dependencies=[{"id": scrape_task.id, "required": True}],
            parent_id=scrape_task.id,
        )

        # Mock the scrape executor
        with patch.object(ScrapeExecutor, "execute", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = {"result": "Sample content to analyze"}

            # Mock CrewAI executor
            crewai_executor_class_mock = AsyncMock()
            crewai_executor_class_mock.return_value = crewai_executor_class_mock
            crewai_executor_class_mock.execute.return_value = {"result": "CrewAI analysis result"}

            with patch.object(crewai_executor_class, "execute", crewai_executor_class_mock.execute):
                # Build task tree
                scrape_node = TaskTreeNode(scrape_task)
                crewai_node = TaskTreeNode(crewai_task)
                scrape_node.add_child(crewai_node)

                # Execute the task tree
                await task_manager.distribute_task_tree(scrape_node)

                # Verify both tasks completed
                updated_scrape = await task_repo.get_task_by_id(scrape_task.id)
                updated_crewai = await task_repo.get_task_by_id(crewai_task.id)

                assert updated_scrape is not None
                assert updated_crewai is not None
                assert updated_scrape.status == "completed"
                assert updated_crewai.status == "completed"

    async def test_generate_executor_full_flow(self, sync_db_session):
        """Test generate_executor creating task tree and executing it"""
        # Import ScrapeExecutor for mocking
        try:
            from apflow.extensions.scrape.scrape_executor import ScrapeExecutor
        except ImportError:
            pytest.skip("ScrapeExecutor not available")

        task_manager = TaskManager(sync_db_session)
        task_repo = task_manager.task_repository

        # Create generate task
        generate_task = await task_repo.create_task(
            name="generate_workflow",
            user_id="test_user",
            schemas={"method": "generate_executor"},
            inputs={
                "requirement": "Scrape content from example.com and analyze it with LLM",
                "user_id": "test_user",
            },
        )

        # Mock the generate executor to return a task tree
        with patch.object(GenerateExecutor, "execute", new_callable=AsyncMock) as mock_generate:
            # Mock generated task tree with scrape -> llm chain
            mock_generate.return_value = {
                "result": {
                    "status": "completed",
                    "tasks": [
                        {
                            "id": "scrape-task-123",
                            "name": "scrape_content",
                            "user_id": "test_user",
                            "schemas": {"method": "scrape_executor"},
                            "inputs": {"url": "https://example.com", "max_chars": 1000},
                        },
                        {
                            "id": "llm-task-456",
                            "name": "analyze_content",
                            "user_id": "test_user",
                            "schemas": {"method": "llm_executor"},
                            "inputs": {"model": "gpt-3.5-turbo"},
                            "dependencies": [{"id": "scrape-task-123", "required": True}],
                            "parent_id": "scrape-task-123",
                        },
                    ],
                    "count": 2,
                }
            }

            # Mock the individual executors for execution
            with patch.object(ScrapeExecutor, "execute", new_callable=AsyncMock) as mock_scrape:
                mock_scrape.return_value = {"result": "Generated content from example.com"}

                with patch.object(LLMExecutor, "execute", new_callable=AsyncMock) as mock_llm:
                    mock_llm.return_value = {"result": "Analysis of generated content"}

                    # Execute the generate task
                    generate_node = TaskTreeNode(generate_task)
                    await task_manager.distribute_task_tree(generate_node)

                    # Verify generate task completed
                    updated_generate = await task_repo.get_task_by_id(generate_task.id)
                    assert updated_generate is not None
                    assert updated_generate.status == "completed"

                    # Verify the generated task tree was created and executed
                    # In a real scenario, the generate executor would create tasks in DB
                    # For this test, we verify the mock was called correctly
                    mock_generate.assert_called_once()

    async def test_schema_fallback_when_no_executor(self, sync_db_session):
        """Test that schema-based mapping falls back gracefully when executors not found"""
        task_manager = TaskManager(sync_db_session)
        task_repo = task_manager.task_repository

        # Create two custom tasks (using base executor without schema methods)
        task_tree_id = "fallback-test-tree"
        task1 = await task_repo.create_task(
            name="task1",
            user_id="test_user",
            schemas={"method": "custom_executor"},  # Non-existent executor
            inputs={},
            task_tree_id=task_tree_id,
        )

        task2 = await task_repo.create_task(
            name="task2",
            user_id="test_user",
            schemas={"method": "another_custom_executor"},  # Non-existent executor
            inputs={},
            dependencies=[{"id": task1.id, "required": True}],
            task_tree_id=task_tree_id,
        )

        # Set task1 as completed with a result
        task1.status = "completed"
        task1.result = {"result": {"custom": "data"}}
        await task_repo.update_task(task1.id)

        # Resolve dependencies for task2
        resolved_inputs = await task_manager.resolve_task_dependencies(task2)

        # Should fall back to simple merge
        assert "custom" in resolved_inputs
        assert resolved_inputs["custom"] == "data"

    async def test_schema_mapping_direct_field_match(self, sync_db_session):
        """Test schema mapping when dependency output field matches input field"""
        task_manager = TaskManager(sync_db_session)
        task_repo = task_manager.task_repository

        # Create source task with result
        task_tree_id = "schema-mapping-test-tree"
        source_task = await task_repo.create_task(
            name="source_task",
            user_id="test_user",
            schemas={"method": "mock_output"},
            result={"result": {"content": "test content"}},
            status="completed",
            task_tree_id=task_tree_id,
        )

        # Create target task that depends on source
        target_task = await task_repo.create_task(
            name="target_task",
            user_id="test_user",
            schemas={"method": "mock_input"},
            dependencies=[{"id": source_task.id, "required": True}],
            task_tree_id=task_tree_id,
        )

        # Mock executors to return the expected schemas
        class MockOutputExecutor:
            def get_output_schema(self):
                return {
                    "type": "object",
                    "properties": {
                        "result": {"type": "object", "properties": {"content": {"type": "string"}}}
                    },
                    "required": ["result"],
                }

        class MockInputExecutor:
            def get_input_schema(self):
                return {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"}  # Direct field match
                    },
                }

        # Mock the executors
        with patch.object(task_manager, "_get_executor_for_task") as mock_get_executor:
            mock_get_executor.side_effect = lambda task: (
                MockOutputExecutor() if task.id == source_task.id else MockInputExecutor()
            )

            # Test dependency resolution
            resolved_inputs = await task_manager.resolve_task_dependencies(target_task)

            # Should map the content field directly
            assert "content" in resolved_inputs
            assert resolved_inputs["content"] == "test content"

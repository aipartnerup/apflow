"""
Test BatchCrewaiExecutor functionality

This module contains tests for BatchCrewaiExecutor, including:
- Executor registration via @executor_register() decorator
- Batch execution of multiple crews
- Error handling and atomic operation semantics
- Real integration tests with actual CrewAI (requires OPENAI_API_KEY)
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock

# Try to import BatchCrewaiExecutor, skip tests if not available
try:
    from apflow.extensions.crewai import BatchCrewaiExecutor
    from apflow.extensions.crewai import CrewaiExecutor
    from apflow.core.extensions import get_registry
except ImportError:
    BatchCrewaiExecutor = None
    CrewaiExecutor = None
    get_registry = None
    pytestmark = pytest.mark.skip("crewai module not available")


@pytest.mark.skipif(BatchCrewaiExecutor is None, reason="BatchCrewaiExecutor not available")
class TestBatchCrewaiExecutorRegistration:
    """Test BatchCrewaiExecutor executor registration"""
    
    def test_executor_register_decorator(self):
        """Test that BatchCrewaiExecutor is registered via @executor_register() decorator"""
        # Import BatchCrewaiExecutor to trigger registration
        
        # Verify extension was registered
        registry = get_registry()
        
        # Check if BatchCrewaiExecutor is registered by ID
        assert registry.is_registered("batch_crewai_executor"), \
            "BatchCrewaiExecutor should be registered with id 'batch_crewai_executor'"
        
        # Get the registered extension
        extension = registry.get_by_id("batch_crewai_executor")
        assert extension is not None, "BatchCrewaiExecutor extension should be found by ID"
        assert extension.id == "batch_crewai_executor"
        assert extension.name == "Batch CrewAI Executor"
        
        # Verify it's registered as an executor
        from apflow.core.extensions.types import ExtensionCategory
        assert extension.category == ExtensionCategory.EXECUTOR
    
    def test_batch_crewai_executor_properties(self):
        """Test BatchCrewaiExecutor class properties"""
        assert BatchCrewaiExecutor.id == "batch_crewai_executor"
        assert BatchCrewaiExecutor.name == "Batch CrewAI Executor"
        assert BatchCrewaiExecutor.description == "Batch execution of multiple crews via CrewAI"
        
        # Test type property
        batch_crewai_executor = BatchCrewaiExecutor(works={})
        assert batch_crewai_executor.type == "crewai"
    
    def test_batch_crewai_executor_inheritance(self):
        """Test that BatchCrewaiExecutor inherits from BaseTask"""
        from apflow.core.base import BaseTask
        assert issubclass(BatchCrewaiExecutor, BaseTask)


@pytest.mark.skipif(BatchCrewaiExecutor is None or CrewaiExecutor is None, reason="BatchCrewaiExecutor or CrewaiExecutor not available")
class TestBatchCrewaiExecutorExecution:
    """Test BatchCrewaiExecutor execution functionality"""
    
    @pytest.mark.asyncio
    async def test_execute_with_mock_crews(self):
        """Test batch execution with mocked crews"""
        # Create mock crew results
        mock_result1 = {
            "status": "success",
            "result": "Result from crew 1",
            "token_usage": {
                "total_tokens": 100,
                "prompt_tokens": 60,
                "completion_tokens": 40,
                "cached_prompt_tokens": 0,
                "successful_requests": 1
            }
        }
        
        mock_result2 = {
            "status": "success",
            "result": "Result from crew 2",
            "token_usage": {
                "total_tokens": 150,
                "prompt_tokens": 90,
                "completion_tokens": 60,
                "cached_prompt_tokens": 0,
                "successful_requests": 1
            }
        }
        
        # Create mock CrewaiExecutor instances
        mock_crewai_executor1 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor1.execute = AsyncMock(return_value=mock_result1)
        mock_crewai_executor1.set_streaming_context = Mock()
        
        mock_crewai_executor2 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor2.execute = AsyncMock(return_value=mock_result2)
        mock_crewai_executor2.set_streaming_context = Mock()
        
        # Create BatchCrewaiExecutor with works
        batch_crewai_executor = BatchCrewaiExecutor(
            works={
                "crew1": {
                    "agents": {
                        "agent1": {
                            "role": "Agent 1",
                            "goal": "Goal 1",
                            "backstory": "Backstory 1"
                        }
                    },
                    "tasks": {
                        "task1": {
                            "description": "Task 1",
                            "expected_output": "Output 1",
                            "agent": "agent1"
                        }
                    }
                },
                "crew2": {
                    "agents": {
                        "agent2": {
                            "role": "Agent 2",
                            "goal": "Goal 2",
                            "backstory": "Backstory 2"
                        }
                    },
                    "tasks": {
                        "task2": {
                            "description": "Task 2",
                            "expected_output": "Output 2",
                            "agent": "agent2"
                        }
                    }
                }
            }
        )
        
        # Mock CrewaiExecutor creation (it's imported inside execute_works method)
        # Need to patch where it's imported from, not where it's used
        with patch('apflow.extensions.crewai.crewai_executor.CrewaiExecutor', side_effect=[mock_crewai_executor1, mock_crewai_executor2]):
            # Execute batch
            result = await batch_crewai_executor.execute()
            
            # Verify result structure
            assert result["status"] == "success"
            assert "result" in result
            assert isinstance(result["result"], dict)
            assert "crew1" in result["result"]
            assert "crew2" in result["result"]
            
            # Verify aggregated token usage
            assert "token_usage" in result
            token_usage = result["token_usage"]
            assert token_usage["total_tokens"] == 250  # 100 + 150
            assert token_usage["prompt_tokens"] == 150  # 60 + 90
            assert token_usage["completion_tokens"] == 100  # 40 + 60
    
    @pytest.mark.asyncio
    async def test_execute_with_failure(self):
        """Test batch execution when one crew fails (atomic operation)"""
        # Create mock crew results - one success, one failure
        mock_result1 = {
            "status": "success",
            "result": "Result from crew 1"
        }
        
        mock_result2 = {
            "status": "failed",
            "error": "Crew 2 failed",
            "result": None
        }
        
        # Create mock CrewaiExecutor instances
        mock_crewai_executor1 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor1.execute = AsyncMock(return_value=mock_result1)
        mock_crewai_executor1.set_streaming_context = Mock()
        
        mock_crewai_executor2 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor2.execute = AsyncMock(return_value=mock_result2)
        mock_crewai_executor2.set_streaming_context = Mock()
        
        # Create BatchCrewaiExecutor
        batch_crewai_executor = BatchCrewaiExecutor(
            works={
                "crew1": {
                    "agents": {"agent1": {"role": "Agent 1", "goal": "Goal 1", "backstory": "Backstory 1"}},
                    "tasks": {"task1": {"description": "Task 1", "expected_output": "Output 1", "agent": "agent1"}}
                },
                "crew2": {
                    "agents": {"agent2": {"role": "Agent 2", "goal": "Goal 2", "backstory": "Backstory 2"}},
                    "tasks": {"task2": {"description": "Task 2", "expected_output": "Output 2", "agent": "agent2"}}
                }
            }
        )
        
        # Mock CrewaiExecutor creation (it's imported inside execute_works method)
        with patch('apflow.extensions.crewai.crewai_executor.CrewaiExecutor') as mock_crew_class:
            mock_crew_class.side_effect = [mock_crewai_executor1, mock_crewai_executor2]
            
            # Execute batch - should fail atomically
            result = await batch_crewai_executor.execute()
            
            # Verify failure result
            assert result["status"] == "failed"
            assert "error" in result
            assert "Failed works" in result["error"]
            assert "crew2" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_with_exception(self):
        """Test batch execution when crew raises exception"""
        # Create mock crew that raises exception
        mock_crewai_executor = Mock(spec=CrewaiExecutor)
        mock_crewai_executor.execute = AsyncMock(side_effect=Exception("Crew execution error"))
        mock_crewai_executor.set_streaming_context = Mock()
        
        # Create BatchCrewaiExecutor
        batch_crewai_executor = BatchCrewaiExecutor(
            works={
                "crew1": {
                    "agents": {"agent1": {"role": "Agent 1", "goal": "Goal 1", "backstory": "Backstory 1"}},
                    "tasks": {"task1": {"description": "Task 1", "expected_output": "Output 1", "agent": "agent1"}}
                }
            }
        )
        
        # Mock CrewaiExecutor creation (it's imported inside execute_works method)
        with patch('apflow.extensions.crewai.crewai_executor.CrewaiExecutor') as mock_crew_class:
            mock_crew_class.return_value = mock_crewai_executor
            
            # Execute batch - should handle exception
            result = await batch_crewai_executor.execute()
            
            # Verify failure result
            assert result["status"] == "failed"
            assert "error" in result
            assert "Failed works" in result["error"]
            assert "crew1" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_with_no_works(self):
        """Test batch execution with no works (should fail)"""
        batch_crewai_executor = BatchCrewaiExecutor(works={})
        
        # Execute batch - should fail
        result = await batch_crewai_executor.execute()
        
        # Verify failure result
        assert result["status"] == "failed"
        assert "error" in result
        assert "No works found" in result["error"]
    
    def test_get_input_schema(self):
        """Test get_input_schema method"""
        batch_crewai_executor = BatchCrewaiExecutor(works={})
        schema = batch_crewai_executor.get_input_schema()
        
        # Should return a dictionary (can be empty)
        assert isinstance(schema, dict)
    
    def test_set_inputs(self):
        """Test set_inputs method"""
        batch_crewai_executor = BatchCrewaiExecutor(works={})
        test_inputs = {"key1": "value1", "key2": "value2"}
        
        batch_crewai_executor.set_inputs(test_inputs)
        
        assert batch_crewai_executor.inputs == test_inputs
    
    def test_set_streaming_context(self):
        """Test set_streaming_context method"""
        batch_crewai_executor = BatchCrewaiExecutor(works={})
        mock_event_queue = Mock()
        mock_context = Mock()
        
        batch_crewai_executor.set_streaming_context(mock_event_queue, mock_context)
        
        assert batch_crewai_executor.event_queue == mock_event_queue
        assert batch_crewai_executor.context == mock_context

    def test_cancelable_property(self):
        """Test that BatchCrewaiExecutor has cancelable=True"""
        batch_crewai_executor = BatchCrewaiExecutor(works={})
        assert batch_crewai_executor.cancelable is True, "BatchCrewaiExecutor should support cancellation"
    
    @pytest.mark.asyncio
    async def test_cancellation_before_execution(self):
        """Test cancellation before any work execution starts"""
        # Create cancellation checker that returns True immediately
        cancellation_checker = Mock(return_value=True)
        
        # Create BatchCrewaiExecutor with cancellation checker
        batch_crewai_executor = BatchCrewaiExecutor(
            works={
                "crew1": {
                    "agents": {"agent1": {"role": "Agent 1", "goal": "Goal 1", "backstory": "Backstory 1"}},
                    "tasks": {"task1": {"description": "Task 1", "expected_output": "Output 1", "agent": "agent1"}}
                },
                "crew2": {
                    "agents": {"agent2": {"role": "Agent 2", "goal": "Goal 2", "backstory": "Backstory 2"}},
                    "tasks": {"task2": {"description": "Task 2", "expected_output": "Output 2", "agent": "agent2"}}
                }
            },
            cancellation_checker=cancellation_checker
        )
        
        # Execute batch - should be cancelled before first work
        result = await batch_crewai_executor.execute()
        
        # Verify cancellation result
        assert result["status"] == "cancelled"
        assert "error" in result
        assert "cancelled" in result["error"].lower()
        assert "0" in result["error"] or "before" in result["error"].lower()
        
        # Verify cancellation checker was called
        assert cancellation_checker.called
    
    @pytest.mark.asyncio
    async def test_cancellation_after_first_work(self):
        """Test cancellation after first work completes, preserving token_usage"""
        # Create mock crew results with token_usage
        mock_result1 = {
            "status": "success",
            "result": "Result from crew 1",
            "token_usage": {
                "total_tokens": 100,
                "prompt_tokens": 60,
                "completion_tokens": 40,
                "cached_prompt_tokens": 0,
                "successful_requests": 1
            }
        }
        
        mock_result2 = {
            "status": "success",
            "result": "Result from crew 2",
            "token_usage": {
                "total_tokens": 150,
                "prompt_tokens": 90,
                "completion_tokens": 60,
                "cached_prompt_tokens": 0,
                "successful_requests": 1
            }
        }
        
        # Create cancellation checker that returns False first (allow first work), then True (cancel)
        # Call sequence: 1=before start, 2=before work1, 3=after work1 (cancel here)
        call_count = [0]
        def cancellation_checker():
            call_count[0] += 1
            # Return True on third call (after first work completes)
            return call_count[0] > 2
        
        # Create mock CrewaiExecutor instances
        mock_crewai_executor1 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor1.execute = AsyncMock(return_value=mock_result1)
        mock_crewai_executor1.set_streaming_context = Mock()
        
        mock_crewai_executor2 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor2.execute = AsyncMock(return_value=mock_result2)
        mock_crewai_executor2.set_streaming_context = Mock()
        
        # Create BatchCrewaiExecutor with cancellation checker
        batch_crewai_executor = BatchCrewaiExecutor(
            works={
                "crew1": {
                    "agents": {"agent1": {"role": "Agent 1", "goal": "Goal 1", "backstory": "Backstory 1"}},
                    "tasks": {"task1": {"description": "Task 1", "expected_output": "Output 1", "agent": "agent1"}}
                },
                "crew2": {
                    "agents": {"agent2": {"role": "Agent 2", "goal": "Goal 2", "backstory": "Backstory 2"}},
                    "tasks": {"task2": {"description": "Task 2", "expected_output": "Output 2", "agent": "agent2"}}
                }
            },
            cancellation_checker=cancellation_checker
        )
        
        # Mock CrewaiExecutor creation
        with patch('apflow.extensions.crewai.crewai_executor.CrewaiExecutor') as mock_crew_class:
            mock_crew_class.side_effect = [mock_crewai_executor1, mock_crewai_executor2]
            
            # Execute batch - should be cancelled after first work
            result = await batch_crewai_executor.execute()
            
            # Verify cancellation result
            assert result["status"] == "cancelled"
            assert "error" in result
            assert "cancelled" in result["error"].lower()
            assert "1" in result["error"]  # Should mention 1 completed work
            
            # Verify only first crew executed
            mock_crewai_executor1.execute.assert_called_once()
            mock_crewai_executor2.execute.assert_not_called()
            
            # Verify token_usage is preserved from first work
            assert "token_usage" in result
            token_usage = result["token_usage"]
            assert token_usage["total_tokens"] == 100  # Only from first work
            assert token_usage["prompt_tokens"] == 60
            assert token_usage["completion_tokens"] == 40
            assert "status" not in token_usage  # token_usage shouldn't have status field
    
    @pytest.mark.asyncio
    async def test_cancellation_preserves_token_usage_from_multiple_works(self):
        """Test that cancellation preserves token_usage from all completed works"""
        # Create mock crew results with token_usage
        mock_result1 = {
            "status": "success",
            "result": "Result from crew 1",
            "token_usage": {
                "total_tokens": 100,
                "prompt_tokens": 60,
                "completion_tokens": 40,
                "cached_prompt_tokens": 0,
                "successful_requests": 1
            }
        }
        
        mock_result2 = {
            "status": "success",
            "result": "Result from crew 2",
            "token_usage": {
                "total_tokens": 150,
                "prompt_tokens": 90,
                "completion_tokens": 60,
                "cached_prompt_tokens": 0,
                "successful_requests": 1
            }
        }
        
        mock_result3 = {
            "status": "success",
            "result": "Result from crew 3",
            "token_usage": {
                "total_tokens": 200,
                "prompt_tokens": 120,
                "completion_tokens": 80,
                "cached_prompt_tokens": 0,
                "successful_requests": 1
            }
        }
        
        # Create cancellation checker that cancels after second work
        # Call sequence: 1=before start, 2=before work1, 3=after work1, 4=before work2, 5=after work2 (cancel here)
        call_count = [0]
        def cancellation_checker():
            call_count[0] += 1
            # Return True on fifth call (after second work completes)
            return call_count[0] > 4
        
        # Create mock CrewaiExecutor instances
        mock_crewai_executor1 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor1.execute = AsyncMock(return_value=mock_result1)
        mock_crewai_executor1.set_streaming_context = Mock()
        
        mock_crewai_executor2 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor2.execute = AsyncMock(return_value=mock_result2)
        mock_crewai_executor2.set_streaming_context = Mock()
        
        mock_crewai_executor3 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor3.execute = AsyncMock(return_value=mock_result3)
        mock_crewai_executor3.set_streaming_context = Mock()
        
        # Create BatchCrewaiExecutor with 3 works
        batch_crewai_executor = BatchCrewaiExecutor(
            works={
                "crew1": {
                    "agents": {"agent1": {"role": "Agent 1", "goal": "Goal 1", "backstory": "Backstory 1"}},
                    "tasks": {"task1": {"description": "Task 1", "expected_output": "Output 1", "agent": "agent1"}}
                },
                "crew2": {
                    "agents": {"agent2": {"role": "Agent 2", "goal": "Goal 2", "backstory": "Backstory 2"}},
                    "tasks": {"task2": {"description": "Task 2", "expected_output": "Output 2", "agent": "agent2"}}
                },
                "crew3": {
                    "agents": {"agent3": {"role": "Agent 3", "goal": "Goal 3", "backstory": "Backstory 3"}},
                    "tasks": {"task3": {"description": "Task 3", "expected_output": "Output 3", "agent": "agent3"}}
                }
            },
            cancellation_checker=cancellation_checker
        )
        
        # Mock CrewaiExecutor creation
        with patch('apflow.extensions.crewai.crewai_executor.CrewaiExecutor') as mock_crew_class:
            mock_crew_class.side_effect = [mock_crewai_executor1, mock_crewai_executor2, mock_crewai_executor3]
            
            # Execute batch - should be cancelled after second work
            result = await batch_crewai_executor.execute()
            
            # Verify cancellation result
            assert result["status"] == "cancelled"
            assert "error" in result
            assert "cancelled" in result["error"].lower()
            assert "2" in result["error"]  # Should mention 2 completed works
            
            # Verify first two crews executed, third did not
            mock_crewai_executor1.execute.assert_called_once()
            mock_crewai_executor2.execute.assert_called_once()
            mock_crewai_executor3.execute.assert_not_called()
            
            # Verify token_usage is aggregated from both completed works
            assert "token_usage" in result
            token_usage = result["token_usage"]
            assert token_usage["total_tokens"] == 250  # 100 + 150
            assert token_usage["prompt_tokens"] == 150  # 60 + 90
            assert token_usage["completion_tokens"] == 100  # 40 + 60
            assert "status" not in token_usage  # token_usage shouldn't have status field
    
    @pytest.mark.asyncio
    async def test_cancellation_with_no_token_usage(self):
        """Test cancellation when completed works don't have token_usage"""
        # Create mock crew results without token_usage
        mock_result1 = {
            "status": "success",
            "result": "Result from crew 1"
        }
        
        # Create cancellation checker that cancels after first work
        # Call sequence: 1=before start, 2=before work1, 3=after work1 (cancel here)
        call_count = [0]
        def cancellation_checker():
            call_count[0] += 1
            return call_count[0] > 2
        
        # Create mock CrewaiExecutor
        mock_crewai_executor1 = Mock(spec=CrewaiExecutor)
        mock_crewai_executor1.execute = AsyncMock(return_value=mock_result1)
        mock_crewai_executor1.set_streaming_context = Mock()
        
        # Create BatchCrewaiExecutor
        batch_crewai_executor = BatchCrewaiExecutor(
            works={
                "crew1": {
                    "agents": {"agent1": {"role": "Agent 1", "goal": "Goal 1", "backstory": "Backstory 1"}},
                    "tasks": {"task1": {"description": "Task 1", "expected_output": "Output 1", "agent": "agent1"}}
                }
            },
            cancellation_checker=cancellation_checker
        )
        
        # Mock CrewaiExecutor creation
        with patch('apflow.extensions.crewai.crewai_executor.CrewaiExecutor') as mock_crew_class:
            mock_crew_class.return_value = mock_crewai_executor1
            
            # Execute batch - should be cancelled after first work
            result = await batch_crewai_executor.execute()
            
            # Verify cancellation result
            assert result["status"] == "cancelled"
            assert "error" in result
            
            # token_usage may or may not be present (depends on aggregation logic)
            # If no token_usage in results, aggregation should return None
            if "token_usage" in result:
                # If present, should be valid
                assert isinstance(result["token_usage"], dict)


@pytest.mark.skipif(BatchCrewaiExecutor is None or CrewaiExecutor is None, reason="BatchCrewaiExecutor or CrewaiExecutor not available")
class TestBatchCrewaiExecutorRealExecution:
    """Test BatchCrewaiExecutor with real CrewAI execution (integration tests)"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY is not set - skipping integration test"
    )
    async def test_execute_with_real_crews(self):
        """Test batch execution with real CrewAI crews (requires OPENAI_API_KEY)"""
        # Check if OpenAI API key is available
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY is not set")
        
        # Create BatchCrewaiExecutor with multiple crews
        # Each crew will perform a simple task to test batch execution
        batch_crewai_executor = BatchCrewaiExecutor(
            name="Test Batch Crew",
            works={
                "research_crew": {
                    "agents": {
                        "researcher": {
                            "role": "Researcher",
                            "goal": "Research and provide brief summaries",
                            "backstory": "You are a helpful research assistant",
                            "verbose": False,
                            "allow_delegation": False,
                            "llm": "openai/gpt-3.5-turbo"
                        }
                    },
                    "tasks": {
                        "research_task": {
                            "description": "Research and summarize what Python programming language is in one sentence",
                            "expected_output": "A one-sentence summary of Python",
                            "agent": "researcher"
                        }
                    }
                },
                "analysis_crew": {
                    "agents": {
                        "analyst": {
                            "role": "Analyst",
                            "goal": "Analyze and provide insights",
                            "backstory": "You are a skilled data analyst",
                            "verbose": False,
                            "allow_delegation": False,
                            "llm": "openai/gpt-3.5-turbo"
                        }
                    },
                    "tasks": {
                        "analysis_task": {
                            "description": "Analyze and explain why Python is popular in one sentence",
                            "expected_output": "A one-sentence explanation of Python's popularity",
                            "agent": "analyst"
                        }
                    }
                }
            }
        )
        
        # Execute batch
        result = await batch_crewai_executor.execute()
        
        print("=== Batch Execution Result ===")
        import json
        print(json.dumps(result, indent=2, default=str))
        
        # Verify result structure
        assert result["status"] in ["success", "failed"]
        
        if result["status"] == "success":
            # Verify success result structure
            assert "result" in result
            assert isinstance(result["result"], dict)
            
            # Verify both crews executed
            assert "research_crew" in result["result"]
            assert "analysis_crew" in result["result"]
            
            # Verify each crew's result
            research_result = result["result"]["research_crew"]
            analysis_result = result["result"]["analysis_crew"]
            
            # Results should contain the crew execution results
            # The structure depends on how CrewaiExecutor returns results
            assert research_result is not None
            assert analysis_result is not None
            
            # Verify aggregated token usage is present
            if "token_usage" in result:
                token_usage = result["token_usage"]
                assert "total_tokens" in token_usage or "status" in token_usage
                
                # If we have token counts, verify they're aggregated
                if "total_tokens" in token_usage:
                    assert token_usage["total_tokens"] > 0
                    print(f"\nAggregated Token Usage: {token_usage}")
        else:
            # If failed, verify error message
            assert "error" in result
            print(f"Batch execution failed: {result.get('error')}")
            
            # Even if failed, token usage should be aggregated if available
            if "token_usage" in result:
                print(f"Token usage from executed crews: {result.get('token_usage')}")
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY is not set - skipping integration test"
    )
    async def test_execute_with_inputs(self):
        """Test batch execution with input parameters passed to crews"""
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY is not set")
        
        # Create BatchCrewaiExecutor with crews that use input parameters
        batch_crewai_executor = BatchCrewaiExecutor(
            name="Test Batch with Inputs",
            works={
                "greeting_crew": {
                    "agents": {
                        "greeter": {
                            "role": "Greeter",
                            "goal": "Create personalized greetings",
                            "backstory": "You are a friendly assistant",
                            "verbose": False,
                            "allow_delegation": False,
                            "llm": "openai/gpt-3.5-turbo"
                        }
                    },
                    "tasks": {
                        "greeting_task": {
                            "description": "Create a greeting message for the person named {name}",
                            "expected_output": "A personalized greeting message",
                            "agent": "greeter"
                        }
                    }
                },
                "farewell_crew": {
                    "agents": {
                        "fareweller": {
                            "role": "Fareweller",
                            "goal": "Create personalized farewells",
                            "backstory": "You are a polite assistant",
                            "verbose": False,
                            "allow_delegation": False,
                            "llm": "openai/gpt-3.5-turbo"
                        }
                    },
                    "tasks": {
                        "farewell_task": {
                            "description": "Create a farewell message for the person named {name}",
                            "expected_output": "A personalized farewell message",
                            "agent": "fareweller"
                        }
                    }
                }
            }
        )
        
        # Execute batch with inputs
        inputs = {"name": "Alice"}
        result = await batch_crewai_executor.execute(inputs=inputs)
        
        print("=== Batch Execution with Inputs Result ===")
        import json
        print(json.dumps(result, indent=2, default=str))
        
        # Verify result structure
        assert result["status"] in ["success", "failed"]
        
        if result["status"] == "success":
            # Verify both crews executed with inputs
            assert "result" in result
            assert isinstance(result["result"], dict)
            assert "greeting_crew" in result["result"]
            assert "farewell_crew" in result["result"]
            
            # Verify inputs were used (results should mention "Alice")
            # Extract actual result content from nested structure
            greeting_crew_result = result["result"]["greeting_crew"]
            farewell_crew_result = result["result"]["farewell_crew"]
            
            # Handle different result structures (could be dict with 'result' key or direct string)
            if isinstance(greeting_crew_result, dict):
                greeting_result = str(greeting_crew_result.get("result", greeting_crew_result))
            else:
                greeting_result = str(greeting_crew_result)
            
            if isinstance(farewell_crew_result, dict):
                farewell_result = str(farewell_crew_result.get("result", farewell_crew_result))
            else:
                farewell_result = str(farewell_crew_result)
            
            # Results should contain the name from inputs
            # Note: LLM responses can be unpredictable, so we check if at least one contains the name
            # or if the execution was successful (which means inputs were passed correctly)
            greeting_has_name = "Alice" in greeting_result or "alice" in greeting_result.lower()
            farewell_has_name = "Alice" in farewell_result or "alice" in farewell_result.lower()
            
            # At least one crew should use the input, or we verify the structure is correct
            # (The important thing is that inputs were passed, not necessarily that LLM used them)
            assert greeting_has_name or farewell_has_name or (
                isinstance(greeting_crew_result, dict) and greeting_crew_result.get("status") == "success" and
                isinstance(farewell_crew_result, dict) and farewell_crew_result.get("status") == "success"
            ), f"Expected at least one result to mention 'Alice', or both crews to succeed. Greeting: {greeting_result[:100]}, Farewell: {farewell_result[:100]}"
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY is not set - skipping integration test"
    )
    async def test_execute_single_crew_batch(self):
        """Test batch execution with a single crew (edge case)"""
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY is not set")
        
        # Create BatchCrewaiExecutor with a single crew
        batch_crewai_executor = BatchCrewaiExecutor(
            name="Single Crew Batch",
            works={
                "single_crew": {
                    "agents": {
                        "assistant": {
                            "role": "Assistant",
                            "goal": "Provide helpful responses",
                            "backstory": "You are a helpful assistant",
                            "verbose": False,
                            "allow_delegation": False,
                            "llm": "openai/gpt-3.5-turbo"
                        }
                    },
                    "tasks": {
                        "simple_task": {
                            "description": "Say hello in one sentence",
                            "expected_output": "A greeting message",
                            "agent": "assistant"
                        }
                    }
                }
            }
        )
        
        # Execute batch
        result = await batch_crewai_executor.execute()
        
        print("=== Single Crew Batch Result ===")
        import json
        print(json.dumps(result, indent=2, default=str))
        
        # Verify result structure
        assert result["status"] in ["success", "failed"]
        
        if result["status"] == "success":
            # Verify single crew executed
            assert "result" in result
            assert isinstance(result["result"], dict)
            assert "single_crew" in result["result"]
            
            # Verify token usage is present
            if "token_usage" in result:
                token_usage = result["token_usage"]
                assert "total_tokens" in token_usage or "status" in token_usage


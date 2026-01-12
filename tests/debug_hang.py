"""
Debug script to help identify where tests hang.

Usage:
    pytest tests/debug_hang.py -v -s
    pytest tests/api/a2a/test_agent_executor.py::TestAgentExecutor::test_cancel_with_custom_error_message -v -s --log-cli-level=DEBUG
"""

import pytest
import signal
import sys
import traceback
from unittest.mock import Mock, AsyncMock, patch


def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    print("\n" + "="*80)
    print("TEST TIMEOUT - Printing stack traces of all threads:")
    print("="*80)
    for thread_id, frame in sys._current_frames().items():
        print(f"\nThread {thread_id}:")
        traceback.print_stack(frame)
    print("="*80)
    sys.exit(1)


@pytest.fixture(autouse=True)
def setup_timeout():
    """Set up timeout signal handler for debugging"""
    # Set alarm for 30 seconds
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)
    yield
    signal.alarm(0)


@pytest.mark.asyncio
async def test_debug_cancel():
    """Debug test to identify where cancel hangs"""
    from apflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
    from apflow.api.routes.tasks import TaskRoutes
    from apflow.core.storage.sqlalchemy.models import TaskModel
    
    print("\n[DEBUG] Creating executor...")
    task_routes = TaskRoutes(
        task_model_class=TaskModel,
        verify_token_func=None,
        verify_permission_func=None
    )
    executor = AIPartnerUpFlowAgentExecutor(
        task_routes=task_routes,
        verify_token_func=None
    )
    print("[DEBUG] Executor created")
    
    print("[DEBUG] Creating mock event queue...")
    mock_event_queue = AsyncMock(spec=['enqueue_event'])
    mock_event_queue.enqueue_event = AsyncMock()
    print("[DEBUG] Mock event queue created")
    
    print("[DEBUG] Creating context...")
    context = Mock()
    context.task_id = "test-task-123"
    context.context_id = "context-123"
    context.metadata = {"error_message": "Cancelled by user request"}
    print("[DEBUG] Context created")
    
    print("[DEBUG] Patching get_default_session...")
    with patch('apflow.api.a2a.agent_executor.get_default_session') as mock_get_session, \
         patch.object(executor.task_executor, 'cancel_task', new_callable=AsyncMock) as mock_cancel_task:
        
        print("[DEBUG] Setting up mocks...")
        mock_get_session.return_value = Mock()
        mock_cancel_task.return_value = {
            "status": "cancelled",
            "message": "Cancelled by user request"
        }
        print("[DEBUG] Mocks set up")
        
        print("[DEBUG] Calling executor.cancel()...")
        try:
            await executor.cancel(context, mock_event_queue)
            print("[DEBUG] executor.cancel() completed successfully")
        except Exception as e:
            print(f"[DEBUG] executor.cancel() raised exception: {e}")
            traceback.print_exc()
            raise
        
        print("[DEBUG] Verifying mocks...")
        assert mock_cancel_task.called
        assert mock_event_queue.enqueue_event.called
        print("[DEBUG] All assertions passed")

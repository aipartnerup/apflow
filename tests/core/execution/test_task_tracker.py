"""
Test TaskTracker singleton and thread safety
"""

import threading
import pytest

from apflow.core.execution.task_tracker import TaskTracker


@pytest.fixture(autouse=True)
def reset_task_tracker():
    """Reset TaskTracker singleton between tests"""
    TaskTracker._instance = None
    TaskTracker._initialized = False
    yield
    TaskTracker._instance = None
    TaskTracker._initialized = False


class TestTaskTracker:
    """Test TaskTracker singleton and basic functionality"""

    def test_singleton_returns_same_instance(self):
        """Test that TaskTracker returns the same instance"""
        tracker1 = TaskTracker()
        tracker2 = TaskTracker()
        assert tracker1 is tracker2

    def test_singleton_thread_safe(self):
        """Test that concurrent creation from multiple threads returns the same instance"""
        instances: list[TaskTracker] = []
        barrier = threading.Barrier(10)

        def create_instance() -> None:
            barrier.wait()
            instances.append(TaskTracker())

        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(instances) == 10
        for instance in instances:
            assert instance is instances[0]

    @pytest.mark.asyncio
    async def test_start_and_stop_tracking(self):
        """Test starting and stopping task tracking"""
        tracker = TaskTracker()

        await tracker.start_task_tracking("task-1")
        assert tracker.is_task_running("task-1") is True
        assert tracker.get_running_tasks_count() == 1

        await tracker.stop_task_tracking("task-1")
        assert tracker.is_task_running("task-1") is False
        assert tracker.get_running_tasks_count() == 0

    def test_is_task_running(self):
        """Test is_task_running returns correct state"""
        tracker = TaskTracker()

        assert tracker.is_task_running("nonexistent") is False

        tracker._running_tasks.add("task-1")
        assert tracker.is_task_running("task-1") is True
        assert tracker.is_task_running("task-2") is False

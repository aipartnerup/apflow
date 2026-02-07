"""
Internal Scheduler Implementation

Built-in scheduler for apflow that polls for due tasks and executes them.
Uses asyncio for lightweight scheduling without external dependencies.

When an API server is running (apflow serve), the scheduler auto-detects it
and routes all operations through the API to avoid DuckDB single-writer
conflicts. Falls back to direct DB access when the API is unavailable.

For production deployments requiring high availability, consider using
external schedulers via the API gateway (tasks.scheduled.* endpoints).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    from apflow.cli.api_client import APIClient

from apflow.scheduler.base import (
    BaseScheduler,
    SchedulerConfig,
    SchedulerState,
    SchedulerStats,
)
from apflow.logger import get_logger

logger = get_logger(__name__)


class InternalScheduler(BaseScheduler):
    """
    Built-in scheduler for apflow.

    Features:
    - Auto-detects API server and routes through it when available
    - Falls back to direct DB access when API is unavailable
    - Polls for due tasks at configurable intervals
    - Executes tasks concurrently up to max_concurrent_tasks
    - Handles task completion and next_run calculation
    - Supports pause/resume without losing state
    - Multi-user support via user_id filter

    Usage:
        config = SchedulerConfig(
            poll_interval=60,          # Check every 60 seconds
            max_concurrent_tasks=5,    # Max 5 concurrent tasks
            user_id="user123"          # Optional: only process this user's tasks
        )
        scheduler = InternalScheduler(config)
        await scheduler.start()

    For CLI usage:
        apflow scheduler start --poll-interval 60 --max-concurrent 5
    """

    def __init__(self, config: Optional[SchedulerConfig] = None):
        super().__init__(config)
        self._poll_task: Optional[asyncio.Task[None]] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._pause_event: Optional[asyncio.Event] = None
        self._active_task_ids: Set[str] = set()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._use_api: bool = False

    async def start(self) -> None:
        """
        Start the scheduler.

        Begins polling for due tasks and executing them.
        Auto-detects whether to use API or direct DB access.
        Raises RuntimeError if already running.
        """
        if self.stats.state in (SchedulerState.running, SchedulerState.starting):
            raise RuntimeError("Scheduler is already running")

        logger.info(
            f"Starting internal scheduler "
            f"(poll_interval={self.config.poll_interval}s, "
            f"max_concurrent={self.config.max_concurrent_tasks})"
        )

        self.stats.state = SchedulerState.starting
        self.stats.started_at = datetime.now(timezone.utc)

        # Detect API mode (same pattern as CLI commands)
        self._use_api = self._detect_api_mode()
        if self._use_api:
            logger.info("Scheduler using API mode (server detected)")
        else:
            logger.info("Scheduler using direct DB mode")

        # Initialize control events
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially

        # Semaphore for concurrent task limiting
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)

        # Start the polling loop
        self._poll_task = asyncio.create_task(self._poll_loop())

        self.stats.state = SchedulerState.running
        logger.info("Internal scheduler started successfully")

    async def stop(self) -> None:
        """
        Stop the scheduler gracefully.

        Waits for active tasks to complete before stopping.
        """
        if self.stats.state == SchedulerState.stopped:
            logger.warning("Scheduler is already stopped")
            return

        logger.info("Stopping internal scheduler...")
        self.stats.state = SchedulerState.stopping

        # Signal the poll loop to stop
        if self._stop_event:
            self._stop_event.set()

        # Resume if paused (so the loop can check stop event)
        if self._pause_event:
            self._pause_event.set()

        # Wait for the poll task to finish
        if self._poll_task:
            try:
                await asyncio.wait_for(self._poll_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("Poll task did not finish in time, cancelling")
                self._poll_task.cancel()
                try:
                    await self._poll_task
                except asyncio.CancelledError:
                    pass

        # Wait for active tasks to complete (with timeout)
        if self._active_task_ids:
            logger.info(f"Waiting for {len(self._active_task_ids)} active tasks to complete...")
            # Give active tasks some time to finish
            wait_start = datetime.now(timezone.utc)
            while self._active_task_ids:
                if (datetime.now(timezone.utc) - wait_start).total_seconds() > 60:
                    logger.warning(f"Timeout waiting for active tasks: {self._active_task_ids}")
                    break
                await asyncio.sleep(1)

        self.stats.state = SchedulerState.stopped
        logger.info("Internal scheduler stopped")

    async def pause(self) -> None:
        """
        Pause the scheduler.

        Stops polling for new tasks but allows active tasks to complete.
        """
        if self.stats.state != SchedulerState.running:
            raise RuntimeError("Can only pause a running scheduler")

        logger.info("Pausing scheduler...")
        self._pause_event.clear()
        self.stats.state = SchedulerState.paused
        logger.info("Scheduler paused")

    async def resume(self) -> None:
        """
        Resume a paused scheduler.

        Resumes polling for due tasks.
        """
        if self.stats.state != SchedulerState.paused:
            raise RuntimeError("Can only resume a paused scheduler")

        logger.info("Resuming scheduler...")
        self._pause_event.set()
        self.stats.state = SchedulerState.running
        logger.info("Scheduler resumed")

    async def trigger(self, task_id: str) -> bool:
        """
        Manually trigger a specific task.

        Executes the task immediately regardless of schedule.

        Args:
            task_id: The task ID to trigger

        Returns:
            True if task was triggered successfully, False otherwise
        """
        logger.info(f"Manually triggering task: {task_id}")

        if task_id in self._active_task_ids:
            logger.warning(f"Task {task_id} is already executing")
            return False

        # Add to active set BEFORE creating task to prevent duplicate triggers
        self._active_task_ids.add(task_id)
        try:
            asyncio.create_task(self._execute_task(task_id, manual=True))
            return True
        except Exception as e:
            # Rollback if task creation fails
            self._active_task_ids.discard(task_id)
            logger.error(f"Failed to trigger task {task_id}: {e}")
            return False

    async def get_status(self) -> SchedulerStats:
        """
        Get current scheduler status and statistics.

        Returns:
            SchedulerStats with current state and metrics
        """
        self.stats.active_tasks = len(self._active_task_ids)
        return self.stats

    def _detect_api_mode(self) -> bool:
        """Detect whether API server is available using the same logic as CLI commands."""
        try:
            from apflow.cli.api_gateway_helper import should_use_api

            return should_use_api()
        except Exception as e:
            logger.debug(f"API detection failed, using direct DB: {e}")
            return False

    def _create_api_client(self, timeout: Optional[float] = None) -> "APIClient":
        """Create an APIClient configured from ConfigManager.

        Args:
            timeout: Override timeout (e.g., task_timeout for execution calls).
                     Defaults to the configured api_timeout.

        Returns:
            Configured APIClient instance (use as async context manager).
        """
        from apflow.cli.api_client import APIClient
        from apflow.core.config_manager import get_config_manager

        cm = get_config_manager()
        return APIClient(
            server_url=cm.api_server_url or "http://localhost:8000",
            auth_token=cm.admin_auth_token,
            timeout=timeout if timeout is not None else cm.api_timeout,
            retry_attempts=cm.api_retry_attempts,
            retry_backoff=cm.api_retry_backoff,
            proxies=None,
        )

    async def _poll_loop(self) -> None:
        """
        Main polling loop that checks for due tasks.

        Runs until stop_event is set.
        """
        logger.debug("Poll loop started")

        while not self._stop_event.is_set():
            try:
                # Wait if paused
                await self._pause_event.wait()

                # Check if we should stop
                if self._stop_event.is_set():
                    break

                # Record poll time
                self.stats.last_poll_at = datetime.now(timezone.utc)
                self.stats.next_poll_at = self.stats.last_poll_at + timedelta(
                    seconds=self.config.poll_interval
                )

                # Get due tasks
                due_tasks = await self._get_due_tasks()

                if due_tasks:
                    logger.info(f"Found {len(due_tasks)} due tasks")

                    # Execute due tasks (respecting concurrency limit)
                    for task in due_tasks:
                        if self._stop_event.is_set():
                            break

                        task_id = task.get("id") or task.id
                        if task_id not in self._active_task_ids:
                            # Add to active set BEFORE creating task to prevent
                            # duplicate scheduling during semaphore wait
                            self._active_task_ids.add(task_id)
                            try:
                                asyncio.create_task(self._execute_task(task_id))
                            except Exception as e:
                                # Rollback if task creation fails
                                self._active_task_ids.discard(task_id)
                                logger.error(f"Failed to schedule task {task_id}: {e}")

                # Wait for next poll interval (or until stopped)
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.config.poll_interval
                    )
                    # If we get here, stop_event was set
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue polling
                    pass

            except Exception as e:
                logger.error(f"Error in poll loop: {e}", exc_info=True)
                self.stats.state = SchedulerState.error
                # Wait a bit before retrying
                await asyncio.sleep(5)
                if self.stats.state == SchedulerState.error:
                    self.stats.state = SchedulerState.running

        logger.debug("Poll loop ended")

    async def _get_due_tasks(self) -> List[Dict[str, Any]]:
        """
        Get tasks that are due for execution.

        Uses API when available, falls back to direct DB access.

        Returns:
            List of task dictionaries that are due
        """
        if self._use_api:
            try:
                return await self._get_due_tasks_via_api()
            except Exception as e:
                logger.warning(f"API call failed for due tasks, falling back to DB: {e}")

        return await self._get_due_tasks_via_db()

    async def _get_due_tasks_via_api(self) -> List[Dict[str, Any]]:
        """Get due tasks via API server."""

        client = self._create_api_client()
        async with client:
            params: Dict[str, Any] = {
                "limit": self.config.max_concurrent_tasks * 2,
            }
            if self.config.user_id:
                params["user_id"] = self.config.user_id

            result = await client.call_method("tasks.scheduled.due", **params)
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and "tasks" in result:
                return result["tasks"]
            return []

    async def _get_due_tasks_via_db(self) -> List[Dict[str, Any]]:
        """Get due tasks via direct database access."""
        try:
            from apflow.core.storage import create_pooled_session
            from apflow.core.storage.sqlalchemy.task_repository import TaskRepository

            async with create_pooled_session() as db_session:
                task_repository = TaskRepository(db_session)

                tasks = await task_repository.get_due_scheduled_tasks(
                    before=datetime.now(timezone.utc),
                    user_id=self.config.user_id,
                    limit=self.config.max_concurrent_tasks * 2,  # Fetch more than we can execute
                )

                return [task.to_dict() for task in tasks]

        except Exception as e:
            logger.error(f"Failed to get due tasks: {e}", exc_info=True)
            return []

    async def _execute_task(self, task_id: str, manual: bool = False) -> None:
        """
        Execute a single scheduled task.

        Uses API when available, falls back to direct DB access.

        Args:
            task_id: The task ID to execute
            manual: Whether this is a manual trigger (bypass schedule check)

        Note:
            task_id must already be in _active_task_ids before calling this method.
            The caller (poll_loop or trigger) is responsible for adding it.
        """
        try:
            # Acquire semaphore to limit concurrency
            async with self._semaphore:
                self.stats.active_tasks = len(self._active_task_ids)

                if self._use_api:
                    try:
                        await self._execute_task_via_api(task_id)
                        return
                    except Exception as e:
                        logger.warning(
                            f"API execution failed for task {task_id}, " f"falling back to DB: {e}"
                        )

                await self._execute_task_via_db(task_id)

        finally:
            # Always remove from active tasks, even if semaphore wait was cancelled.
            # This prevents deadlock when task is added to _active_task_ids but
            # never gets to execute due to cancellation or other errors.
            self._active_task_ids.discard(task_id)
            self.stats.active_tasks = len(self._active_task_ids)

    async def _execute_task_via_api(self, task_id: str) -> None:
        """Execute a task via the API server.

        Uses tasks.webhook.trigger with async_execution=False, which handles the
        full execution cycle (mark_running + execute + complete_scheduled_run)
        atomically on the server side.
        """
        logger.info(f"Executing scheduled task via API: {task_id}")

        # Use task_timeout as the HTTP timeout since execution is synchronous
        client = self._create_api_client(timeout=float(self.config.task_timeout))
        async with client:
            result = await client.call_method(
                "tasks.webhook.trigger",
                task_id=task_id,
                async_execution=False,
            )

        # Parse result and update stats
        success = False
        task_result = None
        error = None

        if isinstance(result, dict):
            success = result.get("status") == "completed" or result.get("success", False)
            task_result = result.get("result")
            error = result.get("error")

        self.stats.tasks_executed += 1
        if success:
            self.stats.tasks_succeeded += 1
            logger.info(f"Task {task_id} completed successfully via API")
        else:
            self.stats.tasks_failed += 1
            logger.warning(f"Task {task_id} failed via API: {error}")

        self._notify_task_complete(task_id, success, task_result)

    async def _execute_task_via_db(self, task_id: str) -> None:
        """Execute a task via direct database access."""
        success = False
        result = None
        error = None

        try:
            logger.info(f"Executing scheduled task: {task_id}")

            from apflow.core.storage import create_pooled_session
            from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
            from apflow.core.execution.task_executor import TaskExecutor

            # Mark task as running
            async with create_pooled_session() as db_session:
                task_repository = TaskRepository(db_session)
                task = await task_repository.mark_scheduled_task_running(task_id)

                if not task:
                    logger.warning(f"Task {task_id} not found or not ready")
                    return

            # Execute the task
            task_executor = TaskExecutor()

            async with create_pooled_session() as db_session:
                task_repository = TaskRepository(db_session)

                # Get task to determine execution mode
                task = await task_repository.get_task_by_id(task_id)
                if not task:
                    logger.error(f"Task {task_id} not found")
                    return

                # Auto-detect execution mode based on has_children
                # If task has children, execute full tree; otherwise execute single
                if task.has_children:
                    logger.info(f"Executing task {task_id} in tree mode (has children)")
                    task_tree = await task_repository.get_task_tree_for_api(task)
                else:
                    logger.info(f"Executing task {task_id} in single mode (no children)")
                    from apflow.core.types import TaskTreeNode

                    task_tree = TaskTreeNode(task=task, children=[])

                # Execute the task tree
                await task_executor.execute_task_tree(
                    task_tree=task_tree,
                    root_task_id=task_id,
                    use_streaming=False,
                    db_session=db_session,
                )

                # Refresh task to get result
                task = await task_repository.get_task_by_id(task_id)
                if task:
                    success = task.status == "completed"
                    result = task.result
                    if task.error:
                        error = task.error

            self.stats.tasks_executed += 1
            if success:
                self.stats.tasks_succeeded += 1
                logger.info(f"Task {task_id} completed successfully")
            else:
                self.stats.tasks_failed += 1
                logger.warning(f"Task {task_id} failed: {error}")

        except Exception as e:
            success = False
            error = str(e)
            self.stats.tasks_executed += 1
            self.stats.tasks_failed += 1
            logger.error(f"Error executing task {task_id}: {e}", exc_info=True)

        finally:
            # Complete the scheduled run (calculate next execution time)
            try:
                from apflow.core.storage import create_pooled_session
                from apflow.core.storage.sqlalchemy.task_repository import TaskRepository

                async with create_pooled_session() as db_session:
                    task_repository = TaskRepository(db_session)
                    await task_repository.complete_scheduled_run(
                        task_id=task_id,
                        success=success,
                        result=result,
                        error=error,
                        calculate_next_run=True,
                    )
            except Exception as e:
                logger.error(f"Failed to complete scheduled run for {task_id}: {e}")

            # Notify callbacks
            self._notify_task_complete(task_id, success, result)


async def run_scheduler(config: Optional[SchedulerConfig] = None) -> None:
    """
    Run the internal scheduler (blocking).

    This is a convenience function for running the scheduler as a standalone process.
    Use Ctrl+C to stop.

    Args:
        config: Optional scheduler configuration

    Usage:
        import asyncio
        from apflow.scheduler import run_scheduler, SchedulerConfig

        config = SchedulerConfig(poll_interval=30)
        asyncio.run(run_scheduler(config))
    """
    scheduler = InternalScheduler(config)

    # Handle shutdown signals
    import signal

    def signal_handler() -> None:
        logger.info("Received shutdown signal")
        asyncio.create_task(scheduler.stop())

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await scheduler.start()
        # Keep running until stopped
        while scheduler.stats.state in (SchedulerState.running, SchedulerState.paused):
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Scheduler error: {e}", exc_info=True)
    finally:
        if scheduler.stats.state != SchedulerState.stopped:
            await scheduler.stop()

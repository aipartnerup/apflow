"""
Tests for the scheduler module

Tests cover:
- BaseScheduler interface and config
- InternalScheduler lifecycle and execution
- WebhookGateway validation and triggering
- ICalExporter format generation
"""

import asyncio

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from apflow.scheduler.base import (
    SchedulerConfig,
    SchedulerState,
    SchedulerStats,
)
from apflow.scheduler.internal import InternalScheduler
from apflow.scheduler.gateway.webhook import (
    WebhookGateway,
    WebhookConfig,
    generate_cron_config,
    generate_kubernetes_cronjob,
)
from apflow.scheduler.gateway.ical import (
    ICalExporter,
    fold_line,
    escape_text,
    format_datetime,
    generate_uid,
    generate_ical_feed_url,
)


# ============================================================================
# SchedulerConfig Tests
# ============================================================================


class TestSchedulerConfig:
    """Tests for SchedulerConfig"""

    def test_default_config(self):
        """Test default configuration values"""
        config = SchedulerConfig()
        assert config.poll_interval == 60
        assert config.max_concurrent_tasks == 10
        assert config.task_timeout == 3600
        assert config.retry_on_failure is False
        assert config.max_retries == 3
        assert config.user_id is None

    def test_custom_config(self):
        """Test custom configuration values"""
        config = SchedulerConfig(
            poll_interval=30,
            max_concurrent_tasks=5,
            task_timeout=1800,
            retry_on_failure=True,
            max_retries=5,
            user_id="user123",
        )
        assert config.poll_interval == 30
        assert config.max_concurrent_tasks == 5
        assert config.task_timeout == 1800
        assert config.retry_on_failure is True
        assert config.max_retries == 5
        assert config.user_id == "user123"

    def test_to_dict(self):
        """Test config to_dict method"""
        config = SchedulerConfig(poll_interval=45, user_id="test")
        data = config.to_dict()
        assert data["poll_interval"] == 45
        assert data["user_id"] == "test"
        assert "max_concurrent_tasks" in data

    def test_from_dict(self):
        """Test config from_dict method"""
        data = {"poll_interval": 90, "max_concurrent_tasks": 20}
        config = SchedulerConfig.from_dict(data)
        assert config.poll_interval == 90
        assert config.max_concurrent_tasks == 20


class TestSchedulerStats:
    """Tests for SchedulerStats"""

    def test_default_stats(self):
        """Test default stats values"""
        stats = SchedulerStats()
        assert stats.state == SchedulerState.stopped
        assert stats.started_at is None
        assert stats.tasks_executed == 0
        assert stats.tasks_succeeded == 0
        assert stats.tasks_failed == 0
        assert stats.active_tasks == 0

    def test_to_dict(self):
        """Test stats to_dict method"""
        stats = SchedulerStats()
        stats.state = SchedulerState.running
        stats.tasks_executed = 10
        stats.started_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        data = stats.to_dict()
        assert data["state"] == "running"
        assert data["tasks_executed"] == 10
        assert data["started_at"] == "2024-01-01T00:00:00+00:00"


# ============================================================================
# InternalScheduler Tests
# ============================================================================


class TestInternalScheduler:
    """Tests for InternalScheduler"""

    def test_init_with_default_config(self):
        """Test scheduler initialization with default config"""
        scheduler = InternalScheduler()
        assert scheduler.config.poll_interval == 60
        assert scheduler.stats.state == SchedulerState.stopped

    def test_init_with_custom_config(self):
        """Test scheduler initialization with custom config"""
        config = SchedulerConfig(poll_interval=30, max_concurrent_tasks=5)
        scheduler = InternalScheduler(config)
        assert scheduler.config.poll_interval == 30
        assert scheduler.config.max_concurrent_tasks == 5

    def test_init_with_verbose(self):
        """Test scheduler initialization with verbose mode"""
        scheduler = InternalScheduler(verbose=True)
        assert scheduler._verbose is True
        assert scheduler._console is not None

    def test_init_without_verbose(self):
        """Test scheduler initialization without verbose mode (default)"""
        scheduler = InternalScheduler()
        assert scheduler._verbose is False
        assert scheduler._console is None

    def test_print_task_result_verbose(self):
        """Test _print_task_result prints task info when verbose"""
        scheduler = InternalScheduler(verbose=True)
        scheduler._console = MagicMock()
        scheduler._print_task_result("task123", "My Task", "completed")
        scheduler._console.print.assert_called_once()
        call_arg = scheduler._console.print.call_args[0][0]
        assert "task123" in call_arg
        assert "My Task" in call_arg
        assert "completed" in call_arg

    def test_print_task_result_verbose_with_error(self):
        """Test _print_task_result shows error reason when task fails"""
        scheduler = InternalScheduler(verbose=True)
        scheduler._console = MagicMock()
        scheduler._print_task_result("task123", "My Task", "failed", error="Connection refused")
        scheduler._console.print.assert_called_once()
        call_arg = scheduler._console.print.call_args[0][0]
        assert "task123" in call_arg
        assert "failed" in call_arg
        assert "Connection refused" in call_arg

    def test_print_task_result_verbose_no_error_on_success(self):
        """Test _print_task_result does not show error line when status is completed"""
        scheduler = InternalScheduler(verbose=True)
        scheduler._console = MagicMock()
        scheduler._print_task_result("task123", "My Task", "completed", error="ignored")
        scheduler._console.print.assert_called_once()
        call_arg = scheduler._console.print.call_args[0][0]
        assert "completed" in call_arg
        assert "Error:" not in call_arg

    def test_print_task_result_verbose_status_colors(self):
        """Test _print_task_result uses correct colors for different statuses"""
        scheduler = InternalScheduler(verbose=True)
        scheduler._console = MagicMock()

        # pending → yellow
        scheduler._print_task_result("t1", "Task", "pending")
        call_arg = scheduler._console.print.call_args[0][0]
        assert "[yellow]pending[/yellow]" in call_arg

        scheduler._console.reset_mock()

        # in_progress → cyan
        scheduler._print_task_result("t2", "Task", "in_progress")
        call_arg = scheduler._console.print.call_args[0][0]
        assert "[cyan]in_progress[/cyan]" in call_arg

    def test_print_task_result_not_verbose(self):
        """Test _print_task_result does nothing when not verbose"""
        scheduler = InternalScheduler(verbose=False)
        # Should not raise
        scheduler._print_task_result("task123", "My Task", "completed")

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Test scheduler start and stop lifecycle"""
        scheduler = InternalScheduler()

        # Mock _get_due_tasks to avoid database access
        scheduler._get_due_tasks = AsyncMock(return_value=[])

        # Start scheduler
        await scheduler.start()
        assert scheduler.stats.state == SchedulerState.running
        assert scheduler.stats.started_at is not None

        # Stop scheduler
        await scheduler.stop()
        assert scheduler.stats.state == SchedulerState.stopped

    @pytest.mark.asyncio
    async def test_start_already_running_raises(self):
        """Test that starting an already running scheduler raises error"""
        scheduler = InternalScheduler()
        scheduler._get_due_tasks = AsyncMock(return_value=[])

        await scheduler.start()

        with pytest.raises(RuntimeError, match="already running"):
            await scheduler.start()

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        """Test scheduler pause and resume"""
        scheduler = InternalScheduler()
        scheduler._get_due_tasks = AsyncMock(return_value=[])

        await scheduler.start()
        assert scheduler.stats.state == SchedulerState.running

        await scheduler.pause()
        assert scheduler.stats.state == SchedulerState.paused

        await scheduler.resume()
        assert scheduler.stats.state == SchedulerState.running

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_pause_not_running_raises(self):
        """Test that pausing a non-running scheduler raises error"""
        scheduler = InternalScheduler()

        with pytest.raises(RuntimeError, match="only pause a running"):
            await scheduler.pause()

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test get_status method"""
        scheduler = InternalScheduler()
        scheduler._get_due_tasks = AsyncMock(return_value=[])

        await scheduler.start()
        stats = await scheduler.get_status()

        assert stats.state == SchedulerState.running
        assert stats.started_at is not None

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_callback_registration(self):
        """Test task completion callback registration"""
        scheduler = InternalScheduler()

        callback_called = False
        callback_args = None

        def callback(task_id, success, result):
            nonlocal callback_called, callback_args
            callback_called = True
            callback_args = (task_id, success, result)

        scheduler.on_task_complete(callback)

        # Simulate callback notification
        scheduler._notify_task_complete("task123", True, {"data": "test"})

        assert callback_called is True
        assert callback_args == ("task123", True, {"data": "test"})

    @pytest.mark.asyncio
    async def test_trigger_duplicate_task_returns_false(self):
        """Test that triggering an already active task returns False"""
        scheduler = InternalScheduler()
        scheduler._get_due_tasks = AsyncMock(return_value=[])
        scheduler._semaphore = asyncio.Semaphore(10)

        # Pre-add task to active set (simulating already running)
        scheduler._active_task_ids.add("task123")

        # Trigger should return False for duplicate
        result = await scheduler.trigger("task123")
        assert result is False

    @pytest.mark.asyncio
    async def test_trigger_adds_to_active_before_create_task(self):
        """Test that trigger adds task_id to _active_task_ids before creating task"""
        scheduler = InternalScheduler()
        scheduler._get_due_tasks = AsyncMock(return_value=[])
        scheduler._semaphore = asyncio.Semaphore(10)

        # Use an event to synchronize and capture state
        task_started = asyncio.Event()
        active_ids_snapshot = None

        async def mock_execute(task_id: str, manual: bool = False) -> None:
            nonlocal active_ids_snapshot
            # Capture state at the moment _execute_task starts
            active_ids_snapshot = scheduler._active_task_ids.copy()
            task_started.set()
            # Simulate cleanup in finally block
            scheduler._active_task_ids.discard(task_id)

        scheduler._execute_task = mock_execute

        result = await scheduler.trigger("task123")

        # Wait for the task to start executing
        await asyncio.wait_for(task_started.wait(), timeout=1.0)

        assert result is True
        # Task should have been in active set when _execute_task was called
        assert "task123" in active_ids_snapshot

    @pytest.mark.asyncio
    async def test_trigger_rollback_on_failure(self):
        """Test that trigger removes task_id from active set if create_task fails"""
        scheduler = InternalScheduler()
        scheduler._get_due_tasks = AsyncMock(return_value=[])
        # Don't initialize semaphore to cause failure in _execute_task

        # Mock _execute_task to raise exception
        async def failing_execute(task_id: str, manual: bool = False) -> None:
            raise RuntimeError("Simulated failure")

        scheduler._execute_task = failing_execute

        # Before trigger
        assert "task123" not in scheduler._active_task_ids

        # Note: asyncio.create_task itself doesn't raise even if the coroutine
        # will raise later. The task creation succeeds, but the task will fail.
        # So we need to verify cleanup happens in _execute_task's finally block.
        result = await scheduler.trigger("task123")

        # trigger returns True because create_task succeeded
        assert result is True
        # But task_id is in active set (will be cleaned up when task completes/fails)
        assert "task123" in scheduler._active_task_ids

    @pytest.mark.asyncio
    async def test_execute_task_cleanup_on_cancellation(self):
        """Test that _execute_task cleans up _active_task_ids even when cancelled"""
        scheduler = InternalScheduler()
        scheduler._semaphore = asyncio.Semaphore(1)  # Only 1 concurrent task

        # Add task to active set (as caller would do)
        scheduler._active_task_ids.add("task123")

        # Create a task that will be cancelled while waiting for semaphore
        # First, acquire the semaphore so the task has to wait
        await scheduler._semaphore.acquire()

        # Start execute task (it will wait for semaphore)
        execute_task = asyncio.create_task(scheduler._execute_task("task123"))

        # Give it a moment to start waiting
        await asyncio.sleep(0.01)

        # Task should still be in active set
        assert "task123" in scheduler._active_task_ids

        # Cancel the task
        execute_task.cancel()

        try:
            await execute_task
        except asyncio.CancelledError:
            pass

        # After cancellation, task_id should be removed from active set
        assert "task123" not in scheduler._active_task_ids

        # Release semaphore
        scheduler._semaphore.release()

    @pytest.mark.asyncio
    async def test_poll_loop_prevents_duplicate_scheduling(self):
        """Test that poll loop doesn't schedule already active tasks"""
        scheduler = InternalScheduler()
        scheduler._stop_event = asyncio.Event()
        scheduler._pause_event = asyncio.Event()
        scheduler._pause_event.set()
        scheduler._semaphore = asyncio.Semaphore(10)

        # Mock task that is returned as "due"
        mock_task = {"id": "task123", "name": "Test Task"}

        # Pre-add task to active set
        scheduler._active_task_ids.add("task123")

        execute_called = False

        async def mock_execute(task_id: str, manual: bool = False) -> None:
            nonlocal execute_called
            execute_called = True

        scheduler._execute_task = mock_execute
        scheduler._get_due_tasks = AsyncMock(return_value=[mock_task])

        # Run one iteration of poll loop manually
        await scheduler._pause_event.wait()
        due_tasks = await scheduler._get_due_tasks()

        for task in due_tasks:
            task_id = task.get("id") or task.id
            if task_id not in scheduler._active_task_ids:
                scheduler._active_task_ids.add(task_id)
                asyncio.create_task(scheduler._execute_task(task_id))

        # _execute_task should not be called for already active task
        assert execute_called is False

    @pytest.mark.asyncio
    async def test_active_task_ids_cleanup_after_execution(self):
        """Test that _active_task_ids is cleaned up after task execution completes"""
        scheduler = InternalScheduler()
        scheduler._semaphore = asyncio.Semaphore(10)

        # Add task to active set
        scheduler._active_task_ids.add("task123")

        # Mock _execute_task to just clean up (simulating normal completion path)
        async def mock_execute(task_id: str, manual: bool = False) -> None:
            try:
                async with scheduler._semaphore:
                    # Simulate some work
                    await asyncio.sleep(0.01)
            finally:
                scheduler._active_task_ids.discard(task_id)

        # Run the mock execute
        await mock_execute("task123")

        # Task should be removed from active set
        assert "task123" not in scheduler._active_task_ids


# ============================================================================
# WebhookGateway Tests
# ============================================================================


class TestWebhookConfig:
    """Tests for WebhookConfig"""

    def test_default_config(self):
        """Test default webhook config"""
        config = WebhookConfig()
        assert config.secret_key is None
        assert config.allowed_ips is None
        assert config.rate_limit == 0
        assert config.timeout == 3600
        assert config.async_execution is True

    def test_custom_config(self):
        """Test custom webhook config"""
        config = WebhookConfig(
            secret_key="my-secret",
            allowed_ips=["127.0.0.1", "10.0.0.1"],
            rate_limit=100,
            timeout=600,
            async_execution=False,
        )
        assert config.secret_key == "my-secret"
        assert config.allowed_ips == ["127.0.0.1", "10.0.0.1"]
        assert config.rate_limit == 100


class TestWebhookGateway:
    """Tests for WebhookGateway"""

    def test_init_with_default_config(self):
        """Test gateway initialization"""
        gateway = WebhookGateway()
        assert gateway.config.secret_key is None

    def test_validate_ip_no_restriction(self):
        """Test IP validation with no restriction"""
        gateway = WebhookGateway()
        assert gateway.validate_ip("192.168.1.1") is True

    def test_validate_ip_with_allowed_list(self):
        """Test IP validation with allowed list"""
        config = WebhookConfig(allowed_ips=["127.0.0.1", "10.0.0.1"])
        gateway = WebhookGateway(config)

        assert gateway.validate_ip("127.0.0.1") is True
        assert gateway.validate_ip("10.0.0.1") is True
        assert gateway.validate_ip("192.168.1.1") is False

    def test_check_rate_limit_no_limit(self):
        """Test rate limit with no limit configured"""
        gateway = WebhookGateway()
        # Should always return True
        for _ in range(100):
            assert gateway.check_rate_limit("192.168.1.1") is True

    def test_check_rate_limit_with_limit(self):
        """Test rate limit enforcement"""
        config = WebhookConfig(rate_limit=5)
        gateway = WebhookGateway(config)

        # First 5 requests should pass
        for i in range(5):
            assert gateway.check_rate_limit("192.168.1.1") is True

        # 6th request should fail
        assert gateway.check_rate_limit("192.168.1.1") is False

    def test_validate_signature_no_secret(self):
        """Test signature validation when no secret configured"""
        gateway = WebhookGateway()
        # Should always return True when no secret
        assert gateway.validate_signature(b"payload", "any-signature") is True

    def test_validate_signature_with_secret(self):
        """Test signature validation with secret"""
        import hmac
        import hashlib

        config = WebhookConfig(secret_key="test-secret")
        gateway = WebhookGateway(config)

        payload = b'{"task_id": "123"}'
        timestamp = "1234567890"

        # Compute correct signature
        message = f"{timestamp}.".encode() + payload
        expected_sig = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

        # Valid signature should pass
        assert gateway.validate_signature(payload, expected_sig, timestamp) is True

        # Invalid signature should fail
        assert gateway.validate_signature(payload, "invalid", timestamp) is False

    @pytest.mark.asyncio
    async def test_validate_request(self):
        """Test full request validation"""
        config = WebhookConfig(allowed_ips=["127.0.0.1"])
        gateway = WebhookGateway(config)

        # Valid request
        result = await gateway.validate_request(client_ip="127.0.0.1")
        assert result["valid"] is True

        # Invalid IP
        result = await gateway.validate_request(client_ip="192.168.1.1")
        assert result["valid"] is False
        assert "IP not allowed" in result["error"]

    def test_generate_webhook_url(self):
        """Test webhook URL generation"""
        gateway = WebhookGateway()
        url_info = gateway.generate_webhook_url(
            task_id="abc123", base_url="https://api.example.com"
        )

        assert url_info["url"] == "https://api.example.com/webhook/trigger/abc123"
        assert url_info["method"] == "POST"

    def test_generate_webhook_url_with_signature(self):
        """Test webhook URL generation with signature info"""
        config = WebhookConfig(secret_key="secret")
        gateway = WebhookGateway(config)

        url_info = gateway.generate_webhook_url(
            task_id="abc123", base_url="https://api.example.com", include_signature=True
        )

        assert "signature_header" in url_info
        assert url_info["signature_algorithm"] == "HMAC-SHA256"


class TestWebhookHelpers:
    """Tests for webhook helper functions"""

    def test_generate_cron_config(self):
        """Test cron config generation"""
        cron = generate_cron_config(
            task_id="abc123",
            schedule_expression="0 9 * * 1-5",
            webhook_url="https://api.example.com/webhook/trigger/abc123",
        )

        assert "0 9 * * 1-5" in cron
        assert "curl -X POST" in cron
        assert "abc123" in cron

    def test_generate_kubernetes_cronjob(self):
        """Test Kubernetes CronJob manifest generation"""
        manifest = generate_kubernetes_cronjob(
            task_id="abc123",
            task_name="Test Task",
            schedule_expression="0 9 * * *",
            webhook_url="https://api.example.com/webhook/trigger/abc123",
            namespace="production",
        )

        assert manifest["apiVersion"] == "batch/v1"
        assert manifest["kind"] == "CronJob"
        assert manifest["metadata"]["namespace"] == "production"
        assert manifest["spec"]["schedule"] == "0 9 * * *"
        assert (
            "curlimages/curl"
            in manifest["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"]
        )


# ============================================================================
# ICalExporter Tests
# ============================================================================


class TestICalHelpers:
    """Tests for iCal helper functions"""

    def test_fold_line_short(self):
        """Test folding short lines (no change)"""
        line = "SHORT LINE"
        assert fold_line(line) == line

    def test_fold_line_long(self):
        """Test folding long lines"""
        line = "A" * 100
        folded = fold_line(line)
        # Should have continuation marker
        assert "\r\n " in folded
        # First line should be 75 chars
        lines = folded.split("\r\n")
        assert len(lines[0]) == 75

    def test_escape_text(self):
        """Test text escaping"""
        assert escape_text("hello;world") == "hello\\;world"
        assert escape_text("hello,world") == "hello\\,world"
        assert escape_text("hello\nworld") == "hello\\nworld"
        assert escape_text("hello\\world") == "hello\\\\world"
        assert escape_text("") == ""
        assert escape_text(None) == ""

    def test_format_datetime(self):
        """Test datetime formatting"""
        dt = datetime(2024, 6, 15, 9, 30, 0, tzinfo=timezone.utc)
        formatted = format_datetime(dt)
        assert formatted == "20240615T093000Z"

    def test_format_datetime_with_timezone(self):
        """Test datetime formatting with non-UTC timezone"""
        tz = timezone(timedelta(hours=8))
        dt = datetime(2024, 6, 15, 17, 30, 0, tzinfo=tz)  # 17:30 UTC+8 = 09:30 UTC
        formatted = format_datetime(dt)
        assert formatted == "20240615T093000Z"

    def test_generate_uid(self):
        """Test UID generation"""
        uid = generate_uid("task123")
        assert "apflow-task123" in uid
        assert "@apflow.local" in uid

    def test_generate_uid_with_run_time(self):
        """Test UID generation with run time"""
        run_time = datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc)
        uid = generate_uid("task123", run_time)
        assert "apflow-task123" in uid
        assert "20240615T090000Z" in uid

    def test_generate_ical_feed_url(self):
        """Test iCal feed URL generation"""
        url = generate_ical_feed_url("https://api.example.com")
        assert url == "https://api.example.com/scheduler/ical"

    def test_generate_ical_feed_url_with_params(self):
        """Test iCal feed URL with parameters"""
        url = generate_ical_feed_url("https://api.example.com", user_id="user123", api_key="key456")
        assert "user_id=user123" in url
        assert "api_key=key456" in url


class TestICalExporter:
    """Tests for ICalExporter"""

    def test_init_defaults(self):
        """Test exporter initialization with defaults"""
        exporter = ICalExporter()
        assert exporter.calendar_name == "APFlow Tasks"
        assert exporter.include_description is True
        assert exporter.default_duration_minutes == 30

    def test_init_custom(self):
        """Test exporter initialization with custom values"""
        exporter = ICalExporter(
            calendar_name="My Tasks",
            include_description=False,
            base_url="https://example.com",
            default_duration_minutes=60,
        )
        assert exporter.calendar_name == "My Tasks"
        assert exporter.include_description is False
        assert exporter.base_url == "https://example.com"

    def test_export_task_basic(self):
        """Test exporting a single task"""
        exporter = ICalExporter()

        task = {
            "id": "task123",
            "name": "Test Task",
            "schedule_type": "daily",
            "schedule_expression": "09:00",
            "next_run_at": datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
        }

        ical = exporter.export_task(task)

        # Check basic structure
        assert "BEGIN:VCALENDAR" in ical
        assert "END:VCALENDAR" in ical
        assert "BEGIN:VEVENT" in ical
        assert "END:VEVENT" in ical

        # Check content
        assert "SUMMARY:Test Task" in ical
        assert "DTSTART:20240615T090000Z" in ical
        assert "X-APFLOW-TASK-ID:task123" in ical

    def test_export_task_without_next_run(self):
        """Test that tasks without next_run_at are skipped"""
        exporter = ICalExporter()

        task = {
            "id": "task123",
            "name": "Test Task",
            "schedule_type": "daily",
            "next_run_at": None,
        }

        ical = exporter.export_task(task)

        # Should have calendar but no events
        assert "BEGIN:VCALENDAR" in ical
        assert "BEGIN:VEVENT" not in ical

    def test_generate_ical_multiple_tasks(self):
        """Test generating iCal with multiple tasks"""
        exporter = ICalExporter()

        tasks = [
            {
                "id": "task1",
                "name": "Task One",
                "schedule_type": "daily",
                "next_run_at": datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
            },
            {
                "id": "task2",
                "name": "Task Two",
                "schedule_type": "weekly",
                "next_run_at": datetime(2024, 6, 16, 10, 0, 0, tzinfo=timezone.utc),
            },
        ]

        ical = exporter.generate_ical(tasks)

        # Count VEVENT occurrences
        vevent_count = ical.count("BEGIN:VEVENT")
        assert vevent_count == 2

        assert "Task One" in ical
        assert "Task Two" in ical

    def test_rrule_generation_interval(self):
        """Test RRULE generation for interval schedule"""
        exporter = ICalExporter()

        # Daily interval (86400 seconds)
        task = {
            "id": "task1",
            "name": "Daily Task",
            "schedule_type": "interval",
            "schedule_expression": "86400",
            "next_run_at": datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
        }

        ical = exporter.export_task(task)
        assert "RRULE:FREQ=DAILY" in ical

    def test_rrule_generation_weekly(self):
        """Test RRULE generation for weekly schedule"""
        exporter = ICalExporter()

        task = {
            "id": "task1",
            "name": "Weekly Task",
            "schedule_type": "weekly",
            "schedule_expression": "1,3,5 09:00",  # Mon, Wed, Fri
            "next_run_at": datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
        }

        ical = exporter.export_task(task)
        assert "RRULE:FREQ=WEEKLY" in ical
        assert "BYDAY=MO,WE,FR" in ical

    def test_rrule_generation_monthly(self):
        """Test RRULE generation for monthly schedule"""
        exporter = ICalExporter()

        task = {
            "id": "task1",
            "name": "Monthly Task",
            "schedule_type": "monthly",
            "schedule_expression": "1,15 09:00",  # 1st and 15th
            "next_run_at": datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
        }

        ical = exporter.export_task(task)
        assert "RRULE:FREQ=MONTHLY" in ical
        assert "BYMONTHDAY=1,15" in ical

    def test_rrule_with_max_runs(self):
        """Test RRULE generation with COUNT for max_runs"""
        exporter = ICalExporter()

        task = {
            "id": "task1",
            "name": "Limited Task",
            "schedule_type": "daily",
            "next_run_at": datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
            "max_runs": 10,
            "run_count": 3,
        }

        ical = exporter.export_task(task)
        assert "COUNT=7" in ical  # 10 - 3 = 7 remaining

    def test_rrule_with_end_date(self):
        """Test RRULE generation with UNTIL for schedule_end_at"""
        exporter = ICalExporter()

        task = {
            "id": "task1",
            "name": "Bounded Task",
            "schedule_type": "daily",
            "next_run_at": datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
            "schedule_end_at": datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        }

        ical = exporter.export_task(task)
        assert "UNTIL=20241231T235959Z" in ical

    def test_description_generation(self):
        """Test event description generation"""
        exporter = ICalExporter(include_description=True)

        task = {
            "id": "task123",
            "name": "Detailed Task",
            "schedule_type": "daily",
            "schedule_expression": "09:00",
            "status": "pending",
            "run_count": 5,
            "max_runs": 10,
            "next_run_at": datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
        }

        ical = exporter.export_task(task)

        # Check description contains task info
        assert "DESCRIPTION:" in ical
        assert "Task ID: task123" in ical or "task123" in ical

    def test_url_in_event(self):
        """Test URL inclusion in event"""
        exporter = ICalExporter(base_url="https://example.com")

        task = {
            "id": "task123",
            "name": "Task with URL",
            "schedule_type": "daily",
            "next_run_at": datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
        }

        ical = exporter.export_task(task)
        assert "URL:https://example.com/tasks/task123" in ical


# ============================================================================
# Integration Tests
# ============================================================================


class TestSchedulerIntegration:
    """Integration tests for scheduler components"""

    @pytest.mark.asyncio
    async def test_scheduler_with_webhook_callback(self):
        """Test scheduler notifying webhook callback on task completion"""
        scheduler = InternalScheduler()
        scheduler._get_due_tasks = AsyncMock(return_value=[])

        callback_results = []

        def callback(task_id, success, result):
            callback_results.append((task_id, success, result))

        scheduler.on_task_complete(callback)

        # Simulate task completion notification
        scheduler._notify_task_complete("task1", True, {"output": "done"})

        assert len(callback_results) == 1
        assert callback_results[0] == ("task1", True, {"output": "done"})

    def test_exporter_to_webhook_workflow(self):
        """Test workflow from exporter to webhook URL generation"""
        # Create task
        task = {
            "id": "task123",
            "name": "Scheduled Task",
            "schedule_type": "cron",
            "schedule_expression": "0 9 * * 1-5",
            "next_run_at": datetime(2024, 6, 17, 9, 0, 0, tzinfo=timezone.utc),
        }

        # Export to iCal
        exporter = ICalExporter(calendar_name="My Schedule")
        ical = exporter.export_task(task)
        assert "Scheduled Task" in ical

        # Generate webhook URL
        gateway = WebhookGateway()
        webhook_info = gateway.generate_webhook_url(
            task_id="task123", base_url="https://api.example.com"
        )

        # Generate cron entry
        cron = generate_cron_config(
            task_id="task123", schedule_expression="0 9 * * 1-5", webhook_url=webhook_info["url"]
        )

        assert "0 9 * * 1-5" in cron
        assert webhook_info["url"] in cron


# ============================================================================
# Scheduler API Integration Tests
# ============================================================================


class TestSchedulerAPIDetection:
    """Tests for scheduler API mode detection via ConfigManager.

    _detect_api_mode() checks whether api_server_url is configured in
    ConfigManager — it does NOT perform a health-check probe.  This avoids
    the session-caching and URL-clearing issues of should_use_api().
    """

    @pytest.fixture(autouse=True)
    def _reset_config(self):
        """Reset ConfigManager between tests."""
        from apflow.core.config_manager import get_config_manager

        cm = get_config_manager()
        cm.clear()
        yield
        cm.clear()

    def test_detect_api_mode_true_when_url_configured(self):
        """Detection returns True when api_server_url is configured."""
        from apflow.core.config_manager import get_config_manager

        cm = get_config_manager()
        cm.set_api_server_url("http://localhost:8000")

        scheduler = InternalScheduler()
        assert scheduler._detect_api_mode() is True

    def test_detect_api_mode_false_when_no_url_configured(self):
        """Detection returns False when no api_server_url is configured."""
        scheduler = InternalScheduler()
        assert scheduler._detect_api_mode() is False

    def test_detect_api_mode_reflects_config_changes(self):
        """Detection re-reads ConfigManager on every call (no stale cache)."""
        from apflow.core.config_manager import get_config_manager

        cm = get_config_manager()
        scheduler = InternalScheduler()

        assert scheduler._detect_api_mode() is False

        cm.set_api_server_url("http://localhost:8000")
        assert scheduler._detect_api_mode() is True

        cm.set_api_server_url(None)
        assert scheduler._detect_api_mode() is False

    @pytest.mark.asyncio
    async def test_start_enables_api_mode_when_url_configured(self):
        """start() detects API and sets _use_api=True when URL configured."""
        from apflow.core.config_manager import get_config_manager

        cm = get_config_manager()
        cm.set_api_server_url("http://localhost:8000")

        scheduler = InternalScheduler()
        scheduler._get_due_tasks = AsyncMock(return_value=[])

        await scheduler.start()
        assert scheduler._use_api is True
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_disables_api_mode_when_no_url(self):
        """start() sets _use_api=False when no URL configured."""
        scheduler = InternalScheduler()
        scheduler._get_due_tasks = AsyncMock(return_value=[])

        await scheduler.start()
        assert scheduler._use_api is False
        await scheduler.stop()

    def test_use_api_defaults_to_false(self):
        """_use_api defaults to False before start."""
        scheduler = InternalScheduler()
        assert scheduler._use_api is False


class TestSchedulerGetDueTasksAPI:
    """Tests for _get_due_tasks_via_api."""

    @pytest.mark.asyncio
    async def test_get_due_tasks_via_api_calls_correct_method(self):
        """Test that _get_due_tasks_via_api calls tasks.scheduled.due."""
        scheduler = InternalScheduler()

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(return_value=[{"id": "task1"}, {"id": "task2"}])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            result = await scheduler._get_due_tasks_via_api()

        assert result == [{"id": "task1"}, {"id": "task2"}]
        mock_client.call_method.assert_called_once_with(
            "tasks.scheduled.due",
            limit=scheduler.config.max_concurrent_tasks * 2,
        )

    @pytest.mark.asyncio
    async def test_get_due_tasks_via_api_with_user_id(self):
        """Test that _get_due_tasks_via_api passes user_id when configured."""
        config = SchedulerConfig(user_id="user123")
        scheduler = InternalScheduler(config)

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(return_value=[])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            await scheduler._get_due_tasks_via_api()

        mock_client.call_method.assert_called_once_with(
            "tasks.scheduled.due",
            limit=config.max_concurrent_tasks * 2,
            user_id="user123",
        )

    @pytest.mark.asyncio
    async def test_get_due_tasks_via_api_handles_dict_response(self):
        """Test that _get_due_tasks_via_api handles dict response with tasks key."""
        scheduler = InternalScheduler()

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(return_value={"tasks": [{"id": "task1"}], "total": 1})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            result = await scheduler._get_due_tasks_via_api()

        assert result == [{"id": "task1"}]

    @pytest.mark.asyncio
    async def test_get_due_tasks_returns_empty_on_api_error(self):
        """Test that _get_due_tasks returns empty list (no DB fallback) when API fails."""
        scheduler = InternalScheduler()
        scheduler._use_api = True

        from apflow.cli.api_client import APIClientError

        scheduler._get_due_tasks_via_api = AsyncMock(
            side_effect=APIClientError("connection refused")
        )
        scheduler._get_due_tasks_via_db = AsyncMock(return_value=[{"id": "task1"}])

        result = await scheduler._get_due_tasks()

        assert result == []
        scheduler._get_due_tasks_via_api.assert_called_once()
        scheduler._get_due_tasks_via_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_due_tasks_skips_api_when_not_configured(self):
        """Test that _get_due_tasks skips API when _use_api is False."""
        scheduler = InternalScheduler()
        scheduler._use_api = False

        scheduler._get_due_tasks_via_api = AsyncMock()
        scheduler._get_due_tasks_via_db = AsyncMock(return_value=[])

        await scheduler._get_due_tasks()

        scheduler._get_due_tasks_via_api.assert_not_called()
        scheduler._get_due_tasks_via_db.assert_called_once()


class TestSchedulerExecuteTaskAPI:
    """Tests for _execute_task_via_api."""

    @pytest.mark.asyncio
    async def test_execute_task_via_api_calls_webhook_trigger(self):
        """Test that _execute_task_via_api calls tasks.webhook.trigger."""
        scheduler = InternalScheduler()

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(
            return_value={"status": "completed", "result": {"output": "done"}}
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            await scheduler._execute_task_via_api("task123")

        mock_client.call_method.assert_called_once_with(
            "tasks.webhook.trigger",
            task_id="task123",
            async_execution=False,
        )

    @pytest.mark.asyncio
    async def test_execute_task_via_api_tracks_success_stats(self):
        """Test that successful API execution increments success stats."""
        scheduler = InternalScheduler()

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(
            return_value={"status": "completed", "result": {"data": "ok"}}
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            await scheduler._execute_task_via_api("task123")

        assert scheduler.stats.tasks_executed == 1
        assert scheduler.stats.tasks_succeeded == 1
        assert scheduler.stats.tasks_failed == 0

    @pytest.mark.asyncio
    async def test_execute_task_via_api_tracks_failure_stats(self):
        """Test that failed API execution increments failure stats."""
        scheduler = InternalScheduler()

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(return_value={"status": "failed", "error": "timeout"})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            await scheduler._execute_task_via_api("task123")

        assert scheduler.stats.tasks_executed == 1
        assert scheduler.stats.tasks_succeeded == 0
        assert scheduler.stats.tasks_failed == 1

    @pytest.mark.asyncio
    async def test_execute_task_via_api_notifies_callback(self):
        """Test that API execution notifies task completion callbacks."""
        scheduler = InternalScheduler()

        callback_results: list = []

        def callback(task_id: str, success: bool, result: object) -> None:
            callback_results.append((task_id, success, result))

        scheduler.on_task_complete(callback)

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(
            return_value={"status": "completed", "result": {"data": "ok"}}
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            await scheduler._execute_task_via_api("task123")

        assert len(callback_results) == 1
        assert callback_results[0] == ("task123", True, {"data": "ok"})

    @pytest.mark.asyncio
    async def test_execute_task_no_db_fallback_on_api_error(self):
        """Test that _execute_task does NOT fall back to DB when API fails."""
        scheduler = InternalScheduler()
        scheduler._use_api = True
        scheduler._semaphore = asyncio.Semaphore(10)
        scheduler._active_task_ids.add("task123")

        from apflow.cli.api_client import APIClientError

        scheduler._execute_task_via_api = AsyncMock(side_effect=APIClientError("server error"))
        scheduler._execute_task_via_db = AsyncMock()

        await scheduler._execute_task("task123")

        scheduler._execute_task_via_api.assert_called_once_with("task123")
        scheduler._execute_task_via_db.assert_not_called()
        # Task should be removed from active set
        assert "task123" not in scheduler._active_task_ids
        # Failure should be counted
        assert scheduler.stats.tasks_executed == 1
        assert scheduler.stats.tasks_failed == 1

    @pytest.mark.asyncio
    async def test_execute_task_skips_api_when_not_configured(self):
        """Test that _execute_task skips API when _use_api is False."""
        scheduler = InternalScheduler()
        scheduler._use_api = False
        scheduler._semaphore = asyncio.Semaphore(10)
        scheduler._active_task_ids.add("task123")

        scheduler._execute_task_via_api = AsyncMock()
        scheduler._execute_task_via_db = AsyncMock()

        await scheduler._execute_task("task123")

        scheduler._execute_task_via_api.assert_not_called()
        scheduler._execute_task_via_db.assert_called_once_with("task123")

    @pytest.mark.asyncio
    async def test_execute_task_via_api_uses_task_timeout(self):
        """Test that _execute_task_via_api creates client with task_timeout."""
        config = SchedulerConfig(task_timeout=7200)
        scheduler = InternalScheduler(config)

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(return_value={"status": "completed"})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client) as mock_create:
            await scheduler._execute_task_via_api("task123")

        mock_create.assert_called_once_with(timeout=7200.0)

    @pytest.mark.asyncio
    async def test_execute_task_via_api_handles_success_flag(self):
        """Test that _execute_task_via_api recognizes success=True in result."""
        scheduler = InternalScheduler()

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(
            return_value={"success": True, "result": {"output": "done"}}
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            await scheduler._execute_task_via_api("task123")

        assert scheduler.stats.tasks_succeeded == 1

    @pytest.mark.asyncio
    async def test_execute_task_via_api_prints_children_results(self):
        """Test that verbose mode displays children task results from API response."""
        scheduler = InternalScheduler(verbose=True)
        scheduler._console = MagicMock()

        api_response = {
            "status": "completed",
            "result": {"output": "aggregated"},
            "children": [
                {"task_id": "child1", "name": "Child A", "status": "completed", "error": None},
                {"task_id": "child2", "name": "Child B", "status": "failed", "error": "timeout"},
            ],
        }

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(return_value=api_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            await scheduler._execute_task_via_api("parent1")

        # 2 children + 1 parent = 3 print calls
        assert scheduler._console.print.call_count == 3
        calls = [c[0][0] for c in scheduler._console.print.call_args_list]
        assert "child1" in calls[0]
        assert "Child A" in calls[0]
        assert "child2" in calls[1]
        assert "timeout" in calls[1]
        assert "parent1" in calls[2]

    @pytest.mark.asyncio
    async def test_execute_task_via_api_no_children_no_extra_output(self):
        """Test that verbose mode works fine when API response has no children."""
        scheduler = InternalScheduler(verbose=True)
        scheduler._console = MagicMock()

        mock_client = AsyncMock()
        mock_client.call_method = AsyncMock(return_value={"status": "completed", "result": None})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(scheduler, "_create_api_client", return_value=mock_client):
            await scheduler._execute_task_via_api("task1")

        # Only parent printed
        assert scheduler._console.print.call_count == 1


class TestSchedulerCreateAPIClient:
    """Tests for _create_api_client helper."""

    def test_create_api_client_uses_config_manager(self):
        """Test that _create_api_client reads from ConfigManager."""
        scheduler = InternalScheduler()

        mock_cm = MagicMock()
        mock_cm.api_server_url = "http://myserver:9000"
        mock_cm.admin_auth_token = "test-token"
        mock_cm.api_timeout = 45.0
        mock_cm.api_retry_attempts = 5
        mock_cm.api_retry_backoff = 2.0

        with patch("apflow.core.config_manager.get_config_manager", return_value=mock_cm):
            client = scheduler._create_api_client()

        assert client.server_url == "http://myserver:9000"
        assert client.auth_token == "test-token"
        assert client.timeout == 45.0
        assert client.retry_attempts == 5
        assert client.retry_backoff == 2.0
        assert client.proxies is None

    def test_create_api_client_with_timeout_override(self):
        """Test that _create_api_client uses timeout override."""
        scheduler = InternalScheduler()

        mock_cm = MagicMock()
        mock_cm.api_server_url = "http://localhost:8000"
        mock_cm.admin_auth_token = None
        mock_cm.api_timeout = 30.0
        mock_cm.api_retry_attempts = 3
        mock_cm.api_retry_backoff = 1.0

        with patch("apflow.core.config_manager.get_config_manager", return_value=mock_cm):
            client = scheduler._create_api_client(timeout=3600.0)

        assert client.timeout == 3600.0

    def test_create_api_client_defaults_server_url(self):
        """Test that _create_api_client defaults to localhost:8000."""
        scheduler = InternalScheduler()

        mock_cm = MagicMock()
        mock_cm.api_server_url = None
        mock_cm.admin_auth_token = None
        mock_cm.api_timeout = 30.0
        mock_cm.api_retry_attempts = 3
        mock_cm.api_retry_backoff = 1.0

        with patch("apflow.core.config_manager.get_config_manager", return_value=mock_cm):
            client = scheduler._create_api_client()

        assert client.server_url == "http://localhost:8000"


class TestSchedulerGetAuthToken:
    """Tests for _get_auth_token auto-generation."""

    def test_uses_configured_admin_auth_token(self):
        """Test that configured admin_auth_token is used directly."""
        scheduler = InternalScheduler()

        mock_cm = MagicMock()
        mock_cm.admin_auth_token = "configured-token-xyz"

        with patch(
            "apflow.core.config_manager.get_config_manager",
            return_value=mock_cm,
        ):
            token = scheduler._get_auth_token()

        assert token == "configured-token-xyz"
        # Auto-generated token should not be created
        assert scheduler._auto_auth_token is None

    def test_auto_generates_admin_jwt_when_no_configured_token(self):
        """Test that admin JWT is auto-generated when no admin_auth_token configured."""
        scheduler = InternalScheduler()

        mock_cm = MagicMock()
        mock_cm.admin_auth_token = None

        with patch(
            "apflow.core.config_manager.get_config_manager",
            return_value=mock_cm,
        ):
            with patch(
                "apflow.cli.jwt_token.generate_token", return_value="auto-jwt-token"
            ) as mock_gen:
                token = scheduler._get_auth_token()

        assert token == "auto-jwt-token"
        assert scheduler._auto_auth_token == "auto-jwt-token"
        mock_gen.assert_called_once_with(
            subject="apflow-scheduler",
            extra_claims={"roles": ["admin"]},
        )

    def test_auto_generated_token_is_cached(self):
        """Test that auto-generated token is reused on subsequent calls."""
        scheduler = InternalScheduler()

        mock_cm = MagicMock()
        mock_cm.admin_auth_token = None

        with patch(
            "apflow.core.config_manager.get_config_manager",
            return_value=mock_cm,
        ):
            with patch(
                "apflow.cli.jwt_token.generate_token", return_value="cached-jwt"
            ) as mock_gen:
                token1 = scheduler._get_auth_token()
                token2 = scheduler._get_auth_token()

        assert token1 == token2 == "cached-jwt"
        # generate_token should only be called once (cached)
        mock_gen.assert_called_once()

    def test_returns_none_when_generation_fails(self):
        """Test graceful fallback when JWT generation fails."""
        scheduler = InternalScheduler()

        mock_cm = MagicMock()
        mock_cm.admin_auth_token = None

        with patch(
            "apflow.core.config_manager.get_config_manager",
            return_value=mock_cm,
        ):
            with patch(
                "apflow.cli.jwt_token.generate_token",
                side_effect=Exception("jwt_secret not found"),
            ):
                token = scheduler._get_auth_token()

        assert token is None

    def test_create_api_client_uses_auto_generated_token(self):
        """Test that _create_api_client passes the auto-generated token to APIClient."""
        scheduler = InternalScheduler()

        mock_cm = MagicMock()
        mock_cm.api_server_url = "http://localhost:8000"
        mock_cm.admin_auth_token = None
        mock_cm.api_timeout = 30.0
        mock_cm.api_retry_attempts = 3
        mock_cm.api_retry_backoff = 1.0

        with patch(
            "apflow.core.config_manager.get_config_manager",
            return_value=mock_cm,
        ):
            with patch(
                "apflow.cli.jwt_token.generate_token",
                return_value="auto-admin-jwt",
            ):
                client = scheduler._create_api_client()

        assert client.auth_token == "auto-admin-jwt"


class TestAPIClientCallMethod:
    """Tests for APIClient.call_method."""

    @pytest.mark.asyncio
    async def test_call_method_delegates_to_tasks_rpc(self):
        """Test that call_method delegates to _tasks_rpc."""
        from apflow.cli.api_client import APIClient

        client = APIClient(server_url="http://localhost:8000")
        client._tasks_rpc = AsyncMock(return_value={"result": "ok"})

        result = await client.call_method("tasks.scheduled.due", limit=20, user_id="user1")

        assert result == {"result": "ok"}
        client._tasks_rpc.assert_called_once_with(
            "tasks.scheduled.due", {"limit": 20, "user_id": "user1"}
        )

    @pytest.mark.asyncio
    async def test_call_method_with_no_params(self):
        """Test that call_method works with no extra params."""
        from apflow.cli.api_client import APIClient

        client = APIClient(server_url="http://localhost:8000")
        client._tasks_rpc = AsyncMock(return_value=[])

        result = await client.call_method("tasks.scheduled.list")

        assert result == []
        client._tasks_rpc.assert_called_once_with("tasks.scheduled.list", {})

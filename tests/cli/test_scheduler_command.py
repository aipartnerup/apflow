"""
Test CLI scheduler command functionality

Tests the scheduler command:
- scheduler start (foreground and background modes)
- scheduler stop
- scheduler status
- scheduler trigger
- scheduler export-ical
- scheduler webhook-url

Tests use mocks by default to avoid starting real processes.
"""

import re

import click
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from apflow.cli.main import cli
from apflow.cli.commands.scheduler import (
    get_pid_file,
    get_log_file,
    read_pid,
    write_pid,
    remove_pid,
    is_process_running,
)

# mix_stderr was added in Click 8.0
_click_major = int(click.__version__.split(".")[0])
runner = CliRunner(mix_stderr=False) if _click_major >= 8 else CliRunner()


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_pattern.sub("", text)


@pytest.fixture
def cleanup_scheduler_files():
    """Cleanup scheduler PID and log files before and after tests"""
    pid_file = get_pid_file()
    log_file = get_log_file()

    # Cleanup before
    if pid_file.exists():
        pid_file.unlink()
    if log_file.exists():
        log_file.unlink()

    yield

    # Cleanup after
    if pid_file.exists():
        pid_file.unlink()
    if log_file.exists():
        log_file.unlink()


class TestSchedulerCommandHelp:
    """Tests for scheduler command help output"""

    def test_scheduler_help(self):
        """Test scheduler command help output"""
        result = runner.invoke(cli, ["scheduler", "--help"])
        assert result.exit_code == 0
        assert "Manage task scheduler" in result.stdout

    def test_scheduler_start_help(self):
        """Test scheduler start subcommand help"""
        result = runner.invoke(cli, ["scheduler", "start", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Start the internal scheduler" in output
        assert "--poll-interval" in output
        assert "--max-concurrent" in output
        assert "--background" in output
        assert "--timeout" in output

    def test_scheduler_stop_help(self):
        """Test scheduler stop subcommand help"""
        result = runner.invoke(cli, ["scheduler", "stop", "--help"])
        assert result.exit_code == 0
        assert "Stop the running scheduler" in result.stdout

    def test_scheduler_status_help(self):
        """Test scheduler status subcommand help"""
        result = runner.invoke(cli, ["scheduler", "status", "--help"])
        assert result.exit_code == 0
        assert "Show scheduler status" in result.stdout

    def test_scheduler_trigger_help(self):
        """Test scheduler trigger subcommand help"""
        result = runner.invoke(cli, ["scheduler", "trigger", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Manually trigger a scheduled task" in output
        assert "--wait" in output

    def test_scheduler_export_ical_help(self):
        """Test scheduler export-ical subcommand help"""
        result = runner.invoke(cli, ["scheduler", "export-ical", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Export scheduled tasks as iCalendar" in output
        assert "--output" in output
        assert "--user-id" in output
        assert "--name" in output

    def test_scheduler_webhook_url_help(self):
        """Test scheduler webhook-url subcommand help"""
        result = runner.invoke(cli, ["scheduler", "webhook-url", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Generate webhook URL for a task" in output
        assert "--base-url" in output


class TestSchedulerPidFunctions:
    """Tests for PID file helper functions"""

    def test_get_pid_file_returns_path(self):
        """Test get_pid_file returns a Path object"""
        pid_file = get_pid_file()
        assert pid_file is not None
        assert hasattr(pid_file, "exists")

    def test_get_log_file_returns_path(self):
        """Test get_log_file returns a Path object"""
        log_file = get_log_file()
        assert log_file is not None
        assert hasattr(log_file, "exists")

    def test_write_and_read_pid(self, cleanup_scheduler_files):
        """Test write_pid and read_pid functions"""
        write_pid(12345)
        assert read_pid() == 12345

    def test_read_pid_no_file(self, cleanup_scheduler_files):
        """Test read_pid when no file exists"""
        assert read_pid() is None

    def test_remove_pid(self, cleanup_scheduler_files):
        """Test remove_pid function"""
        write_pid(99999)
        assert read_pid() == 99999
        remove_pid()
        assert read_pid() is None

    @patch("apflow.cli.commands.scheduler.os.kill")
    def test_is_process_running_true(self, mock_kill):
        """Test is_process_running returns True for running process"""
        mock_kill.return_value = None  # os.kill with signal 0 returns None if process exists
        assert is_process_running(12345) is True
        mock_kill.assert_called_once_with(12345, 0)

    @patch("apflow.cli.commands.scheduler.os.kill")
    def test_is_process_running_false(self, mock_kill):
        """Test is_process_running returns False for non-existent process"""
        mock_kill.side_effect = OSError("No such process")
        assert is_process_running(99999) is False


class TestSchedulerStatus:
    """Tests for scheduler status command"""

    def test_scheduler_status_not_running(self, cleanup_scheduler_files):
        """Test scheduler status when no scheduler is running"""
        result = runner.invoke(cli, ["scheduler", "status"])
        assert result.exit_code == 0
        assert "Not running" in result.stdout

    @patch("apflow.cli.commands.scheduler.is_process_running")
    def test_scheduler_status_running(self, mock_is_running, cleanup_scheduler_files):
        """Test scheduler status when scheduler is running"""
        write_pid(55555)
        mock_is_running.return_value = True

        result = runner.invoke(cli, ["scheduler", "status"])

        assert result.exit_code == 0
        assert "Running" in result.stdout
        assert "55555" in result.stdout

    @patch("apflow.cli.commands.scheduler.is_process_running")
    def test_scheduler_status_stale_pid(self, mock_is_running, cleanup_scheduler_files):
        """Test scheduler status with stale PID file"""
        write_pid(88888)
        mock_is_running.return_value = False

        result = runner.invoke(cli, ["scheduler", "status"])

        assert result.exit_code == 0
        assert "Stale" in result.stdout


class TestSchedulerStart:
    """Tests for scheduler start command"""

    @patch("apflow.cli.commands.scheduler.is_process_running")
    def test_scheduler_start_already_running(self, mock_is_running, cleanup_scheduler_files):
        """Test scheduler start when already running"""
        write_pid(12345)
        mock_is_running.return_value = True

        result = runner.invoke(cli, ["scheduler", "start", "--background"])

        assert result.exit_code == 1
        assert "already running" in result.stdout

    def test_scheduler_start_background(self, cleanup_scheduler_files):
        """Test scheduler start in background mode"""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            result = runner.invoke(
                cli,
                [
                    "scheduler",
                    "start",
                    "--background",
                    "--poll-interval",
                    "30",
                    "--max-concurrent",
                    "5",
                ],
            )

            assert result.exit_code == 0
            assert "started in background" in result.stdout
            assert "12345" in result.stdout
            assert read_pid() == 12345

    def test_scheduler_start_background_with_user_id(self, cleanup_scheduler_files):
        """Test scheduler start with user ID filter"""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 54321
            mock_popen.return_value = mock_process

            result = runner.invoke(
                cli,
                [
                    "scheduler",
                    "start",
                    "--background",
                    "--user-id",
                    "user123",
                ],
            )

            assert result.exit_code == 0
            assert "started in background" in result.stdout

            # Verify user-id was passed to command
            call_args = mock_popen.call_args[0][0]
            assert "--user-id" in call_args
            assert "user123" in call_args

    def test_scheduler_start_removes_stale_pid(self, cleanup_scheduler_files):
        """Test scheduler start removes stale PID file"""
        write_pid(99999)

        with patch("apflow.cli.commands.scheduler.is_process_running", return_value=False):
            with patch("subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.pid = 11111
                mock_popen.return_value = mock_process

                result = runner.invoke(cli, ["scheduler", "start", "--background"])

                assert result.exit_code == 0
                assert read_pid() == 11111


class TestSchedulerStop:
    """Tests for scheduler stop command"""

    def test_scheduler_stop_not_running(self, cleanup_scheduler_files):
        """Test scheduler stop when no scheduler is running"""
        result = runner.invoke(cli, ["scheduler", "stop"])
        assert result.exit_code == 0
        assert "No scheduler is running" in result.stdout

    @patch("apflow.cli.commands.scheduler.is_process_running")
    def test_scheduler_stop_stale_pid(self, mock_is_running, cleanup_scheduler_files):
        """Test scheduler stop with stale PID file"""
        write_pid(77777)
        mock_is_running.return_value = False

        result = runner.invoke(cli, ["scheduler", "stop"])

        assert result.exit_code == 0
        assert "stale PID file" in result.stdout
        assert read_pid() is None

    @patch("apflow.cli.commands.scheduler.is_process_running")
    @patch("apflow.cli.commands.scheduler.os.kill")
    def test_scheduler_stop_success(self, mock_kill, mock_is_running, cleanup_scheduler_files):
        """Test scheduler stop with running scheduler"""
        write_pid(66666)
        mock_is_running.side_effect = [True] + [False] * 10

        result = runner.invoke(cli, ["scheduler", "stop"])

        assert result.exit_code == 0
        assert "Scheduler stopped" in result.stdout
        assert mock_kill.called
        assert read_pid() is None

    def test_scheduler_stop_sigkill_fallback(self, cleanup_scheduler_files):
        """Test scheduler stop with SIGKILL fallback when process doesn't die gracefully"""
        import signal
        import time as time_module

        write_pid(44444)

        with patch("apflow.cli.commands.scheduler.is_process_running") as mock_is_running:
            with patch("apflow.cli.commands.scheduler.os.kill") as mock_kill:
                # Patch time.sleep globally since it's imported inside the function
                with patch.object(time_module, "sleep", lambda s: None):
                    # Process never dies from SIGTERM (32 checks: 1 initial + 30 loop + 1 final)
                    # Then dies after SIGKILL
                    mock_is_running.side_effect = [True] * 32 + [False]

                    result = runner.invoke(cli, ["scheduler", "stop"])

                    assert result.exit_code == 0
                    # Verify SIGKILL was sent
                    kill_calls = mock_kill.call_args_list
                    assert any(call[0][1] == signal.SIGKILL for call in kill_calls)


class TestSchedulerTrigger:
    """Tests for scheduler trigger command"""

    def test_scheduler_trigger_missing_task_id(self):
        """Test scheduler trigger without task ID"""
        result = runner.invoke(cli, ["scheduler", "trigger"])
        assert result.exit_code != 0
        # Error output may go to stdout or stderr depending on Rich/Click configuration
        combined_output = strip_ansi(result.stdout + (result.stderr or ""))
        assert "Missing argument" in combined_output or "TASK_ID" in combined_output

    @patch("apflow.cli.commands.scheduler.asyncio.run")
    def test_scheduler_trigger_success(self, mock_asyncio_run):
        """Test scheduler trigger with successful execution"""
        mock_asyncio_run.return_value = {"success": True, "status": "completed"}

        result = runner.invoke(cli, ["scheduler", "trigger", "task-123"])

        assert result.exit_code == 0
        assert "triggered successfully" in result.stdout

    @patch("apflow.cli.commands.scheduler.asyncio.run")
    def test_scheduler_trigger_with_wait(self, mock_asyncio_run):
        """Test scheduler trigger with --wait flag"""
        mock_asyncio_run.return_value = {
            "success": True,
            "status": "completed",
            "result": {"output": "done"},
        }

        result = runner.invoke(cli, ["scheduler", "trigger", "task-123", "--wait"])

        assert result.exit_code == 0
        assert "triggered successfully" in result.stdout

    @patch("apflow.cli.commands.scheduler.asyncio.run")
    def test_scheduler_trigger_failure(self, mock_asyncio_run):
        """Test scheduler trigger with failed execution"""
        mock_asyncio_run.return_value = {"success": False, "error": "Task not found"}

        result = runner.invoke(cli, ["scheduler", "trigger", "nonexistent-task"])

        assert result.exit_code == 1
        assert "Failed to trigger task" in result.stdout

    @patch("apflow.cli.commands.scheduler.asyncio.run")
    def test_scheduler_trigger_exception(self, mock_asyncio_run):
        """Test scheduler trigger with exception"""
        mock_asyncio_run.side_effect = Exception("Connection error")

        result = runner.invoke(cli, ["scheduler", "trigger", "task-123"])

        assert result.exit_code == 1
        assert "Error triggering task" in result.stdout


class TestSchedulerExportIcal:
    """Tests for scheduler export-ical command"""

    @patch("apflow.cli.commands.scheduler.asyncio.run")
    def test_scheduler_export_ical_stdout(self, mock_asyncio_run):
        """Test scheduler export-ical to stdout"""
        ical_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//APFlow//EN
BEGIN:VEVENT
UID:task-123
SUMMARY:Test Task
END:VEVENT
END:VCALENDAR"""
        mock_asyncio_run.return_value = ical_content

        result = runner.invoke(cli, ["scheduler", "export-ical"])

        assert result.exit_code == 0
        assert "BEGIN:VCALENDAR" in result.stdout

    @patch("apflow.cli.commands.scheduler.asyncio.run")
    def test_scheduler_export_ical_to_file(self, mock_asyncio_run, tmp_path):
        """Test scheduler export-ical to file"""
        ical_content = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR"
        mock_asyncio_run.return_value = ical_content

        output_file = tmp_path / "schedule.ics"

        result = runner.invoke(cli, ["scheduler", "export-ical", "--output", str(output_file)])

        assert result.exit_code == 0
        assert "Exported to" in result.stdout
        assert output_file.exists()
        assert output_file.read_text() == ical_content

    @patch("apflow.cli.commands.scheduler.asyncio.run")
    def test_scheduler_export_ical_with_filters(self, mock_asyncio_run):
        """Test scheduler export-ical with filters"""
        mock_asyncio_run.return_value = "BEGIN:VCALENDAR\nEND:VCALENDAR"

        result = runner.invoke(
            cli,
            [
                "scheduler",
                "export-ical",
                "--user-id",
                "user123",
                "--type",
                "cron",
                "--name",
                "My Calendar",
            ],
        )

        assert result.exit_code == 0

    @patch("apflow.cli.commands.scheduler.asyncio.run")
    def test_scheduler_export_ical_include_disabled(self, mock_asyncio_run):
        """Test scheduler export-ical with --all flag"""
        mock_asyncio_run.return_value = "BEGIN:VCALENDAR\nEND:VCALENDAR"

        result = runner.invoke(cli, ["scheduler", "export-ical", "--all"])

        assert result.exit_code == 0

    @patch("apflow.cli.commands.scheduler.asyncio.run")
    def test_scheduler_export_ical_error(self, mock_asyncio_run):
        """Test scheduler export-ical with error"""
        mock_asyncio_run.side_effect = Exception("Database error")

        result = runner.invoke(cli, ["scheduler", "export-ical"])

        assert result.exit_code == 1
        assert "Error exporting iCal" in result.stdout


class TestSchedulerWebhookUrl:
    """Tests for scheduler webhook-url command"""

    def test_scheduler_webhook_url_missing_task_id(self):
        """Test scheduler webhook-url without task ID"""
        result = runner.invoke(cli, ["scheduler", "webhook-url"])
        assert result.exit_code != 0

    def test_scheduler_webhook_url_default_base_url(self):
        """Test scheduler webhook-url with default base URL"""
        with patch("apflow.scheduler.gateway.WebhookGateway") as mock_gateway_class:
            mock_gateway = MagicMock()
            mock_gateway.generate_webhook_url.return_value = {
                "url": "http://localhost:8000/webhook/trigger/task-123",
                "method": "POST",
            }
            mock_gateway_class.return_value = mock_gateway

            result = runner.invoke(cli, ["scheduler", "webhook-url", "task-123"])

            assert result.exit_code == 0
            assert "http://localhost:8000/webhook/trigger/task-123" in result.stdout
            assert "POST" in result.stdout

    def test_scheduler_webhook_url_custom_base_url(self):
        """Test scheduler webhook-url with custom base URL"""
        with patch("apflow.scheduler.gateway.WebhookGateway") as mock_gateway_class:
            mock_gateway = MagicMock()
            mock_gateway.generate_webhook_url.return_value = {
                "url": "https://api.example.com/webhook/trigger/task-456",
                "method": "POST",
            }
            mock_gateway_class.return_value = mock_gateway

            result = runner.invoke(
                cli,
                [
                    "scheduler",
                    "webhook-url",
                    "task-456",
                    "--base-url",
                    "https://api.example.com",
                ],
            )

            assert result.exit_code == 0
            assert "https://api.example.com" in result.stdout

    def test_scheduler_webhook_url_shows_cron_example(self):
        """Test scheduler webhook-url shows cron example"""
        with patch("apflow.scheduler.gateway.WebhookGateway") as mock_gateway_class:
            mock_gateway = MagicMock()
            mock_gateway.generate_webhook_url.return_value = {
                "url": "http://localhost:8000/webhook/trigger/task-123",
                "method": "POST",
            }
            mock_gateway_class.return_value = mock_gateway

            result = runner.invoke(cli, ["scheduler", "webhook-url", "task-123"])

            assert result.exit_code == 0
            assert "cron" in result.stdout.lower()
            assert "curl" in result.stdout

    def test_scheduler_webhook_url_error(self):
        """Test scheduler webhook-url with error"""
        with patch("apflow.scheduler.gateway.WebhookGateway") as mock_gateway_class:
            mock_gateway = MagicMock()
            mock_gateway.generate_webhook_url.side_effect = Exception("Config error")
            mock_gateway_class.return_value = mock_gateway

            result = runner.invoke(cli, ["scheduler", "webhook-url", "task-123"])

            assert result.exit_code == 1
            assert "Error generating webhook URL" in result.stdout


# ============================================================================
# Integration Tests - Real flows without mocks
# ============================================================================


class TestSchedulerIntegration:
    """Integration tests using real database and components"""

    def test_scheduler_webhook_url_real(self):
        """Test scheduler webhook-url generates real URL without mocks"""
        result = runner.invoke(cli, ["scheduler", "webhook-url", "test-task-123"])

        assert result.exit_code == 0
        assert "webhook/trigger/test-task-123" in result.stdout
        assert "POST" in result.stdout
        assert "curl" in result.stdout

    def test_scheduler_webhook_url_real_custom_base(self):
        """Test scheduler webhook-url with custom base URL"""
        result = runner.invoke(
            cli,
            [
                "scheduler",
                "webhook-url",
                "my-task",
                "--base-url",
                "https://api.myapp.com",
            ],
        )

        assert result.exit_code == 0
        assert "https://api.myapp.com/webhook/trigger/my-task" in result.stdout

    @pytest.mark.asyncio
    async def test_scheduler_trigger_real_task_not_found(self, use_test_db_session):
        """Test scheduler trigger with real database - task not found"""
        result = runner.invoke(cli, ["scheduler", "trigger", "nonexistent-task-xyz"])

        # Should fail because task doesn't exist
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    @pytest.mark.asyncio
    async def test_scheduler_trigger_real_task_exists(self, use_test_db_session):
        """Test scheduler trigger with real database - task exists"""
        import uuid
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class

        # Create a real task in database
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        task_id = f"trigger-test-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=task_id,
            name="Trigger Test Task",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
        )

        # Trigger the task - this should work (or fail with execution error, not "not found")
        result = runner.invoke(cli, ["scheduler", "trigger", task_id])

        # The task exists, so we expect either success or an execution-related message
        # (not "not found")
        if result.exit_code == 0:
            assert "triggered successfully" in result.stdout
        else:
            # Even if execution fails, it should not be "not found"
            assert "not found" not in result.stdout.lower()

    def test_scheduler_export_ical_real(self):
        """Test scheduler export-ical produces valid iCal format"""
        # Export to iCal - should succeed even with no scheduled tasks
        result = runner.invoke(cli, ["scheduler", "export-ical"])

        # iCal export should succeed and return valid iCal format
        assert result.exit_code == 0
        assert "BEGIN:VCALENDAR" in result.stdout
        assert "END:VCALENDAR" in result.stdout

    def test_scheduler_export_ical_to_file_real(self, tmp_path):
        """Test scheduler export-ical to file produces valid output"""
        output_file = tmp_path / "schedule.ics"
        result = runner.invoke(cli, ["scheduler", "export-ical", "--output", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content

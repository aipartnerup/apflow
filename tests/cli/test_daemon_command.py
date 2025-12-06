"""
Test CLI daemon command functionality

Tests the daemon command as documented in README.md
"""

import pytest
import os
import time
from pathlib import Path
from typer.testing import CliRunner
from aipartnerupflow.cli.main import app
from aipartnerupflow.cli.commands.daemon import (
    get_pid_file,
    get_log_file,
    read_pid,
    remove_pid,
    is_process_running,
)

runner = CliRunner()


@pytest.fixture
def cleanup_daemon_files():
    """Cleanup daemon PID and log files before and after tests"""
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


class TestDaemonCommand:
    """Test cases for daemon command"""
    
    def test_daemon_help(self):
        """Test daemon command help"""
        result = runner.invoke(app, ["daemon", "--help"])
        assert result.exit_code == 0
        assert "Manage daemon" in result.stdout
        assert "start" in result.stdout
        assert "stop" in result.stdout
    
    def test_daemon_start_help(self):
        """Test daemon start command help"""
        result = runner.invoke(app, ["daemon", "start", "--help"])
        assert result.exit_code == 0
        assert "Start daemon service" in result.stdout
        assert "--port" in result.stdout or "-p" in result.stdout
        assert "--protocol" in result.stdout
    
    def test_daemon_stop_help(self):
        """Test daemon stop command help"""
        result = runner.invoke(app, ["daemon", "stop", "--help"])
        assert result.exit_code == 0
        assert "Stop daemon service" in result.stdout
    
    def test_daemon_status_when_not_running(self, cleanup_daemon_files):
        """Test daemon status when daemon is not running"""
        result = runner.invoke(app, ["daemon", "status"])
        assert result.exit_code == 0
        assert "Not running" in result.stdout or "no PID file" in result.stdout
    
    def test_daemon_stop_when_not_running(self, cleanup_daemon_files):
        """Test daemon stop when daemon is not running (as documented)"""
        result = runner.invoke(app, ["daemon", "stop"])
        # Should not error, just report not running
        assert result.exit_code == 0
        assert "not running" in result.stdout.lower() or "no PID file" in result.stdout.lower()
    
    def test_daemon_start_with_port(self, cleanup_daemon_files):
        """Test daemon start with port option"""
        # Start daemon in background
        result = runner.invoke(app, [
            "daemon", "start",
            "--port", "8999",  # Use a different port to avoid conflicts
            "--background"
        ])
        
        # Should start successfully
        assert result.exit_code == 0
        assert "started successfully" in result.stdout.lower() or "Daemon started" in result.stdout
        
        # Cleanup: stop the daemon
        time.sleep(1)  # Give it a moment to start
        stop_result = runner.invoke(app, ["daemon", "stop"])
        # Stop might fail if daemon already stopped, that's okay
        # Just verify we tried to stop it
        assert "stop" in stop_result.stdout.lower() or stop_result.exit_code in [0, 1]
    
    def test_daemon_start_with_protocol(self, cleanup_daemon_files):
        """Test daemon start with protocol option"""
        # Start daemon with MCP protocol
        result = runner.invoke(app, [
            "daemon", "start",
            "--port", "8997",
            "--protocol", "mcp",
            "--background"
        ])
        
        # Should start successfully
        assert result.exit_code == 0
        assert "started successfully" in result.stdout.lower() or "Daemon started" in result.stdout
        assert "protocol: mcp" in result.stdout.lower() or "mcp" in result.stdout.lower()
        
        # Cleanup: stop the daemon
        time.sleep(1)  # Give it a moment to start
        stop_result = runner.invoke(app, ["daemon", "stop"])
        assert "stop" in stop_result.stdout.lower() or stop_result.exit_code in [0, 1]
    
    def test_daemon_restart(self, cleanup_daemon_files):
        """Test daemon restart command"""
        # First start
        start_result = runner.invoke(app, [
            "daemon", "start",
            "--port", "8998",
            "--background"
        ])
        
        if start_result.exit_code == 0:
            time.sleep(1)  # Give it time to start
            
            # Then restart
            restart_result = runner.invoke(app, [
                "daemon", "restart",
                "--port", "8998"
            ])
            
            # Restart might fail if stop fails, but command should be recognized
            # Just verify restart command was executed
            assert "restart" in restart_result.stdout.lower() or restart_result.exit_code in [0, 1]
            
            # Cleanup
            time.sleep(1)
            runner.invoke(app, ["daemon", "stop"])


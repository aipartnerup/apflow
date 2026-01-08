import pytest
from typer.testing import CliRunner
from apflow.cli.commands import tasks

runner = CliRunner()

# Test aliases for list, status, cancel, watch, history
@pytest.mark.parametrize("cmd, args", [
    ("ls", []),
    ("list", []),
    ("st", ["dummy_id"]),
    ("status", ["dummy_id"]),
    ("c", ["dummy_id"]),
    ("cancel", ["dummy_id"]),
    ("w", ["--task-id", "dummy_id"]),
    ("watch", ["--task-id", "dummy_id"]),
    ("hi", ["dummy_id"]),
    ("history", ["dummy_id"]),
])
def test_tasks_aliases_and_history(cmd, args):
    result = runner.invoke(tasks.app, [cmd] + args)
    # All should not raise usage error, but will fail on dummy_id
    assert result.exit_code in (0, 1)
    # For history, check error message for not found
    if cmd in ("hi", "history"):
        assert "not found" in result.output or "No history" in result.output
    # For watch/w, allow error logs but require graceful exit
    if cmd in ("watch", "w"):
        assert "No such task" in result.output or "exiting" in result.output or result.exit_code == 0

# Test history with missing task
def test_tasks_history_not_found():
    result = runner.invoke(tasks.app, ["history", "nonexistent_id"])
    assert result.exit_code == 1
    assert "not found" in result.output

# Test list alias returns valid output (empty or error is fine)
def test_tasks_list_alias():
    result = runner.invoke(tasks.app, ["ls"])
    assert result.exit_code in (0, 1)
    # Should not crash (allow error logs, but not crash)
    assert "Traceback" not in result.output

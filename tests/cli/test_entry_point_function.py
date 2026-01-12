"""
Test entry point registration of functions as root commands.
"""
import typer
from apflow.cli.decorators import get_cli_registry
from typer.testing import CliRunner


def test_entry_point_function_registration():
    """Test that functions registered via entry points are treated as root commands."""
    # Simulate entry point loading a function
    def serve_app():
        """Start the server."""
        print("Server started")
    
    # Simulate the entry point loading logic from main.py
    if callable(serve_app):
        typer_app = typer.Typer()
        typer_app.command()(serve_app)
    
    # Register it
    registry = get_cli_registry()
    registry["serve"] = typer_app
    
    # Test that it works as a root command
    runner = CliRunner()
    result = runner.invoke(typer_app, [])
    assert result.exit_code == 0
    assert "Server started" in result.output
    
    # Verify it has a command (not a group)
    commands = list(typer_app.registered_commands)
    assert len(commands) > 0


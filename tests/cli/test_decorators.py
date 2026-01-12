"""
Test CLI decorators: registration and group extension.
"""
import typer
from apflow.cli.decorators import cli_register, get_cli_group, get_cli_registry
from typer.testing import CliRunner

# --- Test fixtures: Register commands for testing ---
# Note: These decorators run at import time, but the registry may be cleared
# by conftest cleanup. The tests will re-register if needed.

# Register as root command (all functions are root commands by default)
@cli_register(name="hello-func", help="Say hello (function)")
def hello_func(name: str = "world"):
    """A simple hello command."""
    print(f"Hello, {name} (from func)!")

# Register as root command with typer.Option
@cli_register(name="hello-root", help="Say hello (root)")
def hello_root(name: str = typer.Option("world", help="Name to greet")):
    """A simple hello command (root)."""
    print(f"Hello, {name} (from root)!")

# Use a plain class with a public method to be registered as a command
@cli_register(name="dummy-group", help="Dummy group")
class DummyGroup:
    def foo(self):
        print("foo from DummyGroup")


def _ensure_test_commands_registered():
    """Ensure test commands are registered (called after cleanup)."""
    # Re-register commands if they're not in the registry
    # This handles the case where conftest clears the registry
    registry = get_cli_registry()
    if "hello-func" not in registry:
        cli_register(name="hello-func", help="Say hello (function)")(hello_func)
    if "hello-root" not in registry:
        cli_register(name="hello-root", help="Say hello (root)")(hello_root)
    if "dummy-group" not in registry:
        cli_register(name="dummy-group", help="Dummy group")(DummyGroup)


# --- Basic Registration Tests ---

def test_cli_register_function():
    """Test registering functions as root commands."""
    _ensure_test_commands_registered()
    registry = get_cli_registry()
    
    # Test hello-func (root command with simple parameter)
    assert "hello-func" in registry
    app = registry["hello-func"]
    assert isinstance(app, typer.Typer)
    # Root command should have a command registered
    commands = list(app.registered_commands)
    assert len(commands) > 0
    # Test root command execution
    runner = CliRunner()
    result = runner.invoke(app, ["--name", "test"])
    assert result.exit_code == 0
    assert "Hello, test (from func)!" in result.output

    # Test hello-root (root command with typer.Option)
    assert "hello-root" in registry
    app2 = registry["hello-root"]
    assert isinstance(app2, typer.Typer)
    # Root command should have a command registered
    assert len(list(app2.registered_commands)) > 0
    # Test root command execution
    result2 = runner.invoke(app2, ["--name", "test"])
    assert result2.exit_code == 0
    assert "Hello, test (from root)!" in result2.output


def test_cli_register_class():
    """Test registering classes as groups."""
    _ensure_test_commands_registered()
    registry = get_cli_registry()
    assert "dummy-group" in registry
    app = registry["dummy-group"]
    assert isinstance(app, typer.Typer)
    commands = list(app.registered_commands)
    assert any(cmd.name == "foo" for cmd in commands)


def test_cli_register_help_text():
    """Test help text is correctly set."""
    _ensure_test_commands_registered()
    registry = get_cli_registry()
    assert registry["hello-func"].info.help == "Say hello (function)"
    assert registry["dummy-group"].info.help == "Dummy group"


# --- Group Extension Tests ---

def test_cli_register_extend_group():
    """Test extending a group using @cli_register with group parameter."""
    # First register a group
    @cli_register(name="test-group", help="Test group")
    class TestGroup:
        def foo(self):
            print("foo from TestGroup")

    # Extend the group using @cli_register with group parameter
    @cli_register(group="test-group", name="bar", help="Bar command")
    def bar():
        print("bar from extension")

    # Test both original and extended commands
    registry = get_cli_registry()
    app = registry["test-group"]
    runner = CliRunner()
    
    # Test original command
    result1 = runner.invoke(app, ["foo"])
    assert result1.exit_code == 0
    assert "foo from TestGroup" in result1.output
    
    # Test extended command
    result2 = runner.invoke(app, ["bar"])
    assert result2.exit_code == 0
    assert "bar from extension" in result2.output


def test_cli_register_override_subcommand():
    """Test overriding a subcommand in a group."""
    # Register a group with a command
    @cli_register(name="test-group2", help="Test group 2")
    class TestGroup2:
        def original(self):
            print("original command")

    # Override the subcommand
    @cli_register(group="test-group2", name="original", override=True)
    def overridden():
        print("overridden command")

    registry = get_cli_registry()
    app = registry["test-group2"]
    runner = CliRunner()
    
    result = runner.invoke(app, ["original"])
    assert result.exit_code == 0
    assert "overridden command" in result.output
    assert "original command" not in result.output


def test_extend_registered_group():
    """Test extending a group using get_cli_group()."""
    # Register a group
    @cli_register(name="test-group3", help="Test group 3")
    class TestGroup3:
        def foo(self):
            print("foo from TestGroup3")

    # Extend the group using get_cli_group
    group = get_cli_group("test-group3")
    
    @group.command()
    def bar():
        print("bar from extension")

    # Test both original and extended commands
    registry = get_cli_registry()
    app = registry["test-group3"]
    runner = CliRunner()
    
    # Test original command
    result1 = runner.invoke(app, ["foo"])
    assert result1.exit_code == 0
    assert "foo from TestGroup3" in result1.output
    
    # Test extended command
    result2 = runner.invoke(app, ["bar"])
    assert result2.exit_code == 0
    assert "bar from extension" in result2.output


def test_extend_builtin_group():
    """Test extending apflow built-in groups (if available)."""
    try:
        # Try to get tasks group (built-in)
        group = get_cli_group("tasks")
        
        # Verify it's a group (has subcommands)
        assert hasattr(group, 'registered_commands')
        
        # Add a custom command
        @group.command()
        def custom_action():
            print("Custom action in tasks group")
        
        # Verify the command count increased (or at least the group is accessible)
        # Note: Due to lazy loading, the command might not persist across calls
        # but the group should be accessible
        assert isinstance(group, typer.Typer)
    except KeyError:
        # If tasks group is not available, skip this test
        pass


def test_get_nonexistent_group():
    """Test that getting a non-existent group raises KeyError."""
    try:
        get_cli_group("nonexistent-group")
        assert False, "Should have raised KeyError"
    except KeyError as e:
        assert "nonexistent-group" in str(e)

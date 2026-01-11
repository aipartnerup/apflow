"""
Test CLI decorators: function and class registration.
"""
import typer
from apflow.cli.decorators import cli_register, get_cli_registry

# --- Function registration test ---

# Register in Group mode
@cli_register(name="hello-func", help="Say hello (function)")
def hello_func(name: str = "world"):
    """A simple hello command."""
    print(f"Hello, {name} (from func)!")

# Register in Root command mode
from apflow.cli.decorators import cli_register as cli_register2
import typer as _typer
@cli_register2(name="hello-root", help="Say hello (root)", root_command=True)
def hello_root(name: str = _typer.Option("world", help="Name to greet")):
    """A simple hello command (root)."""
    print(f"Hello, {name} (from root)!")

# --- Class registration test (original) ---

# Use a plain class with a public method to be registered as a command
@cli_register(name="dummy-group", help="Dummy group")
class DummyGroup:
    def foo(self):
        print("foo from DummyGroup")

def test_cli_register_function():
    registry = get_cli_registry()
    assert "hello-func" in registry
    app = registry["hello-func"]
    assert isinstance(app, typer.Typer)
    # Should have the callback set to hello_func
    # Group mode
    commands = list(app.registered_commands)
    assert any(cmd.name == "hello-func" for cmd in commands)
    # Call group subcommand
    import io, sys
    buf = io.StringIO()
    sys_stdout = sys.stdout
    sys.stdout = buf
    try:
        # Get the first command object and call its callback
        cmd = next(cmd for cmd in app.registered_commands if cmd.name == "hello-func")
        cmd.callback()
    finally:
        sys.stdout = sys_stdout
    output = buf.getvalue()
    assert "Hello, world (from func)!" in output

    # Root command mode
    assert "hello-root" in registry
    app2 = registry["hello-root"]
    assert isinstance(app2, typer.Typer)
    from typer.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(app2, ["--name", "world"])
    assert result.exit_code == 0
    assert "Hello, world (from root)!" in result.output
    # Unwrap the callback to get the original function
    import io
    import sys
    buf = io.StringIO()
    sys_stdout = sys.stdout
    sys.stdout = buf
    try:
        app.callback()
    finally:
        sys.stdout = sys_stdout
    output = buf.getvalue()
    assert "Hello, world (from func)!" in output

def test_cli_register_class():
    registry = get_cli_registry()
    assert "dummy-group" in registry
    app = registry["dummy-group"]
    assert isinstance(app, typer.Typer)
    commands = list(app.registered_commands)
    assert any(cmd.name == "foo" for cmd in commands)

def test_cli_register_help_text():
    registry = get_cli_registry()
    assert registry["hello-func"].info.help == "Say hello (function)"
    assert registry["dummy-group"].info.help == "Dummy group"
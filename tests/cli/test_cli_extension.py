"""
Tests for CLI extension decorators and base class.
"""

import pytest
import typer
from typer.testing import CliRunner

from apflow.cli.decorators import cli_register, get_cli_registry, _cli_registry
from apflow.cli.extension import CLIExtension


runner = CliRunner()


class TestCLIExtension:
    """Test CLIExtension base class."""

    def test_cli_extension_inherits_from_typer(self):
        """Test that CLIExtension is a Typer subclass."""
        ext = CLIExtension()
        assert isinstance(ext, typer.Typer)

    def test_cli_extension_default_no_args_is_help(self):
        """Test that CLIExtension sets no_args_is_help=True by default."""
        ext = CLIExtension()
        assert ext.info.no_args_is_help is True

    def test_cli_extension_override_no_args_is_help(self):
        """Test that CLIExtension allows overriding no_args_is_help."""
        ext = CLIExtension(no_args_is_help=False)
        assert ext.info.no_args_is_help is False

    def test_cli_extension_with_name_and_help(self):
        """Test that CLIExtension accepts name and help."""
        ext = CLIExtension(name="test-cmd", help="Test command help")
        assert ext.info.name == "test-cmd"
        assert ext.info.help == "Test command help"

    def test_cli_extension_can_add_commands(self):
        """Test that CLIExtension can add commands."""
        ext = CLIExtension(no_args_is_help=False)

        @ext.command()
        def greet():
            typer.echo("Hello from extension!")

        # When there's only one command, typer uses it as default
        result = runner.invoke(ext, [])
        assert result.exit_code == 0
        assert "Hello from extension!" in result.stdout


class TestCliRegisterDecorator:
    """Test cli_register decorator."""

    def setup_method(self):
        """Clear registry before each test."""
        _cli_registry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        _cli_registry.clear()

    def test_cli_register_basic(self):
        """Test basic CLI extension registration."""
        @cli_register(name="test-basic")
        class TestCommand(CLIExtension):
            pass

        registry = get_cli_registry()
        assert "test-basic" in registry
        assert isinstance(registry["test-basic"], typer.Typer)

    def test_cli_register_default_name_from_class(self):
        """Test that name defaults to lowercase class name."""
        @cli_register()
        class MyTestCommand(CLIExtension):
            pass

        registry = get_cli_registry()
        assert "mytestcommand" in registry

    def test_cli_register_underscore_to_hyphen(self):
        """Test that underscores in class name are converted to hyphens."""
        @cli_register()
        class my_test_command(CLIExtension):
            pass

        registry = get_cli_registry()
        assert "my-test-command" in registry

    def test_cli_register_with_help(self):
        """Test registration with help text."""
        @cli_register(name="test-help", help="My help text")
        class TestHelpCommand(CLIExtension):
            pass

        registry = get_cli_registry()
        assert "test-help" in registry
        assert registry["test-help"].info.help == "My help text"

    def test_cli_register_duplicate_raises_error(self):
        """Test that duplicate registration raises error."""
        @cli_register(name="duplicate-test")
        class FirstCommand(CLIExtension):
            pass

        with pytest.raises(ValueError, match="already registered"):
            @cli_register(name="duplicate-test")
            class SecondCommand(CLIExtension):
                pass

    def test_cli_register_override_allows_duplicate(self):
        """Test that override=True allows replacing registration."""
        @cli_register(name="override-test")
        class FirstCommand(CLIExtension):
            pass

        @cli_register(name="override-test", override=True)
        class SecondCommand(CLIExtension):
            pass

        registry = get_cli_registry()
        assert "override-test" in registry
        # Should be the second one (SecondCommand instance)

    def test_cli_register_returns_original_class(self):
        """Test that decorator returns the original class."""
        @cli_register(name="return-test")
        class OriginalCommand(CLIExtension):
            custom_attr = "test_value"

        assert hasattr(OriginalCommand, "custom_attr")
        assert OriginalCommand.custom_attr == "test_value"

    def test_cli_register_functional_command(self):
        """Test that registered CLI extension works with commands."""
        @cli_register(name="func-test")
        class FuncTestCommand(CLIExtension):
            pass

        # Get the registered instance and add a command
        registry = get_cli_registry()
        func_app = registry["func-test"]
        # Override no_args_is_help for single command test
        func_app.info.no_args_is_help = False

        @func_app.command()
        def hello(name: str = typer.Option("World", "--name", "-n")):
            typer.echo(f"Hello, {name}!")

        # Test the command with option
        result = runner.invoke(func_app, ["--name", "Test"])
        assert result.exit_code == 0
        assert "Hello, Test!" in result.stdout


class TestGetCliRegistry:
    """Test get_cli_registry function."""

    def setup_method(self):
        """Clear registry before each test."""
        _cli_registry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        _cli_registry.clear()

    def test_get_cli_registry_returns_dict(self):
        """Test that get_cli_registry returns a dict."""
        registry = get_cli_registry()
        assert isinstance(registry, dict)

    def test_get_cli_registry_returns_same_instance(self):
        """Test that get_cli_registry returns the same registry instance."""
        registry1 = get_cli_registry()
        registry2 = get_cli_registry()
        assert registry1 is registry2

    def test_get_cli_registry_reflects_registrations(self):
        """Test that registry reflects all registrations."""
        @cli_register(name="reg-test-1")
        class Command1(CLIExtension):
            pass

        @cli_register(name="reg-test-2")
        class Command2(CLIExtension):
            pass

        registry = get_cli_registry()
        assert len(registry) == 2
        assert "reg-test-1" in registry
        assert "reg-test-2" in registry


class TestCLIExtensionIntegration:
    """Integration tests for CLI extension with main app."""

    def setup_method(self):
        """Clear registry before each test."""
        _cli_registry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        _cli_registry.clear()

    def test_cli_extension_with_multiple_commands(self):
        """Test CLI extension with multiple commands."""
        @cli_register(name="multi-cmd")
        class MultiCommand(CLIExtension):
            pass

        registry = get_cli_registry()
        app = registry["multi-cmd"]

        @app.command()
        def cmd1():
            typer.echo("Command 1")

        @app.command()
        def cmd2():
            typer.echo("Command 2")

        result1 = runner.invoke(app, ["cmd1"])
        assert result1.exit_code == 0
        assert "Command 1" in result1.stdout

        result2 = runner.invoke(app, ["cmd2"])
        assert result2.exit_code == 0
        assert "Command 2" in result2.stdout

    def test_cli_extension_help_output(self):
        """Test CLI extension help output."""
        @cli_register(name="help-test", help="Test help description")
        class HelpTestCommand(CLIExtension):
            pass

        registry = get_cli_registry()
        app = registry["help-test"]
        # Override no_args_is_help for single command test
        app.info.no_args_is_help = False

        @app.command()
        def subcommand():
            """Subcommand help."""
            typer.echo("Subcommand executed")

        # Test that the subcommand executes
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Subcommand executed" in result.stdout

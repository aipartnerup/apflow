"""
CLI extension decorators for apflow.

This module provides decorators for registering CLI extensions.

Features:
--------
- Register CLI command groups (class-based, for multiple subcommands)
- Register single CLI commands (function-based, for root commands)

Usage:
-----

# Register a command group (class, all public methods become subcommands)
@cli_register(name="my-group", help="My command group")
class MyGroup:
    def foo(self):
        pass
    def bar(self):
        pass

# Register a single command (function)
@cli_register(name="hello", help="Say hello")
def hello(name: str = "world"):
    print(f"Hello, {name}!")

All registered commands/groups are stored in the CLI registry and can be discovered via get_cli_registry().
"""

import typer
from typing import Callable, Optional, TypeVar
from apflow.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=typer.Typer)

# Registry for CLI extensions
_cli_registry: dict[str, typer.Typer] = {}


def get_cli_registry() -> dict[str, typer.Typer]:
    """Get the CLI extension registry."""
    return _cli_registry.copy()


def cli_register(
    name: Optional[str] = None,
    help: Optional[str] = None,
    override: bool = False,
    root_command: bool = False,
) -> Callable[[T], T]:
    """
    Decorator to register a CLI extension (typer.Typer subclass).

    Usage:
        @cli_register(name="my-command", help="My custom command")
        class MyCommand(CLIExtension):
            ...

        # Or with default name from class
        @cli_register()
        class tasks(CLIExtension):  # name will be "tasks"
            ...

    Args:
        name: Command name. If not provided, uses class name in lowercase.
        help: Help text for the command.
        override: If True, always force override any previous registration for this name. If False and the name exists, registration is skipped.

    Returns:
        Decorated class (same class, registered automatically)
    """
    def decorator(obj: T) -> T:
        # Determine command name
        cmd_name = name or getattr(obj, "__name__", None)
        if cmd_name:
            cmd_name = cmd_name.lower().replace("_", "-")
        else:
            raise ValueError("Cannot determine command name for CLI registration.")

        if cmd_name in _cli_registry and not override:
            logger.debug(
                f"CLI extension '{cmd_name}' is already registered. "
                f"Use override=True to force override the existing registration."
            )
            return obj


        # Register class-based group
        if isinstance(obj, type):
            instance = obj()
            if isinstance(instance, typer.Typer):
                if help:
                    instance.info.help = help
                _cli_registry[cmd_name] = instance
            else:
                # Wrap non-Typer class as Typer group, register all public methods
                app = typer.Typer(help=help)
                for attr in dir(instance):
                    if attr.startswith("_"):
                        continue
                    method = getattr(instance, attr)
                    if callable(method):
                        app.command(name=attr)(method)
                _cli_registry[cmd_name] = app
            return obj



        # Register function as group or root command
        if callable(obj):
            app = typer.Typer(help=help)
            if root_command:
                app.callback()(obj)
            else:
                app.command(name=cmd_name)(obj)
            _cli_registry[cmd_name] = app
            return obj

        raise TypeError("@cli_register can only be applied to classes or functions.")

    return decorator


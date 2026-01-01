"""
CLI extension decorators for apflow.

This module provides decorators for registering CLI extensions.
"""

import typer
from typing import Callable, Optional, TypeVar

T = TypeVar("T", bound=typer.Typer)

# Registry for CLI extensions
_cli_registry: dict[str, typer.Typer] = {}


def get_cli_registry() -> dict[str, typer.Typer]:
    """Get the CLI extension registry."""
    return _cli_registry


def cli_register(
    name: Optional[str] = None,
    help: Optional[str] = None,
    override: bool = False,
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
        override: If True, allow overriding existing registration.

    Returns:
        Decorated class (same class, registered automatically)
    """
    def decorator(cls: T) -> T:
        cmd_name = name or cls.__name__.lower().replace("_", "-")

        if cmd_name in _cli_registry and not override:
            raise ValueError(
                f"CLI extension '{cmd_name}' is already registered. "
                "Use override=True to replace it."
            )

        # Instantiate if it's a class, otherwise use directly
        if isinstance(cls, type):
            instance = cls()
            if help:
                instance.info.help = help
            _cli_registry[cmd_name] = instance
        else:
            _cli_registry[cmd_name] = cls

        return cls

    return decorator

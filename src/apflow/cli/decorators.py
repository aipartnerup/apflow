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

# Extend existing groups:
from apflow.cli import get_cli_group
my_group = get_cli_group("my-group")
@my_group.command()
def new_subcommand():
    pass
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


def get_cli_group(name: str) -> typer.Typer:
    """
    Get a CLI group by name, supporting both registered extensions and built-in groups.
    
    This function allows external projects to extend existing CLI groups by adding
    subcommands to them.
    
    Args:
        name: Group name (e.g., "tasks", "config", or a custom group name)
    
    Returns:
        Typer app instance for the group
    
    Raises:
        KeyError: If the group doesn't exist
    
    Example:
        # Extend a custom group
        from apflow.cli import get_cli_group
        
        my_group = get_cli_group("my-group")
        @my_group.command()
        def new_command():
            print("New command in my-group")
        
        # Extend apflow built-in group (if supported)
        tasks_group = get_cli_group("tasks")
        @tasks_group.command()
        def custom_action():
            print("Custom action in tasks group")
    """
    # First check registered extensions
    registry = get_cli_registry()
    if name in registry:
        return registry[name]
    
    # Try to get from built-in commands (lazy-loaded)
    # This allows extending apflow's built-in groups like "tasks", "config", etc.
    try:
        # Import the command module to get the Typer app
        # This matches the lazy loading logic in main.py
        builtin_commands = {
            "run": ("apflow.cli.commands.run", "app"),
            "serve": ("apflow.cli.commands.serve", "app"),
            "daemon": ("apflow.cli.commands.daemon", "app"),
            "tasks": ("apflow.cli.commands.tasks", "app"),
            "generate": ("apflow.cli.commands.generate", "app"),
            "config": ("apflow.cli.commands.config", "app"),
            "executors": ("apflow.cli.commands.executors", "app"),
        }
        
        if name in builtin_commands:
            module_path, attr_name = builtin_commands[name]
            import importlib
            module = importlib.import_module(module_path)
            typer_app = getattr(module, attr_name)
            
            # Check if it's a group (has subcommands)
            if hasattr(typer_app, 'registered_commands') and len(typer_app.registered_commands) > 0:
                return typer_app
            else:
                # If it's not a group, we can't extend it
                raise KeyError(f"'{name}' is not a group (it's a single command)")
    except (ImportError, AttributeError):
        pass
    
    raise KeyError(f"CLI group '{name}' not found. Available groups: {list(registry.keys())}")


def cli_register(
    name: Optional[str] = None,
    help: Optional[str] = None,
    override: bool = False,
    group: Optional[str] = None,
) -> Callable[[T], T]:
    """
    Decorator to register a CLI extension (typer.Typer subclass).

    Usage:
        # Register a new root command or group
        @cli_register(name="my-command", help="My custom command")
        class MyCommand(CLIExtension):
            ...

        # Register a function as root command (all functions are root commands)
        @cli_register(name="hello", help="Say hello")
        def hello(name: str = "world"):
            print(f"Hello, {name}!")
        # Usage: apflow hello --name test

        # Extend an existing group with a new subcommand
        @cli_register(group="my-group", name="new-command", help="New subcommand")
        def new_command():
            print("New command in my-group")
        # Usage: apflow my-group new-command

        # Override an existing subcommand in a group
        @cli_register(group="my-group", name="existing-command", override=True)
        def existing_command():
            print("Overridden command")

        # Override an entire group (use with caution)
        @cli_register(name="my-group", override=True)
        class NewMyGroup(CLIExtension):
            ...

    Args:
        name: Command/subcommand name. If not provided, uses class/function name in lowercase.
        help: Help text for the command/subcommand.
        override: 
            - If `group` is None: If True, override entire group/command registration
            - If `group` is set: If True, override existing subcommand in the group
        group: If provided, extend this group with a new subcommand instead of registering a new command.

    Returns:
        Decorated class or function (same object, registered automatically)
    """
    def decorator(obj: T) -> T:
        # Determine command/subcommand name
        cmd_name = name or getattr(obj, "__name__", None)
        if cmd_name:
            cmd_name = cmd_name.lower().replace("_", "-")
        else:
            raise ValueError("Cannot determine command name for CLI registration.")

        # If group is specified, extend the group with a subcommand
        if group:
            group_name = group.lower().replace("_", "-")
            try:
                target_group = get_cli_group(group_name)
            except KeyError:
                raise ValueError(
                    f"Cannot extend group '{group_name}': group not found. "
                    f"Register the group first or use an existing group name."
                )
            
            # Check if subcommand already exists
            existing_commands = {cmd.name for cmd in target_group.registered_commands}
            if cmd_name in existing_commands and not override:
                logger.debug(
                    f"Subcommand '{cmd_name}' already exists in group '{group_name}'. "
                    f"Use override=True to override it."
                )
                return obj
            
            # Register function as subcommand in the group
            if callable(obj):
                target_group.command(name=cmd_name, help=help)(obj)
                logger.debug(f"Added subcommand '{cmd_name}' to group '{group_name}'")
                return obj
            else:
                raise TypeError(
                    f"Cannot extend group '{group_name}' with a class. "
                    f"Only functions can be added as subcommands."
                )

        # Register new command/group (existing logic)
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



        # Register function as root command
        # All single functions are root commands (can be invoked directly)
        # Examples: apflow version, apflow server --port 8000
        if callable(obj):
            app = typer.Typer(help=help)
            # Root command: use command() without name to create a directly callable command
            # This creates a single command that can be invoked directly as: apflow <cmd_name>
            app.command()(obj)
            _cli_registry[cmd_name] = app
            return obj

        raise TypeError("@cli_register can only be applied to classes or functions.")

    return decorator


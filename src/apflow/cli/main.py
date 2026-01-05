"""
CLI main entry point for apflow
"""

import sys
from pathlib import Path

import click

from apflow.core.config_manager import get_config_manager
from apflow.logger import get_logger

logger = get_logger(__name__)


def _load_env_file() -> None:
    """
    Load .env file from appropriate location using ConfigManager.
    """
    possible_paths = [Path.cwd() / ".env"]
    if sys.argv and len(sys.argv) > 0:
        try:
            main_script = Path(sys.argv[0]).resolve()
            if main_script.is_file():
                possible_paths.append(main_script.parent / ".env")
        except Exception:
            pass

    config_manager = get_config_manager()
    config_manager.load_env_files(possible_paths, override=False)


def _setup_cli_logging() -> None:
    """
    Setup logging for CLI based on config.cli.yaml.
    
    Priority:
    1. config.cli.yaml: log_level or log-level
    2. WARNING (default - keep CLI quiet)
    """
    try:
        from apflow.cli.cli_config import load_cli_config
        from apflow.logger import setup_logging
        
        # Load CLI config
        config = load_cli_config()
        
        # Get log level from config (support both log_level and log-level)
        log_level = config.get("log_level") or config.get("log-level") or "WARNING"
        log_level = log_level.upper()
        
        # Use configured level or default to WARNING for CLI
        setup_logging(level=log_level)
    except Exception:
        # If config loading fails, use default WARNING level
        from apflow.logger import setup_logging
        setup_logging(level="WARNING")


# Create main CLI app - using Click's LazyGroup for lazy command loading


class LazyGroup(click.Group):
    """A Click Group that lazy-loads command modules."""

    def __init__(
        self,
        name: str | None = None,
        commands: dict[str, click.Command] | None = None,
        **kwargs: any,
    ) -> None:
        super().__init__(name=name, commands=commands or {}, **kwargs)
        self._lazy_commands = {
            "run": ("apflow.cli.commands.run", "app", "Execute tasks through TaskExecutor"),
            "serve": ("apflow.cli.commands.serve", "app", "Start API server"),
            "daemon": ("apflow.cli.commands.daemon", "app", "Manage daemon service"),
            "tasks": ("apflow.cli.commands.tasks", "app", "Manage and query tasks"),
            "generate": ("apflow.cli.commands.generate", "app", "Generate a task tree from natural language"),
            "config": ("apflow.cli.commands.config", "app", "Manage CLI configuration"),
        }
        # Ensure CLI extensions are loaded (lazy import to avoid circular dependencies)
        self._ensure_extensions_loaded()

    def _ensure_extensions_loaded(self) -> None:
        """Ensure CLI extensions are loaded by importing the registry and entry points."""
        try:
            # Import registry to trigger any module-level registration
            from apflow.cli.decorators import get_cli_registry
            # Just accessing the registry will trigger any imports that register extensions
            get_cli_registry()
            
            # Load CLI extensions from entry points
            self._load_entry_point_plugins()
        except Exception:
            # If extensions fail to load, continue without them
            pass

    def _load_entry_point_plugins(self) -> None:
        """Load CLI plugins from entry points (apflow.cli_plugins)."""
        try:
            import importlib.metadata
            from apflow.cli.decorators import get_cli_registry
            
            registry = get_cli_registry()
            
            # Load plugins from entry points
            try:
                entry_points = importlib.metadata.entry_points(group="apflow.cli_plugins")
            except Exception:
                # Python < 3.10 compatibility
                try:
                    import pkg_resources
                    entry_points = pkg_resources.iter_entry_points("apflow.cli_plugins")
                except Exception:
                    entry_points = []
            
            for entry_point in entry_points:
                try:
                    plugin_name = entry_point.name
                    # Skip if already registered (via decorator or previous entry point)
                    if plugin_name in registry:
                        logger.debug(f"CLI plugin '{plugin_name}' already registered, skipping entry point")
                        continue
                    
                    # Load the plugin
                    typer_app = entry_point.load()
                    
                    # Register the plugin
                    registry[plugin_name] = typer_app
                    logger.debug(f"Loaded CLI plugin '{plugin_name}' from entry point")
                except Exception as e:
                    logger.warning(f"Failed to load CLI plugin from entry point '{entry_point.name}': {e}")
        except Exception as e:
            logger.debug(f"Failed to load CLI entry point plugins: {e}")

    def _get_registered_commands(self) -> dict[str, str]:
        """Get commands from cli_register registry with their help text."""
        try:
            from apflow.cli.decorators import get_cli_registry
            registry = get_cli_registry()
            result = {}
            for cmd_name, typer_app in registry.items():
                help_text = getattr(typer_app.info, "help", None) or f"CLI extension: {cmd_name}"
                result[cmd_name] = help_text
            return result
        except Exception:
            return {}

    def list_commands(self, ctx: click.Context) -> list[str]:
        """Return list of all commands (lazy + regular + registered extensions)."""
        registered = set(self._get_registered_commands().keys())
        return sorted(set(list(self.commands) + list(self._lazy_commands) + list(registered)))

    def format_commands(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        """Format commands for help without loading them."""
        registered_commands = self._get_registered_commands()
        commands = []
        for cmd_name in self.list_commands(ctx):
            # Use pre-defined help for lazy commands (don't load them)
            if cmd_name in self._lazy_commands:
                _, _, help_text = self._lazy_commands[cmd_name]
                commands.append((cmd_name, help_text))
            elif cmd_name in registered_commands:
                # Use help from registered extension
                help_text = registered_commands[cmd_name]
                commands.append((cmd_name, help_text))
            elif cmd_name in self.commands:
                # For already-loaded commands, get actual help
                cmd = self.commands[cmd_name]
                help_text = cmd.get_short_help_str(formatter.width) if hasattr(cmd, "get_short_help_str") else ""
                commands.append((cmd_name, help_text))
        
        if commands:
            with formatter.section("Commands"):
                formatter.write_dl(commands)

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        """Get command, lazily loading if needed."""
        # Check already-loaded commands
        if name in self.commands:
            return self.commands[name]

        # Check registered CLI extensions first
        try:
            from apflow.cli.decorators import get_cli_registry
            registry = get_cli_registry()
            if name in registry:
                typer_app = registry[name]
                import typer.main
                
                # Check if Typer app has subcommands (registered_commands)
                # If it has subcommands, use get_group() to return a Click Group
                # Otherwise, use get_command() to return a single Click command
                if hasattr(typer_app, 'registered_commands') and len(typer_app.registered_commands) > 0:
                    # Has subcommands - return as a group
                    click_cmd = typer.main.get_group(typer_app)
                else:
                    # No subcommands - return as a single command
                    click_cmd = typer.main.get_command(typer_app)
                
                # Cache the loaded command
                self.commands[name] = click_cmd
                return click_cmd
        except Exception as e:
            logger.debug(f"Failed to load registered extension {name}: {e}")

        # Check lazy commands
        if name not in self._lazy_commands:
            return None

        # Load the command module
        module_path, attr_name, _ = self._lazy_commands[name]
        try:
            import importlib

            import typer.main

            module = importlib.import_module(module_path)
            typer_app = getattr(module, attr_name)
            
            # Check if Typer app has subcommands (registered_commands)
            # If it has subcommands, use get_group() to return a Click Group
            # Otherwise, use get_command() to return a single Click command
            if hasattr(typer_app, 'registered_commands') and len(typer_app.registered_commands) > 0:
                # Has subcommands - return as a group
                click_cmd = typer.main.get_group(typer_app)
            else:
                # No subcommands - return as a single command
                click_cmd = typer.main.get_command(typer_app)
            
            # Cache the loaded command
            self.commands[name] = click_cmd
            return click_cmd
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load command {name}: {e}")
            return None


@click.group(
    cls=LazyGroup,
    name="apflow",
    help="Agent workflow orchestration and execution platform CLI",
    context_settings={"help_option_names": ["--help", "-h"]},
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Main CLI entry point."""
    _load_env_file()
    _setup_cli_logging()


@cli.command()
def version() -> None:
    """Show version information."""
    from apflow import __version__

    click.echo(f"apflow version {__version__}")


# Entry point for console script
def main() -> None:
    """Entry point for console script."""
    cli()


# Backward compatibility: alias for imports
app = cli

if __name__ == "__main__":
    app()
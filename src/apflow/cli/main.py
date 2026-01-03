"""
CLI main entry point for apflow
"""

import sys
from pathlib import Path

import click
import typer

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


# Create main CLI app - using Click's LazyGroup for lazy command loading
import click


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

    def list_commands(self, ctx: click.Context) -> list[str]:
        """Return list of all commands (lazy + regular)."""
        return sorted(set(list(self.commands) + list(self._lazy_commands)))

    def format_commands(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        """Format commands for help without loading them."""
        commands = []
        for cmd_name in self.list_commands(ctx):
            # Use pre-defined help for lazy commands (don't load them)
            if cmd_name in self._lazy_commands:
                _, _, help_text = self._lazy_commands[cmd_name]
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
            
            # Convert Typer app to Click command
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
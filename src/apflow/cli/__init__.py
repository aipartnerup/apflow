"""CLI tools for apflow"""

from apflow.cli.decorators import cli_register, get_cli_registry
from apflow.cli.extension import CLIExtension

__all__ = ["CLIExtension", "cli_register", "get_cli_registry", "app"]


def __getattr__(name):
    if name == "app":
        from apflow.cli.main import app
        return app
    raise AttributeError(f"module {__name__} has no attribute {name}")

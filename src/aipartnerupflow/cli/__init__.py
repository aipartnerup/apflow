"""CLI tools for aipartnerupflow"""

from aipartnerupflow.cli.decorators import cli_register, get_cli_registry
from aipartnerupflow.cli.extension import CLIExtension

__all__ = ["CLIExtension", "cli_register", "get_cli_registry", "app"]


def __getattr__(name):
    if name == "app":
        from aipartnerupflow.cli.main import app
        return app
    raise AttributeError(f"module {__name__} has no attribute {name}")

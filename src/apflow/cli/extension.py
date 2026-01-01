"""CLI extension base class for apflow."""

import typer


class CLIExtension(typer.Typer):
    """Base class for CLI extensions."""

    def __init__(self, *args, **kwargs):
        if "no_args_is_help" not in kwargs:
            kwargs["no_args_is_help"] = True
        if "add_completion" not in kwargs:
            kwargs["add_completion"] = False
        super().__init__(*args, **kwargs)

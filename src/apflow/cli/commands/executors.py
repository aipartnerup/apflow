"""
CLI executors command - list available executors

Provides command to query available executors based on APFLOW_EXTENSIONS configuration.
"""

import typer
import json

from apflow.core.extensions.manager import get_available_executors
from apflow.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(
    name="executors",
    help="Query available executors",
    no_args_is_help=False,
)


@app.command("list")
def list_executors(
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json, ids",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed executor information",
    ),
):
    """
    List available executors.

    Shows all executors that are currently accessible based on APFLOW_EXTENSIONS
    environment variable configuration. If APFLOW_EXTENSIONS is set, only executors
    from those extensions are shown (security restriction).

    Examples:
        apflow executors list
        apflow executors list --format json
        apflow executors list --format ids
        apflow executors list --verbose
    """
    try:
        result = get_available_executors()

        if format == "json":
            # JSON output
            typer.echo(json.dumps(result, indent=2))
            return

        if format == "ids":
            # Just list executor IDs
            for executor in result["executors"]:
                typer.echo(executor["id"])
            return

        # Table format (default)
        typer.echo(f"\n{'=' * 80}")
        typer.echo(f"Available Executors ({result['count']} total)")
        if result["restricted"]:
            typer.echo("⚠️  Access restricted by APFLOW_EXTENSIONS")
            typer.echo(f"Allowed IDs: {', '.join(result['allowed_ids'])}")
        else:
            typer.echo("✅ No restrictions (all installed executors available)")
        typer.echo(f"{'=' * 80}\n")

        if not result["executors"]:
            typer.echo("No executors available.")
            return

        for executor in result["executors"]:
            executor_id = executor.get("id", "unknown")
            name = executor.get("name", "N/A")
            description = executor.get("description", "N/A")
            extension_type = executor.get("type", "N/A")

            typer.echo(f"🔧 {typer.style(executor_id, fg=typer.colors.CYAN, bold=True)}")
            typer.echo(f"   Name: {name}")
            typer.echo(f"   Type: {extension_type}")
            
            if verbose:
                typer.echo(f"   Description: {description}")
                
                # Show input schema if available
                input_schema = executor.get("input_schema")
                if input_schema:
                    typer.echo("   Input Schema:")
                    if "properties" in input_schema:
                        for prop_name, prop_info in input_schema["properties"].items():
                            prop_type = prop_info.get("type", "any")
                            prop_desc = prop_info.get("description", "")
                            required = prop_name in input_schema.get("required", [])
                            required_mark = " (required)" if required else ""
                            typer.echo(f"     - {prop_name}: {prop_type}{required_mark}")
                            if prop_desc:
                                typer.echo(f"       {prop_desc}")
                
                # Show tags if available
                tags = executor.get("tags")
                if tags:
                    typer.echo(f"   Tags: {', '.join(tags)}")
            
            typer.echo()

    except Exception as e:
        typer.echo(f"❌ Error listing executors: {str(e)}", err=True)
        logger.error(f"Error listing executors: {str(e)}", exc_info=True)
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
):
    """
    Query available executors.

    If no subcommand is provided, defaults to 'list'.
    """
    if ctx.invoked_subcommand is None:
        # Default to list command
        list_executors()

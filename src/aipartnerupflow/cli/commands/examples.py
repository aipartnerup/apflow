"""
Examples command for initializing example task data
"""

import typer
import asyncio
from aipartnerupflow.examples.init import init_examples_data_sync, check_if_examples_initialized
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(name="examples", help="Manage example task data")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Force re-initialization even if examples already exist"),
):
    """
    Initialize example task data in the database
    
    This command creates example tasks that demonstrate various features:
    - Tasks with different statuses (completed, failed, pending, in_progress)
    - Task trees with parent-child relationships
    - Tasks with different priorities
    - Tasks with dependencies
    
    Args:
        force: If True, re-initialize even if examples already exist
    """
    try:
        # Check if examples already exist
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(check_if_examples_initialized())
                    finally:
                        new_loop.close()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    already_exists = future.result()
            else:
                already_exists = loop.run_until_complete(check_if_examples_initialized())
        except RuntimeError:
            already_exists = asyncio.run(check_if_examples_initialized())
        
        if already_exists and not force:
            typer.echo("Examples data already exists. Use --force to re-initialize.")
            raise typer.Exit(0)
        
        if already_exists and force:
            typer.echo("Re-initializing examples data...")
        else:
            typer.echo("Initializing examples data...")
        
        # Initialize examples
        count = init_examples_data_sync(force=force)
        
        if count > 0:
            typer.echo(f"Successfully initialized {count} example tasks!")
            typer.echo("You can now view them in the webapp or via the API.")
        else:
            typer.echo("No tasks were created. Examples may already exist.")
            
    except Exception as e:
        typer.echo(f"Error initializing examples: {str(e)}", err=True)
        logger.error(f"Error initializing examples: {e}", exc_info=True)
        raise typer.Exit(1)


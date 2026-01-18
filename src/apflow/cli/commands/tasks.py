"""
Tasks command for managing and querying tasks
"""
import typer
import json
import time
from pathlib import Path
from typing import Optional, List
# TaskExecutor imported on-demand to avoid loading extensions at CLI startup
from apflow.logger import get_logger
from apflow.cli.api_gateway_helper import (
    should_use_api,
    run_async_safe,
    get_api_client_if_configured,
    log_api_usage,
)
from rich.console import Console
from rich.table import Table
from rich.live import Live

logger = get_logger(__name__)


app = typer.Typer(name="tasks", help="Manage and query tasks")
console = Console()

# --- Added: history subcommand ---
@app.command("history")
def history(
    task_id: str = typer.Argument(..., help="Task ID to show history for"),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="Filter by user ID"),
    days: Optional[int] = typer.Option(7, "--days", help="Show last N days (default: 7)"),
    limit: Optional[int] = typer.Option(100, "--limit", help="Limit results (default: 100)"),
):
    """
    Show execution history for a specific task (status changes, retries, logs).
    Args:
        task_id: Task ID to show history for
        user_id: Filter by user ID
        days: Show last N days
        limit: Limit results
    """
    try:
        from apflow.core.storage import get_default_session
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class
        from datetime import datetime, timedelta

        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())

        # Get the task
        task = run_async_safe(task_repository.get_task_by_id(task_id))
        if not task:
            typer.echo(f"Task {task_id} not found", err=True)
            raise typer.Exit(1)

        # Calculate time window
        since = None
        if days:
            since = datetime.utcnow() - timedelta(days=days)

        # Query history (status changes, logs, retries)
        # This assumes a method get_task_history exists; if not, fallback to status log
        try:
            history_items = run_async_safe(task_repository.get_task_history(
                task_id=task_id,
                user_id=user_id,
                since=since,
                limit=limit
            ))
        except AttributeError:
            # Fallback: show status change log if get_task_history not implemented
            history_items = getattr(task, "status_log", [])

        if not history_items:
            typer.echo(f"No history found for task {task_id}")
            return

        typer.echo(json.dumps(history_items, indent=2, default=str))

    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error getting task history")
        raise typer.Exit(1)





@app.command("status")
def status(
    task_ids: List[str] = typer.Argument(..., help="Task IDs to check status for"),
):
    """
    Get status of one or more tasks
    
    Args:
        task_ids: List of task IDs to check
    """
    try:
        using_api = should_use_api()
        log_api_usage("status", using_api)
        
        async def get_statuses():
            async with get_api_client_if_configured() as client:
                if client:
                    return await client.get_tasks_status(task_ids)

                statuses = []
                from apflow.core.execution.task_executor import TaskExecutor

                task_executor = TaskExecutor()

                from apflow.core.storage import get_default_session
                from apflow.core.storage.sqlalchemy.task_repository import (
                    TaskRepository,
                )
                from apflow.core.config import get_task_model_class

                db_session = get_default_session()
                task_repository = TaskRepository(
                    db_session,
                    task_model_class=get_task_model_class(),
                )

                for task_id in task_ids:
                    try:
                        try:
                            task = await task_repository.get_task_by_id(task_id)
                        except Exception as inner_error:
                            logger.warning(
                                f"Failed to get task {task_id}: {str(inner_error)}"
                            )
                            task = None

                        is_running = task_executor.is_task_running(task_id)

                        if task:
                            statuses.append({
                                "task_id": task.id,
                                "context_id": task.id,
                                "name": task.name,
                                "status": task.status,
                                "progress": (
                                    float(task.progress)
                                    if task.progress
                                    else 0.0
                                ),
                                "is_running": is_running,
                                "error": task.error,
                                "started_at": (
                                    task.started_at.isoformat()
                                    if task.started_at
                                    else None
                                ),
                                "updated_at": (
                                    task.updated_at.isoformat()
                                    if task.updated_at
                                    else None
                                ),
                            })
                        elif is_running:
                            statuses.append({
                                "task_id": task_id,
                                "context_id": task_id,
                                "name": "Unknown",
                                "status": "in_progress",
                                "progress": 0.0,
                                "is_running": True,
                                "error": None,
                                "started_at": None,
                                "updated_at": None,
                            })
                        else:
                            statuses.append({
                                "task_id": task_id,
                                "context_id": task_id,
                                "name": "Unknown",
                                "status": "not_found",
                                "progress": 0.0,
                                "is_running": False,
                                "error": None,
                                "started_at": None,
                                "updated_at": None,
                            })
                    except Exception as e:
                        logger.warning(
                            f"Failed to get task {task_id}: {str(e)}"
                        )
                        is_running = task_executor.is_task_running(task_id)
                        statuses.append({
                            "task_id": task_id,
                            "context_id": task_id,
                            "name": "Unknown",
                            "status": "error",
                            "progress": 0.0,
                            "is_running": is_running,
                            "error": str(e),
                            "started_at": None,
                            "updated_at": None,
                        })

                return statuses
        
        statuses = run_async_safe(get_statuses())
        typer.echo(json.dumps(statuses, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def count(
    user_id: Optional[str] = typer.Option(None, "--user-id", "-u", help="Filter by user ID"),
    root_only: bool = typer.Option(False, "--root-only", "-r", help="Count only root tasks (task trees)"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: json or table"),
):
    """
    Get count of tasks from database, grouped by status
    
    Examples:
        apflow tasks count              # All tasks by status
        apflow tasks count --root-only  # Root tasks only (task trees)
        apflow tasks count -f table     # Table format
        apflow tasks count -u user_id   # Filter by user
    """
    try:
        from apflow.core.storage import get_default_session
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class
        from apflow.core.types import TaskStatus

        using_api = should_use_api()
        log_api_usage("count", using_api)
        
        # All possible statuses
        all_statuses = [
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ]
        
        # parent_id filter: "" means root tasks (parent_id is None), None means all tasks
        parent_id_filter = "" if root_only else None
        
        async def get_counts():
            async with get_api_client_if_configured() as client:
                if client:
                    return await client.count_tasks(
                        user_id=user_id,
                        root_only=root_only,
                        statuses=all_statuses,
                    )

                db_session = get_default_session()
                task_repository = TaskRepository(
                    db_session,
                    task_model_class=get_task_model_class(),
                )
                
                try:
                    counts = {}
                    total = 0
                    
                    for status in all_statuses:
                        tasks = await task_repository.query_tasks(
                            user_id=user_id,
                            status=status,
                            parent_id=parent_id_filter,
                            limit=10000,
                        )
                        counts[status] = len(tasks)
                        total += len(tasks)
                    
                    return {"total": total, **counts}
                finally:
                    from sqlalchemy.ext.asyncio import AsyncSession
                    if isinstance(db_session, AsyncSession):
                        await db_session.close()
                    else:
                        db_session.close()
        
        result = run_async_safe(get_counts())
        
        # Add metadata to result
        if user_id:
            result["user_id"] = user_id
        if root_only:
            result["root_only"] = True
        
        # Output based on format
        if output_format == "table":
            _print_count_table(result)
        else:
            typer.echo(json.dumps(result, indent=2))
            
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)


def _print_count_table(counts: dict):
    """Print counts as a formatted table"""
    table = Table(title="Task Statistics")
    table.add_column("Status", style="cyan", no_wrap=True)
    table.add_column("Count", style="magenta", justify="right")
    
    # Status display order and styles
    status_styles = {
        "total": ("bold white", "Total"),
        "pending": ("dim", "Pending"),
        "in_progress": ("blue", "In Progress"),
        "completed": ("green", "Completed"),
        "failed": ("red", "Failed"),
        "cancelled": ("yellow", "Cancelled"),
    }
    
    # Add filter info rows
    if "user_id" in counts:
        table.add_row("[dim]User ID[/dim]", f"[dim]{counts['user_id']}[/dim]")
    if counts.get("root_only"):
        table.add_row("[dim]Filter[/dim]", "[dim]Root tasks only[/dim]")
    if "user_id" in counts or counts.get("root_only"):
        table.add_section()
    
    # Add status rows in order
    for status, (style, label) in status_styles.items():
        if status in counts:
            table.add_row(f"[{style}]{label}[/{style}]", f"[{style}]{counts[status]}[/{style}]")
    
    console.print(table)





@app.command("cancel")
def cancel(
    task_ids: List[str] = typer.Argument(..., help="Task IDs to cancel"),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Force cancellation (immediate stop)",
    ),
):
    """
    Cancel one or more running tasks
    
    This calls TaskExecutor.cancel_task() which:
    1. Calls executor.cancel() if executor supports cancellation
    2. Updates database with cancelled status and token_usage
    
    Args:
        task_ids: List of task IDs to cancel
        force: If True, force immediate cancellation (may lose data)
    """
    try:
        using_api = should_use_api()
        log_api_usage("cancel", using_api)
        
        async def cancel_tasks():
            results = []
            
            async with get_api_client_if_configured() as client:
                if client:
                    api_results = await client.cancel_tasks(
                        task_ids, force=force
                    )
                    results.extend(api_results)
                else:
                    error_message = (
                        "Cancelled by user"
                        if not force
                        else "Force cancelled by user"
                    )

                    from apflow.core.execution.task_executor import TaskExecutor

                    task_executor = TaskExecutor()

                    for task_id in task_ids:
                        try:
                            cancel_result = (
                                await task_executor.cancel_task(
                                    task_id, error_message
                                )
                            )

                            cancel_result["task_id"] = task_id
                            cancel_result["force"] = force
                            results.append(cancel_result)
                        except Exception as e:
                            logger.error(
                                f"Error cancelling task {task_id}: "
                                f"{str(e)}",
                                exc_info=True,
                            )
                            results.append({
                                "task_id": task_id,
                                "status": "error",
                                "error": str(e),
                            })
            
            return results
        
        results = run_async_safe(cancel_tasks())
        typer.echo(json.dumps(results, indent=2))
        
        # Check if any cancellation failed
        failed = any(
            r.get("status") == "error"
            or (
                r.get("status") == "failed"
                and "not found" in r.get("message", "").lower()
            )
            for r in results
        )
        if failed:
            raise typer.Exit(1)
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error cancelling tasks")
        raise typer.Exit(1)


def _clone_command(
    task_id: str,
    output: Optional[Path],
    origin_type: str,
    recursive: bool,
    link_task_ids: Optional[str],
    reset_fields: Optional[str],
    dry_run: bool,
) -> None:
    """Shared implementation for tasks.clone."""
    command_name = "clone"
    command_label = "Task clone"

    try:
       
        # Validate origin_type
        if origin_type not in ("copy", "link", "archive", "mixed"):
            typer.echo(
                f"Error: Invalid origin_type '{origin_type}'. Must be 'copy', 'link', 'archive', or 'mixed'",
                err=True,
            )
            raise typer.Exit(1)

        if origin_type == "mixed" and not link_task_ids:
            typer.echo("Error: --link-task-ids is required when origin-type='mixed'", err=True)
            raise typer.Exit(1)

        # Parse link_task_ids if provided
        parsed_link_task_ids = None
        if link_task_ids:
            parsed_link_task_ids = [tid.strip() for tid in link_task_ids.split(",") if tid.strip()]

        # Parse reset_fields as key=value pairs
        reset_kwargs = {}
        if reset_fields:
            for field_pair in reset_fields.split(","):
                if "=" in field_pair:
                    key, value = field_pair.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Interpret empty value as None
                    reset_kwargs[key] = None if value == "" else value
                else:
                    typer.echo(
                        f"⚠️  Warning: Invalid reset field format '{field_pair}', expected 'key=value'",
                        err=True,
                    )

        save = not dry_run
        verb_map = {"copy": "copied", "link": "linked", "archive": "archiveted", "mixed": "cloned"}
        verb = verb_map.get(origin_type, f"{origin_type}ed")
        using_api = should_use_api()
        log_api_usage(command_name, using_api)

        # first try using API if configured
        async def try_api_clone():
            async with get_api_client_if_configured() as client:
                if not client:
                    return None

                return await client.clone_task(
                    task_id=task_id,
                    origin_type=origin_type,
                    recursive=recursive,
                    link_task_ids=parsed_link_task_ids,
                    reset_fields=reset_kwargs,
                    save=save,
                )

        api_response = run_async_safe(try_api_clone())

        if api_response is not None:
            result_output = api_response
            if isinstance(api_response, dict):
                result_output = [api_response]
                task_count = 1
                root_task_id = result_output.get("id")
            else:
                task_count = len(result_output)
                root_task_id = result_output[0].get("id")
            
            if output:
                with open(output, "w") as f:
                    json.dump(result_output, f, indent=2)
                typer.echo(f"{command_label} {'preview' if dry_run else 'result'} saved to {output}")
            else:
                typer.echo(json.dumps(result_output, indent=2))

            if save:
                typer.echo(
                    f"\n✅ Successfully {verb} task {task_id} to new task {root_task_id} "
                    f"(origin_type: {origin_type}, recursive: {recursive})"
                )
            else:
                typer.echo(
                    f"\n✅ Preview generated: {task_count} tasks (origin_type: {origin_type}, not saved)"
                )
            return

        from apflow.core.storage import get_default_session
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class
        from apflow.core.execution.task_creator import TaskCreator

        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())

        async def get_original_task():
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            return task

        original_task = run_async_safe(get_original_task())

        task_creator = TaskCreator(db_session)

        async def clone_task():
            if origin_type == "link":
                return await task_creator.from_link(
                    _original_task=original_task,
                    _save=save,
                    _recursive=recursive,
                    **reset_kwargs,
                )
            if origin_type == "archive":
                return await task_creator.from_archive(
                    _original_task=original_task,
                    _save=save,
                    _recursive=recursive,
                    **reset_kwargs,
                )
            if origin_type == "mixed":
                return await task_creator.from_mixed(
                    _original_task=original_task,
                    _save=save,
                    _recursive=recursive,
                    _link_task_ids=parsed_link_task_ids,
                    **reset_kwargs,
                )
            return await task_creator.from_copy(
                _original_task=original_task,
                _save=save,
                _recursive=recursive,
                **reset_kwargs,
            )

        result = run_async_safe(clone_task())
        result_output = result.output_list()
        if len(result_output) == 1:
            result_output = result_output[0]  # Return single task dict if only one task
        
        new_task_id = result.task.id
        task_count = len(result_output)

        if output:
            with open(output, "w") as f:
                json.dump(result_output, f, indent=2, default=str)
            typer.echo(f"{command_label} {'preview' if dry_run else 'result'} saved to {output}")
        else:
            typer.echo(json.dumps(result_output, indent=2, default=str))

        if save:
            typer.echo(
                f"\n✅ Successfully {verb} task {task_id} to new task {new_task_id} "
                f"(origin_type: {origin_type}, recursive: {recursive})"
            )
        else:
            typer.echo(
                f"\n✅ Preview generated: {task_count} tasks (origin_type: {origin_type}, not saved)"
            )

    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error cloning task")
        raise typer.Exit(1)


@app.command(name="clone")
def clone(
    task_id: str = typer.Argument(..., help="Task ID to clone"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path for cloned task tree"),
    origin_type: str = typer.Option("copy", "--origin-type", help="Origin type: 'copy' (default), 'link', 'archive', or 'mixed'"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Clone/link entire subtree (default: True)"),
    link_task_ids: Optional[str] = typer.Option(None, "--link-task-ids", help="Comma-separated task IDs to link (for mixed mode)"),
    reset_fields: Optional[str] = typer.Option(None, "--reset-fields", help="Field overrides as key=value pairs (e.g., 'user_id=new_user,priority=1')"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview task clone without saving to database"),
):
    """
    Create a clone/link/archive of a task tree (primary command).

    Origin types: copy (default), link, archive, mixed.
    """
    return _clone_command(
        task_id=task_id,
        output=output,
        origin_type=origin_type,
        recursive=recursive,
        link_task_ids=link_task_ids,
        reset_fields=reset_fields,
        dry_run=dry_run,
    )


@app.command()
def get(
    task_id: str = typer.Argument(..., help="Task ID to get"),
):
    """
    Get task by ID (equivalent to tasks.get API)
    
    Args:
        task_id: Task ID to retrieve
    """
    try:
        using_api = should_use_api()
        log_api_usage("get", using_api)
        
        async def get_task():
            async with get_api_client_if_configured() as client:
                if client:
                    # Use API
                    task_dict = await client.get_task(task_id)
                    return task_dict
                else:
                    # Use local database
                    from apflow.core.storage import get_default_session
                    from apflow.core.storage.sqlalchemy.task_repository import (
                        TaskRepository,
                    )
                    from apflow.core.config import get_task_model_class
                    
                    db_session = get_default_session()
                    task_repository = TaskRepository(
                        db_session,
                        task_model_class=get_task_model_class(),
                    )
                    
                    task = await task_repository.get_task_by_id(task_id)
                    if not task:
                        raise ValueError(f"Task {task_id} not found")
                    return task.output()
        
        task_dict = run_async_safe(get_task())
        typer.echo(json.dumps(task_dict, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error getting task")
        raise typer.Exit(1)


@app.command()
def create(
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="JSON file containing task(s) definition"),
    stdin: bool = typer.Option(False, "--stdin", help="Read from stdin instead of file"),
):
    """
    Create task tree from JSON file or stdin (equivalent to tasks.create API)
    
    Args:
        file: JSON file containing task(s) definition
        stdin: Read from stdin instead of file

    """
    try:
        import sys
        
        # Read task data
        if stdin:
            task_data = json.load(sys.stdin)
        elif file:
            with open(file, 'r') as f:
                task_data = json.load(f)
        else:
            typer.echo("Error: Either --file or --stdin must be specified", err=True)
            raise typer.Exit(1)
        
        # Convert to tasks array format if needed
        if isinstance(task_data, dict):
            tasks_array = [task_data]
        elif isinstance(task_data, list):
            tasks_array = task_data
        else:
            raise ValueError("Task data must be a dict (single task) or list (tasks array)")

        using_api = should_use_api()
        log_api_usage("create", using_api)

        async def try_api_create():
            async with get_api_client_if_configured() as client:
                if not client:
                    return None
                return await client.create_tasks(tasks_array)

        api_result = run_async_safe(try_api_create())
        if api_result is not None:
            typer.echo(json.dumps(api_result, indent=2))
            root_task_id = api_result.get("task", {}).get("id")
            if root_task_id:
                typer.echo(f"\n✅ Successfully created task tree: root task {root_task_id}")
            return
        
        from apflow.core.storage import get_default_session
        from apflow.core.execution.task_creator import TaskCreator
        
        db_session = get_default_session()
        task_creator = TaskCreator(db_session)
        
        async def create_task():
            return await task_creator.create_task_tree_from_array(tasks=tasks_array)
        
        task_tree = run_async_safe(create_task())
        result = task_tree.output_list()
        if len(result) == 1:    
            result = result[0]  # Return single task dict if only one task
        typer.echo(json.dumps(result, indent=2))
        typer.echo(f"\n✅ Successfully created task tree: root task {task_tree.task.id}")
        
    except ValueError as e:
        if "external dependencies" in str(e):
            typer.echo(f"Error: Cannot copy/archive a subtree with external dependencies.\n{str(e)}", err=True)
            logger.error(f"External dependency error: {str(e)}")
            sys.exit(1)
        else:
            typer.echo(f"Error: {str(e)}", err=True)
            logger.exception("ValueError during task creation")
            sys.exit(1)
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error creating task")
        sys.exit(1)


@app.command()
def update(
    task_id: str = typer.Argument(..., help="Task ID to update"),
    name: Optional[str] = typer.Option(None, "--name", help="Update task name"),
    status: Optional[str] = typer.Option(None, "--status", help="Update task status"),
    progress: Optional[float] = typer.Option(None, "--progress", help="Update task progress (0.0-1.0)"),
    error: Optional[str] = typer.Option(None, "--error", help="Update task error message"),
    result: Optional[str] = typer.Option(None, "--result", help="Update task result (JSON string)"),
    priority: Optional[int] = typer.Option(None, "--priority", help="Update task priority"),
    inputs: Optional[str] = typer.Option(None, "--inputs", help="Update task inputs (JSON string)"),
    params: Optional[str] = typer.Option(None, "--params", help="Update task params (JSON string)"),
    schemas: Optional[str] = typer.Option(None, "--schemas", help="Update task schemas (JSON string)"),
):
    """
    Update task fields (equivalent to tasks.update API)
    
    Args:
        task_id: Task ID to update
        name: Update task name
        status: Update task status
        progress: Update task progress (0.0-1.0)
        error: Update task error message
        result: Update task result (JSON string)
        priority: Update task priority
        inputs: Update task inputs (JSON string)
        params: Update task params (JSON string)
        schemas: Update task schemas (JSON string)
    """
    try:
        from apflow.core.storage import get_default_session
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class
        
        using_api = should_use_api()
        log_api_usage("update", using_api)
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        # Build update params
        update_params = {}
        if name is not None:
            update_params["name"] = name
        if status is not None:
            update_params["status"] = status
        if progress is not None:
            update_params["progress"] = progress
        if error is not None:
            update_params["error"] = error
        if result is not None:
            update_params["result"] = json.loads(result)
        if priority is not None:
            update_params["priority"] = priority
        if inputs is not None:
            update_params["inputs"] = json.loads(inputs)
        if params is not None:
            update_params["params"] = json.loads(params)
        if schemas is not None:
            update_params["schemas"] = json.loads(schemas)
        
        if not update_params:
            typer.echo("Error: At least one field must be specified for update", err=True)
            raise typer.Exit(1)
        
        async def update_task():
            async with get_api_client_if_configured() as client:
                if client:
                    return await client.update_task(task_id, **update_params)

            # Get task first
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Update status-related fields if status is provided
            if "status" in update_params:
                await task_repository.update_task(
                    task_id=task_id,
                    status=update_params["status"],
                    error=update_params.get("error"),
                    result=update_params.get("result"),
                    progress=update_params.get("progress"),
                )
            else:
                # Update individual fields
                if "error" in update_params:
                    await task_repository.update_task(
                        task_id=task_id,
                        status=task.status,
                        error=update_params["error"]
                    )
                if "result" in update_params:
                    await task_repository.update_task(
                        task_id=task_id,
                        status=task.status,
                        result=update_params["result"]
                    )
                if "progress" in update_params:
                    await task_repository.update_task(
                        task_id=task_id,
                        status=task.status,
                        progress=update_params["progress"]
                    )
            
            # Update other fields
            if "name" in update_params:
                await task_repository.update_task(task_id, name=update_params["name"])
            if "priority" in update_params:
                await task_repository.update_task(task_id, priority=update_params["priority"])
            if "inputs" in update_params:
                await task_repository.update_task(task_id, inputs=update_params["inputs"])
            if "params" in update_params:
                await task_repository.update_task(task_id, params=update_params["params"])
            if "schemas" in update_params:
                await task_repository.update_task(task_id, schemas=update_params["schemas"])
            
            # Get updated task
            updated_task = await task_repository.get_task_by_id(task_id)
            if not updated_task:
                raise ValueError(f"Task {task_id} not found after update")
            
            return updated_task.output()
        
        task_dict = run_async_safe(update_task())
        typer.echo(json.dumps(task_dict, indent=2))
        typer.echo(f"\n✅ Successfully updated task {task_id}")
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error updating task")
        raise typer.Exit(1)


@app.command()
def delete(
    task_id: str = typer.Argument(..., help="Task ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion (if needed)"),
):
    """
    Delete task (equivalent to tasks.delete API)
    
    Args:
        task_id: Task ID to delete
        force: Force deletion (if needed)
    """
    try:
        from apflow.core.storage import get_default_session
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class
        
        using_api = should_use_api()
        log_api_usage("delete", using_api)
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        async def delete_task():
            async with get_api_client_if_configured() as client:
                if client:
                    return await client.delete_task(task_id)

            # Get task first to check if exists
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Get all children recursively
            all_children = await task_repository.get_all_children_recursive(task_id)
            
            # Check if all tasks are pending
            all_tasks_to_check = [task] + all_children
            non_pending = [t for t in all_tasks_to_check if t.status != "pending"]
            
            # Check for linked tasks
            from apflow.core.storage.sqlalchemy.models import TaskOriginType
            has_references = await task_repository.task_has_references(task_id, TaskOriginType.link)
            
            # Build error message if deletion is not allowed
            error_parts = []
            if non_pending:
                non_pending_children = [t for t in non_pending if t.id != task_id]
                if non_pending_children:
                    children_info = ", ".join([f"{t.id}: {t.status}" for t in non_pending_children])
                    error_parts.append(f"task has {len(non_pending_children)} non-pending children: [{children_info}]")
                if any(t.id == task_id for t in non_pending):
                    main_task_status = next(t.status for t in non_pending if t.id == task_id)
                    error_parts.append(f"task status is '{main_task_status}' (must be 'pending')")
            
            if has_references:
                error_parts.append("task has dependent tasks")
            
            if error_parts and not force:
                error_message = "Cannot delete task: " + "; ".join(error_parts)
                raise ValueError(error_message)
            
            # Delete all tasks (children first, then parent)
            deleted_count = 0
            for child in all_children:
                success = await task_repository.delete_task(child.id)
                if success:
                    deleted_count += 1
            
            # Delete the main task
            success = await task_repository.delete_task(task_id)
            if success:
                deleted_count += 1
            
            return {
                "success": True,
                "task_id": task_id,
                "deleted_count": deleted_count,
                "children_deleted": len(all_children)
            }
        
        result = run_async_safe(delete_task())
        typer.echo(json.dumps(result, indent=2))
        children_deleted = result.get("children_deleted", 0)
        typer.echo(
            f"\n✅ Successfully deleted task {task_id} and {children_deleted} children"
        )
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error deleting task")
        raise typer.Exit(1)


@app.command()
def tree(
    task_id: str = typer.Argument(..., help="Task ID to get tree for"),
):
    """
    Get task tree structure (equivalent to tasks.tree API)
    
    Args:
        task_id: Task ID (root or any task in tree)
    """
    try:
        from apflow.core.storage import get_default_session
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class
        
        using_api = should_use_api()
        log_api_usage("tree", using_api)
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        async def get_tree():
            async with get_api_client_if_configured() as client:
                if client:
                    return await client.get_task_tree(task_id)

            # Get task
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # # If task has parent, find root first
            # root_task = await task_repository.get_root_task(task)
            
            # Build task tree
            task_tree_node = await task_repository.get_task_tree_for_api(task)
            
            # Convert TaskTreeNode to dictionary format
            return task_tree_node.output()
        
        result = run_async_safe(get_tree())
        typer.echo(json.dumps(result, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error getting task tree")
        raise typer.Exit(1)


@app.command()
def children(
    parent_id: Optional[str] = typer.Option(None, "--parent-id", "-p", help="Parent task ID"),
    task_id: Optional[str] = typer.Option(None, "--task-id", "-t", help="Task ID (alternative to parent-id)"),
):
    """
    Get child tasks (equivalent to tasks.children API)
    
    Args:
        parent_id: Parent task ID
        task_id: Task ID (alternative to parent-id)
    """
    try:
        parent_task_id = parent_id or task_id
        if not parent_task_id:
            typer.echo("Error: Either --parent-id or --task-id must be specified", err=True)
            raise typer.Exit(1)
        
        from apflow.core.storage import get_default_session
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class
        
        using_api = should_use_api()
        log_api_usage("children", using_api)
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        async def get_children():
            async with get_api_client_if_configured() as client:
                if client:
                    return await client.get_task_children(parent_task_id)

            # Get parent task to verify it exists
            parent_task = await task_repository.get_task_by_id(parent_task_id)
            if not parent_task:
                raise ValueError(f"Parent task {parent_task_id} not found")
            
            # Get child tasks
            children = await task_repository.get_child_tasks_by_parent_id(parent_task_id)
            
            # Convert to dictionaries
            return [child.output() for child in children]
        
        result = run_async_safe(get_children())
        typer.echo(json.dumps(result, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error getting child tasks")
        raise typer.Exit(1)


@app.command("list")
def list_tasks(
    user_id: Optional[str] = typer.Option(
        None, "--user-id", "-u", help="Filter by user ID",
    ),
    status: Optional[str] = typer.Option(
        None, "--status", "-s", help="Filter by status",
    ),
    root_only: bool = typer.Option(
        True, "--root-only/--all-tasks",
        help="Only show root tasks (default: True)",
    ),
    limit: int = typer.Option(
        100, "--limit", "-l",
        help="Maximum number of tasks to return",
    ),
    offset: int = typer.Option(
        0, "--offset", "-o", help="Pagination offset",
    ),
):
    """
    List tasks from database or API
    
    Args:
        user_id: Filter by user ID
        status: Filter by status
        root_only: Only show root tasks (default: True)
        limit: Maximum number of tasks to return
        offset: Pagination offset
    """
    try:
        using_api = should_use_api()
        log_api_usage("list", using_api)
        
        async def get_all_tasks():
            async with get_api_client_if_configured() as client:
                if client:
                    # Use API
                    tasks = await client.list_tasks(
                        user_id=user_id,
                        status=status,
                        root_only=root_only,
                        limit=limit,
                        offset=offset,
                    )
                    return tasks
                else:
                    # Use local database
                    from apflow.core.storage import get_default_session
                    from apflow.core.storage.sqlalchemy.task_repository import (
                        TaskRepository,
                    )
                    from apflow.core.config import get_task_model_class
                    
                    db_session = get_default_session()
                    task_repository = TaskRepository(
                        db_session,
                        task_model_class=get_task_model_class(),
                    )
                    
                    try:
                        parent_id_filter = "" if root_only else None
                        tasks = await task_repository.query_tasks(
                            user_id=user_id,
                            status=status,
                            parent_id=parent_id_filter,
                            limit=limit,
                            offset=offset,
                            order_by="created_at",
                            order_desc=True,
                        )
                        
                        # Convert to dictionaries
                        task_dicts = []
                        for task in tasks:
                            task_dict = task.output()
                            
                            # Check if task has children
                            if not task_dict.get("has_children"):
                                children = (
                                    await task_repository
                                    .get_child_tasks_by_parent_id(
                                        task.id
                                    )
                                )
                                task_dict["has_children"] = (
                                    len(children) > 0
                                )
                            
                            task_dicts.append(task_dict)
                        
                        return task_dicts
                    finally:
                        from sqlalchemy.ext.asyncio import AsyncSession
                        if isinstance(db_session, AsyncSession):
                            await db_session.close()
                        else:
                            db_session.close()
        
        tasks = run_async_safe(get_all_tasks())
        typer.echo(json.dumps(tasks, indent=2))
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error listing all tasks")
        raise typer.Exit(1)


@app.command("watch")
def watch(
    task_id: Optional[str] = typer.Option(None, "--task-id", "-t", help="Watch specific task ID"),
    interval: float = typer.Option(1.0, "--interval", "-i", help="Update interval in seconds"),
    all_tasks: bool = typer.Option(False, "--all", "-a", help="Watch all running tasks"),
):
    """
    Watch task status in real-time (interactive mode)
    
    This command provides real-time monitoring of task status updates.
    Press Ctrl+C to stop watching.
    
    Args:
        task_id: Specific task ID to watch (optional)
        interval: Update interval in seconds (default: 1.0)
        all_tasks: Watch all running tasks instead of specific task
    """
    try:
        from apflow.core.execution.task_executor import TaskExecutor
        task_executor = TaskExecutor()
        
        # Get database session
        from apflow.core.storage import get_default_session
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class
        
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        
        # Helper function to get task
        async def get_task_safe(task_id: str):
            try:
                return await task_repository.get_task_by_id(task_id)
            except Exception:
                return None
        
        def create_status_table(task_ids: List[str]) -> Table:
            """Create a table showing task statuses"""
            table = Table(title="Task Status Monitor")
            table.add_column("Task ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Progress", style="yellow")
            table.add_column("Running", style="blue")
            
            for tid in task_ids:
                is_running = task_executor.is_task_running(tid)
                task = run_async_safe(get_task_safe(tid))
                
                if task:
                    status_style = {
                        "completed": "green",
                        "failed": "red",
                        "cancelled": "yellow",
                        "in_progress": "blue",
                        "pending": "dim"
                    }.get(task.status, "white")
                    
                    progress_str = f"{float(task.progress) * 100:.1f}%" if task.progress else "0.0%"
                    running_str = "✓" if is_running else "✗"
                    
                    table.add_row(
                        task.id[:8] + "...",
                        task.name[:30] + "..." if len(task.name) > 30 else task.name,
                        f"[{status_style}]{task.status}[/{status_style}]",
                        progress_str,
                        running_str
                    )
                else:
                    table.add_row(
                        tid[:8] + "...",
                        "Unknown",
                        "[dim]unknown[/dim]",
                        "0.0%",
                        "✓" if is_running else "✗"
                    )
            
            return table
        
        # Determine which tasks to watch
        if all_tasks:
            # Watch all running tasks
            task_ids_to_watch = task_executor.get_all_running_tasks()
            if not task_ids_to_watch:
                typer.echo("No running tasks to watch")
                return
        elif task_id:
            # Watch specific task
            task_ids_to_watch = [task_id]
        else:
            typer.echo("Error: Either --task-id or --all must be specified", err=True)
            raise typer.Exit(1)
        
        typer.echo(f"Watching {len(task_ids_to_watch)} task(s). Press Ctrl+C to stop.")
        
        try:
            # Create live display
            with Live(create_status_table(task_ids_to_watch), refresh_per_second=1/interval, console=console) as live:
                while True:
                    time.sleep(interval)
                    live.update(create_status_table(task_ids_to_watch))

                    # Check if all watched tasks are missing (None)
                    missing_count = 0
                    for tid in task_ids_to_watch:
                        task = run_async_safe(get_task_safe(tid))
                        if task is None:
                            missing_count += 1
                    if missing_count == len(task_ids_to_watch):
                        typer.echo("No such task(s) or database error, exiting.")
                        break

                    # Check if all tasks are finished
                    if not all_tasks:
                        # For single task, check if it's finished
                        task = run_async_safe(get_task_safe(task_id))
                        if task and task.status in ["completed", "failed", "cancelled"]:
                            typer.echo(f"\nTask {task_id} finished with status: {task.status}")
                            break
        except KeyboardInterrupt:
            typer.echo("\nStopped watching")
            
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        logger.exception("Error watching tasks")
        raise typer.Exit(1)


"""
Monitoring commands for real-time task observation

Provides commands for monitoring task status, watching task progress,
viewing execution timeline, and checking database health.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.live import Live
from rich.panel import Panel

from apflow.logger import get_logger
from apflow.cli.api_gateway_helper import (
    should_use_api,
    run_async_safe,
    get_api_client_if_configured,
)

logger = get_logger(__name__)
console = Console()

app = typer.Typer(name="monitor", help="Monitor tasks and system health")


def format_duration(seconds: Optional[float]) -> str:
    """Format duration in human-readable format"""
    if seconds is None:
        return "N/A"

    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def get_status_emoji(status: str) -> str:
    """Get emoji for task status"""
    emoji_map = {
        "pending": "⏳",
        "in_progress": "🔄",
        "completed": "✅",
        "failed": "❌",
        "cancelled": "🚫",
    }
    return emoji_map.get(status, "❓")


@app.command("status")
def status_command(
    all_tasks: bool = typer.Option(
        False, "--all", "-a", help="Show all tasks (including completed)"
    ),
    tree: bool = typer.Option(False, "--tree", "-t", help="Show task tree structure"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of tasks to display"),
):
    """
    Display current task status

    Shows running tasks by default, or all tasks with --all flag.
    """
    try:
        should_use_api()

        async def get_tasks_status():
            async with get_api_client_if_configured() as client:
                if client:
                    # API mode - fetch from server
                    if all_tasks:
                        response = await client.list_tasks(limit=limit)
                        return response.get("tasks", [])
                    else:
                        # Get running tasks only
                        response = await client.list_tasks(status="in_progress", limit=limit)
                        return response.get("tasks", [])
                else:
                    # Local mode - query database
                    from apflow.core.storage import get_default_session
                    from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
                    from apflow.core.config import get_task_model_class
                    from apflow.core.execution.task_executor import TaskExecutor

                    db_session = get_default_session()
                    repo = TaskRepository(db_session, task_model_class=get_task_model_class())
                    executor = TaskExecutor()

                    if all_tasks:
                        # Get all recent tasks
                        tasks = await repo.query_tasks(
                            limit=limit, order_by="updated_at", order_desc=True
                        )
                    else:
                        # Get only running and pending tasks
                        tasks = await repo.query_tasks_by_statuses(
                            ["in_progress", "pending"],
                            limit=limit,
                            order_by="updated_at",
                            order_desc=True,
                        )

                    # Convert to dict format
                    result = []
                    for task in tasks:
                        is_running = executor.is_task_running(task.id)

                        # Calculate elapsed time
                        elapsed = None
                        if task.started_at:
                            if task.completed_at:
                                elapsed = (task.completed_at - task.started_at).total_seconds()
                            else:
                                elapsed = (
                                    datetime.now(timezone.utc) - task.started_at
                                ).total_seconds()

                        result.append(
                            {
                                "id": task.id,
                                "name": task.name,
                                "status": task.status,
                                "progress": float(task.progress) if task.progress else 0.0,
                                "is_running": is_running,
                                "elapsed_time": elapsed,
                                "error": task.error,
                            }
                        )

                    return result

        tasks = run_async_safe(get_tasks_status())

        if not tasks:
            if all_tasks:
                console.print("[yellow]No tasks found[/yellow]")
            else:
                console.print("[green]No running tasks[/green]")
            return

        # Create table
        table = Table(title=f"Task Status ({len(tasks)} tasks)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Progress", style="yellow")
        table.add_column("Elapsed", style="blue")
        table.add_column("Error", style="red")

        for task in tasks:
            status_emoji = get_status_emoji(task["status"])
            status_text = f"{status_emoji} {task['status']}"

            progress_value = task.get("progress", 0.0)
            progress_text = f"{progress_value * 100:.0f}%" if progress_value else "N/A"

            elapsed_text = format_duration(task.get("elapsed_time"))

            error_text = task.get("error", "")
            if error_text and len(error_text) > 50:
                error_text = error_text[:47] + "..."

            table.add_row(
                task["id"][:12],  # Show first 12 chars of ID
                task["name"],
                status_text,
                progress_text,
                elapsed_text,
                error_text or "-",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error fetching task status: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command("watch")
def watch_command(
    task_id: str = typer.Argument(..., help="Task ID to watch"),
    interval: float = typer.Option(1.0, "--interval", "-i", help="Refresh interval in seconds"),
):
    """
    Watch task progress in real-time

    Continuously monitors and displays task status until completion.
    """
    try:
        should_use_api()

        async def watch_task():
            async with get_api_client_if_configured() as client:
                with Live(refresh_per_second=1 / interval, console=console) as live:
                    while True:
                        if client:
                            # API mode
                            task_data = await client.get_task(task_id)
                        else:
                            # Local mode
                            from apflow.core.storage import get_default_session
                            from apflow.core.storage.sqlalchemy.task_repository import (
                                TaskRepository,
                            )
                            from apflow.core.config import get_task_model_class
                            from apflow.core.execution.task_executor import TaskExecutor

                            db_session = get_default_session()
                            repo = TaskRepository(
                                db_session, task_model_class=get_task_model_class()
                            )
                            executor = TaskExecutor()

                            task = await repo.get_task_by_id(task_id)
                            if not task:
                                raise ValueError(f"Task {task_id} not found")

                            # Calculate elapsed time
                            elapsed = None
                            if task.started_at:
                                if task.completed_at:
                                    elapsed = (task.completed_at - task.started_at).total_seconds()
                                else:
                                    elapsed = (
                                        datetime.now(timezone.utc) - task.started_at
                                    ).total_seconds()

                            # Estimate remaining time
                            remaining = None
                            if task.progress and task.progress > 0 and elapsed:
                                total_estimated = elapsed / task.progress
                                remaining = total_estimated - elapsed

                            task_data = {
                                "id": task.id,
                                "name": task.name,
                                "status": task.status,
                                "progress": float(task.progress) if task.progress else 0.0,
                                "elapsed_time": elapsed,
                                "remaining_time": remaining,
                                "error": task.error,
                                "is_running": executor.is_task_running(task.id),
                            }

                        # Create real-time panel
                        status_emoji = get_status_emoji(task_data["status"])

                        content = f"""[bold]ID:[/bold] {task_data['id']}
[bold]Name:[/bold] {task_data['name']}
[bold]Status:[/bold] {status_emoji} {task_data['status']}
[bold]Progress:[/bold] {task_data['progress'] * 100:.1f}%
[bold]Elapsed:[/bold] {format_duration(task_data.get('elapsed_time'))}
[bold]Estimated Remaining:[/bold] {format_duration(task_data.get('remaining_time'))}
[bold]Running:[/bold] {'Yes' if task_data.get('is_running') else 'No'}"""

                        if task_data.get("error"):
                            content += f"\n[bold red]Error:[/bold red] {task_data['error']}"

                        panel = Panel(
                            content,
                            title=f"[bold]Task Monitor: {task_data['name']}[/bold]",
                            border_style=(
                                "green" if task_data["status"] == "in_progress" else "yellow"
                            ),
                        )

                        live.update(panel)

                        # Stop watching if task completed
                        if task_data["status"] in ["completed", "failed", "cancelled"]:
                            break

                        await asyncio.sleep(interval)

        run_async_safe(watch_task())

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped watching task[/yellow]")
    except Exception as e:
        console.print(f"[red]Error watching task: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command("trace")
def trace_command(
    task_id: str = typer.Argument(..., help="Task ID to trace"),
):
    """
    Display task execution timeline

    Shows detailed execution timeline including dependencies.
    """
    try:
        should_use_api()

        async def get_task_timeline():
            async with get_api_client_if_configured() as client:
                if client:
                    # API mode
                    task_data = await client.get_task(task_id)
                else:
                    # Local mode
                    from apflow.core.storage import get_default_session
                    from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
                    from apflow.core.config import get_task_model_class

                    db_session = get_default_session()
                    repo = TaskRepository(db_session, task_model_class=get_task_model_class())

                    task = await repo.get_task_by_id(task_id)
                    if not task:
                        raise ValueError(f"Task {task_id} not found")

                    # Get dependency tasks
                    dep_tasks = []
                    if task.dependencies:
                        for dep in task.dependencies:
                            dep_task = await repo.get_task_by_id(dep["id"])
                            if dep_task:
                                dep_tasks.append(
                                    {
                                        "id": dep_task.id,
                                        "name": dep_task.name,
                                        "status": dep_task.status,
                                        "required": dep.get("required", False),
                                    }
                                )

                    task_data = {
                        "id": task.id,
                        "name": task.name,
                        "status": task.status,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "started_at": task.started_at.isoformat() if task.started_at else None,
                        "completed_at": (
                            task.completed_at.isoformat() if task.completed_at else None
                        ),
                        "dependencies": dep_tasks,
                    }

                return task_data

        task_data = run_async_safe(get_task_timeline())

        # Create timeline tree
        tree = Tree(f"📊 [bold]Task Timeline: {task_data['name']}[/bold]")

        # Add creation
        if task_data.get("created_at"):
            tree.add(f"🔵 Created: {task_data['created_at']}")

        # Add start
        if task_data.get("started_at"):
            created_time = (
                datetime.fromisoformat(task_data["created_at"])
                if task_data.get("created_at")
                else None
            )
            started_time = datetime.fromisoformat(task_data["started_at"])
            if created_time:
                queue_time = (started_time - created_time).total_seconds()
                tree.add(f"🟢 Started: {task_data['started_at']} (+{format_duration(queue_time)})")
            else:
                tree.add(f"🟢 Started: {task_data['started_at']}")

        # Add completion
        if task_data.get("completed_at"):
            started_time = (
                datetime.fromisoformat(task_data["started_at"])
                if task_data.get("started_at")
                else None
            )
            completed_time = datetime.fromisoformat(task_data["completed_at"])
            if started_time:
                exec_time = (completed_time - started_time).total_seconds()
                status_emoji = get_status_emoji(task_data["status"])
                tree.add(
                    f"{status_emoji} Completed: {task_data['completed_at']} (+{format_duration(exec_time)})"
                )
            else:
                tree.add(f"✅ Completed: {task_data['completed_at']}")

        # Add dependencies
        if task_data.get("dependencies"):
            deps_node = tree.add("📦 [bold]Dependencies[/bold]")
            for dep in task_data["dependencies"]:
                status_emoji = get_status_emoji(dep["status"])
                required_text = " (required)" if dep.get("required") else ""
                deps_node.add(f"{status_emoji} {dep['name']}: {dep['status']}{required_text}")

        console.print(tree)

    except Exception as e:
        console.print(f"[red]Error fetching task timeline: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command("db")
def db_status_command():
    """
    Display database connection status and statistics

    Shows database type, connection info, size, and task counts.
    """
    try:
        should_use_api()

        async def get_db_info():
            async with get_api_client_if_configured() as client:
                if client:
                    # API mode - get from server
                    return await client.get_system_health()
                else:
                    # Local mode
                    from apflow.core.storage import get_default_session, get_engine_url
                    from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
                    from apflow.core.config import get_task_model_class
                    import os

                    db_session = get_default_session()
                    repo = TaskRepository(db_session, task_model_class=get_task_model_class())

                    # Get database URL and parse
                    engine_url = get_engine_url()
                    dialect = engine_url.split("://")[0] if "://" in engine_url else "unknown"

                    # Get task count
                    all_tasks = await repo.query_tasks(limit=10000)  # Get up to 10k for count
                    task_count = len(all_tasks)

                    # Get database file size (for DuckDB)
                    db_size = None
                    db_path = None
                    if dialect == "duckdb":
                        # Extract path from URL
                        if ":///" in engine_url:
                            db_path = engine_url.split("///")[1]
                            if os.path.exists(db_path):
                                db_size = os.path.getsize(db_path)

                    # Check connection
                    connected = True
                    try:
                        await repo.query_tasks(limit=1)
                    except Exception:
                        connected = False

                    return {
                        "dialect": dialect,
                        "url": engine_url,
                        "path": db_path,
                        "size": db_size,
                        "task_count": task_count,
                        "connected": connected,
                    }

        db_info = run_async_safe(get_db_info())

        # Create status table
        table = Table(title="Database Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Type", db_info.get("dialect", "unknown"))

        if db_info.get("path"):
            table.add_row("Location", db_info["path"])
        else:
            # Show sanitized URL for non-file databases
            url = db_info.get("url", "")
            if "@" in url:
                # Hide credentials
                url = url.split("@")[0].split("://")[0] + "://*****@" + url.split("@")[1]
            table.add_row("URL", url)

        if db_info.get("size") is not None:
            size_mb = db_info["size"] / 1024 / 1024
            table.add_row("Size", f"{size_mb:.2f} MB")

        table.add_row("Tasks", str(db_info.get("task_count", 0)))

        connection_status = "✅ Connected" if db_info.get("connected") else "❌ Disconnected"
        table.add_row("Connection", connection_status)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error fetching database status: {str(e)}[/red]")
        raise typer.Exit(1)

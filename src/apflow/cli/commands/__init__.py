"""
CLI commands for apflow
"""

from apflow.cli.commands.run import app as run_app
from apflow.cli.commands.serve import app as serve_app
from apflow.cli.commands.daemon import app as daemon_app
from apflow.cli.commands.tasks import app as tasks_app
from apflow.cli.commands.generate import app as generate_app

__all__ = [
    "run",
    "serve",
    "daemon",
    "tasks",
    "generate",
]

# Expose apps for main.py
run = type("run", (), {"app": run_app})()
serve = type("serve", (), {"app": serve_app})()
daemon = type("daemon", (), {"app": daemon_app})()
tasks = type("tasks", (), {"app": tasks_app})()
generate = type("generate", (), {"app": generate_app})()


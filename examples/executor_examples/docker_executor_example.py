"""
Docker Executor Examples

Demonstrates containerized task execution:
1. Running commands in containers
2. Volume mounting for data access
3. Environment variables
4. Image management
5. Batch processing workflows

Prerequisites:
- pip install apflow[docker]
- Docker installed and running
- Docker daemon accessible

Run: python docker_executor_example.py
"""

from apflow import TaskBuilder


def simple_container():
    """Run a simple command in a container."""
    print("=== Simple Container Execution ===")

    task = (
        TaskBuilder("hello_container", "docker_executor")
        .with_inputs(
            {
                "image": "alpine:latest",
                "command": "echo 'Hello from Docker!'",
                "timeout": 60,
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")
    print("Note: Requires Docker installed and running")


def python_script_execution():
    """Execute a Python script in a container."""
    print("\n=== Python Script in Container ===")

    task = (
        TaskBuilder("run_python_script", "docker_executor")
        .with_inputs(
            {
                "image": "python:3.11",
                "command": "python -c 'import sys; print(f\"Python {sys.version}\")'",
                "timeout": 120,
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")


def data_processing_with_volumes():
    """Process data with volume mounting."""
    print("\n=== Data Processing with Volumes ===")

    task = (
        TaskBuilder("process_data", "docker_executor")
        .with_inputs(
            {
                "image": "python:3.11",
                "command": "python /app/process.py",
                "volumes": {
                    "/host/data": "/app/data",  # Mount host data directory
                    "/host/results": "/app/results",  # Mount results directory
                    "/host/scripts": "/app",  # Mount scripts directory
                },
                "env": {
                    "INPUT_FILE": "/app/data/input.csv",
                    "OUTPUT_FILE": "/app/results/output.csv",
                },
                "timeout": 600,  # 10 minutes
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")
    print("Volumes:")
    print("  - /host/data -> /app/data")
    print("  - /host/results -> /app/results")


def batch_processing():
    """Batch process multiple files in containers."""
    print("\n=== Batch Processing ===")

    task = (
        TaskBuilder("batch_convert", "docker_executor")
        .with_inputs(
            {
                "image": "python:3.11-slim",
                "command": "python /app/batch_convert.py",
                "volumes": {"/data/batch": "/app/data", "/data/output": "/app/output"},
                "env": {"BATCH_SIZE": "100", "FORMAT": "json"},
                "timeout": 1200,  # 20 minutes
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")


def nodejs_application():
    """Run Node.js application in container."""
    print("\n=== Node.js Application ===")

    task = (
        TaskBuilder("run_node_app", "docker_executor")
        .with_inputs(
            {
                "image": "node:18",
                "command": "node /app/server.js",
                "volumes": {"/host/app": "/app", "/host/node_modules": "/app/node_modules"},
                "env": {"NODE_ENV": "production", "PORT": "3000"},
                "timeout": 300,
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")


def database_migration():
    """Run database migrations in container."""
    print("\n=== Database Migration ===")

    task = (
        TaskBuilder("run_migrations", "docker_executor")
        .with_inputs(
            {
                "image": "postgres:15",
                "command": "psql -U postgres -f /migrations/001_init.sql",
                "volumes": {"/host/migrations": "/migrations"},
                "env": {
                    "POSTGRES_PASSWORD": "secret",
                    "POSTGRES_DB": "myapp",
                },
                "timeout": 600,
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")


def image_processing():
    """Process images using specialized container."""
    print("\n=== Image Processing ===")

    task = (
        TaskBuilder("process_images", "docker_executor")
        .with_inputs(
            {
                "image": "python:3.11",
                "command": "python -m pip install pillow && python /app/resize.py",
                "volumes": {"/host/images": "/app/images", "/host/output": "/app/output"},
                "env": {"MAX_WIDTH": "1920", "MAX_HEIGHT": "1080", "QUALITY": "85"},
                "timeout": 900,  # 15 minutes
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")


def machine_learning_inference():
    """Run ML inference in GPU container."""
    print("\n=== ML Inference (GPU) ===")

    task = (
        TaskBuilder("ml_inference", "docker_executor")
        .with_inputs(
            {
                "image": "tensorflow/tensorflow:latest-gpu",
                "command": "python /app/inference.py",
                "volumes": {"/host/models": "/app/models", "/host/data": "/app/data"},
                "env": {"MODEL_PATH": "/app/models/model.h5", "BATCH_SIZE": "32"},
                "timeout": 3600,  # 1 hour
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")
    print("Note: Requires GPU-enabled Docker setup")


def workflow_with_containers():
    """Create a workflow using multiple containers."""
    print("\n=== Multi-Container Workflow ===")

    # Task 1: Prepare data
    prepare_task = (
        TaskBuilder("prepare_data", "docker_executor")
        .with_inputs(
            {
                "image": "python:3.11",
                "command": "python /app/prepare.py",
                "volumes": {"/data/raw": "/app/input", "/data/processed": "/app/output"},
            }
        )
        .build()
    )

    # Task 2: Process data (depends on prepare)
    process_task = (
        TaskBuilder("process_data", "docker_executor")
        .with_inputs(
            {
                "image": "python:3.11",
                "command": "python /app/process.py",
                "volumes": {"/data/processed": "/app/input", "/data/results": "/app/output"},
            }
        )
        .with_dependencies([prepare_task.id])
        .build()
    )

    # Task 3: Generate report (depends on process)
    report_task = (
        TaskBuilder("generate_report", "docker_executor")
        .with_inputs(
            {
                "image": "python:3.11",
                "command": "python /app/report.py",
                "volumes": {"/data/results": "/app/input", "/data/reports": "/app/output"},
            }
        )
        .with_dependencies([process_task.id])
        .build()
    )

    print(f"Workflow created with {3} tasks:")
    print(f"1. {prepare_task.id} - Prepare data")
    print(f"2. {process_task.id} - Process data (depends on prepare)")
    print(f"3. {report_task.id} - Generate report (depends on process)")


if __name__ == "__main__":
    simple_container()
    python_script_execution()
    data_processing_with_volumes()
    batch_processing()
    nodejs_application()
    database_migration()
    image_processing()
    machine_learning_inference()
    workflow_with_containers()

    print("\n=== Docker Executor Features ===")
    print("✅ Isolated execution environments")
    print("✅ Reproducible workflows")
    print("✅ Volume mounting for data access")
    print("✅ Environment variables")
    print("✅ Timeout control")
    print("✅ Support for any Docker image")
    print("⚠️  Requires Docker daemon")
    print("⚠️  Validate image sources")
    print("⚠️  Limit container resources")
    print("\nSee docs/guides/executor-selection.md for more details")

"""
SSH Executor Examples

Demonstrates remote command execution via SSH:
1. Basic command execution
2. Using SSH keys for authentication
3. Deployment scripts
4. File operations
5. System administration tasks

Prerequisites:
- pip install apflow[ssh]
- SSH access to a remote server
- SSH key configured

Run: python ssh_executor_example.py
"""

from apflow import TaskBuilder


def basic_command():
    """Execute a basic command on remote server."""
    print("=== Basic SSH Command ===")

    task = (
        TaskBuilder("check_disk_space", "ssh_executor")
        .with_inputs(
            {
                "host": "example.com",
                "port": 22,
                "username": "deploy",
                "key_file": "~/.ssh/id_rsa",
                "command": "df -h",
                "timeout": 30,
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")
    print("Note: Update host, username, and key_file to execute")


def deployment_script():
    """Execute a deployment script on remote server."""
    print("\n=== Deployment via SSH ===")

    task = (
        TaskBuilder("deploy_app", "ssh_executor")
        .with_inputs(
            {
                "host": "prod-server.example.com",
                "port": 22,
                "username": "deploy",
                "key_file": "~/.ssh/deploy_key",
                "command": "bash /opt/scripts/deploy.sh",
                "timeout": 300,  # 5 minutes for deployment
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")
    print("Deployment script will execute on remote server")


def system_info():
    """Collect system information from remote server."""
    print("\n=== Collect System Information ===")

    # Multiple commands can be chained
    commands = [
        "uname -a",  # System info
        "uptime",  # Uptime
        "free -h",  # Memory usage
        "df -h",  # Disk usage
    ]

    task = (
        TaskBuilder("system_info", "ssh_executor")
        .with_inputs(
            {
                "host": "server.example.com",
                "port": 22,
                "username": "admin",
                "key_file": "~/.ssh/admin_key",
                "command": " && ".join(commands),
                "timeout": 60,
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")
    print(f"Commands to execute: {len(commands)}")


def log_rotation():
    """Rotate logs on remote server."""
    print("\n=== Log Rotation ===")

    task = (
        TaskBuilder("rotate_logs", "ssh_executor")
        .with_inputs(
            {
                "host": "app-server.example.com",
                "port": 22,
                "username": "sysadmin",
                "key_file": "~/.ssh/sysadmin_key",
                "command": "sudo logrotate -f /etc/logrotate.conf",
                "timeout": 120,
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")


def database_backup():
    """Create database backup on remote server."""
    print("\n=== Database Backup ===")

    backup_command = (
        "pg_dump -U postgres mydb | " "gzip > /backups/mydb_$(date +%Y%m%d_%H%M%S).sql.gz"
    )

    task = (
        TaskBuilder("backup_database", "ssh_executor")
        .with_inputs(
            {
                "host": "db-server.example.com",
                "port": 22,
                "username": "postgres",
                "key_file": "~/.ssh/postgres_key",
                "command": backup_command,
                "timeout": 600,  # 10 minutes for backup
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")
    print(f"Backup command: {backup_command}")


def service_restart():
    """Restart a service on remote server."""
    print("\n=== Service Restart ===")

    task = (
        TaskBuilder("restart_nginx", "ssh_executor")
        .with_inputs(
            {
                "host": "web-server.example.com",
                "port": 22,
                "username": "admin",
                "key_file": "~/.ssh/admin_key",
                "command": "sudo systemctl restart nginx",
                "timeout": 30,
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")


def workflow_with_dependencies():
    """Create a workflow with multiple SSH tasks."""
    print("\n=== Multi-Server Workflow ===")

    # Task 1: Pull latest code
    pull_task = (
        TaskBuilder("pull_code", "ssh_executor")
        .with_inputs(
            {
                "host": "app-server.example.com",
                "username": "deploy",
                "key_file": "~/.ssh/deploy_key",
                "command": "cd /opt/app && git pull origin main",
            }
        )
        .build()
    )

    # Task 2: Restart application (depends on pull)
    restart_task = (
        TaskBuilder("restart_app", "ssh_executor")
        .with_inputs(
            {
                "host": "app-server.example.com",
                "username": "deploy",
                "key_file": "~/.ssh/deploy_key",
                "command": "sudo systemctl restart myapp",
            }
        )
        .with_dependencies([pull_task.id])
        .build()
    )

    # Task 3: Health check (depends on restart)
    health_task = (
        TaskBuilder("health_check", "ssh_executor")
        .with_inputs(
            {
                "host": "app-server.example.com",
                "username": "deploy",
                "key_file": "~/.ssh/deploy_key",
                "command": "curl -f http://localhost:8000/health",
            }
        )
        .with_dependencies([restart_task.id])
        .build()
    )

    print(f"Workflow created with {3} tasks:")
    print(f"1. {pull_task.id} - Pull code")
    print(f"2. {restart_task.id} - Restart app (depends on pull)")
    print(f"3. {health_task.id} - Health check (depends on restart)")


if __name__ == "__main__":
    basic_command()
    deployment_script()
    system_info()
    log_rotation()
    database_backup()
    service_restart()
    workflow_with_dependencies()

    print("\n=== SSH Executor Features ===")
    print("✅ Key-based authentication")
    print("✅ Configurable timeouts")
    print("✅ Command chaining with &&")
    print("✅ Sudo support")
    print("✅ Secure key validation (checks permissions)")
    print("⚠️  Use key-based auth (not passwords)")
    print("⚠️  Restrict SSH access properly")
    print("\nSee docs/guides/executor-selection.md for more details")

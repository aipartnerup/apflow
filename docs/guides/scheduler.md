# Task Scheduling

APFlow provides built-in task scheduling capabilities with support for both internal scheduling and external scheduler integration.

## Overview

The scheduler module offers:

- **Internal Scheduler**: Built-in scheduler for standalone deployment
- **External Gateway**: Integration with external schedulers (cron, Kubernetes, etc.)
- **Calendar Integration**: iCal export for calendar applications

## Schedule Types

APFlow supports six schedule types:

| Type | Expression Example | Description |
|------|-------------------|-------------|
| `once` | `2024-01-15T09:00:00Z` | Single execution at a specific datetime |
| `interval` | `3600` | Recurring at fixed intervals (in seconds) |
| `cron` | `0 9 * * 1-5` | Standard cron expression |
| `daily` | `09:00` | Daily at specific time (HH:MM) |
| `weekly` | `1,3,5 09:00` | Weekly on specific days (1=Mon, 7=Sun) |
| `monthly` | `1,15 09:00` | Monthly on specific dates |

## Installation

Install with scheduling support:

```bash
pip install apflow[scheduling]
```

Or with all features:

```bash
pip install apflow[standard]
```

## Quick Start

### 1. Create a Scheduled Task

Use the CLI to create and configure a scheduled task:

```bash
# Create a task
apflow tasks create --name "Daily Report" --inputs '{"report_type": "summary"}'

# Configure scheduling
apflow tasks update <task_id> \
    --schedule-type daily \
    --schedule-expression "09:00" \
    --schedule-enabled

# Initialize the schedule (calculates next_run_at)
apflow tasks scheduled init <task_id>
```

### 2. Start the Internal Scheduler

```bash
# Run in foreground
apflow scheduler start

# Run with verbose logging (DEBUG level)
apflow scheduler start --verbose

# Run in background
apflow scheduler start --background

# With custom options
apflow scheduler start \
    --poll-interval 30 \
    --max-concurrent 5 \
    --user-id user123
```

### 3. Monitor Scheduled Tasks

```bash
# List all scheduled tasks
apflow scheduler list

# List with filters
apflow scheduler list --status running
apflow scheduler list --type daily --all

# Check for due tasks
apflow tasks scheduled due

# Check for tasks due before a specific time
apflow tasks scheduled due --before "2024-12-31T23:59:59Z"

# Check scheduler status
apflow scheduler status
```

## Internal Scheduler

The internal scheduler polls the database for due tasks and executes them automatically.

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--poll-interval` | 60 | Seconds between checking for due tasks |
| `--max-concurrent` | 10 | Maximum concurrent task executions |
| `--timeout` | 3600 | Default task timeout in seconds |
| `--user-id` | None | Only process tasks for this user |
| `--background` | False | Run as background daemon |
| `--verbose` / `-v` | False | Enable DEBUG-level logging output |

### Python API

```python
import asyncio
from apflow.scheduler import InternalScheduler
from apflow.scheduler.base import SchedulerConfig

# Configure scheduler
config = SchedulerConfig(
    poll_interval=30,           # Check every 30 seconds
    max_concurrent_tasks=5,     # Max 5 parallel tasks
    task_timeout=1800,          # 30 minute timeout
    user_id="user123"           # Optional: filter by user
)

# Create and start scheduler
scheduler = InternalScheduler(config)

async def main():
    # Register completion callback
    def on_complete(task_id, success, result):
        print(f"Task {task_id}: {'completed' if success else 'failed'}")

    scheduler.on_task_complete(on_complete)

    # Start scheduler
    await scheduler.start()

    # Run until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await scheduler.stop()

asyncio.run(main())
```

### Scheduler Authentication

When running in API mode, the scheduler needs an admin token to trigger tasks on behalf of any user. The token is resolved in this order:

1. **`admin_auth_token`** from `config.cli.yaml` (if explicitly configured)
2. **Auto-generated** admin JWT using the local `jwt_secret` from `config.cli.yaml`

The auto-generated token is cached for the scheduler session and eliminates the need for manual token configuration when running locally. At startup, the scheduler logs its auth identity (subject and source) for troubleshooting.

### Listing Scheduled Tasks

```bash
# List all enabled scheduled tasks
apflow scheduler list

# Include disabled schedules
apflow scheduler list --all

# Filter by schedule type
apflow scheduler list --type daily

# Filter by task status
apflow scheduler list --status running

# JSON output
apflow scheduler list -f json
```

### Scheduler Lifecycle

```
start() → running → pause() → paused → resume() → running → stop() → stopped
```

## External Scheduler Integration

APFlow provides gateway APIs for integration with external schedulers.

### Webhook Gateway

External schedulers can trigger task execution via HTTP webhooks.

#### Generate Webhook URL

```bash
apflow scheduler webhook-url <task_id> --base-url https://api.example.com
```

Output:
```
URL: https://api.example.com/webhook/trigger/abc123
Method: POST
```

#### Cron Integration

```bash
# Add to crontab
0 9 * * 1-5 curl -X POST https://api.example.com/webhook/trigger/abc123
```

#### Kubernetes CronJob

```python
from apflow.scheduler.gateway.webhook import generate_kubernetes_cronjob

manifest = generate_kubernetes_cronjob(
    task_id="abc123",
    task_name="Daily Report",
    schedule_expression="0 9 * * *",
    webhook_url="https://api.example.com/webhook/trigger/abc123",
    namespace="production"
)
```

### API Endpoints for External Schedulers

| Endpoint | Method | Description |
|----------|--------|-------------|
| `tasks.scheduled.list` | JSON-RPC | List all scheduled tasks (supports `status` filter) |
| `tasks.scheduled.due` | JSON-RPC | Get tasks due for execution |
| `tasks.scheduled.init` | JSON-RPC | Initialize/recalculate next_run_at |
| `tasks.scheduled.complete` | JSON-RPC | Mark task completed, calculate next run (supports `calculate_next_run` flag) |
| `tasks.scheduled.export-ical` | JSON-RPC | Export scheduled tasks as iCalendar format |
| `tasks.webhook.trigger` | JSON-RPC | Trigger task execution via webhook |
| `/webhook/trigger/{task_id}` | REST POST | Simple REST endpoint for external schedulers |

#### Webhook Authentication

The webhook trigger endpoint supports a three-layer authentication priority chain:

| Priority | Method | Description |
|----------|--------|-------------|
| 1 | **JWT** | Standard JWT via `Authorization` header (handled by middleware) |
| 2 | **Webhook verify hook** | Custom verification via `@register_webhook_verify_hook` decorator |
| 3 | **APFLOW_WEBHOOK_SECRET** | Internal HMAC signature validation |

IP whitelist (`APFLOW_WEBHOOK_ALLOWED_IPS`) and rate limit (`APFLOW_WEBHOOK_RATE_LIMIT`) are applied as additional protection after authentication.

**Custom webhook verification hook:**

```python
from apflow import register_webhook_verify_hook
from apflow.core.types import WebhookVerifyContext, WebhookVerifyResult

@register_webhook_verify_hook
async def verify_tenant_webhook(ctx: WebhookVerifyContext) -> WebhookVerifyResult:
    # ctx provides: task_id, signature, timestamp, client_ip
    if is_valid_signature(ctx.signature, ctx.timestamp):
        return WebhookVerifyResult(valid=True, user_id="tenant-user")
    return WebhookVerifyResult(valid=False, error="Invalid signature")
```

#### REST Webhook Endpoint

The simplest way to trigger tasks from external schedulers:

```bash
# Basic trigger (with JWT)
curl -X POST https://api.example.com/webhook/trigger/abc123 \
  -H "Authorization: Bearer <jwt-token>"

# With HMAC signature validation (if APFLOW_WEBHOOK_SECRET is configured)
curl -X POST https://api.example.com/webhook/trigger/abc123 \
  -H "X-Webhook-Signature: <hmac-signature>" \
  -H "X-Webhook-Timestamp: <unix-timestamp>"

# Synchronous execution (wait for result)
curl -X POST "https://api.example.com/webhook/trigger/abc123?async=false"
```

#### JSON-RPC Webhook Trigger

```bash
curl -X POST https://api.example.com/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.webhook.trigger",
    "params": {
      "task_id": "abc123",
      "async_execution": true
    },
    "id": 1
  }'
```

#### Get Due Tasks

```bash
curl -X POST https://api.example.com/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.scheduled.due",
    "params": {
      "limit": 10
    },
    "id": 1
  }'
```

## Calendar Integration

Export scheduled tasks to iCalendar format for viewing in calendar applications.

### CLI Export

```bash
# Export to file
apflow scheduler export-ical -o schedule.ics

# Export for specific user
apflow scheduler export-ical --user-id user123 -o user_schedule.ics

# Custom calendar name
apflow scheduler export-ical --name "My Task Schedule" -o schedule.ics
```

### API Export

```bash
curl -X POST https://api.example.com/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.scheduled.export-ical",
    "params": {
      "calendar_name": "APFlow Tasks",
      "enabled_only": true,
      "limit": 100
    },
    "id": 1
  }'
```

### Python API

```python
from apflow.scheduler.gateway import ICalExporter

exporter = ICalExporter(
    calendar_name="APFlow Tasks",
    base_url="https://app.example.com",
    default_duration_minutes=30
)

# Export all scheduled tasks
ical_content = await exporter.export_tasks(
    user_id="user123",
    enabled_only=True
)

# Write to file
with open("schedule.ics", "w") as f:
    f.write(ical_content)
```

### Calendar Subscription URL

Generate a URL for live calendar subscription:

```python
from apflow.scheduler.gateway.ical import generate_ical_feed_url

url = generate_ical_feed_url(
    base_url="https://api.example.com",
    user_id="user123",
    api_key="your-api-key"
)
# Result: https://api.example.com/scheduler/ical?user_id=user123&api_key=your-api-key
```

## Execution Mode

When a scheduled task is triggered, APFlow always loads the task tree from the database and executes it using the unified tree execution model. Dependency cascade is handled by `execute_after_task` regardless of task structure.

For tasks with children, all child tasks are reset to clean `pending` state before each scheduled run. This ensures every execution cycle starts fresh — previous results, errors, and progress are cleared automatically.

```
# Scheduled execution cycle
┌─────────────────┐
│  Root Task      │  ← Scheduler triggers
│  (scheduled)    │
├─────────────────┤
│  ├─ Child 1     │  ← All children reset to pending
│  ├─ Child 2     │     and re-executed in dependency order
│  └─ Child 3     │
└─────────────────┘
```

## Multi-User Support

APFlow supports multi-user scheduling through the `user_id` field:

```python
# Create task with user_id
await task_repository.create_task(
    name="User Report",
    user_id="user123",
    schedule_type="daily",
    schedule_expression="09:00",
    schedule_enabled=True
)

# Start scheduler for specific user
config = SchedulerConfig(user_id="user123")
scheduler = InternalScheduler(config)
```

## Best Practices

### 1. Use Appropriate Schedule Types

- **once**: One-time scheduled events
- **interval**: Regular polling or heartbeat tasks
- **cron**: Complex schedules with minute-level control
- **daily/weekly/monthly**: Simple recurring tasks

### 2. Set Schedule Boundaries

```python
from datetime import datetime, timezone, timedelta

await task_repository.update_task(
    task_id=task_id,
    schedule_start_at=datetime.now(timezone.utc),
    schedule_end_at=datetime.now(timezone.utc) + timedelta(days=30),
    max_runs=100  # Stop after 100 executions
)
```

### 3. Monitor Execution

```python
# Check run count
task = await task_repository.get_task_by_id(task_id)
print(f"Executed {task.run_count} times")
print(f"Last run: {task.last_run_at}")
print(f"Next run: {task.next_run_at}")
```

### 4. Handle Failures

```python
# The scheduler automatically:
# - Records errors in task.error
# - Calculates next_run_at regardless of success/failure
# - Respects max_runs limit
# - Disables schedule when schedule_end_at is reached
```

## Troubleshooting

### Tasks Not Executing

1. Check schedule is enabled:
   ```bash
   apflow tasks get <task_id> | grep schedule_enabled
   ```

2. Verify next_run_at is set:
   ```bash
   apflow tasks scheduled init <task_id>
   ```

3. Check scheduler is running:
   ```bash
   apflow scheduler status
   ```

### Scheduler Won't Start

Check for existing process:
```bash
apflow scheduler status
apflow scheduler stop  # If stale
apflow scheduler start
```

### iCal Not Updating

Calendar applications cache feeds. Try:
- Force refresh in calendar app
- Wait for cache expiration (varies by app)
- Use unique URL with timestamp for testing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      APFlow Scheduler                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Scheduler Interface                     │   │
│  │         start() | stop() | trigger()                │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                │                │                 │
│   ┌─────┴─────┐    ┌─────┴─────┐    ┌─────┴─────┐         │
│   │  Internal │    │  Webhook  │    │   iCal    │         │
│   │ Scheduler │    │  Gateway  │    │  Export   │         │
│   └───────────┘    └───────────┘    └───────────┘         │
│         │                │                │                 │
└─────────│────────────────│────────────────│─────────────────┘
          │                │                │
          ▼                ▼                ▼
    ┌───────────┐    ┌───────────┐    ┌───────────┐
    │   Task    │    │   cron    │    │  Google   │
    │ Executor  │    │   K8s     │    │ Calendar  │
    └───────────┘    │  Temporal │    │  Outlook  │
                     └───────────┘    └───────────┘
```

## API Reference

### SchedulerConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| poll_interval | int | 60 | Seconds between polls |
| max_concurrent_tasks | int | 10 | Max parallel executions |
| task_timeout | int | 3600 | Task timeout in seconds |
| retry_on_failure | bool | False | Retry failed tasks |
| max_retries | int | 3 | Max retry attempts |
| user_id | str | None | User ID filter |

### SchedulerStats

| Field | Type | Description |
|-------|------|-------------|
| state | SchedulerState | Current state |
| started_at | datetime | Start time |
| tasks_executed | int | Total executed |
| tasks_succeeded | int | Successful count |
| tasks_failed | int | Failed count |
| active_tasks | int | Currently running |

### WebhookConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| secret_key | str | None | HMAC signature key |
| allowed_ips | list | None | Allowed IP addresses |
| rate_limit | int | 0 | Requests/minute (0=unlimited) |
| timeout | int | 3600 | Task timeout |
| async_execution | bool | True | Execute in background |

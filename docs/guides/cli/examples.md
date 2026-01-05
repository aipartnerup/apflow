# CLI Usage Examples & Scenarios

Complete examples and common scenarios for using the CLI.

## Quick Start Examples

### Example 1: Monitor System Resources

Execute a single task to check CPU usage:

```bash
# Execute task
apflow run batch-001 --tasks '[
  {
    "id": "check-cpu",
    "name": "Check CPU Usage",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "cpu"}
  }
]'

# Output: {"cpu": 45.2, "timestamp": "2024-01-15T10:30:00Z"}

# Check task status
apflow tasks status check-cpu
```

### Example 2: Batch System Check

Check multiple system resources in one batch:

```bash
apflow run batch-002 --tasks '[
  {
    "id": "cpu-check",
    "name": "CPU Usage",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "cpu"}
  },
  {
    "id": "mem-check",
    "name": "Memory Usage",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "memory"}
  },
  {
    "id": "disk-check",
    "name": "Disk Usage",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "disk"}
  }
]'

# Run all 3 tasks in parallel (default)
# Check status
apflow tasks list --batch-id batch-002
```

### Example 3: API Request with Error Handling

Make HTTP request with error handling:

```bash
# Execute HTTP request
apflow run batch-003 --tasks '[
  {
    "id": "api-call",
    "name": "Fetch User Data",
    "schemas": {"method": "http_executor"},
    "inputs": {
      "url": "https://api.example.com/users/123",
      "method": "GET",
      "headers": {"Authorization": "Bearer token-123"}
    }
  }
]' --retry-count 3

# If fails, CLI retries up to 3 times
apflow tasks status api-call --watch
```

## Real-World Scenarios

### Scenario 1: Daily Health Check (Cron Job)

Setup a cron job to monitor system health daily:

**File**: `check_health.sh`
```bash
#!/bin/bash

TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BATCH_ID="health-check-$TIMESTAMP"

apflow run "$BATCH_ID" --tasks '[
  {
    "id": "cpu",
    "name": "Check CPU",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "cpu"}
  },
  {
    "id": "memory",
    "name": "Check Memory",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "memory"}
  },
  {
    "id": "disk",
    "name": "Check Disk",
    "schemas": {"method": "system_info_executor"},
    "inputs": {"resource": "disk"}
  }
]' --tags health-check,automated

# Log results
RESULTS=$(apflow tasks list --batch-id "$BATCH_ID")
echo "Health check results: $RESULTS" >> /var/log/health-check.log

# Alert if any failed
FAILED=$(echo "$RESULTS" | grep -c '"status": "failed"')
if [ "$FAILED" -gt 0 ]; then
  echo "WARNING: $FAILED checks failed" | mail -s "Health Check Alert" admin@example.com
fi
```

**Setup cron job**:
```bash
# Edit crontab
crontab -e

# Add entry to run daily at 2 AM
0 2 * * * /path/to/check_health.sh
```

### Scenario 2: Data Processing Pipeline

Process data in multiple stages:

```bash
# Stage 1: Fetch data
FETCH_BATCH="data-pipeline-fetch-$(date +%s)"

apflow run "$FETCH_BATCH" --tasks '[
  {
    "id": "fetch-data",
    "name": "Fetch Data from API",
    "schemas": {"method": "http_executor"},
    "inputs": {
      "url": "https://api.example.com/data",
      "method": "GET"
    }
  }
]'

# Wait for completion
apflow tasks watch --task-id fetch-data

# Stage 2: Process fetched data
PROCESS_BATCH="data-pipeline-process-$(date +%s)"

apflow run "$PROCESS_BATCH" --tasks '[
  {
    "id": "process-data",
    "name": "Process Data",
    "schemas": {"method": "command_executor"},
    "inputs": {
      "command": "python process_data.py --input /tmp/data.json --output /tmp/processed.json",
      "timeout": 300
    }
  }
]'

# Stage 3: Archive results
ARCHIVE_BATCH="data-pipeline-archive-$(date +%s)"

apflow run "$ARCHIVE_BATCH" --tasks '[
  {
    "id": "archive-data",
    "name": "Archive Results",
    "schemas": {"method": "command_executor"},
    "inputs": {
      "command": "tar -czf /archive/data-$(date +%Y%m%d).tar.gz /tmp/processed.json",
      "timeout": 60
    }
  }
]'

echo "Pipeline complete"
apflow tasks list --batch-id "$ARCHIVE_BATCH" --include-details
```

### Scenario 3: Monitoring with API Server

Setup CLI with API server for continuous monitoring:

**Step 1: Initialize configuration**
```bash
apflow config init-server

# Creates:
# - .data/config.cli.yaml with api_server_url and JWT token
```

**Step 2: Start API server**
```bash
# Terminal 1: Start API server
apflow daemon start --port 8000
```

**Step 3: Create monitoring script**
```bash
# Terminal 2: Monitoring script
#!/bin/bash

while true; do
  # Execute monitoring task
  BATCH_ID="monitor-$(date +%s)"
  
  apflow run "$BATCH_ID" --tasks '[
    {
      "id": "monitor",
      "name": "System Monitor",
      "schemas": {"method": "system_info_executor"},
      "inputs": {"resource": "cpu"}
    }
  ]'
  
  # Display current status
  echo "=== Status at $(date) ==="
  apflow tasks list --limit 5 --sort created_at --reverse
  
  # Wait 30 seconds
  sleep 30
done
```

**Key point**: CLI automatically routes through API server!

### Scenario 4: Batch Job with Retries

Process batch with automatic retry on failure:

```bash
# Create batch of jobs
BATCH_ID="batch-jobs-$(date +%Y%m%d_%H%M%S)"

# Array of tasks to process
TASKS='[
  {
    "id": "job-1",
    "name": "Job 1",
    "schemas": {"method": "http_executor"},
    "inputs": {
      "url": "https://api.example.com/job1",
      "method": "POST"
    }
  },
  {
    "id": "job-2",
    "name": "Job 2",
    "schemas": {"method": "http_executor"},
    "inputs": {
      "url": "https://api.example.com/job2",
      "method": "POST"
    }
  },
  {
    "id": "job-3",
    "name": "Job 3",
    "schemas": {"method": "http_executor"},
    "inputs": {
      "url": "https://api.example.com/job3",
      "method": "POST"
    }
  }
]'

# Execute with retry
apflow run "$BATCH_ID" --tasks "$TASKS" \
  --parallel-count 3 \
  --retry-count 5 \
  --retry-delay 10 \
  --timeout 3600

# Monitor progress
echo "Monitoring batch $BATCH_ID..."
apflow tasks watch --batch-id "$BATCH_ID"

# Show final results
echo "Final Results:"
apflow tasks list --batch-id "$BATCH_ID"
```

### Scenario 5: Task Dependency Chain

Execute tasks in sequence (one task per stage):

```bash
#!/bin/bash

# Task 1: Prepare
echo "Stage 1: Prepare..."
STAGE1=$(apflow run stage-1 --tasks '[
  {
    "id": "prepare",
    "name": "Prepare Environment",
    "schemas": {"method": "command_executor"},
    "inputs": {
      "command": "mkdir -p /tmp/workflow && cd /tmp/workflow && echo \"ready\" > status.txt"
    }
  }
]')

# Wait for completion
apflow tasks watch --task-id prepare
STATUS=$(apflow tasks status prepare --include-details)
if echo "$STATUS" | grep -q '"status": "failed"'; then
  echo "Preparation failed!"
  exit 1
fi

# Task 2: Process
echo "Stage 2: Process..."
apflow run stage-2 --tasks '[
  {
    "id": "process",
    "name": "Process Data",
    "schemas": {"method": "command_executor"},
    "inputs": {
      "command": "python /path/to/process.py"
    }
  }
]'

apflow tasks watch --task-id process
STATUS=$(apflow tasks status process --include-details)
if echo "$STATUS" | grep -q '"status": "failed"'; then
  echo "Processing failed!"
  exit 1
fi

# Task 3: Finalize
echo "Stage 3: Finalize..."
apflow run stage-3 --tasks '[
  {
    "id": "finalize",
    "name": "Generate Report",
    "schemas": {"method": "command_executor"},
    "inputs": {
      "command": "python /path/to/report.py"
    }
  }
]'

apflow tasks watch --task-id finalize

echo "Workflow complete!"
```

## Advanced Usage Patterns

### Pattern 1: Conditional Execution

Execute next task based on previous task result:

```bash
# Task 1
apflow run batch --tasks '[
  {
    "id": "check-env",
    "name": "Check Environment",
    "schemas": {"method": "command_executor"},
    "inputs": {
      "command": "test -f /etc/important-file && echo ok || echo missing"
    }
  }
]'

# Get result
RESULT=$(apflow tasks status check-env --include-details)

# Conditional next task
if echo "$RESULT" | grep -q "ok"; then
  echo "Environment OK, proceeding..."
  apflow run batch --tasks '[
    {
      "id": "deploy",
      "name": "Deploy",
      "schemas": {"method": "command_executor"},
      "inputs": {"command": "bash deploy.sh"}
    }
  ]'
else
  echo "Environment missing required files"
  exit 1
fi
```

### Pattern 2: Parallel Task Execution

Run multiple independent tasks in parallel:

```bash
# Define 10 independent tasks
TASKS=$(python3 << 'EOF'
import json

tasks = []
for i in range(10):
    tasks.append({
        "id": f"task-{i:02d}",
        "name": f"Process Item {i}",
        "schemas": {"method": "http_executor"},
        "inputs": {
            "url": f"https://api.example.com/items/{i}",
            "method": "POST"
        }
    })

print(json.dumps(tasks))
EOF
)

# Run with parallelism
apflow run batch --tasks "$TASKS" --parallel-count 5

# Monitor all
apflow tasks watch --all
```

### Pattern 3: Dynamic Task Generation

Generate tasks dynamically from external source:

```bash
#!/bin/bash

# Fetch task list from API
TASK_CONFIG=$(curl -s https://internal-api.example.com/tasks)

# Transform to apflow format
APFLOW_TASKS=$(python3 << EOF
import json
import sys

config = json.loads('$TASK_CONFIG')
tasks = []

for item in config['items']:
    tasks.append({
        "id": item['id'],
        "name": item['name'],
        "schemas": {"method": "http_executor"},
        "inputs": {
            "url": item['endpoint'],
            "method": item.get('method', 'GET')
        }
    })

print(json.dumps(tasks))
EOF
)

# Execute generated tasks
apflow run dynamic-batch --tasks "$APFLOW_TASKS" --parallel-count 3
```

## Common Workflow Examples

### Workflow: Web Service Health Check

```bash
#!/bin/bash

# Configuration
SERVICES=(
  "https://api.example.com/health"
  "https://db.example.com/status"
  "https://cache.example.com/ping"
)

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BATCH_ID="health-check-$TIMESTAMP"

# Generate tasks
TASKS=$(python3 << 'EOF'
import json
import os

services = os.environ['SERVICES'].split(',')
tasks = []

for i, service in enumerate(services):
    tasks.append({
        "id": f"health-check-{i}",
        "name": f"Check {service}",
        "schemas": {"method": "http_executor"},
        "inputs": {
            "url": service,
            "method": "GET",
            "timeout": 5
        }
    })

print(json.dumps(tasks))
EOF
)

export SERVICES="${SERVICES[*]}"

# Execute
apflow run "$BATCH_ID" --tasks "$TASKS" --parallel-count 3 --timeout 30

# Report
echo "=== Health Check Report ==="
echo "Batch ID: $BATCH_ID"
echo "Timestamp: $TIMESTAMP"
echo ""
apflow tasks list --batch-id "$BATCH_ID"
```

## Conclusion

The CLI is flexible and powerful:
- ✅ Simple commands for common tasks
- ✅ Complex workflows through scripting
- ✅ Parallel execution for performance
- ✅ Retry logic for reliability
- ✅ Integration with existing tools via JSON
- ✅ Works standalone or with API server

Start simple, build complexity gradually!

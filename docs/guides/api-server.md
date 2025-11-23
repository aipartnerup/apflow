# API Server Usage Guide

This guide explains how to use the aipartnerupflow API server for remote task execution and integration.

## Overview

The API server provides:
- **A2A Protocol Server**: Standard agent-to-agent communication protocol
- **HTTP API**: RESTful endpoints for task management
- **Real-time Streaming**: Progress updates via SSE/WebSocket
- **Multi-user Support**: User isolation and authentication

## Starting the API Server

### Basic Startup

```bash
# Start server on default port (8000)
aipartnerupflow serve

# Or use the server command
aipartnerupflow-server

# Or use Python module
python -m aipartnerupflow.api.main
```

### Advanced Options

```bash
# Custom host and port
aipartnerupflow serve --host 0.0.0.0 --port 8080

# Enable auto-reload (development)
aipartnerupflow serve --reload

# Multiple workers (production)
aipartnerupflow serve --workers 4

# Custom configuration
aipartnerupflow serve --config config.yaml
```

## API Endpoints

### A2A Protocol Endpoints

The API server implements the A2A (Agent-to-Agent) Protocol standard.

#### Get Agent Card

```bash
curl http://localhost:8000/.well-known/agent-card
```

Returns agent capabilities and available skills.

#### Execute Task Tree (A2A Protocol)

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "execute_task_tree",
    "params": {
      "tasks": [
        {
          "id": "task1",
          "name": "my_task",
          "user_id": "user123",
          "inputs": {"key": "value"}
        }
      ]
    },
    "id": "request-123"
  }'
```

### Task Management Endpoints

#### Create Tasks

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.create",
    "params": {
      "tasks": [...]
    },
    "id": "request-123"
  }'
```

#### Get Task Status

```bash
curl http://localhost:8000/tasks/{task_id}/status
```

#### List Tasks

```bash
curl http://localhost:8000/tasks?user_id=user123
```

## Streaming Support

### Server-Sent Events (SSE)

Connect to streaming endpoint for real-time updates:

```bash
curl -N http://localhost:8000/stream/{task_id}
```

### WebSocket

Connect via WebSocket for bidirectional communication:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Progress:', update.progress);
};
```

## Client Integration

### Python Client Example

```python
import httpx
import json

# Execute task via API
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/",
        json={
            "jsonrpc": "2.0",
            "method": "execute_task_tree",
            "params": {
                "tasks": [
                    {
                        "id": "task1",
                        "name": "my_task",
                        "user_id": "user123",
                        "inputs": {"key": "value"}
                    }
                ]
            },
            "id": "request-123"
        }
    )
    result = response.json()
    print(result)
```

### JavaScript Client Example

```javascript
// Execute task via API
const response = await fetch('http://localhost:8000/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    jsonrpc: '2.0',
    method: 'execute_task_tree',
    params: {
      tasks: [
        {
          id: 'task1',
          name: 'my_task',
          user_id: 'user123',
          inputs: { key: 'value' }
        }
      ]
    },
    id: 'request-123'
  })
});

const result = await response.json();
console.log(result);
```

## Authentication

### JWT Authentication (Optional)

If authentication is enabled:

```bash
# Get token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'

# Use token
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

## LLM API Key Management

The API server supports dynamic LLM API key injection for CrewAI tasks. Keys can be provided via request headers or user configuration.

### Request Header (Demo/One-time Usage)

For demo or one-time usage, you can provide LLM API keys via the `X-LLM-API-KEY` header:

```bash
# Simple format (auto-detects provider from model)
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-LLM-API-KEY: sk-your-openai-key" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks.create",
    "params": {
      "tasks": [{
        "id": "task1",
        "name": "CrewAI Task",
        "schemas": {"method": "crewai_executor"},
        "params": {
          "works": {
            "agents": {
              "researcher": {
                "role": "Research Analyst",
                "llm": "openai/gpt-4"
              }
            }
          }
        }
      }]
    }
  }'

# Provider-specific format (explicit provider)
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-LLM-API-KEY: openai:sk-your-openai-key" \
  -d '{...}'

# Anthropic example
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-LLM-API-KEY: anthropic:sk-ant-your-key" \
  -d '{...}'
```

**Header Format:**
- Simple: `X-LLM-API-KEY: <api-key>` (provider auto-detected from model name)
- Provider-specific: `X-LLM-API-KEY: <provider>:<api-key>` (e.g., `openai:sk-xxx`, `anthropic:sk-ant-xxx`)

**Supported Providers:**
- `openai` - OpenAI (GPT models)
- `anthropic` - Anthropic (Claude models)
- `google` / `gemini` - Google (Gemini models)
- `mistral` - Mistral AI
- `groq` - Groq
- And more (see LLM Key Injector documentation)

**Priority:**
1. Request header (`X-LLM-API-KEY`) - highest priority
2. User config (if `llm-key-config` extension is installed)
3. Environment variables (automatically read by CrewAI/LiteLLM)

### User Configuration (Multi-user Scenarios)

For production multi-user scenarios, use the `llm-key-config` extension:

```bash
# Install extension
pip install aipartnerupflow[llm-key-config]
```

Then configure keys programmatically:

```python
from aipartnerupflow.extensions.llm_key_config import LLMKeyConfigManager

# Set user's LLM key
config_manager = LLMKeyConfigManager()
config_manager.set_key(user_id="user123", api_key="sk-xxx", provider="openai")

# Set provider-specific keys
config_manager.set_key(user_id="user123", api_key="sk-xxx", provider="openai")
config_manager.set_key(user_id="user123", api_key="sk-ant-xxx", provider="anthropic")
```

**Note:** Keys are stored in memory (not in database). For production multi-server scenarios, consider using Redis.

### Environment Variables (Fallback)

If no header or user config is provided, CrewAI/LiteLLM will automatically use provider-specific environment variables:

```bash
export OPENAI_API_KEY="sk-xxx"
export ANTHROPIC_API_KEY="sk-ant-xxx"
export GOOGLE_API_KEY="xxx"
```

### Examples Auto-initialization

When the API server starts, it automatically initializes example tasks if the database is empty. This helps beginners get started quickly.

To manually initialize examples:

```bash
# Via CLI
aipartnerupflow examples init

# Or force re-initialization
aipartnerupflow examples init --force
```

## Configuration

### Environment Variables

```bash
# Server configuration
export AIPARTNERUPFLOW_HOST=0.0.0.0
export AIPARTNERUPFLOW_PORT=8000

# Database configuration
export AIPARTNERUPFLOW_DATABASE_URL=postgresql://user:pass@localhost/db

# Authentication
export AIPARTNERUPFLOW_JWT_SECRET=your-secret-key
```

### Configuration File

Create `config.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 8000
  workers: 4

database:
  url: postgresql://user:pass@localhost/db

auth:
  enabled: true
  jwt_secret: your-secret-key
```

## Production Deployment

### Using Uvicorn Directly

```bash
uvicorn aipartnerupflow.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4
```

### Using Docker

```dockerfile
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install aipartnerupflow[a2a]
CMD ["aipartnerupflow-server", "--host", "0.0.0.0", "--port", "8000"]
```

### Using Systemd

Create `/etc/systemd/system/aipartnerupflow.service`:

```ini
[Unit]
Description=aipartnerupflow API Server
After=network.target

[Service]
Type=simple
User=apflow
WorkingDirectory=/opt/aipartnerupflow
ExecStart=/usr/local/bin/aipartnerupflow-server --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Metrics

```bash
curl http://localhost:8000/metrics
```

## Troubleshooting

### Server Won't Start

- Check if port is already in use
- Verify database connection
- Check logs for errors

### Tasks Not Executing

- Verify executor is registered
- Check task name matches executor ID
- Review server logs

### Connection Issues

- Verify firewall settings
- Check network connectivity
- Ensure server is accessible

## Next Steps

- See [HTTP API Reference](../api/http.md) for complete endpoint documentation
- Check [Examples](../examples/basic_task.md) for integration examples


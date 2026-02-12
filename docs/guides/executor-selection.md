# Executor Selection Guide

Choose the right executor for your task. This guide helps you decide which built-in executor to use or when to create a custom one.

## Quick Decision Tree

```
What does your task need to do?
│
├─ Call an HTTP/REST API?
│  └─ Use: rest_executor
│     Example: Fetch data from third-party API, trigger webhooks
│
├─ Execute commands on a remote server?
│  ├─ Via SSH → Use: ssh_executor
│  │  Example: Deploy code, run maintenance scripts
│  └─ In a container → Use: docker_executor
│     Example: Run isolated workloads, reproducible environments
│
├─ Call a gRPC service?
│  └─ Use: grpc_executor
│     Example: Microservice communication, high-performance RPC
│
├─ Use AI agents?
│  ├─ Multi-agent collaboration → Use: crewai_executor
│  │  Example: Research team, content generation workflow
│  ├─ Single LLM call → Use: litellm_executor
│  │  Example: Text generation, completion, chat
│  └─ Use MCP tools → Use: mcp_executor
│     Example: Call Model Context Protocol services
│
├─ Real-time bidirectional communication?
│  └─ Use: websocket_executor
│     Example: Live updates, streaming data
│
└─ Custom business logic?
   └─ Create: Custom Executor
      Example: Domain-specific operations, internal services
```

---

## Executor Comparison

| Executor | Use Case | Pros | Cons | Installation |
|----------|----------|------|------|--------------|
| **REST** | HTTP API calls | Simple, universal, no dependencies | No persistent connections | Built-in |
| **SSH** | Remote command execution | Full server access, scriptable | Requires SSH credentials | `pip install apflow[ssh]` |
| **Docker** | Containerized execution | Isolated, reproducible | Requires Docker daemon | `pip install apflow[docker]` |
| **gRPC** | High-performance RPC | Fast, type-safe, efficient | Requires proto definitions | `pip install apflow[grpc]` |
| **WebSocket** | Bidirectional streaming | Real-time, low latency | Connection management | Built-in |
| **CrewAI** | Multi-agent AI workflows | AI-native, collaborative agents | Requires API keys (OpenAI) | `pip install apflow[crewai]` |
| **LiteLLM** | LLM API calls | Supports 100+ models | API costs | `pip install apflow[llm]` |
| **MCP** | MCP tool calls | Standard protocol, composable | Requires MCP servers | `pip install apflow[mcp]` |

---

## Detailed Scenarios

### Scenario 1: Call Third-Party API

**Executor**: `rest_executor`

**Example**: Fetch weather data

```python
from apflow import TaskBuilder, execute_tasks

task = TaskBuilder("fetch_weather", "rest_executor")\
    .with_inputs({
        "url": "https://api.weather.com/v1/forecast",
        "method": "GET",
        "params": {"city": "San Francisco"},
        "headers": {"Authorization": "Bearer YOUR_TOKEN"}
    })\
    .build()

result = execute_tasks([task])
print(result["json"])
```

**When to use**:
- Calling REST APIs (GET, POST, PUT, DELETE)
- Webhook notifications
- Third-party service integration

**Alternatives**:
- gRPC executor (if service supports gRPC)
- Custom executor (if complex authentication or business logic needed)

---

### Scenario 2: Execute Commands on Remote Server

**Executor**: `ssh_executor`

**Example**: Deploy application

```python
task = TaskBuilder("deploy_app", "ssh_executor")\
    .with_inputs({
        "host": "prod-server.example.com",
        "port": 22,
        "username": "deploy",
        "key_file": "~/.ssh/deploy_key",
        "command": "bash /opt/scripts/deploy.sh",
        "timeout": 300  # 5 minutes
    })\
    .build()

result = execute_tasks([task])
print(f"Exit code: {result['return_code']}")
print(f"Output: {result['stdout']}")
```

**When to use**:
- Remote deployments
- Server maintenance
- Running scripts on remote machines
- System administration tasks

**Alternatives**:
- Docker executor (if containerized deployment)
- REST executor (if server has API for deployments)

---

### Scenario 3: Run Isolated Workload

**Executor**: `docker_executor`

**Example**: Process data in Python container

```python
task = TaskBuilder("process_data", "docker_executor")\
    .with_inputs({
        "image": "python:3.11",
        "command": "python /app/process.py",
        "volumes": {
            "/host/data": "/app/data",
            "/host/results": "/app/results"
        },
        "env": {
            "INPUT_FILE": "/app/data/input.csv",
            "OUTPUT_FILE": "/app/results/output.csv"
        },
        "timeout": 600
    })\
    .build()

result = execute_tasks([task])
print(f"Container logs: {result['logs']}")
```

**When to use**:
- Isolated execution environments
- Reproducible workflows
- Running code with specific dependencies
- Batch processing

**Alternatives**:
- SSH executor (if remote execution acceptable)
- Custom executor (if can run locally without isolation)

---

### Scenario 4: High-Performance Microservice Communication

**Executor**: `grpc_executor`

**Example**: Call internal microservice

```python
task = TaskBuilder("call_service", "grpc_executor")\
    .with_inputs({
        "host": "service.internal",
        "port": 50051,
        "method": "GetUser",
        "data": {"user_id": "12345"}
    })\
    .build()

result = execute_tasks([task])
print(result["response"])
```

**When to use**:
- Microservice architectures
- Low-latency requirements
- Type-safe APIs
- Internal service communication

**Alternatives**:
- REST executor (if HTTP is acceptable)
- Custom executor (if using different protocol)

---

### Scenario 5: Multi-Agent AI Workflow

**Executor**: `crewai_executor`

**Example**: Research and write article

```python
task = TaskBuilder("write_article", "crewai_executor")\
    .with_inputs({
        "crew_config": {
            "agents": [
                {
                    "role": "Researcher",
                    "goal": "Research topic thoroughly",
                    "backstory": "Expert researcher"
                },
                {
                    "role": "Writer",
                    "goal": "Write engaging article",
                    "backstory": "Professional writer"
                }
            ],
            "tasks": [
                {
                    "description": "Research topic: {topic}",
                    "agent": "Researcher"
                },
                {
                    "description": "Write article based on research",
                    "agent": "Writer"
                }
            ]
        },
        "inputs": {"topic": "Quantum Computing"}
    })\
    .build()

result = execute_tasks([task])
print(result["output"])
```

**When to use**:
- Multi-agent collaboration
- Complex AI workflows
- Research and content generation
- Agent-based problem solving

**Alternatives**:
- LiteLLM executor (for single LLM calls)
- Custom executor (for custom AI workflows)

---

### Scenario 6: Single LLM API Call

**Executor**: `litellm_executor`

**Example**: Generate text completion

```python
task = TaskBuilder("generate_text", "litellm_executor")\
    .with_inputs({
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Explain quantum computing in simple terms"}
        ],
        "max_tokens": 500
    })\
    .build()

result = execute_tasks([task])
print(result["completion"])
```

**When to use**:
- Single LLM calls
- Text generation
- Chat completions
- Model comparisons (supports 100+ models)

**Alternatives**:
- CrewAI executor (for multi-agent workflows)
- Custom executor (for custom LLM integration)

---

## Custom Executors

When built-in executors don't fit your needs:

### Create a Custom Executor

```python
from apflow import executor_register
from apflow.extensions import BaseTask
from typing import Dict, Any

@executor_register()
class MyCustomExecutor(BaseTask):
    """
    Custom executor for domain-specific operations
    """
    id = "my_custom_executor"
    name = "My Custom Executor"
    description = "Handles custom business logic"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Your custom logic here
        result = self.process_data(inputs["data"])

        return {
            "success": True,
            "result": result
        }

    def process_data(self, data):
        # Custom processing
        return f"Processed: {data}"
```

**When to create custom executor**:
- Domain-specific business logic
- Integration with internal systems
- Custom authentication/authorization
- Complex data transformations
- When no built-in executor fits

---

## Executor Capabilities Matrix

| Feature | REST | SSH | Docker | gRPC | WebSocket | CrewAI | LiteLLM | MCP |
|---------|------|-----|--------|------|-----------|--------|---------|-----|
| **Cancellation** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Streaming** | ❌ | ❌ | ❌ | ⚠️ | ✅ | ⚠️ | ⚠️ | ❌ |
| **Timeout** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Retries** | Manual | Manual | Manual | Manual | Manual | Manual | Manual | Manual |
| **Authentication** | ✅ | ✅ | ❌ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ |

**Legend**:
- ✅ Fully supported
- ⚠️ Partially supported or requires configuration
- ❌ Not supported

---

## Performance Considerations

### Latency

**Low latency** (< 100ms typical):
- gRPC executor (binary protocol)
- Custom executor (local)

**Medium latency** (100ms - 1s):
- REST executor (HTTP overhead)
- WebSocket executor (after connection)

**High latency** (> 1s):
- SSH executor (network + auth)
- Docker executor (container startup)
- AI executors (LLM API latency)

### Throughput

**High throughput**:
- gRPC executor (efficient serialization)
- Custom executor (no network overhead)

**Medium throughput**:
- REST executor
- WebSocket executor

**Lower throughput**:
- SSH executor (connection overhead)
- Docker executor (container lifecycle)
- AI executors (rate limits)

---

## Security Considerations

| Executor | Security Notes |
|----------|----------------|
| **REST** | ✅ Blocks private IPs by default (SSRF protection)<br>⚠️ Verify SSL certificates<br>⚠️ Handle secrets securely |
| **SSH** | ✅ Validates key permissions<br>⚠️ Use key-based auth (not passwords)<br>⚠️ Restrict SSH access |
| **Docker** | ⚠️ Runs with host Docker privileges<br>⚠️ Validate image sources<br>⚠️ Limit container resources |
| **gRPC** | ⚠️ Implement authentication<br>⚠️ Use TLS in production |
| **AI** | ⚠️ Protect API keys<br>⚠️ Monitor costs<br>⚠️ Validate AI outputs |

---

## Next Steps

- **[REST Executor Documentation](../executors/rest.md)**
- **[SSH Executor Documentation](../executors/ssh.md)**
- **[Creating Custom Executors](../guides/custom-executors.md)**
- **[Task Dependencies](../guides/task-dependencies.md)**

---

## Quick Reference

```bash
# Install executor extras
pip install apflow[ssh]        # SSH executor
pip install apflow[docker]     # Docker executor
pip install apflow[grpc]       # gRPC executor
pip install apflow[crewai]     # CrewAI executor
pip install apflow[llm]        # LiteLLM executor
pip install apflow[mcp]        # MCP executor
pip install apflow[all]        # All executors

# List available executors
apflow executors list

# Get executor details
apflow executors get <executor-id>
```

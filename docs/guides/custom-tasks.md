# Custom Tasks Guide

Learn how to create your own custom executors (tasks) in aipartnerupflow. This guide will walk you through everything from simple tasks to advanced patterns.

## What You'll Learn

- ✅ How to create custom executors
- ✅ How to register and use them
- ✅ Input validation with JSON Schema
- ✅ Error handling best practices
- ✅ Common patterns and examples
- ✅ Testing your custom tasks

## Table of Contents

1. [Quick Start](#quick-start)
2. [Understanding Executors](#understanding-executors)
3. [Creating Your First Executor](#creating-your-first-executor)
4. [Required Components](#required-components)
5. [Input Schema](#input-schema)
6. [Error Handling](#error-handling)
7. [Common Patterns](#common-patterns)
8. [Advanced Features](#advanced-features)
9. [Best Practices](#best-practices)
10. [Testing](#testing)

## Quick Start

The fastest way to create a custom executor:

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class MyFirstExecutor(BaseTask):
    """A simple custom executor"""
    
    id = "my_first_executor"
    name = "My First Executor"
    description = "Does something useful"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
        result = f"Processed: {inputs.get('data', 'no data')}"
        return {"status": "completed", "result": result}
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Define input parameters"""
        return {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Input data"}
            },
            "required": ["data"]
        }
```

**That's it!** Just import it and use it:

```python
# Import to register
from my_module import MyFirstExecutor

# Use it
task = await task_manager.task_repository.create_task(
    name="my_first_executor",  # Must match id
    user_id="user123",
    inputs={"data": "Hello!"}
)
```

## Understanding Executors

### What is an Executor?

An **executor** is a piece of code that performs a specific task. Think of it as a function that:
- Takes inputs (parameters)
- Does some work
- Returns a result

**Example:**
- An executor that fetches data from an API
- An executor that processes files
- An executor that sends emails
- An executor that runs AI models

### Executor vs Task

**Executor**: The code that does the work (reusable)
**Task**: An instance of work to be done (specific execution)

**Analogy:**
- **Executor** = A recipe (reusable template)
- **Task** = A specific meal made from the recipe (one-time execution)

### BaseTask vs ExecutableTask

**BaseTask**: Recommended base class (simpler, includes registration)
```python
from aipartnerupflow import BaseTask, executor_register

@executor_register()
class MyTask(BaseTask):
    id = "my_task"
    # ...
```

**ExecutableTask**: Lower-level interface (more control)
```python
from aipartnerupflow import ExecutableTask

class MyTask(ExecutableTask):
    @property
    def id(self) -> str:
        return "my_task"
    # ...
```

**Recommendation**: Use `BaseTask` with `@executor_register()` - it's simpler!

## Creating Your First Executor

Let's create a complete, working example step by step.

### Step 1: Create the Executor Class

Create a file `greeting_executor.py`:

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class GreetingExecutor(BaseTask):
    """Creates personalized greetings"""
    
    id = "greeting_executor"
    name = "Greeting Executor"
    description = "Creates personalized greeting messages"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute greeting creation"""
        name = inputs.get("name", "Guest")
        language = inputs.get("language", "en")
        
        greetings = {
            "en": f"Hello, {name}!",
            "es": f"¡Hola, {name}!",
            "fr": f"Bonjour, {name}!"
        }
        
        return {
            "greeting": greetings.get(language, greetings["en"]),
            "name": name,
            "language": language
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Define input parameters"""
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the person to greet"
                },
                "language": {
                    "type": "string",
                    "enum": ["en", "es", "fr", "zh"],
                    "description": "Language for the greeting",
                    "default": "en"
                }
            },
            "required": ["name"]
        }
```

### Step 2: Use Your Executor

Create a file `use_greeting.py`:

```python
import asyncio
from aipartnerupflow import TaskManager, TaskTreeNode, create_session
# Import to register the executor
from greeting_executor import GreetingExecutor

async def main():
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create task using your executor
    task = await task_manager.task_repository.create_task(
        name="greeting_executor",  # Must match executor id
        user_id="user123",
        inputs={
            "name": "Alice",
            "language": "en"
        }
    )
    
    # Execute
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # Get result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Greeting: {result.result['greeting']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 3: Run It

```bash
python use_greeting.py
```

**Expected Output:**
```
Greeting: Hello, Alice!
```

**Congratulations!** You just created and used your first custom executor! 🎉

## Required Components

Every executor must have these components:

### 1. Unique ID

**Purpose**: Identifies the executor (used when creating tasks)

```python
id = "my_executor_id"  # Must be unique across all executors
```

**Best Practices:**
- Use lowercase with underscores
- Be descriptive: `fetch_user_data` not `task1`
- Keep it consistent: don't change after deployment

### 2. Display Name

**Purpose**: Human-readable name

```python
name = "My Executor"  # What users see
```

### 3. Description

**Purpose**: Explains what the executor does

```python
description = "Fetches user data from the API"
```

### 4. Execute Method

**Purpose**: The actual work happens here

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the task
    
    Args:
        inputs: Input parameters (from task.inputs)
        
    Returns:
        Execution result dictionary
    """
    # Your logic here
    return {"status": "completed", "result": "..."}
```

**Key Points:**
- Must be `async`
- Receives `inputs` dictionary
- Returns a dictionary
- Can raise exceptions (will be caught by TaskManager)

### 5. Input Schema

**Purpose**: Defines what inputs are expected (for validation)

```python
def get_input_schema(self) -> Dict[str, Any]:
    """
    Return JSON Schema for input parameters
    
    Returns:
        JSON Schema dictionary
    """
    return {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param1"]
    }
```

## Input Schema

Input schemas use JSON Schema format to define and validate inputs.

### Basic Schema

```python
def get_input_schema(self) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"}
        },
        "required": ["name"]
    }
```

### Common Field Types

#### String

```python
"name": {
    "type": "string",
    "description": "Person's name",
    "minLength": 1,
    "maxLength": 100
}
```

#### Integer

```python
"age": {
    "type": "integer",
    "description": "Person's age",
    "minimum": 0,
    "maximum": 150
}
```

#### Boolean

```python
"enabled": {
    "type": "boolean",
    "description": "Whether feature is enabled",
    "default": false
}
```

#### Array

```python
"items": {
    "type": "array",
    "items": {"type": "string"},
    "description": "List of items",
    "minItems": 1
}
```

#### Object

```python
"config": {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "value": {"type": "string"}
    },
    "description": "Configuration object"
}
```

#### Enum (Limited Choices)

```python
"status": {
    "type": "string",
    "enum": ["pending", "active", "completed"],
    "description": "Task status",
    "default": "pending"
}
```

### Default Values

Provide defaults for optional parameters:

```python
"timeout": {
    "type": "integer",
    "description": "Timeout in seconds",
    "default": 30  # Used if not provided
}
```

### Required Fields

Specify which fields are required:

```python
{
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"}
    },
    "required": ["name", "email"]  # Both required
}
```

### Complete Schema Example

```python
def get_input_schema(self) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "API endpoint URL",
                "format": "uri"
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE"],
                "description": "HTTP method",
                "default": "GET"
            },
            "headers": {
                "type": "object",
                "description": "HTTP headers",
                "additionalProperties": {"type": "string"}
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "minimum": 1,
                "maximum": 300,
                "default": 30
            },
            "retry": {
                "type": "boolean",
                "description": "Whether to retry on failure",
                "default": false
            }
        },
        "required": ["url"]
    }
```

## Error Handling

### Returning Errors (Recommended)

Return error information in the result:

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = perform_operation(inputs)
        return {"status": "completed", "result": result}
    except ValueError as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": "validation_error"
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": "execution_error"
        }
```

**Benefits:**
- More control over error format
- Can include additional context
- Task status will be "failed"

### Raising Exceptions

You can also raise exceptions (TaskManager will catch them):

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    if not inputs.get("required_param"):
        raise ValueError("required_param is required")
    
    # Continue with execution
    return {"status": "completed", "result": "..."}
```

**Note**: TaskManager will catch exceptions and mark the task as "failed".

### Best Practices

1. **Validate early**: Check inputs at the start
2. **Return meaningful errors**: Include error type and message
3. **Handle specific exceptions**: Catch specific errors, not just `Exception`
4. **Include context**: Add relevant information to error messages

**Example:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    url = inputs.get("url")
    if not url:
        return {
            "status": "failed",
            "error": "URL is required",
            "error_type": "validation_error",
            "field": "url"
        }
    
    if not isinstance(url, str):
        return {
            "status": "failed",
            "error": "URL must be a string",
            "error_type": "type_error",
            "field": "url",
            "received_type": type(url).__name__
        }
    
    # Continue with execution
    try:
        result = await fetch_url(url)
        return {"status": "completed", "result": result}
    except TimeoutError:
        return {
            "status": "failed",
            "error": f"Request to {url} timed out",
            "error_type": "timeout_error"
        }
```

## Common Patterns

### Pattern 1: HTTP API Call

```python
import aiohttp
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class APICallExecutor(BaseTask):
    """Calls an external HTTP API"""
    
    id = "api_call_executor"
    name = "API Call Executor"
    description = "Calls an external HTTP API"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        url = inputs.get("url")
        method = inputs.get("method", "GET")
        headers = inputs.get("headers", {})
        timeout = inputs.get("timeout", 30)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    data = await response.json() if response.content_type == "application/json" else await response.text()
                    
                    return {
                        "status": "completed",
                        "status_code": response.status,
                        "data": data
                    }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "API URL"},
                "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET"},
                "headers": {"type": "object"},
                "timeout": {"type": "integer", "default": 30}
            },
            "required": ["url"]
        }
```

### Pattern 2: Data Processing

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class DataProcessor(BaseTask):
    """Processes data"""
    
    id = "data_processor"
    name = "Data Processor"
    description = "Processes data with various operations"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data = inputs.get("data", [])
        operation = inputs.get("operation", "sum")
        
        if not isinstance(data, list):
            return {
                "status": "failed",
                "error": "Data must be a list",
                "error_type": "validation_error"
            }
        
        if operation == "sum":
            result = sum(data)
        elif operation == "average":
            result = sum(data) / len(data) if data else 0
        elif operation == "max":
            result = max(data) if data else None
        elif operation == "min":
            result = min(data) if data else None
        else:
            return {
                "status": "failed",
                "error": f"Unknown operation: {operation}",
                "error_type": "validation_error"
            }
        
        return {
            "status": "completed",
            "operation": operation,
            "result": result,
            "input_count": len(data)
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of numbers"
                },
                "operation": {
                    "type": "string",
                    "enum": ["sum", "average", "max", "min"],
                    "default": "sum"
                }
            },
            "required": ["data"]
        }
```

### Pattern 3: File Operations

```python
import aiofiles
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class FileReader(BaseTask):
    """Reads files"""
    
    id = "file_reader"
    name = "File Reader"
    description = "Reads content from files"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        file_path = inputs.get("file_path")
        
        if not file_path:
            return {
                "status": "failed",
                "error": "file_path is required",
                "error_type": "validation_error"
            }
        
        try:
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
            
            return {
                "status": "completed",
                "file_path": file_path,
                "content": content,
                "size": len(content)
            }
        except FileNotFoundError:
            return {
                "status": "failed",
                "error": f"File not found: {file_path}",
                "error_type": "file_not_found"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to file"
                }
            },
            "required": ["file_path"]
        }
```

### Pattern 4: Database Query

```python
from aipartnerupflow import BaseTask, executor_register
from typing import Dict, Any

@executor_register()
class DatabaseQuery(BaseTask):
    """Executes database queries"""
    
    id = "db_query"
    name = "Database Query"
    description = "Executes database queries"
    
    def __init__(self):
        super().__init__()
        # Initialize database connection
        # self.db = create_db_connection()
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get("query")
        params = inputs.get("params", {})
        
        if not query:
            return {
                "status": "failed",
                "error": "query is required",
                "error_type": "validation_error"
            }
        
        try:
            # Execute query
            # result = await self.db.fetch(query, params)
            result = []  # Placeholder
            
            return {
                "status": "completed",
                "rows": result,
                "count": len(result)
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "error_type": "database_error"
            }
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query"},
                "params": {"type": "object", "description": "Query parameters"}
            },
            "required": ["query"]
        }
```

## Advanced Features

### Cancellation Support

Implement cancellation for long-running tasks:

```python
class CancellableTask(BaseTask):
    cancelable: bool = True  # Mark as cancellable
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self._cancelled = False
        
        for i in range(100):
            # Check for cancellation
            if self._cancelled:
                return {
                    "status": "cancelled",
                    "message": "Task was cancelled",
                    "progress": i
                }
            
            # Do work
            await asyncio.sleep(0.1)
        
        return {"status": "completed", "result": "done"}
    
    async def cancel(self) -> Dict[str, Any]:
        """Cancel task execution"""
        self._cancelled = True
        return {
            "status": "cancelled",
            "message": "Cancellation requested"
        }
```

**Note**: Not all executors need cancellation. Only implement if your task can be safely cancelled.

### Accessing Task Context

Access task information through the executor:

```python
class ContextAwareTask(BaseTask):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Task context is available through TaskManager
        # You can access it via hooks or by storing task reference
        
        # Example: Access task ID (if available)
        # task_id = getattr(self, '_task_id', None)
        
        return {"status": "completed"}
```

## Best Practices

### 1. Keep Tasks Focused

**Good:**
```python
class FetchUserData(BaseTask):
    # Only fetches user data
```

**Bad:**
```python
class DoEverything(BaseTask):
    # Fetches, processes, saves, sends notifications, etc.
```

### 2. Validate Inputs Early

```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Validate at the start
    url = inputs.get("url")
    if not url:
        return {"status": "failed", "error": "URL is required"}
    
    if not isinstance(url, str):
        return {"status": "failed", "error": "URL must be a string"}
    
    # Continue with execution
```

### 3. Use Async Properly

**Good:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
    return {"status": "completed", "data": data}
```

**Bad:**
```python
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    import requests
    response = requests.get(url)  # Blocking!
    return {"status": "completed", "data": response.json()}
```

### 4. Document Your Tasks

```python
class MyCustomTask(BaseTask):
    """
    Custom task that performs specific operations.
    
    This task processes input data and returns processed results.
    It supports various processing modes and configurations.
    
    Example:
        task = create_task(
            name="my_custom_task",
            inputs={"data": [1, 2, 3], "mode": "sum"}
        )
    """
```

### 5. Return Consistent Results

```python
# Good: Consistent format
return {
    "status": "completed",
    "result": result,
    "metadata": {...}
}

# Bad: Inconsistent format
return result  # Sometimes just the result
return {"data": result}  # Sometimes wrapped
```

## Testing

### Unit Testing

Test your executor in isolation:

```python
import pytest
from my_executors import GreetingExecutor

@pytest.mark.asyncio
async def test_greeting_executor():
    executor = GreetingExecutor()
    
    # Test with valid inputs
    result = await executor.execute({
        "name": "Alice",
        "language": "en"
    })
    
    assert result["status"] == "completed"
    assert "Hello, Alice!" in result["greeting"]
    
    # Test with default language
    result = await executor.execute({"name": "Bob"})
    assert result["language"] == "en"
    
    # Test with invalid language
    result = await executor.execute({
        "name": "Charlie",
        "language": "invalid"
    })
    # Should handle gracefully
```

### Integration Testing

Test with TaskManager:

```python
import pytest
from aipartnerupflow import TaskManager, TaskTreeNode, create_session
from my_executors import GreetingExecutor

@pytest.mark.asyncio
async def test_executor_integration():
    # Import to register
    from my_executors import GreetingExecutor
    
    db = create_session()
    task_manager = TaskManager(db)
    
    # Create and execute task
    task = await task_manager.task_repository.create_task(
        name="greeting_executor",
        user_id="test_user",
        inputs={"name": "Test User", "language": "en"}
    )
    
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # Verify result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    assert result.status == "completed"
    assert "Test User" in result.result["greeting"]
```

## Built-in Executors

aipartnerupflow provides several built-in executors for common use cases. These executors are automatically registered and can be used directly in your tasks.

### HTTP/REST API Executor

Execute HTTP requests to external APIs, webhooks, and HTTP-based services.

**Installation:**
```bash
# httpx is included in a2a extra
pip install aipartnerupflow[a2a]
```

**Usage:**
```python
{
    "schemas": {
        "method": "rest_executor"
    },
    "inputs": {
        "url": "https://api.example.com/users",
        "method": "GET",
        "headers": {"Authorization": "Bearer token"},
        "timeout": 30.0
    }
}
```

**Features:**
- Supports GET, POST, PUT, DELETE, PATCH methods
- Authentication: Bearer token, Basic auth, API key
- Custom headers and query parameters
- JSON and form data support
- SSL verification control

### SSH Remote Executor

Execute commands on remote servers via SSH.

**Installation:**
```bash
pip install aipartnerupflow[ssh]
```

**Usage:**
```python
{
    "schemas": {
        "method": "ssh_executor"
    },
    "inputs": {
        "host": "example.com",
        "username": "user",
        "key_file": "/path/to/key",
        "command": "ls -la",
        "timeout": 30
    }
}
```

**Features:**
- Password and key-based authentication
- Environment variable support
- Automatic key file permission validation
- Command timeout handling

### Docker Container Executor

Execute commands in isolated Docker containers.

**Installation:**
```bash
pip install aipartnerupflow[docker]
```

**Usage:**
```python
{
    "schemas": {
        "method": "docker_executor"
    },
    "inputs": {
        "image": "python:3.11",
        "command": "python -c 'print(\"Hello\")'",
        "env": {"KEY": "value"},
        "volumes": {"/host/path": "/container/path"},
        "resources": {"cpu": "1.0", "memory": "512m"}
    }
}
```

**Features:**
- Custom Docker images
- Environment variables
- Volume mounts
- Resource limits (CPU, memory)
- Automatic container cleanup

### gRPC Executor

Call gRPC services and microservices.

**Installation:**
```bash
pip install aipartnerupflow[grpc]
```

**Usage:**
```python
{
    "schemas": {
        "method": "grpc_executor"
    },
    "inputs": {
        "server": "localhost:50051",
        "service": "Greeter",
        "method": "SayHello",
        "request": {"name": "World"},
        "timeout": 30.0
    }
}
```

**Features:**
- Dynamic proto loading support
- Custom metadata
- Timeout handling
- Error handling

### WebSocket Executor

Bidirectional WebSocket communication.

**Installation:**
```bash
# websockets is included in a2a extra
pip install aipartnerupflow[a2a]
```

**Usage:**
```python
{
    "schemas": {
        "method": "websocket_executor"
    },
    "inputs": {
        "url": "ws://example.com/ws",
        "message": "Hello",
        "wait_response": true,
        "timeout": 30.0
    }
}
```

**Features:**
- Send and receive messages
- JSON message support
- Configurable response waiting
- Connection timeout handling

### aipartnerupflow API Executor

Call other aipartnerupflow API instances for distributed execution.

**Installation:**
```bash
# httpx is included in a2a extra
pip install aipartnerupflow[a2a]
```

**Usage:**
```python
{
    "schemas": {
        "method": "apflow_api_executor"
    },
    "inputs": {
        "base_url": "http://remote-instance:8000",
        "method": "tasks.execute",
        "params": {"task_id": "task-123"},
        "auth_token": "eyJ...",
        "wait_for_completion": true
    }
}
```

**Features:**
- All task management methods (tasks.execute, tasks.create, tasks.get, etc.)
- JWT authentication support
- Task completion polling
- Streaming support
- Distributed execution scenarios

**Use Cases:**
- Distributed task execution across multiple instances
- Service orchestration
- Load balancing
- Cross-environment task execution

### Summary

All built-in executors follow the same pattern:
1. Inherit from `BaseTask`
2. Registered with `@executor_register()`
3. Support cancellation (where applicable)
4. Provide input schema validation
5. Return consistent result format

You can use these executors directly in your task schemas or extend them for custom behavior.

## Next Steps

- **[Task Orchestration Guide](task-orchestration.md)** - Learn how to orchestrate multiple tasks
- **[Basic Examples](../examples/basic_task.md)** - More practical examples
- **[Best Practices Guide](best-practices.md)** - Advanced techniques
- **[API Reference](../api/python.md)** - Complete API documentation

---

**Need help?** Check the [FAQ](faq.md) or [Quick Start Guide](../getting-started/quick-start.md)

# Installation

> **Looking for a step-by-step beginner tutorial?** See the [Quick Start Guide](quick-start.md) for a hands-on introduction. This page lists all installation options and extras.

apflow can be installed with different feature sets depending on your needs.

## Core Library (Minimum)

The core library provides pure task orchestration without any LLM dependencies:

```bash
pip install apflow
```

**Includes:**
- Task orchestration specifications (TaskManager)
- Core interfaces (ExecutableTask, BaseTask, TaskStorage)
- Storage (DuckDB default)
- **NO CrewAI dependency**

**Excludes:**
- CrewAI support
- Batch execution
- API server
- CLI tools

## With Optional Features

### CrewAI Support

```bash
pip install apflow[crewai]
```

**Includes:**
- CrewaiExecutor for LLM-based agent crews
- BatchCrewaiExecutor for atomic batch execution of multiple crews

### A2A Protocol Server

```bash
pip install apflow[a2a]
```

**Includes:**
- A2A Protocol Server for agent-to-agent communication
- HTTP, SSE, and WebSocket support

**Usage:**
```bash
# Run A2A server
python -m apflow.api.main

# Or use the CLI command
apflow-server
```

### CLI Tools

```bash
pip install apflow[cli]
```

**Includes:**
- Command-line interface tools

**Usage:**
```bash
# Run CLI
apflow

# Or use the shorthand
apflow
```

### PostgreSQL Storage

```bash
pip install apflow[postgres]
```

**Includes:**
- PostgreSQL storage support (for enterprise/distributed scenarios)

### SSH Executor

```bash
pip install apflow[ssh]
```

**Includes:**
- SSH executor for remote command execution
- Execute commands on remote servers via SSH

### Docker Executor

```bash
pip install apflow[docker]
```

**Includes:**
- Docker executor for containerized execution
- Execute commands in isolated Docker containers

### gRPC Executor

```bash
pip install apflow[grpc]
```

**Includes:**
- gRPC executor for gRPC service calls
- Call gRPC services and microservices

### Everything

```bash
pip install apflow[all]
```

**Includes:**
- All optional features (crewai, a2a, cli, postgres, ssh, docker, grpc)

## Requirements

- **Python**: 3.10 or higher (3.12+ recommended)
- **DuckDB**: Included by default (no setup required)
- **PostgreSQL**: Optional, for distributed/production scenarios

## Development Installation

For development, install with development dependencies:

```bash
# Clone the repository
git clone https://github.com/aipartnerup/apflow.git
cd apflow

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with all features
pip install -e ".[all,dev]"
```

## Verification

After installation, verify the installation:

```python
import apflow
print(apflow.__version__)
```

Or using the CLI (if installed with `[cli]`):

```bash
apflow --version
```


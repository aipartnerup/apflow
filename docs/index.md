<style>
/* Hide the sidebar only on the desktop and keep the menu on the mobile. */
@media (min-width: 960px) {
  .md-sidebar--primary,
  .md-nav--primary {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
  }
  .md-main__inner {
    max-width: 100% !important;
  }
  .md-content {
    margin-left: 0 !important;
    max-width: 100% !important;
    padding-left: 1rem !important;
  }
}
</style>

# Welcome to apflow

**apflow** is a unified framework for orchestrating and executing tasks across multiple execution methods. It manages when tasks run, how they depend on each other, and ensures everything executes in the right order—whether you're calling HTTP APIs, executing SSH commands, running Docker containers, or coordinating AI agents.

---

## Problems We Solve

Are you struggling with these common challenges?

<div class="grid cards" markdown>

-   __Complex Task Dependencies__

    ---

    Manually tracking dependencies, ensuring proper execution order, and handling failures across complex workflows becomes a nightmare. You end up writing custom coordination code and dealing with race conditions.

-   __Multiple Execution Methods__

    ---

    You need to call HTTP APIs, execute SSH commands, run Docker containers, communicate via gRPC, and coordinate AI agents—but each requires different libraries and integration patterns.

-   __Traditional Tasks + AI Agents__

    ---

    You want to add AI capabilities to existing workflows, but most solutions force you to choose: either traditional task execution OR AI agents. You're stuck with all-or-nothing decisions.

-   __State Persistence & Recovery__

    ---

    When workflows fail or get interrupted, you lose progress. Implementing retry logic, checkpointing, and state recovery requires significant custom development.

-   __Real-time Monitoring__

    ---

    You need to show progress to users, but building real-time monitoring with polling, WebSocket connections, or custom streaming solutions takes weeks.

</div>

---

## Why apflow?

<div class="grid cards" markdown>

-   __Unified Interface__

    ---

    One framework handles traditional tasks, HTTP/REST APIs, SSH commands, Docker containers, gRPC services, WebSocket communication, MCP tools, and AI agents—all through the same ExecutableTask interface.

-   __Start Simple, Scale Up__

    ---

    Begin with a lightweight, dependency-free core. Add AI capabilities, A2A server, CLI tools, or PostgreSQL storage only when you need them. No forced upfront installations.

-   __Language-Agnostic Protocol__

    ---

    Built on the AI Partner Up Flow Protocol, ensuring interoperability across Python, Go, Rust, JavaScript, and more. Different language implementations work together seamlessly.

-   __Production-Ready__

    ---

    Built-in storage (DuckDB or PostgreSQL), real-time streaming, automatic retries, state persistence, and comprehensive monitoring—all included. No need to build these from scratch.

-   __Extensive Executor Ecosystem__

    ---

    Choose from HTTP/REST APIs (with authentication), SSH remote execution, Docker containers, gRPC services, WebSocket communication, MCP integration, and LLM-based task tree generation.

</div>

---

## What Happens When You Use apflow?

| Before | After |
|--------|-------|
| **Weeks** of custom coordination code | **Days** to define task trees with dependencies |
| **Multiple** orchestration systems for different execution methods | **One unified** interface for all execution methods |
| **All-or-nothing** decisions requiring complete rewrites | **Gradual** addition of AI agents incrementally |
| **Weeks** building custom polling or streaming solutions | **Built-in** real-time streaming via A2A Protocol |
| **Manual** recovery logic and lost progress | **Automatic** retries with exponential backoff and state persistence |
| **Worrying** about resource usage at scale | **Production-ready** from day one, handle hundreds of concurrent workflows |

---

## Quick Start

**New to apflow?** Get up and running in minutes!

**Installation:**

```bash
pip install apflow
```

[Quick Start Guide](getting-started/quick-start.md){ .md-button .md-button--primary }

[Core Concepts](getting-started/concepts.md){ .md-button }

[Examples](examples/basic_task.md){ .md-button }

---

## Documentation Sections

<div class="grid cards" markdown>

-   __Getting Started__

    ---

    Learn the fundamentals and get started quickly

    [Getting Started →](getting-started/index.md)

-   __User Guides__

    ---

    Complete guides for using apflow

    [Guides →](guides/task-orchestration.md)

-   __API Reference__

    ---

    Complete API documentation for Python and HTTP

    [API Reference →](api/python.md)

-   __Architecture__

    ---

    System architecture and design principles

    [Architecture →](architecture/overview.md)

-   __Protocol__

    ---

    Language-agnostic protocol specification

    [Protocol →](protocol/index.md)

-   __Development__

    ---

    Contributing and extending the framework

    [Development →](development/setup.md)

-   __Examples__

    ---

    Code examples and common patterns

    [Examples →](examples/basic_task.md)

</div>

---

## Learning Paths

### Quick Start (15 minutes)

Perfect for getting started quickly:

1. **[Quick Start](getting-started/quick-start.md)** - Get running in 10 minutes
2. **[Basic Examples](examples/basic_task.md)** - Try examples
3. **[Core Concepts](getting-started/concepts.md)** - Understand basics

### Complete Beginner (1-2 hours)

Step-by-step learning path:

1. **[Getting Started Index](getting-started/index.md)** - Overview and learning paths
2. **[First Steps Tutorial](getting-started/tutorials/tutorial-01-first-steps.md)** - Complete beginner tutorial
3. **[Task Trees Tutorial](getting-started/tutorials/tutorial-02-task-trees.md)** - Build task trees
4. **[Dependencies Tutorial](getting-started/tutorials/tutorial-03-dependencies.md)** - Master dependencies
5. **[Core Concepts](getting-started/concepts.md)** - Deep dive
6. **[Basic Examples](examples/basic_task.md)** - Practice

### Professional Developer (2-4 hours)

For experienced developers:

1. **[Quick Start](getting-started/quick-start.md)** - Quick refresher
2. **[Task Orchestration](guides/task-orchestration.md)** - Master orchestration
3. **[Custom Tasks](guides/custom-tasks.md)** - Create executors
4. **[Best Practices](guides/best-practices.md)** - Learn patterns
5. **[API Reference](api/python.md)** - Complete reference

### Contributor (4+ hours)

For framework contributors:

1. **[Development Setup](development/setup.md)** - Set up environment
2. **[Architecture Overview](architecture/overview.md)** - Understand design
3. **[Contributing](development/contributing.md)** - Learn process

---

## Popular Guides

### For Users

- **[Task Orchestration](guides/task-orchestration.md)** - Complete guide to task orchestration, dependencies, and priorities
- **[Custom Tasks](guides/custom-tasks.md)** - Guide to creating custom tasks with ExecutableTask interface
- **[CLI](guides/cli.md)** - Complete CLI usage guide
- **[API Server](guides/api-server.md)** - API server setup and usage guide
- **[Best Practices](guides/best-practices.md)** - Best practices and recommendations
- **[FAQ](guides/faq.md)** - Common questions and troubleshooting

### For Developers

- **[Python API](api/python.md)** - Core Python library API reference (TaskManager, ExecutableTask, TaskTreeNode, etc.)
- **[HTTP API](api/http.md)** - A2A Protocol Server HTTP API reference
- **[Quick Reference](api/quick-reference.md)** - Cheat sheet with common snippets
- **[Contributing](development/contributing.md)** - Contribution guidelines and process

### Architecture & Design

- **[Architecture Overview](architecture/overview.md)** - System architecture and design principles
- **[Directory Structure](architecture/directory-structure.md)** - Directory structure and naming conventions
- **[Extension Registry Design](architecture/extension-registry-design.md)** - Extension registry design (Protocol-based architecture)
- **[Configuration](architecture/configuration.md)** - Database table configuration

### Protocol

- **[Protocol Overview](protocol/index.md)** - AI Partner Up Flow Protocol specification
- **[Core Concepts](protocol/02-core-concepts.md)** - Fundamental protocol concepts
- **[Data Model](protocol/03-data-model.md)** - Task schema and data structures
- **[Execution Lifecycle](protocol/04-execution-lifecycle.md)** - State machine and execution flow

### Examples & Tutorials

- **[Basic Task](examples/basic_task.md)** - Basic task examples and common patterns
- **[Task Tree](examples/task-tree.md)** - Task tree examples with dependencies and priorities
- **[Real World Examples](examples/real-world.md)** - Real-world use cases and examples
- **[First Steps Tutorial](getting-started/tutorials/tutorial-01-first-steps.md)** - Complete beginner tutorial

---

## Quick Navigation

### By Task

**I want to...**

- **Get started quickly** → [Quick Start](getting-started/quick-start.md)
- **Understand concepts** → [Core Concepts](getting-started/concepts.md)
- **Create a custom executor** → [Custom Tasks Guide](guides/custom-tasks.md)
- **Build complex workflows** → [Task Orchestration Guide](guides/task-orchestration.md)
- **See examples** → [Examples](examples/basic_task.md)
- **Find API reference** → [Python API](api/python.md) or [Quick Reference](api/quick-reference.md)
- **Troubleshoot issues** → [FAQ](guides/faq.md)
- **Learn best practices** → [Best Practices](guides/best-practices.md)
- **Set up development** → [Development Setup](development/setup.md)
- **Understand architecture** → [Architecture Overview](architecture/overview.md)
- **Read the protocol** → [Protocol Specification](protocol/index.md)

### By Role

**I am a...**

- **New User** → Start with [Getting Started](getting-started/index.md)
- **Developer** → Check [Guides](guides/task-orchestration.md) and [API Reference](api/python.md)
- **Contributor** → See [Development](development/setup.md) section
- **Architect** → Review [Architecture](architecture/overview.md) documentation

---

## Additional Resources

- [GitHub Repository](https://github.com/aipartnerup/apflow) - Source code and issues
- [PyPI Package](https://pypi.org/project/apflow/) - Install from PyPI
- [Protocol Documentation](protocol/index.md) - AI Partner Up Flow Protocol specification
- [GitHub Issues](https://github.com/aipartnerup/apflow/issues) - Report bugs and request features
- [GitHub Discussions](https://github.com/aipartnerup/apflow/discussions) - Ask questions and share ideas

---

## Need Help?

Check out our [FAQ](guides/faq.md) for common questions and answers, or [start a discussion](https://github.com/aipartnerup/apflow/discussions) on GitHub.

---

**Ready to start?** → [Getting Started →](getting-started/index.md) or [Quick Start →](getting-started/quick-start.md)

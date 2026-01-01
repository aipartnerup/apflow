# Getting Started with apflow

Welcome to apflow! This guide will help you get started quickly, whether you're new to task orchestration or an experienced developer.

## Problems We Solve

You might be struggling with these common challenges:

- **Managing Complex Task Dependencies is Painful**: Manually tracking which tasks depend on others, ensuring proper execution order, and handling failures across complex workflows becomes a nightmare. You end up writing custom coordination code, dealing with race conditions, and spending weeks debugging dependency issues.

- **Integrating Multiple Execution Methods Creates Complexity**: You need to call HTTP APIs, execute SSH commands, run Docker containers, communicate via gRPC, and coordinate AI agents—but each requires different libraries, error handling, and integration patterns. Managing multiple orchestration systems becomes overwhelming.

- **Combining Traditional Tasks with AI Agents is Challenging**: You want to add AI capabilities to existing workflows, but most solutions force you to choose: either traditional task execution OR AI agents. You're stuck with all-or-nothing decisions, requiring complete rewrites to introduce AI gradually.

- **State Persistence and Recovery are Hard to Implement**: When workflows fail or get interrupted, you lose progress. Implementing retry logic, checkpointing, and state recovery requires significant custom development. You spend more time building infrastructure than solving business problems.

- **Real-time Monitoring Requires Custom Solutions**: You need to show progress to users, but building real-time monitoring with polling, WebSocket connections, or custom streaming solutions takes weeks. Your users wait without feedback, and you struggle to debug long-running workflows.

## Why apflow?

Here's what makes apflow the right choice for your orchestration needs:

- **One Unified Interface for Everything**: Stop managing multiple orchestration systems. One framework handles traditional tasks, HTTP/REST APIs, SSH commands, Docker containers, gRPC services, WebSocket communication, MCP tools, and AI agents—all through the same ExecutableTask interface. No more switching between different libraries and patterns.

- **Start Simple, Scale Up Gradually**: Begin with a lightweight, dependency-free core that handles traditional task orchestration. Add AI capabilities, A2A server, CLI tools, or PostgreSQL storage only when you need them. Unlike frameworks that force you to install everything upfront, apflow lets you start minimal and grow incrementally. This modular approach means you only pay for what you use and keep deployments lean.

- **Language-Agnostic Protocol**: Built on the AI Partner Up Flow Protocol (APFlow Protocol), ensuring interoperability across Python, Go, Rust, JavaScript, and more. Different language implementations work together seamlessly. The protocol provides complete specifications for building compatible libraries, making it future-proof and vendor-independent.

- **Production-Ready from Day One**: Built-in storage (DuckDB or PostgreSQL), real-time streaming, automatic retries, state persistence, and comprehensive monitoring—all included. No need to build these from scratch. The framework handles error recovery, checkpointing, and workflow resumption automatically. Focus on your business logic, not infrastructure.

- **Extensive Executor Ecosystem**: Choose from HTTP/REST APIs (with authentication), SSH remote execution, Docker containers, gRPC services, WebSocket communication, MCP integration, and LLM-based task tree generation. All executors support the same interface, making it easy to mix and match execution methods in a single workflow.

## What Happens When You Use apflow?

Here's the real impact of using our framework:

- **You Build Workflows Faster**: Before: Weeks of custom coordination code, dependency management, and error handling. You spend more time building infrastructure than solving business problems. After: Define task trees with dependencies in days, not weeks. The framework handles coordination, error recovery, and state management automatically. Focus on what matters—your business logic.

- **You Integrate Everything Easily**: Before: Multiple orchestration systems for HTTP APIs, SSH commands, Docker containers, and AI agents. Each requires different libraries, patterns, and error handling. After: One unified interface for all execution methods. Mix HTTP calls, SSH commands, Docker containers, gRPC services, WebSocket, MCP tools, and AI agents in a single workflow seamlessly.

- **You Add AI Gradually**: Before: All-or-nothing decisions. To add AI capabilities, you must rewrite entire workflows or choose between traditional tasks OR AI agents. After: Start with traditional task orchestration, then add AI agents incrementally when ready. No rewrites needed. The framework bridges traditional and AI execution seamlessly.

- **You Monitor in Real-Time**: Before: Weeks building custom polling, WebSocket connections, or streaming solutions. Users wait without feedback, and debugging long-running workflows is painful. After: Built-in real-time streaming via A2A Protocol. Monitor progress, task status, and intermediate results instantly. Users see updates in real-time, and you debug workflows easily.

- **You Recover from Failures Automatically**: Before: Manual recovery logic, lost progress on interruptions, and weeks implementing retry strategies and checkpointing. After: Automatic retries with exponential backoff, state persistence, and workflow resumption from checkpoints. Failed tasks recover automatically, and interrupted workflows resume seamlessly.

- **You Scale with Confidence**: Before: Worrying about resource usage, dependency management at scale, and coordinating hundreds of concurrent workflows manually. After: Production-ready from day one. Built-in storage, streaming architecture, and efficient resource management. Handle hundreds of concurrent workflows with confidence.

## What is apflow?

**apflow** is a Python framework for orchestrating and executing tasks. Think of it as a conductor for your application's tasks - it manages when tasks run, how they depend on each other, and ensures everything executes in the right order.

### Key Benefits

- **Simple Task Management**: Create, organize, and execute tasks with ease
- **Dependency Handling**: Tasks automatically wait for their dependencies to complete
- **Flexible Execution**: Support for custom tasks, LLM agents (CrewAI), and more
- **Production Ready**: Built-in storage, streaming, and API support
- **Extensible**: Easy to add custom task types and integrations

## Quick Navigation

### 🚀 New to apflow?

Start here if you're completely new:

1. **[Core Concepts](concepts.md)** - Learn the fundamental ideas (5 min read)
2. **[Quick Start Guide](quick-start.md)** - Build your first task (10 min)
3. **[First Steps Tutorial](tutorials/tutorial-01-first-steps.md)** - Complete beginner tutorial

### 📚 Already familiar?

Jump to what you need:

- **[Examples](examples.md)** - Copy-paste ready examples
- **[Task Orchestration Guide](../guides/task-orchestration.md)** - Deep dive into task management
- **[Custom Tasks Guide](../guides/custom-tasks.md)** - Create your own task types
- **[API Reference](../api/python.md)** - Complete API documentation

### 🎯 What do you want to do?

**I want to...**

- **Execute simple tasks** → [Quick Start](quick-start.md)
- **Build complex workflows** → [Task Orchestration Guide](../guides/task-orchestration.md)
- **Create custom task types** → [Custom Tasks Guide](../guides/custom-tasks.md)
- **Use LLM agents** → [CrewAI Examples](../examples/basic_task.md#example-4-using-crewai-llm-tasks)
- **Understand the architecture** → [Architecture Overview](../architecture/overview.md)

## Core Concepts at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                    Your Application                      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              apflow Framework                   │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Task 1     │  │   Task 2     │  │   Task 3     │ │
│  │  (Fetch)    │  │  (Process)   │  │  (Save)      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                  │         │
│         └─────────────────┼──────────────────┘         │
│                           │                             │
│                    Dependencies                          │
│              (Task 2 waits for Task 1)                  │
│                                                          │
│              TaskManager orchestrates                   │
│              execution order automatically              │
└─────────────────────────────────────────────────────────┘
```

### The Basics

- **Task**: A unit of work (e.g., "fetch data", "process file", "send email")
- **Task Tree**: A hierarchical structure organizing related tasks
- **Dependencies**: Relationships that control execution order
- **Executor**: The code that actually runs a task
- **TaskManager**: The orchestrator that manages task execution

## Installation

Choose your installation based on what you need:

```bash
# Minimal: Core orchestration only
pip install apflow

# With LLM support (CrewAI)
pip install apflow[crewai]

# With API server
pip install apflow[a2a]

# With CLI tools
pip install apflow[cli]

# Everything
pip install apflow[all]
```

See [Installation Guide](installation.md) for details.

## Your First 5 Minutes

Here's the fastest way to see apflow in action:

```python
from apflow import TaskManager, TaskTreeNode, create_session
import asyncio

async def main():
    # 1. Create a database session
    db = create_session()
    
    # 2. Create a task manager
    task_manager = TaskManager(db)
    
    # 3. Create a simple task
    task = await task_manager.task_repository.create_task(
        name="system_info_executor",  # Built-in executor
        user_id="user123",
        inputs={"resource": "cpu"}
    )
    
    # 4. Build and execute
    task_tree = TaskTreeNode(task)
    await task_manager.distribute_task_tree(task_tree)
    
    # 5. Check the result
    result = await task_manager.task_repository.get_task_by_id(task.id)
    print(f"Task completed: {result.status}")
    print(f"Result: {result.result}")

asyncio.run(main())
```

**That's it!** You just executed your first task. 

👉 **Next**: Read [Core Concepts](concepts.md) to understand what just happened, or jump to [Quick Start](quick-start.md) for a more detailed walkthrough.

## Learning Paths

### Path 1: Quick Learner (30 minutes)
1. [Core Concepts](concepts.md) (5 min)
2. [Quick Start](quick-start.md) (10 min)
3. [Basic Examples](../examples/basic_task.md) (15 min)

### Path 2: Comprehensive (2 hours)
1. [Core Concepts](concepts.md)
2. [Quick Start](quick-start.md)
3. [First Steps Tutorial](tutorials/tutorial-01-first-steps.md)
4. [Task Trees Tutorial](tutorials/tutorial-02-task-trees.md)
5. [Dependencies Tutorial](tutorials/tutorial-03-dependencies.md)

### Path 3: Professional Developer (4+ hours)
1. Complete Path 2
2. [Custom Tasks Guide](../guides/custom-tasks.md)
3. [Best Practices](../guides/best-practices.md)
4. [API Reference](../api/python.md)
5. [Advanced Topics](../advanced/extending.md)

## Common Questions

**Q: Do I need to know task orchestration?**  
A: No! Start with [Core Concepts](concepts.md) - we explain everything from scratch.

**Q: Can I use this without LLM/AI?**  
A: Yes! The core framework has no AI dependencies. LLM support is optional via `[crewai]`.

**Q: Is this production-ready?**  
A: Yes! It includes storage, error handling, streaming, and API support out of the box.

**Q: How is this different from Celery/Airflow?**  
A: apflow focuses on simplicity and flexibility. It's designed for both simple workflows and complex AI agent orchestration.

## Next Steps

- **New to task orchestration?** → Start with [Core Concepts](concepts.md)
- **Ready to code?** → Jump to [Quick Start](quick-start.md)
- **Want examples?** → Check [Examples](examples.md)
- **Need help?** → See [FAQ](../guides/faq.md)

---

**Ready to begin?** → [Start with Core Concepts →](concepts.md)


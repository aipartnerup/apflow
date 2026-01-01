# Architecture Diagrams

This document contains visual diagrams that illustrate the architecture, execution flows, and key processes of apflow.

## Table of Contents

1. [Task Execution Sequence Diagram](#task-execution-sequence-diagram)
2. [Task Orchestration Flow Diagram](#task-orchestration-flow-diagram)
3. [A2A Protocol Interaction Sequence Diagram](#a2a-protocol-interaction-sequence-diagram)
4. [Task Lifecycle State Diagram](#task-lifecycle-state-diagram)
5. [Dependency Resolution Flow Diagram](#dependency-resolution-flow-diagram)

## Task Execution Sequence Diagram

This diagram shows the complete flow from API request to task completion, including all major components involved in task execution.

```mermaid
sequenceDiagram
    participant Client
    participant APIServer as A2A Protocol Server
    participant AgentExecutor as AgentExecutor
    participant TaskRoutes as TaskRoutes
    participant TaskExecutor as TaskExecutor
    participant TaskManager as TaskManager
    participant Executor as Executor (CrewaiExecutor/HTTP/etc)
    participant Storage as Storage (Database)
    
    Client->>APIServer: POST /tasks.execute
    APIServer->>AgentExecutor: execute(context, event_queue)
    AgentExecutor->>TaskRoutes: handle_task_execute(params)
    TaskRoutes->>TaskExecutor: execute_task_tree(task_tree)
    
    TaskExecutor->>TaskExecutor: Mark tasks for re-execution
    TaskExecutor->>TaskManager: Create TaskManager instance
    TaskExecutor->>TaskManager: distribute_task_tree(task_tree)
    
    loop For each task in tree
        TaskManager->>TaskManager: Check dependencies
        TaskManager->>TaskManager: Check priority
        alt Dependencies satisfied
            TaskManager->>Storage: Update task status (in_progress)
            TaskManager->>Executor: Execute task
            Executor-->>TaskManager: Return result
            TaskManager->>Storage: Update task status (completed)
            TaskManager->>TaskManager: Check dependent tasks
        else Dependencies not satisfied
            TaskManager->>TaskManager: Wait for dependencies
        end
    end
    
    TaskManager-->>TaskExecutor: All tasks completed
    TaskExecutor-->>TaskRoutes: Return result
    TaskRoutes-->>AgentExecutor: Return response
    AgentExecutor-->>APIServer: Return result
    APIServer-->>Client: JSON Response / SSE Stream
```

## Task Orchestration Flow Diagram

This diagram illustrates how TaskManager orchestrates task execution, including dependency resolution, priority scheduling, and state management.

```mermaid
flowchart TD
    Start([Start: Task Tree Execution]) --> LoadTree[Load Task Tree]
    LoadTree --> MarkReexec[Mark Tasks for Re-execution]
    MarkReexec --> InitManager[Initialize TaskManager]
    InitManager --> ProcessRoot[Process Root Task]
    
    ProcessRoot --> CheckStatus{Task Status?}
    CheckStatus -->|pending| CheckDeps[Check Dependencies]
    CheckStatus -->|failed| CheckDeps
    CheckStatus -->|completed| CheckReexec{Marked for<br/>Re-execution?}
    CheckStatus -->|in_progress| CheckReexec
    
    CheckReexec -->|Yes| CheckDeps
    CheckReexec -->|No| SkipTask[Skip Task]
    
    CheckDeps --> AllDepsSatisfied{All Dependencies<br/>Satisfied?}
    AllDepsSatisfied -->|No| WaitDeps[Wait for Dependencies]
    WaitDeps --> CheckDeps
    
    AllDepsSatisfied -->|Yes| CheckPriority[Check Priority]
    CheckPriority --> ReadyQueue[Add to Ready Queue]
    ReadyQueue --> SortByPriority[Sort by Priority]
    SortByPriority --> ExecuteTask[Execute Task]
    
    ExecuteTask --> UpdateStatus1[Update Status: in_progress]
    UpdateStatus1 --> RunExecutor[Run Executor]
    RunExecutor --> ExecSuccess{Execution<br/>Successful?}
    
    ExecSuccess -->|Yes| UpdateStatus2[Update Status: completed]
    ExecSuccess -->|No| UpdateStatus3[Update Status: failed]
    
    UpdateStatus2 --> MergeResults[Merge Dependency Results]
    UpdateStatus3 --> MergeResults
    MergeResults --> UpdateStorage[Update Storage]
    UpdateStorage --> CheckDependents[Check Dependent Tasks]
    
    CheckDependents --> MoreTasks{More Tasks<br/>in Tree?}
    MoreTasks -->|Yes| ProcessRoot
    MoreTasks -->|No| AllComplete{All Tasks<br/>Complete?}
    
    SkipTask --> MoreTasks
    AllComplete -->|Yes| End([End: Execution Complete])
    AllComplete -->|No| WaitDeps
```

## A2A Protocol Interaction Sequence Diagram

This diagram shows how the A2A Protocol Server handles requests, from client request to task execution and response.

```mermaid
sequenceDiagram
    participant Client
    participant A2AServer as A2A Protocol Server
    participant AgentExecutor as AgentExecutor
    participant TaskRoutes as TaskRoutes
    participant TaskExecutor as TaskExecutor
    participant TaskManager as TaskManager
    participant EventQueue as EventQueue (SSE/WebSocket)
    
    Client->>A2AServer: HTTP POST / (JSON-RPC)
    Note over Client,A2AServer: Request: {"method": "tasks.execute", "params": {...}}
    
    A2AServer->>AgentExecutor: execute(context, event_queue)
    Note over A2AServer,AgentExecutor: RequestContext contains method, params, metadata
    
    AgentExecutor->>AgentExecutor: Extract method from context
    alt Method is "tasks.execute"
        AgentExecutor->>AgentExecutor: Check streaming mode
        alt Streaming Mode
            AgentExecutor->>TaskRoutes: handle_task_execute(params, streaming=True)
            TaskRoutes->>TaskExecutor: execute_task_tree(task_tree, use_streaming=True)
            TaskExecutor->>TaskManager: distribute_task_tree_with_streaming()
            TaskManager->>EventQueue: Stream progress updates
            EventQueue-->>Client: SSE Events (real-time)
            Note over EventQueue,Client: Multiple events: status, progress, result
        else Simple Mode
            AgentExecutor->>TaskRoutes: handle_task_execute(params, streaming=False)
            TaskRoutes->>TaskExecutor: execute_task_tree(task_tree)
            TaskExecutor->>TaskManager: distribute_task_tree()
            TaskManager-->>TaskExecutor: Execution complete
            TaskExecutor-->>TaskRoutes: Return result
            TaskRoutes-->>AgentExecutor: Return response
            AgentExecutor-->>A2AServer: Return Task object
            A2AServer-->>Client: JSON Response
        end
    else Other Methods (tasks.create, tasks.get, etc.)
        AgentExecutor->>TaskRoutes: Route to appropriate handler
        TaskRoutes-->>AgentExecutor: Return result
        AgentExecutor-->>A2AServer: Return response
        A2AServer-->>Client: JSON Response
    end
```

## Task Lifecycle State Diagram

This diagram shows all possible state transitions for a task during its lifecycle.

```mermaid
stateDiagram-v2
    [*] --> pending: Task Created
    
    pending --> in_progress: Execution Started
    pending --> cancelled: User Cancellation
    
    in_progress --> completed: Execution Successful
    in_progress --> failed: Execution Failed
    in_progress --> cancelled: User Cancellation
    
    completed --> [*]: Task Finished
    failed --> [*]: Task Finished
    cancelled --> [*]: Task Finished
    
    note right of pending
        Initial state after task creation.
        Waiting for dependencies to be satisfied.
    end note
    
    note right of in_progress
        Task is currently executing.
        Executor is running the task logic.
    end note
    
    note right of completed
        Task finished successfully.
        Result is available in task.result.
    end note
    
    note right of failed
        Task execution failed.
        Error details in task.error.
    end note
    
    note right of cancelled
        Task was cancelled before completion.
        Can be cancelled from any active state.
    end note
```

## Dependency Resolution Flow Diagram

This diagram illustrates how the system resolves task dependencies, waits for dependencies to complete, and merges dependency results into task inputs.

```mermaid
flowchart TD
    Start([Task Ready to Execute]) --> GetDeps[Get Task Dependencies]
    GetDeps --> HasDeps{Has<br/>Dependencies?}
    
    HasDeps -->|No| ExecuteTask[Execute Task Immediately]
    HasDeps -->|Yes| CheckDepStatus[Check Each Dependency Status]
    
    CheckDepStatus --> AllRequiredComplete{All Required<br/>Dependencies<br/>Complete?}
    
    AllRequiredComplete -->|No| CheckOptional{Has Optional<br/>Dependencies?}
    AllRequiredComplete -->|Yes| MergeResults[Merge Dependency Results]
    
    CheckOptional -->|Yes| CheckOptionalStatus{Optional Dependencies<br/>Complete or Failed?}
    CheckOptional -->|No| WaitForDeps[Wait for Required Dependencies]
    
    CheckOptionalStatus -->|Complete| MergeResults
    CheckOptionalStatus -->|Failed| MergeResults
    CheckOptionalStatus -->|In Progress| WaitForDeps
    
    WaitForDeps --> CheckDepStatus
    
    MergeResults --> CollectResults[Collect Results from Dependencies]
    CollectResults --> MergeWithInputs[Merge with Task Inputs]
    
    MergeWithInputs --> ExecuteTask
    
    ExecuteTask --> TaskComplete([Task Execution Complete])
    
    style Start fill:#e1f5ff
    style ExecuteTask fill:#c8e6c9
    style TaskComplete fill:#c8e6c9
    style WaitForDeps fill:#fff9c4
    style MergeResults fill:#e1bee7
```

## Component Interaction Overview

This diagram provides a high-level view of how major components interact in the system.

```mermaid
flowchart LR
    subgraph External["External Interface"]
        Client[Client Applications]
        CLI[CLI Tools]
    end
    
    subgraph API["API Layer"]
        A2A[A2A Protocol Server]
        Routes[TaskRoutes]
    end
    
    subgraph Core["Core Orchestration"]
        Executor[TaskExecutor]
        Manager[TaskManager]
    end
    
    subgraph Execution["Execution Layer"]
        CrewAI[CrewaiExecutor]
        HTTP[HTTPExecutor]
        Custom[Custom Executors]
    end
    
    subgraph Support["Support Layer"]
        DB[(Database)]
        Stream[Streaming]
    end
    
    Client --> A2A
    CLI --> Executor
    A2A --> Routes
    Routes --> Executor
    Executor --> Manager
    Manager --> CrewAI
    Manager --> HTTP
    Manager --> Custom
    Manager --> DB
    Manager --> Stream
    Stream --> A2A
    
    style External fill:#e1f5ff
    style API fill:#fff4e1
    style Core fill:#e8f5e9
    style Execution fill:#f3e5f5
    style Support fill:#e0f2f1
```

## Notes on Diagram Usage

These diagrams are designed to:

1. **Help developers understand** the system architecture and data flow
2. **Guide implementation** by showing the sequence of operations
3. **Aid debugging** by visualizing the execution path
4. **Support documentation** for new contributors

All diagrams use Mermaid syntax and should render correctly in MkDocs when using:
- `mkdocs-mermaid2-plugin`, or
- Material for MkDocs theme with Mermaid support

For more details on specific components, see:
- [Architecture Overview](overview.md) - Detailed component descriptions
- [Task Orchestration Guide](../guides/task-orchestration.md) - Task orchestration patterns
- [Core Concepts](../getting-started/concepts.md) - Fundamental concepts


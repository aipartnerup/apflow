"""
Built-in Executors Example

This example demonstrates using apflow's built-in executors:
1. REST executor for HTTP API calls
2. No custom code needed

Run: python built_in_executors.py
"""

from apflow import TaskBuilder, execute_tasks


def rest_api_example():
    """Example using REST executor to call GitHub API."""
    print("=== REST Executor Example ===")

    # Create task using built-in rest_executor
    task = (
        TaskBuilder("fetch_github_user", "rest_executor")
        .with_inputs({"url": "https://api.github.com/users/octocat", "method": "GET"})
        .build()
    )

    # Execute task
    result = execute_tasks([task])

    # Display results
    json_data = result.get("json", {})
    print(f"GitHub User: {json_data.get('login', 'N/A')}")
    print(f"Name: {json_data.get('name', 'N/A')}")
    print(f"Public Repos: {json_data.get('public_repos', 'N/A')}")
    print(f"Followers: {json_data.get('followers', 'N/A')}")


def rest_api_with_auth_example():
    """Example using REST executor with authentication headers."""
    print("\n=== REST Executor with Authentication Example ===")

    # Create task with authentication headers
    task = (
        TaskBuilder("fetch_api_data", "rest_executor")
        .with_inputs(
            {
                "url": "https://api.example.com/data",
                "method": "GET",
                "headers": {
                    "Authorization": "Bearer YOUR_TOKEN_HERE",
                    "Content-Type": "application/json",
                },
            }
        )
        .build()
    )

    print("Task created (would execute with valid token)")
    print(f"Task ID: {task.id}")
    print(f"URL: https://api.example.com/data")


def rest_api_post_example():
    """Example using REST executor to POST data."""
    print("\n=== REST Executor POST Example ===")

    # Create task to POST data
    task = (
        TaskBuilder("create_resource", "rest_executor")
        .with_inputs(
            {
                "url": "https://jsonplaceholder.typicode.com/posts",
                "method": "POST",
                "json": {"title": "Test Post", "body": "This is a test", "userId": 1},
            }
        )
        .build()
    )

    # Execute task
    result = execute_tasks([task])

    # Display results
    json_data = result.get("json", {})
    print(f"Created resource ID: {json_data.get('id', 'N/A')}")
    print(f"Title: {json_data.get('title', 'N/A')}")


if __name__ == "__main__":
    # Run REST API examples
    rest_api_example()
    rest_api_with_auth_example()
    rest_api_post_example()

    print("\n=== Other Built-in Executors ===")
    print("apflow includes these executors:")
    print("- rest_executor: HTTP/REST API calls")
    print("- ssh_executor: Execute commands on remote servers (requires apflow[ssh])")
    print("- docker_executor: Run containers (requires apflow[docker])")
    print("- grpc_executor: gRPC service calls (requires apflow[grpc])")
    print("- websocket_executor: WebSocket communication")
    print("- crewai_executor: Multi-agent AI workflows (requires apflow[crewai])")
    print("- litellm_executor: LLM API calls (requires apflow[llm])")
    print("- mcp_executor: MCP tool calls (requires apflow[mcp])")
    print("\nSee docs/guides/executor-selection.md for details")

"""
REST Executor Examples

Demonstrates various REST API interaction patterns:
1. Simple GET requests
2. POST with JSON data
3. Authentication with headers
4. Query parameters
5. Error handling

Run: python rest_executor_example.py
"""

from apflow import TaskBuilder, execute_tasks


def simple_get_request():
    """Simple GET request to fetch data."""
    print("=== Simple GET Request ===")

    task = (
        TaskBuilder("fetch_weather", "rest_executor")
        .with_inputs(
            {
                "url": "https://api.github.com/users/octocat",
                "method": "GET",
            }
        )
        .build()
    )

    result = execute_tasks([task])
    print(f"Status: {result.get('status_code')}")
    print(f"Response: {result.get('json', {}).get('login')}")


def post_with_json():
    """POST request with JSON data."""
    print("\n=== POST with JSON Data ===")

    task = (
        TaskBuilder("create_post", "rest_executor")
        .with_inputs(
            {
                "url": "https://jsonplaceholder.typicode.com/posts",
                "method": "POST",
                "json": {
                    "title": "My New Post",
                    "body": "This is the content of my post",
                    "userId": 1,
                },
            }
        )
        .build()
    )

    result = execute_tasks([task])
    print(f"Created ID: {result.get('json', {}).get('id')}")
    print(f"Status: {result.get('status_code')}")


def request_with_headers():
    """Request with custom headers for authentication."""
    print("\n=== Request with Authentication Headers ===")

    task = (
        TaskBuilder("authenticated_request", "rest_executor")
        .with_inputs(
            {
                "url": "https://api.example.com/protected",
                "method": "GET",
                "headers": {
                    "Authorization": "Bearer YOUR_API_TOKEN",
                    "User-Agent": "apflow-client/1.0",
                    "Accept": "application/json",
                },
            }
        )
        .build()
    )

    print(f"Task created: {task.id}")
    print("Note: Replace YOUR_API_TOKEN with actual token to execute")


def request_with_params():
    """Request with query parameters."""
    print("\n=== Request with Query Parameters ===")

    task = (
        TaskBuilder("search_repos", "rest_executor")
        .with_inputs(
            {
                "url": "https://api.github.com/search/repositories",
                "method": "GET",
                "params": {"q": "language:python", "sort": "stars", "order": "desc", "per_page": 5},
            }
        )
        .build()
    )

    result = execute_tasks([task])
    items = result.get("json", {}).get("items", [])
    print(f"Found {len(items)} repositories")
    for i, repo in enumerate(items[:3], 1):
        print(f"{i}. {repo.get('full_name')} - ⭐ {repo.get('stargazers_count')}")


def request_with_timeout():
    """Request with custom timeout."""
    print("\n=== Request with Timeout ===")

    task = (
        TaskBuilder("fetch_with_timeout", "rest_executor")
        .with_inputs(
            {
                "url": "https://api.github.com/users/octocat",
                "method": "GET",
                "timeout": 5,  # 5 second timeout
            }
        )
        .build()
    )

    result = execute_tasks([task])
    print(f"Request completed in time: {result.get('status_code')}")


def webhook_notification():
    """Send webhook notification (POST)."""
    print("\n=== Webhook Notification ===")

    task = (
        TaskBuilder("send_webhook", "rest_executor")
        .with_inputs(
            {
                "url": "https://webhook.site/your-unique-id",
                "method": "POST",
                "json": {
                    "event": "task_completed",
                    "task_id": "12345",
                    "status": "success",
                    "timestamp": "2024-01-01T12:00:00Z",
                },
                "headers": {"Content-Type": "application/json"},
            }
        )
        .build()
    )

    print(f"Webhook task created: {task.id}")
    print("Note: Visit webhook.site to create a test URL")


if __name__ == "__main__":
    simple_get_request()
    post_with_json()
    request_with_headers()
    request_with_params()
    request_with_timeout()
    webhook_notification()

    print("\n=== REST Executor Capabilities ===")
    print("✅ Supports: GET, POST, PUT, DELETE, PATCH")
    print("✅ Authentication: Headers, Bearer tokens, Basic auth")
    print("✅ Data formats: JSON, form data, multipart")
    print("✅ Query parameters and custom headers")
    print("✅ Timeout and retry configuration")
    print("✅ SSRF protection (blocks private IPs by default)")
    print("\nSee docs/guides/executor-selection.md for more details")

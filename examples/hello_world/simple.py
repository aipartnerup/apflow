"""
Simple Hello World Example

This is the most basic apflow example. It demonstrates:
1. Creating a custom executor
2. Building a task
3. Executing the task

Run: python simple.py
"""

from apflow import executor_register, TaskBuilder, execute_tasks
from apflow.extensions import BaseTask


# Define a simple executor
@executor_register()
class HelloWorld(BaseTask):
    """Simple hello world executor that greets a name."""

    id = "hello_world"
    name = "Hello World"
    description = "Greets a person by name"

    async def execute(self, inputs: dict) -> dict:
        name = inputs.get("name", "World")
        return {"message": f"Hello, {name}!"}


# Create and execute a task
if __name__ == "__main__":
    task = TaskBuilder("greet_alice", "hello_world").with_inputs({"name": "Alice"}).build()

    result = execute_tasks([task])
    print(result["message"])  # Output: Hello, Alice!

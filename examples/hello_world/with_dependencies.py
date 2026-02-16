"""
Task Dependencies Example

This example demonstrates:
1. Creating multiple tasks
2. Setting up task dependencies
3. Executing tasks in the correct order

Run: python with_dependencies.py
"""

from apflow import executor_register, TaskBuilder, execute_tasks
from apflow.extensions import BaseTask


# Define a data fetcher executor
@executor_register()
class DataFetcher(BaseTask):
    """Simulates fetching data from a source."""

    id = "data_fetcher"
    name = "Data Fetcher"
    description = "Fetches data from a source"

    async def execute(self, inputs: dict) -> dict:
        source = inputs.get("source", "unknown")
        print(f"Fetching data from {source}...")
        return {"data": f"data_from_{source}", "status": "success"}


# Define a data processor executor
@executor_register()
class DataProcessor(BaseTask):
    """Processes fetched data."""

    id = "data_processor"
    name = "Data Processor"
    description = "Processes data"

    async def execute(self, inputs: dict) -> dict:
        data = inputs.get("data", "")
        print(f"Processing data: {data}...")
        processed = data.upper()
        return {"processed_data": processed, "status": "processed"}


# Define a data saver executor
@executor_register()
class DataSaver(BaseTask):
    """Saves processed data."""

    id = "data_saver"
    name = "Data Saver"
    description = "Saves data to storage"

    async def execute(self, inputs: dict) -> dict:
        data = inputs.get("processed_data", "")
        destination = inputs.get("destination", "default")
        print(f"Saving data to {destination}: {data}")
        return {"saved": True, "location": destination}


if __name__ == "__main__":
    # Task 1: Fetch data
    fetch_task = TaskBuilder("fetch_data", "data_fetcher").with_inputs({"source": "api"}).build()

    # Task 2: Process data (depends on Task 1)
    process_task = (
        TaskBuilder("process_data", "data_processor")
        .with_inputs({"data": "{{fetch_data.data}}"})
        .with_dependencies([fetch_task.id])
        .build()
    )

    # Task 3: Save data (depends on Task 2)
    save_task = (
        TaskBuilder("save_data", "data_saver")
        .with_inputs(
            {"processed_data": "{{process_data.processed_data}}", "destination": "database"}
        )
        .with_dependencies([process_task.id])
        .build()
    )

    # Execute tasks in dependency order
    print("Executing task workflow with dependencies...\n")
    results = execute_tasks([fetch_task, process_task, save_task])

    print("\n=== Workflow Results ===")
    print(f"Fetch result: {results.get(fetch_task.id, {})}")
    print(f"Process result: {results.get(process_task.id, {})}")
    print(f"Save result: {results.get(save_task.id, {})}")

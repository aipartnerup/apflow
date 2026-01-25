import pytest
import os
from apflow.extensions.generate.generate_executor import GenerateExecutor

@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set in environment"
)
async def test_llm_generate_uses_scrape_executor():
    """
    Integration test: LLM should use scrape_executor for website analysis requirements.
    Requires a valid OPENAI_API_KEY in environment.
    """
    executor = GenerateExecutor()
    requirement = "Please analyze aipartnerup.com and provide an evaluation."
    user_id = "test_user"

    result = await executor.execute({
        "requirement": requirement,
        "user_id": user_id
    })

    assert "tasks" in result, f"LLM did not return tasks: {result}"
    tasks = result["tasks"]
    # Print for debug
    print("Generated tasks:", tasks)
    # At least one task should use scrape_executor
    assert any(
        t.get("schemas", {}).get("method") == "scrape_executor"
        for t in tasks
    ), "No task uses scrape_executor. Tasks: {}".format(tasks)
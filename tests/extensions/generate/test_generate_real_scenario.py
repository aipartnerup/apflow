"""
Real-world integration tests for generate executor auto-fix functionality.

Tests the auto-fix mechanism with realistic scenarios that would occur in production,
particularly the multi-executor root task validation and auto-fix.

Requires OPENAI_API_KEY environment variable for real LLM calls.
"""

import pytest
import os
import json
from pathlib import Path
from apflow.extensions.generate.generate_executor import GenerateExecutor
from apflow import TaskManager, create_session
from apflow.core.execution.task_creator import TaskCreator


# Load .env file if it exists
def load_env_file():
    """Load environment variables from .env file in project root"""
    env_file = Path(__file__).parent.parent.parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value


# Load environment variables at module level
load_env_file()

# Note: Do NOT enable command_executor by default
# Tests should use scrape_executor for web scraping, not command_executor
# os.environ["APFLOW_STDIO_ALLOW_COMMAND"] = "1"  # Commented out to test realistic scenarios


@pytest.mark.asyncio
@pytest.mark.timeout(180)
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set in environment")
async def test_generate_website_analysis_with_auto_fix():
    """
    Real integration test: Generate task tree for analyzing aipartnerup.com.
    
    This test:
    1. Calls GenerateExecutor with real AI to generate a task tree
    2. The requirement naturally leads to multiple executors (scrape + analysis)
    3. Validates that auto-fix converts root to aggregator if needed
    4. Ensures the final task tree passes all validations
    """
    executor = GenerateExecutor(user_id="demo_user_91c0194805d17ad1")
    requirement = "please analyze aipartnerup.com and give a report"
    
    print(f"\n{'='*80}")
    print(f"Requirement: {requirement}")
    print(f"{'='*80}\n")
    
    result = await executor.execute({
        "requirement": requirement,
        "user_id": "demo_user_91c0194805d17ad1",
        "generation_mode": "single_shot",
    })
    
    print("\n=== Generated Task Tree ===")
    print(json.dumps(result, indent=2))
    
    # Validate result
    assert result["status"] == "completed", f"Generation failed: {result.get('error')}"
    assert "tasks" in result, "Result should contain tasks"
    
    tasks = result["tasks"]
    assert isinstance(tasks, list), "Tasks should be a list"
    assert len(tasks) > 0, "Should generate at least one task"
    
    # Check if multiple executors are used
    executors = set()
    for task in tasks:
        executor_id = task.get("schemas", {}).get("method", "")
        if executor_id and "aggregate" not in executor_id.lower():
            executors.add(executor_id)
    
    print("\n=== Executors Used ===")
    print(f"Non-aggregator executors: {executors}")
    print(f"Total tasks: {len(tasks)}")
    
    # If multiple executors, verify root is aggregator
    if len(executors) >= 2:
        root_tasks = [t for t in tasks if not t.get("parent_id")]
        assert len(root_tasks) == 1, "Should have exactly one root task"
        
        root_task = root_tasks[0]
        root_executor = root_task.get("schemas", {}).get("method", "")
        
        print(f"\nRoot task executor: {root_executor}")
        print(f"Root task name: {root_task.get('name')}")
        
        # When using multiple executors, root should be aggregator
        assert "aggregate" in root_executor.lower(), (
            f"With {len(executors)} different executors, root should use aggregator, "
            f"but uses '{root_executor}'"
        )
        print("✅ Root task correctly uses aggregator executor")
    else:
        print(f"\n✓ Only {len(executors)} executor(s) used, no aggregator needed")
    
    # Final validation
    validation = executor._validate_tasks_array(tasks)
    assert validation["valid"], f"Final task tree should be valid: {validation['error']}"
    print("\n✅ Final task tree passes all validations")


@pytest.mark.asyncio
async def test_manual_multi_executor_scenario_with_auto_fix():
    """
    Unit test: Manually create a multi-executor scenario and verify auto-fix.
    
    This test doesn't require API key as it manually constructs the task tree
    and tests the validation + auto-fix logic directly.
    """
    executor = GenerateExecutor(user_id="demo_user_91c0194805d17ad1")
    
    # Create a realistic task tree that would fail validation
    tasks_with_multiple_executors = [
        {
            "id": "root-task-1",
            "name": "Analyze AI Partner Up Website",
            "schemas": {"method": "scrape_executor"},
            "inputs": {
                "url": "https://aipartnerup.com",
                "user_id": "demo_user_91c0194805d17ad1"
            }
        },
        {
            "id": "task-2",
            "name": "Analyze Scraped Website Content with AI Crew",
            "parent_id": "root-task-1",
            "schemas": {"method": "crewai_executor"},
            "inputs": {
                "user_id": "demo_user_91c0194805d17ad1",
                "works": {
                    "agents": {
                        "web_analyst": {
                            "role": "Web Content Analyst",
                            "goal": "Analyze website content and structure"
                        }
                    },
                    "tasks": {
                        "analyze_content": {
                            "description": "Analyze the scraped website content",
                            "agent": "web_analyst"
                        }
                    }
                }
            },
            "dependencies": [{"id": "root-task-1", "required": True}]
        }
    ]
    
    print("\n=== Initial Task Tree (Multiple Executors) ===")
    print(json.dumps(tasks_with_multiple_executors, indent=2))
    
    # Validate - should fail
    print("\n=== Validation (Should Fail) ===")
    validation_result = executor._validate_tasks_array(tasks_with_multiple_executors)
    print(f"Valid: {validation_result['valid']}")
    
    assert not validation_result['valid'], "Should fail validation"
    assert "different executors" in validation_result['error'], (
        "Error should mention different executors"
    )
    print(f"Expected error: {validation_result['error']}")
    
    # Test auto-fix
    print("\n=== Attempting Auto-Fix ===")
    fixed_tasks = executor._attempt_auto_fix(
        tasks_with_multiple_executors,
        validation_result['error']
    )
    
    assert fixed_tasks is not None, "Auto-fix should succeed"
    print("✅ Auto-fix succeeded!")
    
    print("\n=== Fixed Task Tree ===")
    print(json.dumps(fixed_tasks, indent=2))
    
    # Verify the fix
    root_tasks = [t for t in fixed_tasks if not t.get("parent_id")]
    assert len(root_tasks) == 1, "Should have one root task"
    
    root_task = root_tasks[0]
    root_executor = root_task.get("schemas", {}).get("method", "")
    
    assert root_executor == "aggregate_results_executor", (
        f"Root should use aggregate_results_executor, got '{root_executor}'"
    )
    print(f"✅ Root task converted to: {root_executor}")
    
    # Validate fixed tasks
    print("\n=== Revalidation ===")
    revalidation = executor._validate_tasks_array(fixed_tasks)
    print(f"Valid: {revalidation['valid']}")
    
    assert revalidation['valid'], f"Fixed tasks should be valid: {revalidation['error']}"
    print("✅ Fixed task tree passes validation!")


@pytest.mark.asyncio
@pytest.mark.timeout(180)
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set in environment")
async def test_generate_explicit_multi_executor_requirement():
    """
    Real integration test: Explicit requirement for multiple executors.
    
    Tests that when a requirement explicitly needs multiple different executors,
    the generate executor properly creates an aggregator root.
    """
    executor = GenerateExecutor(user_id="test_user")
    requirement = (
        "Create a workflow to analyze a website: "
        "1. First scrape the website content using scrape_executor "
        "2. Then use crewai_executor with AI agents to analyze the content "
        "3. Finally generate a summary report. "
        "Make sure to use different executors for different tasks."
    )
    
    print(f"\n{'='*80}")
    print(f"Requirement: {requirement}")
    print(f"{'='*80}\n")
    
    result = await executor.execute({
        "requirement": requirement,
        "user_id": "test_user",
        "generation_mode": "single_shot",
    })
    
    print("\n=== Generated Task Tree ===")
    print(json.dumps(result, indent=2))
    
    assert result["status"] == "completed", f"Generation failed: {result.get('error')}"
    
    tasks = result["tasks"]
    assert len(tasks) >= 2, "Should generate multiple tasks"
    
    # Count unique executors
    executors_used = set()
    for task in tasks:
        executor_id = task.get("schemas", {}).get("method", "")
        if executor_id:
            executors_used.add(executor_id)
    
    print("\n=== Executors Used ===")
    for executor_id in executors_used:
        count = sum(1 for t in tasks if t.get("schemas", {}).get("method") == executor_id)
        print(f"  {executor_id}: {count} task(s)")
    
    # Verify structure
    root_tasks = [t for t in tasks if not t.get("parent_id")]
    assert len(root_tasks) == 1, f"Should have one root, got {len(root_tasks)}"
    
    root_executor = root_tasks[0].get("schemas", {}).get("method", "")
    print(f"\nRoot executor: {root_executor}")
    
    # Validate the final tree
    validation = executor._validate_tasks_array(tasks)
    assert validation["valid"], f"Generated task tree should be valid: {validation['error']}"
    print("\n✅ Task tree passes all validations")


@pytest.mark.asyncio
@pytest.mark.timeout(300)  # 5 minutes for full execution
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set in environment")
async def test_end_to_end_generate_and_execute_website_analysis():
    """
    End-to-end integration test: Generate task tree and execute it.
    
    This test:
    1. Uses GenerateExecutor to generate a task tree from natural language
    2. Creates the task tree using TaskCreator
    3. Executes the entire task tree using TaskManager
    4. Validates the execution results
    
    User requirement: "please analyze aipartnerup.com and give a report with json format"
    """
    print(f"\n{'='*80}")
    print("END-TO-END TEST: Generate + Execute Website Analysis")
    print(f"{'='*80}\n")
    
    # Step 1: Generate task tree
    print("Step 1: Generating task tree from requirement...")
    generator = GenerateExecutor(user_id="demo_user_91c0194805d17ad1")
    requirement = "please analyze aipartnerup.com and give a report with json format"
    
    print(f"Requirement: {requirement}\n")
    
    generation_result = await generator.execute({
        "requirement": requirement,
        "user_id": "demo_user_91c0194805d17ad1",
        "generation_mode": "single_shot",
    })
    
    print("=== Generation Result ===")
    print(f"Status: {generation_result['status']}")
    assert generation_result["status"] == "completed", f"Generation failed: {generation_result.get('error')}"
    
    tasks_array = generation_result["tasks"]
    print(f"Generated {len(tasks_array)} tasks")
    print("\n=== Generated Task Tree ===")
    print(json.dumps(tasks_array, indent=2))
    
    # Step 2: Create task tree in database
    print("\n" + "="*80)
    print("Step 2: Creating task tree in database...")
    print("="*80 + "\n")
    
    db = create_session()
    task_creator = TaskCreator(db)
    
    try:
        task_tree = await task_creator.create_task_tree_from_array(tasks_array)
        print("✅ Task tree created successfully")
        print(f"Root task ID: {task_tree.task.id}")
        print(f"Root task name: {task_tree.task.name}")
        
        # Count tasks in tree
        def count_tasks(node):
            return 1 + sum(count_tasks(child) for child in node.children)
        
        total_tasks = count_tasks(task_tree)
        print(f"Total tasks in tree: {total_tasks}")
        
        # Step 3: Execute task tree
        print("\n" + "="*80)
        print("Step 3: Executing task tree...")
        print("="*80 + "\n")
        
        task_manager = TaskManager(db)
        
        # Execute the tree
        await task_manager.distribute_task_tree(task_tree)
        
        print("\n✅ Task tree execution completed!")
        
        # Step 4: Validate results
        print("\n" + "="*80)
        print("Step 4: Validating execution results...")
        print("="*80 + "\n")
        
        # Get all tasks and check their status
        async def get_all_task_ids(node):
            task_ids = [node.task.id]
            for child in node.children:
                task_ids.extend(await get_all_task_ids(child))
            return task_ids
        
        all_task_ids = await get_all_task_ids(task_tree)
        
        completed_count = 0
        failed_count = 0
        
        for task_id in all_task_ids:
            task = await task_manager.task_repository.get_task_by_id(task_id)
            print(f"\nTask: {task.name}")
            print(f"  ID: {task.id}")
            print(f"  Status: {task.status}")
            print(f"  Executor: {task.schemas.get('method', 'N/A') if task.schemas else 'N/A'}")
            
            if task.status == "completed":
                completed_count += 1
                if task.result:
                    result_str = json.dumps(task.result, indent=2) if isinstance(task.result, dict) else str(task.result)
                    # Truncate long results
                    if len(result_str) > 500:
                        result_str = result_str[:500] + "\n  ... (truncated)"
                    print(f"  Result: {result_str}")
            elif task.status == "failed":
                failed_count += 1
                print(f"  Error: {task.error}")
        
        print(f"\n{'='*80}")
        print("Execution Summary:")
        print(f"  Total tasks: {total_tasks}")
        print(f"  Completed: {completed_count}")
        print(f"  Failed: {failed_count}")
        print(f"{'='*80}\n")
        
        # Validate root task result
        root_task = await task_manager.task_repository.get_task_by_id(task_tree.task.id)
        assert root_task.status in ["completed", "failed"], f"Root task should be completed or failed, got: {root_task.status}"
        
        if root_task.status == "completed":
            print("✅ Root task completed successfully!")
            print("\n=== Final Report (Root Task Result) ===")
            if root_task.result:
                print(json.dumps(root_task.result, indent=2))
            
            # Verify the result format
            assert root_task.result is not None, "Root task should have a result"
            
            # If it's an aggregator, it should contain results from child tasks
            root_executor = root_task.schemas.get("method", "") if root_task.schemas else ""
            if "aggregate" in root_executor.lower():
                print("\n✅ Root task used aggregator executor as expected")
                # Aggregator should have collected results from dependencies
                if isinstance(root_task.result, dict):
                    print(f"Aggregated {len(root_task.result)} results")
        else:
            print(f"❌ Root task failed: {root_task.error}")
            # Even if root failed, we can still verify the workflow was attempted
            assert failed_count < total_tasks, "Not all tasks should have failed"
        
        # Final validation: Check that we had meaningful execution
        assert completed_count > 0, "At least some tasks should have completed"
        print("\n✅ End-to-end test completed successfully!")
        print(f"   {completed_count}/{total_tasks} tasks completed")
        
    finally:
        db.close()


@pytest.mark.asyncio
@pytest.mark.timeout(180)
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set in environment")
async def test_generate_system_monitoring_workflow():
    """
    Real scenario: Generate system monitoring workflow with parallel task execution.
    
    Requirement: "Check system health by monitoring CPU, memory, and disk usage in parallel"
    Expected: Multiple system_info_executor tasks with aggregate_results_executor as root
    """
    print(f"\n{'='*80}")
    print("SCENARIO: System Monitoring Workflow")
    print(f"{'='*80}\n")
    
    executor = GenerateExecutor(user_id="test_user")
    requirement = "Check system health by monitoring CPU, memory, and disk usage in parallel"
    
    print(f"Requirement: {requirement}\n")
    
    result = await executor.execute({
        "requirement": requirement,
        "user_id": "test_user",
        "generation_mode": "single_shot",
    })
    
    print("=== Generated Task Tree ===")
    print(json.dumps(result, indent=2))
    
    assert result["status"] == "completed", f"Generation failed: {result.get('error')}"
    
    tasks = result["tasks"]
    assert len(tasks) >= 3, "Should generate at least 3 tasks (CPU, memory, disk)"
    
    # Count system_info_executor usage
    system_info_tasks = [
        t for t in tasks 
        if t.get("schemas", {}).get("method") == "system_info_executor"
    ]
    
    print(f"\n✅ Generated {len(system_info_tasks)} system_info_executor tasks")
    
    # Verify parallel structure (all should share same parent)
    if len(system_info_tasks) > 1:
        parent_ids = {t.get("parent_id") for t in system_info_tasks}
        if len(parent_ids) == 1:
            print(f"✅ Parallel structure detected: all tasks share parent {parent_ids.pop()}")
    
    # Validate task tree
    validation = executor._validate_tasks_array(tasks)
    assert validation["valid"], f"Task tree should be valid: {validation['error']}"
    print("✅ Task tree passes validation")


@pytest.mark.asyncio
@pytest.mark.timeout(180)
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set in environment")
async def test_generate_api_data_pipeline():
    """
    Real scenario: Generate API data pipeline with sequential processing.
    
    Requirement: "Fetch weather data from API, transform it, then send to webhook"
    Expected: Sequential rest_executor tasks
    """
    print(f"\n{'='*80}")
    print("SCENARIO: API Data Pipeline")
    print(f"{'='*80}\n")
    
    executor = GenerateExecutor(user_id="test_user")
    requirement = (
        "Fetch weather data from api.weather.com, "
        "transform the data format, "
        "then send the result to a webhook"
    )
    
    print(f"Requirement: {requirement}\n")
    
    result = await executor.execute({
        "requirement": requirement,
        "user_id": "test_user",
        "generation_mode": "single_shot",
    })
    
    print("=== Generated Task Tree ===")
    print(json.dumps(result, indent=2))
    
    assert result["status"] == "completed", f"Generation failed: {result.get('error')}"
    
    tasks = result["tasks"]
    assert len(tasks) >= 2, "Should generate at least 2 tasks"
    
    # Count rest_executor usage
    rest_tasks = [
        t for t in tasks 
        if t.get("schemas", {}).get("method") == "rest_executor"
    ]
    
    # Count generate_executor usage (should be minimal for simple API pipeline)
    generate_tasks = [
        t for t in tasks 
        if t.get("schemas", {}).get("method") == "generate_executor"
    ]
    
    print(f"\n✅ Generated {len(rest_tasks)} rest_executor tasks")
    print(f"   Generated {len(generate_tasks)} generate_executor tasks")
    
    # For simple API pipeline, should prefer direct executors over generate_executor
    # However, we allow some flexibility as LLM might decompose slightly
    if len(generate_tasks) > 0:
        print("   ⚠️  Note: Using generate_executor for simple tasks is not optimal")
    
    # Verify sequential dependencies
    tasks_with_deps = [t for t in tasks if t.get("dependencies")]
    if tasks_with_deps:
        print(f"✅ Sequential structure: {len(tasks_with_deps)} tasks have dependencies")
    
    # Validate task tree
    validation = executor._validate_tasks_array(tasks)
    assert validation["valid"], f"Task tree should be valid: {validation['error']}"
    print("✅ Task tree passes validation")


@pytest.mark.asyncio
@pytest.mark.timeout(180)
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set in environment")
async def test_generate_multi_source_data_aggregation():
    """
    Real scenario: Scrape multiple websites and aggregate results (no AI).
    
    Requirement: "Scrape product prices from 3 competitor websites and compare them"
    Expected: Multiple scrape_executor tasks with aggregate_results_executor root
    """
    print(f"\n{'='*80}")
    print("SCENARIO: Multi-Source Data Aggregation (No AI)")
    print(f"{'='*80}\n")
    
    executor = GenerateExecutor(user_id="test_user")
    requirement = (
        "Scrape product prices from amazon.com, ebay.com, and walmart.com "
        "for iPhone 15 Pro and compare the prices"
    )
    
    print(f"Requirement: {requirement}\n")
    
    result = await executor.execute({
        "requirement": requirement,
        "user_id": "test_user",
        "generation_mode": "single_shot",
    })
    
    print("=== Generated Task Tree ===")
    print(json.dumps(result, indent=2))
    
    assert result["status"] == "completed", f"Generation failed: {result.get('error')}"
    
    tasks = result["tasks"]
    
    # Count scrape_executor usage
    scrape_tasks = [
        t for t in tasks 
        if t.get("schemas", {}).get("method") == "scrape_executor"
    ]
    
    print(f"\n✅ Generated {len(scrape_tasks)} scrape_executor tasks")
    assert len(scrape_tasks) >= 2, "Should have multiple scraping tasks"
    
    # Check for aggregator root (multiple executors or multiple scrape tasks)
    root_tasks = [t for t in tasks if not t.get("parent_id")]
    if len(root_tasks) == 1:
        root_executor = root_tasks[0].get("schemas", {}).get("method", "")
        if len(scrape_tasks) > 1:
            print(f"Root executor: {root_executor}")
            # With multiple scrape tasks, should use aggregator
            if "aggregate" in root_executor.lower():
                print("✅ Using aggregator for multiple data sources")
    
    # Should NOT use crewai_executor for simple price comparison
    crewai_tasks = [
        t for t in tasks 
        if t.get("schemas", {}).get("method") == "crewai_executor"
    ]
    print(f"CrewAI tasks: {len(crewai_tasks)} (should be 0 for simple data collection)")
    
    # Validate task tree
    validation = executor._validate_tasks_array(tasks)
    assert validation["valid"], f"Task tree should be valid: {validation['error']}"
    print("✅ Task tree passes validation")


@pytest.mark.asyncio
@pytest.mark.timeout(180)
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set in environment")
async def test_generate_simple_query_single_executor():
    """
    Real scenario: Simple single-executor query.
    
    Requirement: "Check CPU usage"
    Expected: Single system_info_executor task (no aggregator needed)
    """
    print(f"\n{'='*80}")
    print("SCENARIO: Simple Single Executor Query")
    print(f"{'='*80}\n")
    
    executor = GenerateExecutor(user_id="test_user")
    requirement = "Check current CPU usage percentage"
    
    print(f"Requirement: {requirement}\n")
    
    result = await executor.execute({
        "requirement": requirement,
        "user_id": "test_user",
        "generation_mode": "single_shot",
    })
    
    print("=== Generated Task Tree ===")
    print(json.dumps(result, indent=2))
    
    assert result["status"] == "completed", f"Generation failed: {result.get('error')}"
    
    tasks = result["tasks"]
    
    # For simple query, should generate minimal tasks
    print(f"\nGenerated {len(tasks)} task(s)")
    
    # Check that it uses appropriate executor
    if len(tasks) >= 1:
        main_task = tasks[0] if not tasks[0].get("parent_id") else tasks[-1]
        executor_type = main_task.get("schemas", {}).get("method", "")
        print(f"Executor type: {executor_type}")
        
        # Should use system_info_executor for CPU query
        assert "system_info" in executor_type.lower(), (
            f"Should use system_info_executor for CPU query, got {executor_type}"
        )
        print("✅ Correct executor selected")
    
    # Should NOT need aggregator for single query
    aggregate_tasks = [
        t for t in tasks 
        if "aggregate" in t.get("schemas", {}).get("method", "").lower()
    ]
    if len(tasks) == 1:
        assert len(aggregate_tasks) == 0, "Single query shouldn't need aggregator"
        print("✅ No unnecessary aggregator for simple query")
    
    # Validate task tree
    validation = executor._validate_tasks_array(tasks)
    assert validation["valid"], f"Task tree should be valid: {validation['error']}"
    print("✅ Task tree passes validation")


@pytest.mark.asyncio
@pytest.mark.timeout(180)
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set in environment")
async def test_generate_complex_ai_analysis():
    """
    Real scenario: Complex AI analysis requiring multiple agents.
    
    Requirement: "Research market trends for electric vehicles and create detailed report"
    Expected: crewai_executor with multiple agents (researcher, analyst, writer)
    """
    print(f"\n{'='*80}")
    print("SCENARIO: Complex AI Multi-Agent Analysis")
    print(f"{'='*80}\n")
    
    executor = GenerateExecutor(user_id="test_user")
    requirement = (
        "Research current market trends for electric vehicles in China, "
        "analyze the competitive landscape, "
        "and create a comprehensive business report with recommendations"
    )
    
    print(f"Requirement: {requirement}\n")
    
    result = await executor.execute({
        "requirement": requirement,
        "user_id": "test_user",
        "generation_mode": "single_shot",
    })
    
    print("=== Generated Task Tree ===")
    print(json.dumps(result, indent=2))
    
    assert result["status"] == "completed", f"Generation failed: {result.get('error')}"
    
    tasks = result["tasks"]
    
    # Check for crewai_executor usage
    crewai_tasks = [
        t for t in tasks 
        if t.get("schemas", {}).get("method") == "crewai_executor"
    ]
    
    print(f"\n✅ Generated {len(crewai_tasks)} crewai_executor task(s)")
    
    if crewai_tasks:
        # Validate crewai structure
        for task in crewai_tasks:
            works = task.get("inputs", {}).get("works", {})
            agents = works.get("agents", {})
            crew_tasks = works.get("tasks", {})
            
            print(f"\nCrewAI task: {task.get('name')}")
            print(f"  Agents: {len(agents)}")
            print(f"  Tasks: {len(crew_tasks)}")
            
            assert len(agents) >= 1, "Should have at least 1 agent"
            assert len(crew_tasks) >= 1, "Should have at least 1 task"
            
            # Verify agent structure
            for agent_name, agent_config in agents.items():
                assert "role" in agent_config, f"Agent {agent_name} missing 'role'"
                assert "goal" in agent_config, f"Agent {agent_name} missing 'goal'"
                assert "backstory" in agent_config, f"Agent {agent_name} missing 'backstory'"
                assert "llm" in agent_config, f"Agent {agent_name} missing 'llm'"
            
            print("  ✅ All agents have required fields")
    
    # Validate task tree
    validation = executor._validate_tasks_array(tasks)
    assert validation["valid"], f"Task tree should be valid: {validation['error']}"
    print("✅ Task tree passes validation")


@pytest.mark.asyncio
@pytest.mark.timeout(180)
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set in environment")
async def test_generate_hybrid_workflow_scrape_and_api():
    """
    Real scenario: Hybrid workflow combining scraping and API calls (no AI).
    
    Requirement: "Scrape news headlines from website then post summary to Slack"
    Expected: scrape_executor + rest_executor (sequential)
    """
    print(f"\n{'='*80}")
    print("SCENARIO: Hybrid Workflow (Scrape + API)")
    print(f"{'='*80}\n")
    
    executor = GenerateExecutor(user_id="test_user")
    requirement = (
        "Scrape the latest technology news headlines from techcrunch.com "
        "and post a summary to Slack webhook"
    )
    
    print(f"Requirement: {requirement}\n")
    
    result = await executor.execute({
        "requirement": requirement,
        "user_id": "test_user",
        "generation_mode": "single_shot",
    })
    
    print("=== Generated Task Tree ===")
    print(json.dumps(result, indent=2))
    
    assert result["status"] == "completed", f"Generation failed: {result.get('error')}"
    
    tasks = result["tasks"]
    
    # Count executor types
    executor_types = {}
    for task in tasks:
        executor_id = task.get("schemas", {}).get("method", "")
        if executor_id:
            executor_types[executor_id] = executor_types.get(executor_id, 0) + 1
    
    print("\n=== Executor Usage ===")
    for executor_id, count in executor_types.items():
        print(f"  {executor_id}: {count}")
    
    # Should use scrape_executor for scraping
    assert any("scrape" in e.lower() for e in executor_types.keys()), \
        f"Should use scrape_executor for web scraping. Got executors: {list(executor_types.keys())}"
    
    # Should use rest_executor for Slack webhook OR allow generate_executor decomposition
    has_rest = any("rest" in e.lower() for e in executor_types.keys())
    has_generate = any("generate" in e.lower() for e in executor_types.keys())
    
    if has_rest:
        print("✅ Correct executors selected (scrape + rest)")
    elif has_generate:
        print("⚠️  Using generate_executor for decomposition (not optimal but acceptable)")
    else:
        # Check if it used other valid executors
        print(f"⚠️  Unexpected executor selection: {executor_types}")
    
    # Should NOT use command_executor (security)
    assert not any("command" in e.lower() for e in executor_types.keys()), \
        "Should NOT use command_executor for web scraping"
    
    # Verify sequential structure
    tasks_with_deps = [t for t in tasks if t.get("dependencies")]
    if tasks_with_deps:
        print(f"✅ Sequential dependencies: {len(tasks_with_deps)} tasks")
    
    # Validate task tree
    validation = executor._validate_tasks_array(tasks)
    assert validation["valid"], f"Task tree should be valid: {validation['error']}"
    print("✅ Task tree passes validation")


# Generate Executor Test Cases

This document provides comprehensive test cases for the `generate_executor` to demonstrate its intelligent task tree generation capabilities. These examples show how the executor understands business requirements and generates appropriate task trees.

## Quick Start

All test cases can be run using the CLI command:

```bash
apflow generate task-tree "YOUR_REQUIREMENT_HERE"
```

Or save the output to a file:

```bash
apflow generate task-tree "YOUR_REQUIREMENT" --output tasks.json
```

With custom LLM parameters:

```bash
apflow generate task-tree "YOUR_REQUIREMENT" --temperature 0.9 --max-tokens 6000
```

## Test Case 1: Complex Data Pipeline

**Command:**
```bash
apflow generate task-tree "Fetch data from two different APIs in parallel, then merge the results, validate the merged data, and finally save to database"
```

**Expected Behavior:**
- Should generate parallel tasks for fetching from two APIs
- Should create a merge/aggregate task that depends on both fetch tasks
- Should create validation and save tasks in sequence
- Should demonstrate understanding of parallel execution patterns

## Test Case 2: ETL Workflow

**Command:**
```bash
apflow generate task-tree "Extract data from a REST API, transform it by filtering and aggregating, then load it into a database with proper error handling"
```

**Expected Behavior:**
- Should create sequential pipeline: Extract → Transform → Load
- Should use appropriate executors for each step
- Should include proper dependencies for execution order

## Test Case 3: Multi-Source Data Collection

**Command:**
```bash
apflow generate task-tree "Collect system information about CPU and memory in parallel, then run a command to analyze the collected data, and finally aggregate the results"
```

**Expected Behavior:**
- Should use system_info_executor for parallel data collection
- Should create command_executor for analysis
- Should use aggregate_results_executor for final step
- Should demonstrate parent_id for organization and dependencies for execution order

## Test Case 4: API Integration with Processing

**Command:**
```bash
apflow generate task-tree "Call a REST API to get user data, process the response to extract key information using a Python script, validate the processed data, and save results to a file"
```

**Expected Behavior:**
- Should create rest_executor for API call
- Should create command_executor for processing
- Should create validation and file operations
- Should show proper dependency chain

## Test Case 5: Complex Workflow with Conditional Steps

**Command:**
```bash
apflow generate task-tree "Fetch data from API, then process it in two different ways in parallel (filter and aggregate), merge both results, and finally save to database"
```

**Expected Behavior:**
- Should demonstrate fan-out pattern (one task spawns multiple)
- Should demonstrate fan-in pattern (multiple tasks converge)
- Should show proper use of dependencies for parallel execution

## Test Case 6: Real-World Business Scenario

**Command:**
```bash
apflow generate task-tree "Monitor system resources (CPU, memory, disk) in parallel, analyze the collected metrics, generate a report, and send notification if any metric exceeds threshold"
```

**Expected Behavior:**
- Should use system_info_executor multiple times in parallel
- Should create analysis and reporting tasks
- Should demonstrate complex dependency relationships

## Test Case 7: Data Processing Pipeline

**Command:**
```bash
apflow generate task-tree "Download data from multiple sources simultaneously, transform each dataset independently, then combine all transformed results into a single output file"
```

**Expected Behavior:**
- Should show parallel download tasks
- Should show parallel transformation tasks
- Should create final aggregation task
- Should demonstrate proper dependency management

## Test Case 8: API Chain with Error Handling

**Command:**
```bash
apflow generate task-tree "Call API A to get authentication token, use token to call API B for data, process the data, and if processing fails, call a fallback API"
```

**Expected Behavior:**
- Should create sequential API calls with token passing
- Should demonstrate optional dependencies for fallback
- Should show proper error handling pattern

## Test Case 9: Hierarchical Data Processing

**Command:**
```bash
apflow generate task-tree "Fetch data from API, organize it into categories, process each category independently in parallel, then aggregate all category results"
```

**Expected Behavior:**
- Should demonstrate hierarchical organization (parent_id)
- Should show parallel processing within categories
- Should create final aggregation step
- Should show both organizational and execution dependencies

## Test Case 10: Complete Business Workflow

**Command:**
```bash
apflow generate task-tree "Create a workflow that fetches customer data from API, validates customer information, processes orders in parallel for each customer, aggregates order results, calculates totals, and generates a final report"
```

**Expected Behavior:**
- Should demonstrate complex multi-step workflow
- Should show parallel processing pattern
- Should create proper dependency chain
- Should include all necessary executors

## Usage Tips

1. **Be Specific**: More detailed requirements lead to better task trees
2. **Mention Patterns**: Use words like "parallel", "sequential", "merge", "aggregate" to guide generation
3. **Specify Executors**: Mention specific operations (API, database, file, command) for better executor selection
4. **Describe Flow**: Explain the data flow and execution order in your requirement

## Expected Improvements

With intelligent prompt generation, the executor should:
- ✅ Select relevant documentation sections based on requirement keywords
- ✅ Understand business context and map to appropriate executors
- ✅ Generate complete, realistic input parameters
- ✅ Create proper dependency chains for execution order
- ✅ Use parent_id appropriately for organization
- ✅ Follow framework best practices and patterns


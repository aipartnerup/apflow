"""
Generate Executor

This executor generates valid task tree JSON arrays from natural language
requirements using LLM. The generated tasks are compatible with
TaskCreator.create_task_tree_from_array().
"""

import json
import re
from typing import Dict, Any, List, Optional, Set
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.extensions.generate.executor_info import format_executors_for_llm
from aipartnerupflow.extensions.generate.docs_loader import load_all_docs
from aipartnerupflow.extensions.generate.llm_client import create_llm_client, LLMClient

logger = get_logger(__name__)


@executor_register()
class GenerateExecutor(BaseTask):
    """
    Executor for generating task trees from natural language requirements
    
    This executor uses LLM to generate valid task tree JSON arrays that can be
    used with TaskCreator.create_task_tree_from_array().
    
    Example usage:
        task = await task_manager.task_repository.create_task(
            name="generate_executor",
            user_id="user123",
            inputs={
                "requirement": "Fetch data from API, process it, and save to database",
                "user_id": "user123"
            }
        )
    """
    
    id = "generate_executor"
    name = "Generate Executor"
    description = "Generate task tree JSON arrays from natural language requirements using LLM"
    tags = ["generation", "llm", "task-tree", "automation"]
    examples = [
        "Generate task tree from requirement",
        "Create workflow from natural language",
        "Auto-generate task structure"
    ]
    
    cancelable: bool = False
    
    @property
    def type(self) -> str:
        """Extension type identifier"""
        return "generate"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate task tree JSON array from requirement
        
        Args:
            inputs: Dictionary containing:
                - requirement: Natural language requirement (required)
                - user_id: User ID for generated tasks (optional)
                - llm_provider: LLM provider ("openai" or "anthropic", optional)
                - llm_model: Model name (optional)
                - temperature: LLM temperature (optional, default 0.7)
                - max_tokens: Maximum tokens (optional, default 4000)
        
        Returns:
            Dictionary with:
                - status: "completed" or "failed"
                - tasks: List of task dictionaries (if successful)
                - error: Error message (if failed)
        """
        try:
            requirement = inputs.get("requirement")
            if not requirement:
                return {
                    "status": "failed",
                    "error": "requirement is required in inputs",
                    "tasks": []
                }
            
            user_id = inputs.get("user_id")
            llm_provider = inputs.get("llm_provider")
            llm_model = inputs.get("llm_model")
            temperature = inputs.get("temperature", 0.7)
            max_tokens = inputs.get("max_tokens", 4000)
            
            # Create LLM client
            try:
                llm_client = create_llm_client(
                    provider=llm_provider,
                    model=llm_model
                )
            except Exception as e:
                logger.error(f"Failed to create LLM client: {e}")
                return {
                    "status": "failed",
                    "error": f"Failed to create LLM client: {str(e)}",
                    "tasks": []
                }
            
            # Build prompt
            prompt = self._build_llm_prompt(requirement, user_id)
            
            # Generate response
            logger.info(f"Generating task tree for requirement: {requirement[:100]}...")
            try:
                response = await llm_client.generate(
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            except Exception as e:
                logger.error(f"LLM generation error: {e}")
                return {
                    "status": "failed",
                    "error": f"LLM generation failed: {str(e)}",
                    "tasks": []
                }
            
            # Parse response
            try:
                tasks = self._parse_llm_response(response)
            except Exception as e:
                logger.error(f"Failed to parse LLM response: {e}")
                return {
                    "status": "failed",
                    "error": f"Failed to parse LLM response: {str(e)}",
                    "tasks": []
                }
            
            # Validate tasks
            validation_result = self._validate_tasks_array(tasks)
            if not validation_result["valid"]:
                return {
                    "status": "failed",
                    "error": f"Validation failed: {validation_result['error']}",
                    "tasks": tasks  # Return tasks anyway for debugging
                }
            
            # Set user_id if provided
            if user_id:
                for task in tasks:
                    if "user_id" not in task:
                        task["user_id"] = user_id
            
            logger.info(f"Successfully generated {len(tasks)} tasks")
            return {
                "status": "completed",
                "tasks": tasks,
                "count": len(tasks)
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in generate_executor: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": f"Unexpected error: {str(e)}",
                "tasks": []
            }
    
    def _build_llm_prompt(self, requirement: str, user_id: Optional[str] = None) -> str:
        """
        Build LLM prompt with context
        
        Args:
            requirement: User's natural language requirement
            user_id: Optional user ID
            
        Returns:
            Complete prompt string
        """
        # Load documentation
        docs = load_all_docs()
        
        # Get executor information
        executors_info = format_executors_for_llm()
        
        # Build prompt
        prompt_parts = [
            "You are a task tree generator for the aipartnerupflow framework.",
            "Your job is to generate a valid task tree JSON array from natural language requirements.",
            "",
            "=== Framework Documentation ===",
            docs,
            "",
            "=== Available Executors ===",
            executors_info,
            "",
            "=== Task Array Format ===",
            "The output must be a JSON array of task objects. Each task must have:",
            "- name: (required) Executor ID that matches one of the available executors",
            "- id: (optional) Task ID. If provided, ALL tasks must have id and use id for references",
            "- user_id: (optional) User ID",
            "- priority: (optional) Priority level (0=urgent, 1=high, 2=normal, 3=low, default: 1)",
            "- inputs: (optional) Execution-time input parameters for the executor",
            "- schemas: (optional) Task schemas, e.g., {\"method\": \"executor_id\"}",
            "- params: (optional) Executor initialization parameters",
            "- parent_id: (optional) Parent task ID or name (for hierarchy organization)",
            "- dependencies: (optional) List of dependencies, e.g., [{\"id\": \"task_0\", \"required\": true}]",
            "",
            "=== Important Rules ===",
            "1. Either ALL tasks have 'id' field, or NONE do (use name for references if no id)",
            "2. parent_id is for ORGANIZATION only (like folders), it does NOT control execution order",
            "3. dependencies control EXECUTION ORDER - use dependencies to make tasks wait for each other",
            "4. There must be exactly ONE root task (task with no parent_id)",
            "5. All parent_id and dependency references must exist in the array",
            "6. No circular dependencies allowed",
            "7. Task names must match available executor IDs exactly",
            "8. Input parameters must match the executor's input schema",
            "",
            "=== Example Task Array ===",
            json.dumps([
                {
                    "id": "task_1",
                    "name": "rest_executor",
                    "user_id": "user123",
                    "priority": 1,
                    "inputs": {
                        "url": "https://api.example.com/data",
                        "method": "GET"
                    }
                },
                {
                    "id": "task_2",
                    "name": "command_executor",
                    "user_id": "user123",
                    "parent_id": "task_1",
                    "dependencies": [{"id": "task_1", "required": True}],
                    "priority": 2,
                    "inputs": {
                        "command": "python process_data.py"
                    }
                }
            ], indent=2),
            "",
            "=== User Requirement ===",
            requirement,
            "",
            "=== Your Task ===",
            "Generate a valid task tree JSON array that fulfills the requirement above.",
            "Return ONLY the JSON array, no markdown code blocks, no explanations.",
            "Ensure all tasks are properly connected in a single tree with one root task.",
            "Use appropriate executors from the available list.",
            "Set proper dependencies to control execution order.",
            "",
        ]
        
        if user_id:
            prompt_parts.append(f"Note: Use user_id='{user_id}' for all tasks.")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM JSON response
        
        Args:
            response: LLM response text
            
        Returns:
            List of task dictionaries
            
        Raises:
            ValueError: If response cannot be parsed
        """
        # Try to extract JSON from response (might be wrapped in markdown code blocks)
        response = response.strip()
        
        # Remove markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Try to find JSON array directly
            json_match = re.search(r'(\[.*\])', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
        
        # Parse JSON
        try:
            tasks = json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from LLM response: {e}. Response: {response[:500]}")
        
        # Validate it's a list
        if not isinstance(tasks, list):
            raise ValueError(f"LLM response is not a list, got {type(tasks)}")
        
        # Validate each task is a dict
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise ValueError(f"Task at index {i} is not a dictionary, got {type(task)}")
        
        return tasks
    
    def _validate_tasks_array(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate generated tasks array against TaskCreator requirements
        
        Args:
            tasks: List of task dictionaries
            
        Returns:
            Dictionary with:
                - valid: bool
                - error: str (if invalid)
        """
        if not tasks:
            return {"valid": False, "error": "Tasks array is empty"}
        
        # Check all tasks have 'name' field
        for i, task in enumerate(tasks):
            if "name" not in task:
                return {"valid": False, "error": f"Task at index {i} is missing 'name' field"}
            if not task["name"]:
                return {"valid": False, "error": f"Task at index {i} has empty 'name' field"}
        
        # Check id consistency (either all have id or none do)
        tasks_with_id = sum(1 for task in tasks if "id" in task)
        tasks_without_id = len(tasks) - tasks_with_id
        
        if tasks_with_id > 0 and tasks_without_id > 0:
            return {
                "valid": False,
                "error": "Mixed mode not supported: either all tasks must have 'id', or all tasks must not have 'id'"
            }
        
        # Build identifier sets
        if tasks_with_id > 0:
            # Use id for references
            identifiers: Set[str] = {task["id"] for task in tasks if "id" in task}
            identifier_to_task = {task["id"]: task for task in tasks if "id" in task}
        else:
            # Use name for references
            identifiers = {task["name"] for task in tasks}
            identifier_to_task = {task["name"]: task for task in tasks}
        
        # Check for duplicate identifiers
        if len(identifiers) < len(tasks):
            return {"valid": False, "error": "Duplicate task identifiers found"}
        
        # Validate parent_id references
        for i, task in enumerate(tasks):
            parent_id = task.get("parent_id")
            if parent_id:
                if parent_id not in identifiers:
                    return {
                        "valid": False,
                        "error": f"Task '{task.get('name', i)}' has parent_id '{parent_id}' which is not in the tasks array"
                    }
        
        # Validate dependency references
        for i, task in enumerate(tasks):
            dependencies = task.get("dependencies")
            if dependencies:
                if not isinstance(dependencies, list):
                    return {
                        "valid": False,
                        "error": f"Task '{task.get('name', i)}' has invalid dependencies (must be a list)"
                    }
                for dep in dependencies:
                    if isinstance(dep, dict):
                        dep_ref = dep.get("id") or dep.get("name")
                        if dep_ref and dep_ref not in identifiers:
                            return {
                                "valid": False,
                                "error": f"Task '{task.get('name', i)}' has dependency '{dep_ref}' which is not in the tasks array"
                            }
                    elif isinstance(dep, str):
                        if dep not in identifiers:
                            return {
                                "valid": False,
                                "error": f"Task '{task.get('name', i)}' has dependency '{dep}' which is not in the tasks array"
                            }
        
        # Check for single root task
        root_tasks = [task for task in tasks if not task.get("parent_id")]
        if len(root_tasks) == 0:
            return {"valid": False, "error": "No root task found (task with no parent_id)"}
        if len(root_tasks) > 1:
            return {
                "valid": False,
                "error": f"Multiple root tasks found: {[task.get('name', 'unknown') for task in root_tasks]}. Only one root task is allowed."
            }
        
        # Check for circular dependencies (simple check - all tasks reachable from root)
        if tasks_with_id > 0:
            root_id = root_tasks[0]["id"]
            reachable = {root_id}
            
            def collect_reachable(current_id: str):
                for task in tasks:
                    if task.get("parent_id") == current_id:
                        task_id = task["id"]
                        if task_id not in reachable:
                            reachable.add(task_id)
                            collect_reachable(task_id)
            
            collect_reachable(root_id)
            
            all_ids = {task["id"] for task in tasks}
            unreachable = all_ids - reachable
            if unreachable:
                return {
                    "valid": False,
                    "error": f"Tasks not reachable from root: {[identifier_to_task[id].get('name', id) for id in unreachable]}"
                }
        
        return {"valid": True, "error": None}
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "requirement": {
                    "type": "string",
                    "description": "Natural language requirement describing the task tree to generate"
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID for generated tasks (optional)"
                },
                "llm_provider": {
                    "type": "string",
                    "enum": ["openai", "anthropic"],
                    "description": "LLM provider to use (defaults to OPENAI_API_KEY or AIPARTNERUPFLOW_LLM_PROVIDER env var)"
                },
                "llm_model": {
                    "type": "string",
                    "description": "LLM model name (optional, uses provider default)"
                },
                "temperature": {
                    "type": "number",
                    "description": "LLM temperature (default: 0.7)",
                    "default": 0.7
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens for LLM response (default: 4000)",
                    "default": 4000
                }
            },
            "required": ["requirement"]
        }


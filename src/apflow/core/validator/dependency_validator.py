"""
Dependency validation utilities for task updates

This module provides reusable functions for validating task dependencies,
including circular dependency detection and dependency reference validation.

All dependency validation logic is centralized here for maintainability.
"""

from typing import Dict, Any, List, Set, Optional
from apflow.core.storage.sqlalchemy.models import TaskModelType
from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
from apflow.logger import get_logger

logger = get_logger(__name__)


def detect_circular_dependencies(
    task_id: str,
    new_dependencies: List[Any],
    all_tasks_in_tree: List[TaskModelType]
) -> None:
    """
    Detect circular dependencies using DFS algorithm.
    
    This function builds a dependency graph including the task being updated
    and all other tasks in the tree, then uses DFS to detect cycles.
    
    Args:
        task_id: ID of the task being updated
        new_dependencies: New dependencies list for the task
        all_tasks_in_tree: All tasks in the same task tree
        
    Raises:
        ValueError: If circular dependencies are detected
    """
    # Build dependency graph: task_id -> set of task_ids it depends on
    dependency_graph: Dict[str, Set[str]] = {}
    task_id_to_name: Dict[str, str] = {}  # For better error messages
    
    # Initialize graph with all tasks in tree
    for task in all_tasks_in_tree:
        dependency_graph[task.id] = set()
        task_id_to_name[task.id] = task.name
    
    # Add dependencies for the task being updated (using new_dependencies)
    for dep in new_dependencies:
        dep_id = None
        if isinstance(dep, dict):
            dep_id = dep.get("id")
        elif isinstance(dep, str):
            dep_id = dep
        
        if dep_id and dep_id in dependency_graph:
            dependency_graph[task_id].add(dep_id)
    
    # Add dependencies for all other tasks (using their current dependencies)
    for task in all_tasks_in_tree:
        if task.id == task_id:
            continue  # Already handled above
        
        task_deps = task.dependencies or []
        for dep in task_deps:
            dep_id = None
            if isinstance(dep, dict):
                dep_id = dep.get("id")
            elif isinstance(dep, str):
                dep_id = dep
            
            if dep_id and dep_id in dependency_graph:
                dependency_graph[task.id].add(dep_id)
    
    # DFS to detect cycles
    visited: Set[str] = set()
    
    def dfs(node: str, path: List[str]) -> Optional[List[str]]:
        """
        DFS to detect cycles.
        
        Args:
            node: Current node being visited
            path: Current path from root to this node
            
        Returns:
            Cycle path if cycle detected, None otherwise
        """
        if node in path:
            # Found a cycle - extract the cycle path
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]  # Complete the cycle
            return cycle
        
        if node in visited:
            # Already processed this node completely, no cycle from here
            return None
        
        # Mark as visited and add to current path
        visited.add(node)
        path.append(node)
        
        # Visit all dependencies
        node_deps = dependency_graph.get(node, set())
        for dep in node_deps:
            # Skip if dependency is not in the graph
            if dep not in dependency_graph:
                continue
            cycle = dfs(dep, path)
            if cycle:
                return cycle
        
        # Remove from current path (backtrack)
        path.pop()
        return None
    
    # Check all nodes for cycles
    for identifier in dependency_graph.keys():
        if identifier not in visited:
            cycle_path = dfs(identifier, [])
            if cycle_path:
                # Format cycle path with task names for better error message
                cycle_names = [task_id_to_name.get(id, id) for id in cycle_path]
                raise ValueError(
                    f"Circular dependency detected: {' -> '.join(cycle_names)}. "
                    f"Tasks cannot have circular dependencies as this would cause infinite loops."
                )



async def validate_dependency_references(
    task_id: str,
    new_dependencies: List[Any],
    task_repository: TaskRepository,
    user_id: Optional[str] = None,
    only_within_tree: Optional[bool] = False,
) -> None:
    """
    Validate that all dependency references exist and belong to the same user.
    If only_within_tree is True, dependencies must be in the same task tree.
    If False, dependencies can be any task with the same user_id.
    Args:
        task_id: ID of the task being updated
        new_dependencies: New dependencies list for the task
        task_repository: TaskRepository instance
        user_id: The user ID that all dependencies must match
        only_within_tree: If True, dependencies must be in the same task tree (default False)
    Raises:
        ValueError: If any dependency reference is not found or user_id does not match
    """
    # Get the task being updated
    task = await task_repository.get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")

    if only_within_tree:
        # Restrict dependencies to the same task tree
        root_task = await task_repository.get_root_task(task)
        all_tasks_in_tree = await task_repository.get_all_tasks_in_tree(root_task)
        task_ids_in_tree = {t.id for t in all_tasks_in_tree}
        for dep in new_dependencies:
            dep_id = None
            if isinstance(dep, dict):
                dep_id = dep.get("id")
            elif isinstance(dep, str):
                dep_id = dep
            if not dep_id:
                raise ValueError("Dependency must have 'id' field or be a string task ID")
            if dep_id not in task_ids_in_tree:
                raise ValueError(f"Dependency reference '{dep_id}' not found in task tree")
            dep_task = next((t for t in all_tasks_in_tree if t.id == dep_id), None)
            if dep_task is not None:
                dep_user_id = getattr(dep_task, "user_id", None)
                # Only check user_id if both are not None
                if user_id is not None and dep_user_id is not None and user_id != dep_user_id:
                    raise ValueError(f"Dependency '{dep_id}' does not belong to user '{user_id}'")
    else:
        # Allow dependencies to any task with the same user_id
        for dep in new_dependencies:
            dep_id = None
            if isinstance(dep, dict):
                dep_id = dep.get("id")
            elif isinstance(dep, str):
                dep_id = dep
            if not dep_id:
                raise ValueError("Dependency must have 'id' field or be a string task ID")
            dep_task = await task_repository.get_task_by_id(dep_id)
            if not dep_task:
                raise ValueError(f"Dependency reference '{dep_id}' not found for user '{user_id}'")
            dep_user_id = getattr(dep_task, "user_id", None)
            # Only check user_id if both are not None
            if user_id is not None and dep_user_id is not None and user_id != dep_user_id:
                raise ValueError(f"Dependency '{dep_id}' does not belong to user '{user_id}'")


async def check_dependent_tasks_executing(
    task_id: str,
    task_repository: TaskRepository
) -> List[str]:
    """
    Check if any tasks that depend on this task are currently executing.
    Args:
        task_id: ID of the task being updated
        task_repository: TaskRepository instance
    Returns:
        List of task IDs that depend on this task and are in_progress
    """
    # Find all tasks in the same tree
    task = await task_repository.get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    root_task = await task_repository.get_root_task(task)
    all_tasks_in_tree = await task_repository.get_all_tasks_in_tree(root_task)
    dependent_task_ids = []
    for t in all_tasks_in_tree:
        deps = t.dependencies or []
        for dep in deps:
            dep_id = dep.get("id") if isinstance(dep, dict) else dep
            if dep_id == task_id and getattr(t, "status", None) == "in_progress":
                dependent_task_ids.append(t.id)
    return dependent_task_ids


async def are_dependencies_satisfied(
    task: TaskModelType,
    task_repository: TaskRepository,
    tasks_to_reexecute: set[str]
) -> bool:
    """
    Check if all dependencies for a task are satisfied
    
    Re-execution Logic:
    - A dependency is satisfied if the dependency task is `completed`
    - Even if a dependency is marked for re-execution, if it's already `completed`,
      its result is available and can satisfy dependent tasks
    - This allows dependent tasks to proceed while still allowing re-execution
      of dependencies if needed
    
    Args:
        task: Task to check dependencies for
        task_repository: TaskRepository instance for querying tasks
        tasks_to_reexecute: Set of task IDs marked for re-execution
        
    Returns:
        True if all dependencies are satisfied, False otherwise
    """
    task_dependencies = task.dependencies or []
    if not task_dependencies:
        logger.info(f"🔍 [DEBUG] No dependencies for task {task.id}, ready to execute")
        return True
    
    # Get all completed tasks by id in the same task tree using repository
    completed_tasks_by_id = await task_repository.get_completed_tasks_by_id(task)
    logger.info(f"🔍 [DEBUG] Available tasks for {task.id}: {list(completed_tasks_by_id.keys())}")
    
    # Check each dependency
    for dep in task_dependencies:
        if isinstance(dep, dict):
            dep_id = dep.get("id")  # This is the task id of the dependency
            dep_required = dep.get("required", True)
            
            logger.info(f"🔍 [DEBUG] Checking dependency {dep_id} (required: {dep_required}) for task {task.id}")
            
            if dep_required and dep_id not in completed_tasks_by_id:
                logger.info(f"❌ Task {task.id} dependency {dep_id} not satisfied (not found in tasks: {list(completed_tasks_by_id.keys())})")
                return False
            elif dep_required and dep_id in completed_tasks_by_id:
                # Check if the dependency task is actually completed
                dep_task = completed_tasks_by_id[dep_id]
                dep_task_id = str(dep_task.id)
                # If dependency is marked for re-execution and is still in progress or pending, it's not satisfied yet
                # But if it's already completed, we can consider it satisfied (it will be re-executed but result is available)
                if dep_task_id in tasks_to_reexecute:
                    # Check current status from database to see if it's actually completed
                    # If it's completed, we can use the result even if marked for re-execution
                    if dep_task.status == "completed":
                        logger.info(f"✅ Task {task.id} dependency {dep_id} satisfied (task {dep_task.id} completed, marked for re-execution but result available)")
                    else:
                        logger.info(f"❌ Task {task.id} dependency {dep_id} is marked for re-execution and not completed yet (status: {dep_task.status})")
                        return False
                elif dep_task.status != "completed":
                    logger.info(f"❌ Task {task.id} dependency {dep_id} found but not completed (status: {dep_task.status})")
                    return False
                else:
                    logger.info(f"✅ Task {task.id} dependency {dep_id} satisfied (task {dep_task.id} completed)")
        elif isinstance(dep, str):
            # Simple string dependency (just the id) - backward compatibility
            dep_id = dep
            if dep_id not in completed_tasks_by_id:
                logger.info(f"❌ Task {task.id} dependency {dep_id} not satisfied")
                return False
            dep_task = completed_tasks_by_id[dep_id]
            dep_task_id = str(dep_task.id)
            # If dependency is marked for re-execution, check if it's actually completed
            if dep_task_id in tasks_to_reexecute:
                # If it's completed, we can use the result even if marked for re-execution
                if dep_task.status == "completed":
                    logger.info(f"✅ Task {task.id} dependency {dep_id} satisfied (task {dep_task.id} completed, marked for re-execution but result available)")
                else:
                    logger.info(f"❌ Task {task.id} dependency {dep_id} is marked for re-execution and not completed yet (status: {dep_task.status})")
                    return False
            elif dep_task.status != "completed":
                logger.info(f"❌ Task {task.id} dependency {dep_id} found but not completed (status: {dep_task.status})")
                return False
            else:
                logger.info(f"✅ Task {task.id} dependency {dep_id} satisfied (task {dep_task.id} completed)")
    
    logger.info(f"✅ All dependencies satisfied for task {task.id}")
    return True

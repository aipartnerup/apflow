"""
Dependency validation utilities for task updates

This module provides reusable functions for validating task dependencies,
including circular dependency detection and dependency reference validation.

All dependency validation logic is centralized here for maintainability.
"""

from typing import Dict, Any, List, Set, Optional
from apflow.core.storage.sqlalchemy.models import TaskModel
from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
from apflow.logger import get_logger

logger = get_logger(__name__)


def detect_circular_dependencies(
    task_id: str,
    new_dependencies: List[Any],
    all_tasks_in_tree: List[TaskModel]
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
    dependency_graph: Dict[str, Set[str]] = {}
    task_id_to_name: Dict[str, str] = {}
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
            continue
        task_deps = task.dependencies or []
        for dep in task_deps:
            dep_id = None
            if isinstance(dep, dict):
                dep_id = dep.get("id")
            elif isinstance(dep, str):
                dep_id = dep
            if dep_id and dep_id in dependency_graph:
                dependency_graph[task.id].add(dep_id)
    visited: Set[str] = set()
    def dfs(node: str, path: List[str]) -> Optional[List[str]]:
        if node in path:
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            return cycle
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        node_deps = dependency_graph.get(node, set())
        for dep in node_deps:
            if dep not in dependency_graph:
                continue
            cycle = dfs(dep, path)
            if cycle:
                return cycle
        path.pop()
        return None
    for identifier in dependency_graph.keys():
        if identifier not in visited:
            cycle_path = dfs(identifier, [])
            if cycle_path:
                cycle_names = [task_id_to_name.get(id, id) for id in cycle_path]
                raise ValueError(
                    f"Circular dependency detected: {' -> '.join(cycle_names)}. "
                    f"Tasks cannot have circular dependencies as this would cause infinite loops."
                )



async def validate_dependency_references(
    task_id: str,
    new_dependencies: List[Any],
    task_repository: TaskRepository,
    user_id: str,
    only_within_tree: bool = True,
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
        only_within_tree: If True, dependencies must be in the same task tree (default True)
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
            # Check user_id match
            dep_task = next((t for t in all_tasks_in_tree if t.id == dep_id), None)
            if dep_task is not None and getattr(dep_task, "user_id", None) != user_id:
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
            if getattr(dep_task, "user_id", None) != user_id:
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

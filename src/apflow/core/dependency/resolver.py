"""
Dependency resolution utilities for task execution

This module provides reusable functions for resolving task dependencies,
including checking if dependencies are satisfied and merging dependency results.

All dependency resolution logic is centralized here for maintainability.
"""
from typing import Any, Dict, List, Set

def are_dependencies_satisfied(task_id: str, completed_task_ids: Set[str], dependencies: List[Any]) -> bool:
    """
    Check if all dependencies for a task are satisfied (i.e., completed).
    Args:
        task_id: ID of the task being checked
        completed_task_ids: Set of completed task IDs
        dependencies: List of dependencies (task IDs or dicts with 'id')
    Returns:
        True if all dependencies are satisfied, False otherwise
    """
    for dep in dependencies:
        dep_id = dep.get("id") if isinstance(dep, dict) else dep
        if dep_id not in completed_task_ids:
            return False
    return True

def resolve_task_dependencies(task_id: str, dependency_results: Dict[str, Any], dependencies: List[Any]) -> Dict[str, Any]:
    """
    Merge results from dependencies for a given task.
    Args:
        task_id: ID of the task being resolved
        dependency_results: Mapping from dependency task ID to its result/output
        dependencies: List of dependencies (task IDs or dicts with 'id')
    Returns:
        Merged dictionary of dependency results for the task
    """
    merged = {}
    for dep in dependencies:
        dep_id = dep.get("id") if isinstance(dep, dict) else dep
        if dep_id in dependency_results:
            merged[dep_id] = dependency_results[dep_id]
    return merged

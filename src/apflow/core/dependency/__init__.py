# Dependency module exports
from .validator import (
    detect_circular_dependencies,
    validate_dependency_references,
    check_dependent_tasks_executing,
)
from .resolver import (
    are_dependencies_satisfied,
    resolve_task_dependencies,
)

__all__ = [
    # Validation
    "detect_circular_dependencies",
    "validate_dependency_references",
    "check_dependent_tasks_executing",
    # Resolution
    "are_dependencies_satisfied",
    "resolve_task_dependencies",
]

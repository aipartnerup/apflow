# Dependency module exports
from .dependency_validator import (
    detect_circular_dependencies,
    validate_dependency_references,
    check_dependent_tasks_executing,
    are_dependencies_satisfied,
)

__all__ = [
    # Validation
    "detect_circular_dependencies",
    "validate_dependency_references",
    "check_dependent_tasks_executing",
    "are_dependencies_satisfied",
]

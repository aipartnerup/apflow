"""
Unit tests for apflow.core.dependency.resolver
"""
from apflow.core.dependency import resolver

def test_are_dependencies_satisfied():
    # All dependencies satisfied
    assert resolver.are_dependencies_satisfied(
        "A", {"B", "C"}, ["B", "C"]
    ) is True
    # Not all dependencies satisfied
    assert resolver.are_dependencies_satisfied(
        "A", {"B"}, ["B", "C"]
    ) is False
    # Dependency as dict
    assert resolver.are_dependencies_satisfied(
        "A", {"B"}, [{"id": "B"}]
    ) is True
    # Empty dependencies
    assert resolver.are_dependencies_satisfied(
        "A", set(), []
    ) is True

def test_resolve_task_dependencies():
    dep_results = {"B": 1, "C": 2}
    # All dependencies present
    merged = resolver.resolve_task_dependencies("A", dep_results, ["B", "C"])
    assert merged == {"B": 1, "C": 2}
    # Some dependencies missing
    merged = resolver.resolve_task_dependencies("A", dep_results, ["B", "D"])
    assert merged == {"B": 1}
    # Dependency as dict
    merged = resolver.resolve_task_dependencies("A", dep_results, [{"id": "B"}])
    assert merged == {"B": 1}
    # No dependencies
    merged = resolver.resolve_task_dependencies("A", dep_results, [])
    assert merged == {}

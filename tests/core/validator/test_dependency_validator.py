"""
Unit tests for apflow.core.dependency.validator
"""
import pytest
import asyncio
from apflow.core.validator import dependency_validator

class DummyTask:
    def __init__(self, id, name=None, dependencies=None, status=None, user_id=None):
        self.id = id
        self.name = name or id
        self.dependencies = dependencies or []
        self.status = status
        self.user_id = user_id

@pytest.mark.parametrize("tasks,task_id,new_deps,should_raise", [
    # No cycle
    ([DummyTask("A", dependencies=["B"]), DummyTask("B")], "A", ["B"], False),
    # Simple cycle
    ([DummyTask("A", dependencies=["B"]), DummyTask("B", dependencies=["A"])], "A", ["B"], True),
    # Self-cycle
    ([DummyTask("A", dependencies=["A"])], "A", ["A"], True),
    # No dependencies
    ([DummyTask("A"), DummyTask("B")], "A", [], False),
])
def test_detect_circular_dependencies(tasks, task_id, new_deps, should_raise):
    if should_raise:
        with pytest.raises(ValueError, match="circular|Circular|infinite"):
            dependency_validator.detect_circular_dependencies(task_id, new_deps, tasks)
    else:
        dependency_validator.detect_circular_dependencies(task_id, new_deps, tasks)

class DummyRepo:
    def __init__(self, tasks):
        self.tasks = {t.id: t for t in tasks}
        self.root = next(iter(tasks))
    async def get_task_by_id(self, id):
        return self.tasks.get(id)
    async def get_root_task(self, task):
        return self.root
    async def get_all_tasks_in_tree(self, root):
        return list(self.tasks.values())


# Test dependency reference validation with user_id and only_within_tree

@pytest.mark.asyncio
@pytest.mark.parametrize("tasks,task_id,new_deps,user_id,only_within_tree,should_raise", [
    # All dependencies exist, same user, within tree
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u1")], "A", ["B"], "u1", True, False),
    # Dependency missing in tree
    ([DummyTask("A", user_id="u1")], "A", ["B"], "u1", True, True),
    # Dependency as dict, same user
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u1")], "A", [{"id": "B"}], "u1", True, False),
    # Dependency as dict, user mismatch
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u2")], "A", [{"id": "B"}], "u1", True, True),
    # Dependency outside tree, allowed by only_within_tree=False, user match
    ([DummyTask("A", user_id="u1")], "A", ["B"], "u1", False, True),  # B missing
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u1")], "A", ["B"], "u1", False, False),
    # Dependency outside tree, user mismatch
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u2")], "A", ["B"], "u1", False, True),
])
async def test_validate_dependency_references(tasks, task_id, new_deps, user_id, only_within_tree, should_raise):
    repo = DummyRepo(tasks)
    if should_raise:
        with pytest.raises(ValueError):
            await dependency_validator.validate_dependency_references(task_id, new_deps, repo, user_id, only_within_tree)
    else:
        await dependency_validator.validate_dependency_references(task_id, new_deps, repo, user_id, only_within_tree)

# Comprehensive test cases for validate_dependency_references


@pytest.mark.asyncio
@pytest.mark.parametrize("tasks,task_id,new_deps,user_id,only_within_tree,expected_error", [
    # Dependency is None
    ([DummyTask("A", user_id="u1")], "A", [None], "u1", True, "Dependency must have 'id' field or be a string task ID"),
    # Dependency is empty dict
    ([DummyTask("A", user_id="u1")], "A", [{}], "u1", True, "Dependency must have 'id' field or be a string task ID"),
    # Dependency is integer (invalid type)
    ([DummyTask("A", user_id="u1")], "A", [123], "u1", True, "Dependency must have 'id' field or be a string task ID"),
    # Task being updated does not exist
    ([DummyTask("A", user_id="u1")], "B", ["A"], "u1", True, "Task B not found"),
    # Dependency exists but user_id is None (should not raise, user_id check skipped)
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u1")], "A", ["B"], None, True, None),
    # Dependency exists, only_within_tree False, user_id None (should not raise, user_id check skipped)
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u1")], "A", ["B"], None, False, None),
    # Dependency exists, only_within_tree True, user_id None, dependency user_id is not None (should not raise)
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u2")], "A", ["B"], None, True, None),
    # Dependency exists, only_within_tree False, user_id mismatch (should raise)
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u2")], "A", ["B"], "u1", False, "Dependency 'B' does not belong to user 'u1'"),
    # Dependency exists, only_within_tree True, user_id mismatch (should raise)
    ([DummyTask("A", user_id="u1"), DummyTask("B", user_id="u2")], "A", ["B"], "u1", True, "Dependency 'B' does not belong to user 'u1'"),
    # Dependency does not exist, only_within_tree False
    ([DummyTask("A", user_id="u1")], "A", ["B"], "u1", False, "Dependency reference 'B' not found for user 'u1'"),
    # Dependency does not exist, only_within_tree True
    ([DummyTask("A", user_id="u1")], "A", ["B"], "u1", True, "Dependency reference 'B' not found in task tree"),
])
async def test_validate_dependency_references_comprehensive(tasks, task_id, new_deps, user_id, only_within_tree, expected_error):
    """
    Comprehensive coverage for validate_dependency_references:
    - Handles None, empty dict, invalid types
    - Handles missing task being updated
    - Handles user_id None
    - Handles user_id mismatch
    - Handles missing dependency
    """
    repo = DummyRepo(tasks)
    if expected_error:
        with pytest.raises(ValueError) as exc:
            await dependency_validator.validate_dependency_references(task_id, new_deps, repo, user_id, only_within_tree)
        assert expected_error in str(exc.value)
    else:
        await dependency_validator.validate_dependency_references(task_id, new_deps, repo, user_id, only_within_tree)

@pytest.mark.asyncio
def test_check_dependent_tasks_executing():
    # A <- B (in_progress), A <- C (completed)
    a = DummyTask("A")
    b = DummyTask("B", dependencies=["A"], status="in_progress")
    c = DummyTask("C", dependencies=["A"], status="completed")
    repo = DummyRepo([a, b, c])
    result = asyncio.run(dependency_validator.check_dependent_tasks_executing("A", repo))
    assert result == ["B"]


def test_are_dependencies_satisfied():
    # All dependencies satisfied
    assert dependency_validator.are_dependencies_satisfied(
        "A", {"B", "C"}, ["B", "C"]
    ) is True
    # Not all dependencies satisfied
    assert dependency_validator.are_dependencies_satisfied(
        "A", {"B"}, ["B", "C"]
    ) is False
    # Dependency as dict
    assert dependency_validator.are_dependencies_satisfied(
        "A", {"B"}, [{"id": "B"}]
    ) is True
    # Empty dependencies
    assert dependency_validator.are_dependencies_satisfied(
        "A", set(), []
    ) is True

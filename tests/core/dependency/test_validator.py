"""
Unit tests for apflow.core.dependency.validator
"""
import pytest
from types import SimpleNamespace
from apflow.core.dependency import validator
import re

class DummyTask:
    def __init__(self, id, name=None, dependencies=None, status=None, user_id=None):
        self.id = id
        self.name = name or id
        self.dependencies = dependencies or []
        self.status = status
        self.user_id = user_id or "user1"

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
            validator.detect_circular_dependencies(task_id, new_deps, tasks)
    else:
        validator.detect_circular_dependencies(task_id, new_deps, tasks)

import asyncio

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
import pytest_asyncio

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
            await validator.validate_dependency_references(task_id, new_deps, repo, user_id, only_within_tree)
    else:
        await validator.validate_dependency_references(task_id, new_deps, repo, user_id, only_within_tree)

@pytest.mark.asyncio
def test_check_dependent_tasks_executing():
    # A <- B (in_progress), A <- C (completed)
    a = DummyTask("A")
    b = DummyTask("B", dependencies=["A"], status="in_progress")
    c = DummyTask("C", dependencies=["A"], status="completed")
    repo = DummyRepo([a, b, c])
    result = asyncio.run(validator.check_dependent_tasks_executing("A", repo))
    assert result == ["B"]

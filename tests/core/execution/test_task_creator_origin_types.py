"""
Test TaskCreator methods for origin types: from_link, from_copy, from_snapshot, from_mixed
"""
import pytest
from apflow.core.execution.task_creator import TaskCreator
from apflow.core.execution.task_manager import TaskManager
from apflow.core.types import TaskTreeNode
from apflow.core.storage.sqlalchemy.models import TaskModel, TaskOriginType


class TestTaskCreatorFromLink:
    """Test TaskCreator.from_link method"""

    @pytest.mark.asyncio
    async def test_from_link_fails_if_not_completed(self, sync_db_session):
        """Test that linking a task tree with any non-completed node raises ValueError"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)

        # Create a root task (not completed)
        root = await task_manager.task_repository.create_task(
            name="Root Task",
            user_id="user_123",
            status="completed",
        )
        # Add a completed child
        child = await task_manager.task_repository.create_task(
            name="Child Task",
            user_id="user_123",
            parent_id=root.id,
            status="completed",
        )
        root.has_children = True
        sync_db_session.commit()

        # Should raise ValueError because root is not completed
        with pytest.raises(ValueError, match="fully completed task tree"):
            await creator.from_link(
                _original_task=root,
                _save=True,
                _recursive=True
            )

        # Now complete the root, but make child not completed
        root.status = "completed"
        child.status = "pending"
        sync_db_session.commit()
        # Debug: print and assert child status
        sync_db_session.refresh(child)
        print(f"[DEBUG] child.status after set: {child.status}")
        assert child.status == "pending", f"Expected child.status to be 'pending', got {child.status}"
        sync_db_session.refresh(root)
        print(f"[DEBUG] root.status after set: {root.status}")

        with pytest.raises(ValueError, match="Only a fully completed task tree can be linked"):
            # Debug: print status before call
            sync_db_session.refresh(child)
            print(f"[DEBUG] child.status before from_link: {child.status}")
            await creator.from_link(
                _original_task=root,
                _save=True,
                _recursive=True
            )

        # Complete both, should succeed
        child.status = "completed"
        sync_db_session.commit()
        result = await creator.from_link(
            _original_task=root,
            _save=True,
            _recursive=True
        )
        assert isinstance(result, TaskTreeNode)
        assert result.task.status == "completed"
        for c in result.children:
            assert c.task.status == "completed"

    @pytest.mark.asyncio
    async def test_from_link_status_matches_source(self, sync_db_session):
        """Test that the linked task status matches the source task status"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)

        # Create a completed original task
        original_task = await task_manager.task_repository.create_task(
            name="Original Task",
            user_id="user_123",
            status="completed",
        )
        sync_db_session.commit()
        sync_db_session.refresh(original_task)
        original_task.status = "completed"
        original_task.status = "completed"
        sync_db_session.commit()
        sync_db_session.refresh(original_task)
        linked_task = await creator.from_link(
            _original_task=original_task,
            _save=True,
            _recursive=False
        )
        assert linked_task.status == "completed"

        # Create a custom status original task
        for status in ["failed", "skipped", "cancelled"]:
            t = await task_manager.task_repository.create_task(
                name=f"Task {status}",
                user_id="user_123",
                status=status,
            )
            # Complete all tasks in tree for link to succeed
            t.status = "completed"
            sync_db_session.commit()
            sync_db_session.refresh(t)
            linked = await creator.from_link(
                _original_task=t,
                _save=True,
                _recursive=False
            )
            assert linked.status == "completed"
    
    
    @pytest.mark.asyncio
    async def test_from_link_single_task(self, sync_db_session):
        """Test linking a single task without recursion"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create original task
        original_task = await task_manager.task_repository.create_task(
            name="Original Task",
            user_id="user_123",
            priority=2,
            inputs={"key": "value"},
            params={"param1": "param_value"},
            schemas={"type": "stdio"},
            status="completed",
        )

        sync_db_session.commit()

        # Ensure all tasks in the tree are marked as completed
        task_tree = await task_manager.task_repository.build_task_tree(original_task)
        for node in task_tree.iter_nodes():
            node.task.status = "completed"
            sync_db_session.commit()
            sync_db_session.refresh(node.task)

        linked_task = await creator.from_link(
            _original_task=original_task,
            _save=True,
            _recursive=False
        )
        
        # Verify return type is TaskModel
        assert isinstance(linked_task, TaskModel)
        
        # Verify origin type is link
        assert linked_task.origin_type == TaskOriginType.link
        
        # Verify original_task_id points to original
        assert linked_task.original_task_id == original_task.id
        
        # Verify fields are copied from original
        assert linked_task.name == original_task.name
        assert linked_task.user_id == original_task.user_id
        assert linked_task.priority == original_task.priority
        assert linked_task.inputs == original_task.inputs
        assert linked_task.params == original_task.params
        
        # Verify original is marked as having references
        sync_db_session.refresh(original_task)
        assert original_task.has_references is True
    
    @pytest.mark.asyncio
    async def test_from_link_single_task_with_reset_kwargs(self, sync_db_session):
        """Test linking a single completed task with field overrides"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)

        original_task = await task_manager.task_repository.create_task(
            name="Original Task",
            user_id="user_123",
            priority=2,
            status="completed",
        )

        sync_db_session.commit()
        sync_db_session.refresh(original_task)
        original_task.status = "completed"
        sync_db_session.commit()
        sync_db_session.refresh(original_task)

        linked_task = await creator.from_link(
            _original_task=original_task,
            _save=True,
            _recursive=False,
            user_id="new_user_456",
            priority=1,
        )

        # Verify field overrides are applied
        assert linked_task.user_id == "new_user_456"
        assert linked_task.priority == 1

        # Verify other fields are from original
        assert linked_task.name == original_task.name
    
    @pytest.mark.asyncio
    async def test_from_link_single_task_no_save(self, sync_db_session):
        """Test linking a single task without saving to database"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        original_task = await task_manager.task_repository.create_task(
            name="Original Task",
            user_id="user_123",
            status="completed",
        )

        original_task.status = "completed"
        sync_db_session.commit()
        sync_db_session.refresh(original_task)

        linked_task = await creator.from_link(
            _original_task=original_task,
            _save=False,
            _recursive=False
        )
        
        # Verify task is created
        assert isinstance(linked_task, TaskModel)
        
        # Verify it has origin_type.link
        assert linked_task.origin_type == TaskOriginType.link
    
    @pytest.mark.asyncio
    async def test_from_link_recursive_tree(self, sync_db_session):
        """Test linking entire task tree recursively"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree
        root = await task_manager.task_repository.create_task(
            name="Root Task",
            user_id="user_123",
            priority=1,
            status="completed",
        )

        child1 = await task_manager.task_repository.create_task(
            name="Child 1",
            user_id="user_123",
            parent_id=root.id,
            priority=2,
            status="completed",
        )

        child2 = await task_manager.task_repository.create_task(
            name="Child 2",
            user_id="user_123",
            parent_id=root.id,
            status="completed",
            dependencies=[{"id": child1.id, "required": True}],
        )

        root.status = "completed"
        child1.status = "completed"
        child2.status = "completed"
        root.has_children = True
        sync_db_session.commit()

        # Explicitly refresh all tasks to ensure status is up-to-date
        sync_db_session.refresh(root)
        sync_db_session.refresh(child1)
        sync_db_session.refresh(child2)

        linked_tree = await creator.from_link(
            _original_task=root,
            _save=True,
            _recursive=True
        )
        
        # Verify return type is TaskTreeNode
        assert isinstance(linked_tree, TaskTreeNode)
        
        # Verify root task
        assert linked_tree.task.origin_type == TaskOriginType.link
        assert linked_tree.task.original_task_id == root.id
        
        # Verify children are linked
        assert len(linked_tree.children) == 2
        for child_node in linked_tree.children:
            assert child_node.task.origin_type == TaskOriginType.link
            assert child_node.task.parent_id == linked_tree.task.id

    @pytest.mark.asyncio
    async def test_from_link_with_auto_include_deps_true(self, sync_db_session):
        """Linking with _auto_include_deps=True includes upstream dependencies in minimal subtree"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        dep_task = await task_manager.task_repository.create_task(
            name="Dependency Task",
            user_id="user_123",
            status="completed",
        )
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
            status="completed",
            dependencies=[{"id": dep_task.id, "required": True}]
        )

        sync_db_session.commit()
        dep_task.status = "completed"
        task_a.status = "completed"
        sync_db_session.commit()
        sync_db_session.refresh(dep_task)
        sync_db_session.refresh(task_a)

        linked_tree = await creator.from_link(
            _original_task=task_a,
            _save=True,
            _recursive=True,
            _auto_include_deps=True
        )
        
        assert isinstance(linked_tree, TaskTreeNode)
        assert linked_tree.task.origin_type == TaskOriginType.link
        assert linked_tree.task.original_task_id == task_a.id

    @pytest.mark.asyncio
    async def test_from_link_with_auto_include_deps_false(self, sync_db_session):
        """Linking with _auto_include_deps=False does not attempt to resolve dependencies (all must be completed)"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)

        dep_task = await task_manager.task_repository.create_task(
            name="Dependency Task",
            user_id="user_123",
            status="completed",
        )
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
            status="completed",
            dependencies=[{"id": dep_task.id, "required": True}]
        )

        # Ensure all dependencies are completed (simulate a tree)
        dep_task.status = "completed"
        task_a.status = "completed"
        sync_db_session.commit()

        linked_tree = await creator.from_link(
            _original_task=task_a,
            _save=True,
            _recursive=True,
            _auto_include_deps=False
        )

        assert isinstance(linked_tree, TaskTreeNode)
        assert linked_tree.task.origin_type == TaskOriginType.link

    @pytest.mark.asyncio
    async def test_from_link_include_dependents_non_root_task(self, sync_db_session):
        """_include_dependents=True includes downstream dependents for non-root link operations (all must be completed)"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)

        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
            status="completed",
        )
        task_b = await task_manager.task_repository.create_task(
            name="Task B",
            user_id="user_123",
            parent_id=task_a.id,
            status="completed",
        )
        dependent = await task_manager.task_repository.create_task(
            name="Dependent Task",
            user_id="user_123",
            status="completed",
            dependencies=[{"id": task_b.id, "required": True}]
        )
        # Ensure all are completed
        task_a.status = "completed"
        task_b.status = "completed"
        dependent.status = "completed"
        sync_db_session.commit()

        linked_tree = await creator.from_link(
            _original_task=task_b,
            _save=True,
            _recursive=True,
            _include_dependents=True
        )

        assert isinstance(linked_tree, TaskTreeNode)
        assert linked_tree.task.origin_type == TaskOriginType.link


class TestTaskCreatorFromCopy:
    """Test TaskCreator.from_copy method"""
    
    @pytest.mark.asyncio
    async def test_from_copy_single_task(self, sync_db_session):
        """Test copying a single task without recursion"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        original_task = await task_manager.task_repository.create_task(
            name="Original Task",
            user_id="user_123",
            priority=2,
            inputs={"key": "value"},
            status="completed",
            result={"output": "result_value"},
        )
        
        copied_task = await creator.from_copy(
            _original_task=original_task,
            _save=True,
            _recursive=False
        )
        
        # Verify return type is TaskModel
        assert isinstance(copied_task, TaskModel)
        
        # Verify origin type is copy
        assert copied_task.origin_type == TaskOriginType.copy
        
        # Verify original_task_id points to original
        assert copied_task.original_task_id == original_task.id
        
        # Verify fields are copied from original
        assert copied_task.name == original_task.name
        assert copied_task.inputs == original_task.inputs
        
        # Verify it's a different task
        assert copied_task.id != original_task.id
    
    @pytest.mark.asyncio
    async def test_from_copy_single_task_with_field_override(self, sync_db_session):
        """Test copying a single task with field overrides"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        original_task = await task_manager.task_repository.create_task(
            name="Original Task",
            user_id="user_123",
            inputs={"key": "value"},
        )
        
        copied_task = await creator.from_copy(
            _original_task=original_task,
            _save=True,
            _recursive=False,
            user_id="new_user_456",
            inputs={"new_key": "new_value"},
            status="pending"
        )
        
        # Verify field overrides are applied
        assert copied_task.user_id == "new_user_456"
        assert copied_task.inputs == {"new_key": "new_value"}
        
        # Verify other fields are from original
        assert copied_task.name == original_task.name
    
    @pytest.mark.asyncio
    async def test_from_copy_single_task_no_save(self, sync_db_session):
        """Test copying a single task without saving"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        original_task = await task_manager.task_repository.create_task(
            name="Original Task",
            user_id="user_123",
        )
        
        copied_task = await creator.from_copy(
            _original_task=original_task,
            _save=False,
            _recursive=False
        )
        
        # Verify task is created
        assert isinstance(copied_task, TaskModel)
        assert copied_task.origin_type == TaskOriginType.copy
    
    @pytest.mark.asyncio
    async def test_from_copy_recursive_tree(self, sync_db_session):
        """Test copying entire task tree recursively"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree
        root = await task_manager.task_repository.create_task(
            name="Root Task",
            user_id="user_123",
            priority=1,
        )
        
        child1 = await task_manager.task_repository.create_task(
            name="Child 1",
            user_id="user_123",
            parent_id=root.id,
            priority=2,
        )
        
        await task_manager.task_repository.create_task(
            name="Child 2",
            user_id="user_123",
            parent_id=root.id,
            dependencies=[{"id": child1.id, "required": True}],
        )
        
        root.has_children = True
        sync_db_session.commit()
        
        copied_tree = await creator.from_copy(
            _original_task=root,
            _save=True,
            _recursive=True
        )
        
        # Verify return type is TaskTreeNode
        assert isinstance(copied_tree, TaskTreeNode)
        
        # Verify root task
        assert copied_tree.task.origin_type == TaskOriginType.copy
        assert copied_tree.task.original_task_id == root.id
        
        # Verify children are copied
        assert len(copied_tree.children) == 2
        for child_node in copied_tree.children:
            assert child_node.task.origin_type == TaskOriginType.copy
            assert child_node.task.parent_id == copied_tree.task.id
    
    @pytest.mark.asyncio
    async def test_from_copy_recursive_tree_no_save(self, sync_db_session):
        """Test copying entire task tree without saving returns task array"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree
        root = await task_manager.task_repository.create_task(
            name="Root Task",
            user_id="user_123",
        )
        
        await task_manager.task_repository.create_task(
            name="Child",
            user_id="user_123",
            parent_id=root.id,
        )
        
        root.has_children = True
        sync_db_session.commit()
        
        result = await creator.from_copy(
            _original_task=root,
            _save=False,
            _recursive=True
        )
        
        # Verify return type is List[Dict] when save=False
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], dict)
        
        # Verify task array has required fields
        for task_dict in result:
            assert "id" in task_dict
            assert "name" in task_dict
            assert "origin_type" in task_dict
    
    @pytest.mark.asyncio
    async def test_from_copy_with_auto_include_deps_true(self, sync_db_session):
        """Test copying task with _auto_include_deps=True includes upstream dependencies"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task with upstream dependency
        # dep_task -> task_a (task_a depends on dep_task)
        dep_task = await task_manager.task_repository.create_task(
            name="Dependency Task",
            user_id="user_123",
        )
        
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
            dependencies=[{"id": dep_task.id, "required": True}]
        )
        
        # Copy task_a with auto_include_deps=True (should raise ValueError due to external dependency)
        with pytest.raises(ValueError, match="external dependencies"):
            await creator.from_copy(
                _original_task=task_a,
                _save=True,
                _recursive=True,
                _auto_include_deps=True
            )
    
    @pytest.mark.asyncio
    async def test_from_copy_with_auto_include_deps_false(self, sync_db_session):
        """Test copying task with _auto_include_deps=False doesn't auto-include dependencies"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task with upstream dependency
        dep_task = await task_manager.task_repository.create_task(
            name="Dependency Task",
            user_id="user_123",
        )
        
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
            dependencies=[{"id": dep_task.id, "required": True}]
        )
        
        # Copy task_a with auto_include_deps=False (should raise ValueError due to external dependency)
        with pytest.raises(ValueError, match="external dependencies"):
            await creator.from_copy(
                _original_task=task_a,
                _save=True,
                _recursive=True,
                _auto_include_deps=False
            )
    
    @pytest.mark.asyncio
    async def test_from_copy_include_dependents_non_root_task(self, sync_db_session):
        """Test _include_dependents=True includes downstream dependent tasks for non-root"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task_a with child task_b
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
        )
        
        await task_manager.task_repository.create_task(
            name="Task B",
            user_id="user_123",
            parent_id=task_a.id,
        )
        
        # Create external task that depends on task_a
        await task_manager.task_repository.create_task(
            name="Dependent Task",
            user_id="user_123",
            dependencies=[{"id": task_a.id, "required": True}]
        )
        
        task_a.has_children = True
        sync_db_session.commit()
        
        # Copy task_a with include_dependents=True
        copied_tree = await creator.from_copy(
            _original_task=task_a,
            _save=True,
            _recursive=True,
            _include_dependents=True
        )
        
        # Verify task is copied with children
        assert isinstance(copied_tree, TaskTreeNode)
        assert copied_tree.task.origin_type == TaskOriginType.copy
        assert len(copied_tree.children) == 1
    
    @pytest.mark.asyncio
    async def test_from_copy_include_dependents_ignored_for_root(self, sync_db_session):
        """Test _include_dependents is ignored when task is root"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create root task with child
        root = await task_manager.task_repository.create_task(
            name="Root Task",
            user_id="user_123",
        )
        
        await task_manager.task_repository.create_task(
            name="Child",
            user_id="user_123",
            parent_id=root.id,
        )
        
        # Create external task that depends on root
        await task_manager.task_repository.create_task(
            name="External",
            user_id="user_123",
            dependencies=[{"id": root.id, "required": True}]
        )
        
        root.has_children = True
        sync_db_session.commit()
        
        # Copy root with include_dependents=True
        # Should ignore include_dependents since root is a root task
        copied_tree = await creator.from_copy(
            _original_task=root,
            _save=True,
            _recursive=True,
            _include_dependents=True
        )
        
        # Verify only the subtree is copied (not the external dependent)
        assert isinstance(copied_tree, TaskTreeNode)
        assert len(copied_tree.children) == 1
        assert copied_tree.task.parent_id is None


class TestTaskCreatorFromSnapshot:
    """Test TaskCreator.from_snapshot method"""
    
    @pytest.mark.asyncio
    async def test_from_snapshot_single_task(self, sync_db_session):
        """Test snapshotting a single task"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        completed_task = await task_manager.task_repository.create_task(
            name="Completed Task",
            user_id="user_123",
            priority=2,
            inputs={"key": "value"},
            status="completed",
            result={"output": "result_value"},
            progress=1.0,
        )
        
        snapshot_task = await creator.from_snapshot(
            _original_task=completed_task,
            _save=True,
            _recursive=False
        )
        
        # Verify origin type is snapshot
        assert snapshot_task.origin_type == TaskOriginType.snapshot
        
        # Verify snapshot preserves fields
        assert snapshot_task.name == completed_task.name
        assert snapshot_task.result == completed_task.result
        assert snapshot_task.status == completed_task.status
        assert snapshot_task.progress == completed_task.progress
        
        # Verify it's a different task
        assert snapshot_task.id != completed_task.id
    
    @pytest.mark.asyncio
    async def test_from_snapshot_recursive_tree(self, sync_db_session):
        """Test snapshotting entire task tree"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree
        root = await task_manager.task_repository.create_task(
            name="Root Task",
            user_id="user_123",
            status="completed",
            progress=1.0,
        )
        
        await task_manager.task_repository.create_task(
            name="Child Task",
            user_id="user_123",
            parent_id=root.id,
            status="completed",
            progress=1.0,
        )
        
        root.has_children = True
        sync_db_session.commit()
        
        snapshot_tree = await creator.from_snapshot(
            _original_task=root,
            _save=True,
            _recursive=True
        )
        
        # Verify return type is TaskTreeNode
        assert isinstance(snapshot_tree, TaskTreeNode)
        
        # Verify root task
        assert snapshot_tree.task.origin_type == TaskOriginType.snapshot
        assert snapshot_tree.task.original_task_id == root.id
        
        # Verify children are snapshotted
        assert len(snapshot_tree.children) == 1
        assert snapshot_tree.children[0].task.origin_type == TaskOriginType.snapshot
    
    @pytest.mark.asyncio
    async def test_from_snapshot_no_save(self, sync_db_session):
        """Test snapshotting without saving returns task"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        completed_task = await task_manager.task_repository.create_task(
            name="Completed Task",
            user_id="user_123",
            status="completed",
        )
        
        result = await creator.from_snapshot(
            _original_task=completed_task,
            _save=False,
            _recursive=False
        )
        
        # Verify return type is TaskModel (single task, no recursion)
        assert isinstance(result, TaskModel)

    @pytest.mark.asyncio
    async def test_from_snapshot_with_auto_include_deps_true(self, sync_db_session):
        """Snapshot with _auto_include_deps=True includes upstream dependencies in minimal subtree"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        dep_task = await task_manager.task_repository.create_task(
            name="Dependency Task",
            user_id="user_123",
        )
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
            dependencies=[{"id": dep_task.id, "required": True}]
        )
        
        snapshot_tree = await creator.from_snapshot(
            _original_task=task_a,
            _save=True,
            _recursive=True,
            _auto_include_deps=True
        )
        
        assert isinstance(snapshot_tree, TaskTreeNode)
        assert snapshot_tree.task.origin_type == TaskOriginType.snapshot
        assert snapshot_tree.task.original_task_id == task_a.id

    @pytest.mark.asyncio
    async def test_from_snapshot_with_auto_include_deps_false(self, sync_db_session):
        """Snapshot with _auto_include_deps=False does not attempt to resolve dependencies"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        dep_task = await task_manager.task_repository.create_task(
            name="Dependency Task",
            user_id="user_123",
        )
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
            dependencies=[{"id": dep_task.id, "required": True}]
        )
        
        # Snapshot with _auto_include_deps=False (should raise ValueError due to external dependency)
        with pytest.raises(ValueError, match="external dependencies"):
            await creator.from_snapshot(
                _original_task=task_a,
                _save=True,
                _recursive=True,
                _auto_include_deps=False
            )

    @pytest.mark.asyncio
    async def test_from_snapshot_include_dependents_non_root_task(self, sync_db_session):
        """_include_dependents=True includes downstream dependents for non-root snapshot operations"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
        )
        task_b = await task_manager.task_repository.create_task(
            name="Task B",
            user_id="user_123",
            parent_id=task_a.id,
        )
        await task_manager.task_repository.create_task(
            name="Dependent Task",
            user_id="user_123",
            dependencies=[{"id": task_b.id, "required": True}]
        )
        task_a.has_children = True
        sync_db_session.commit()
        
        snapshot_tree = await creator.from_snapshot(
            _original_task=task_b,
            _save=True,
            _recursive=True,
            _include_dependents=True
        )
        
        assert isinstance(snapshot_tree, TaskTreeNode)
        assert snapshot_tree.task.origin_type == TaskOriginType.snapshot


class TestTaskCreatorFromMixed:
    """Test TaskCreator.from_mixed method"""
    
    @pytest.mark.asyncio
    async def test_from_mixed_link_specific_tasks(self, sync_db_session):
        """Test mixed mode with specific tasks to link"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree
        root = await task_manager.task_repository.create_task(
            name="Root Task",
            user_id="user_123",
            priority=1,
        )
        
        child1 = await task_manager.task_repository.create_task(
            name="Child 1",
            user_id="user_123",
            parent_id=root.id,
            priority=2,
        )
        
        await task_manager.task_repository.create_task(
            name="Child 2",
            user_id="user_123",
            parent_id=root.id,
            dependencies=[{"id": child1.id, "required": True}],
        )
        
        await task_manager.task_repository.create_task(
            name="Grandchild 1",
            user_id="user_123",
            parent_id=child1.id,
        )
        
        root.has_children = True
        child1.has_children = True
        sync_db_session.commit()
        
        # Link root and child1, copy others
        mixed_tree = await creator.from_mixed(
            _original_task=root,
            _save=True,
            _recursive=True,
            _link_task_ids=[root.id, child1.id]
        )
        
        # Verify return type is TaskTreeNode
        assert isinstance(mixed_tree, TaskTreeNode)
        
        # Verify root is linked
        assert mixed_tree.task.origin_type == TaskOriginType.link
        
        # Verify mixed origin types exist
        origin_types = {mixed_tree.task.origin_type}
        for child in mixed_tree.children:
            origin_types.add(child.task.origin_type)
        
        # Should have mixed types
        assert len(origin_types) >= 1
    
    @pytest.mark.asyncio
    async def test_from_mixed_single_task_link(self, sync_db_session):
        """Test mixed mode for single task - link"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        task = await task_manager.task_repository.create_task(
            name="Test Task",
            user_id="user_123",
        )
        
        await creator.from_mixed(
            _original_task=task,
            _save=True,
            _recursive=False,
            _link_task_ids=[task.id]
        )

    
    @pytest.mark.asyncio
    async def test_from_mixed_single_task_copy(self, sync_db_session):
        """Test mixed mode for single task - copy"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        task = await task_manager.task_repository.create_task(
            name="Test Task",
            user_id="user_123",
        )
        
        # Ensure task is refreshed before use
        sync_db_session.refresh(task)
        
        mixed_task = await creator.from_mixed(
            _original_task=task,
            _save=True,
            _recursive=False,
            _link_task_ids=[],  # Empty list means no tasks to link, so copy
        )
        
        # Verify task is copied
        assert mixed_task.origin_type == TaskOriginType.copy
    
    @pytest.mark.asyncio
    async def test_from_mixed_with_field_override(self, sync_db_session):
        """Test mixed mode with field overrides for copied tasks"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create task tree
        root = await task_manager.task_repository.create_task(
            name="Root Task",
            user_id="user_123",
        )
        
        await task_manager.task_repository.create_task(
            name="Child",
            user_id="user_123",
            parent_id=root.id,
        )
        
        root.has_children = True
        sync_db_session.commit()
        
        mixed_tree = await creator.from_mixed(
            _original_task=root,
            _save=True,
            _recursive=True,
            _link_task_ids=[root.id],  # Only link root
            user_id="new_user_789",
            inputs={"override": "value"}
        )
        
        # Verify root is linked (no overrides applied)
        assert mixed_tree.task.origin_type == TaskOriginType.link
        
        # Verify children that are copied have the overrides
        for child_node in mixed_tree.children:
            if child_node.task.origin_type == TaskOriginType.copy:
                assert child_node.task.user_id == "new_user_789"
                assert child_node.task.inputs == {"override": "value"}
    
    @pytest.mark.asyncio
    async def test_from_mixed_no_save(self, sync_db_session):
        """Test mixed mode without saving returns task array"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create simple task
        root = await task_manager.task_repository.create_task(
            name="Root Task",
            user_id="user_123",
        )
        
        result = await creator.from_mixed(
            _original_task=root,
            _save=False,
            _recursive=True,
            _link_task_ids=[root.id]
        )
        
        # Verify return type is List[Dict]
        assert isinstance(result, list)
        assert all(isinstance(item, dict) for item in result)

    @pytest.mark.asyncio
    async def test_from_mixed_auto_include_deps_on_copied_portion(self, sync_db_session):
        """Mixed mode: auto include upstream deps only for copied tasks"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Build simple tree: A (root) -> B (child)
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
        )
        task_b = await task_manager.task_repository.create_task(
            name="Task B",
            user_id="user_123",
            parent_id=task_a.id,
        )
        task_a.has_children = True
        sync_db_session.commit()
        
        # B depends on external dep
        dep_task = await task_manager.task_repository.create_task(
            name="Dependency Task",
            user_id="user_123",
        )
        task_b.dependencies = [{"id": dep_task.id, "required": True}]
        sync_db_session.commit()
        
        # Link A, copy B (copied portion should include deps when flag is True)
        mixed_tree = await creator.from_mixed(
            _original_task=task_a,
            _save=True,
            _recursive=True,
            _link_task_ids=[str(task_a.id)],
            _auto_include_deps=True
        )
        
        assert isinstance(mixed_tree, TaskTreeNode)
        assert mixed_tree.task.origin_type in (TaskOriginType.link, TaskOriginType.copy)
        
    @pytest.mark.asyncio
    async def test_from_mixed_include_dependents_on_copied_portion(self, sync_db_session):
        """Mixed mode: include downstream dependents only for copied tasks"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Build tree where original_task is non-root: R -> A -> B
        root = await task_manager.task_repository.create_task(
            name="Root",
            user_id="user_123",
        )
        task_a = await task_manager.task_repository.create_task(
            name="Task A",
            user_id="user_123",
            parent_id=root.id,
        )
        task_b = await task_manager.task_repository.create_task(
            name="Task B",
            user_id="user_123",
            parent_id=task_a.id,
        )
        root.has_children = True
        task_a.has_children = True
        sync_db_session.commit()
        
        # External dependent on B
        await task_manager.task_repository.create_task(
            name="Dependent Task",
            user_id="user_123",
            dependencies=[{"id": task_b.id, "required": True}]
        )
        
        # Operate from A (non-root). Link A, copy B. Include dependents should apply to copied B.
        mixed_tree = await creator.from_mixed(
            _original_task=task_a,
            _save=True,
            _recursive=True,
            _link_task_ids=[str(task_a.id)],
            _include_dependents=True
        )
        
        assert isinstance(mixed_tree, TaskTreeNode)
        assert mixed_tree.task.origin_type in (TaskOriginType.link, TaskOriginType.copy)


class TestTaskCreatorEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_from_copy_task_with_external_dependency(self, sync_db_session):
        """Test that copying task with external dependency raises error"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create two separate tasks
        task1 = await task_manager.task_repository.create_task(
            name="Task 1",
            user_id="user_123",
        )
        
        task2 = await task_manager.task_repository.create_task(
            name="Task 2",
            user_id="user_123",
            dependencies=[{"id": task1.id, "required": True}]
        )
        
        # Try to copy task2 recursively (external dependency on task1)
        with pytest.raises(ValueError, match="external dependencies"):
            await creator.from_copy(
                _original_task=task2,
                _save=True,
                _recursive=True
            )
    
    @pytest.mark.asyncio
    async def test_from_copy_promotes_non_root_task(self, sync_db_session):
        """Test that copying non-root task promotes it to independent tree"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)
        
        # Create parent and child
        parent = await task_manager.task_repository.create_task(
            name="Parent",
            user_id="user_123",
        )
        
        child = await task_manager.task_repository.create_task(
            name="Child",
            user_id="user_123",
            parent_id=parent.id,
        )
        
        parent.has_children = True
        sync_db_session.commit()
        
        # Copy child (non-root)
        copied_tree = await creator.from_copy(
            _original_task=child,
            _save=True,
            _recursive=True
        )
        
        # Verify root's parent_id is None
        assert copied_tree.task.parent_id is None
        
        # Verify task_tree_id is set to root
        assert copied_tree.task.task_tree_id == copied_tree.task.id
    
    @pytest.mark.asyncio
    async def test_origin_type_immutability(self, sync_db_session):
        """Test that origin_type is set correctly for each operation (all must be completed for link)"""
        task_manager = TaskManager(sync_db_session)
        creator = TaskCreator(sync_db_session)

        original = await task_manager.task_repository.create_task(
            name="Original",
            user_id="user_123",
            status="completed",
        )
        # Ensure completed
        original.status = "completed"
        sync_db_session.commit()

        # Test each origin type
        linked = await creator.from_link(_original_task=original, _recursive=False)
        assert linked.origin_type == TaskOriginType.link

        copied = await creator.from_copy(_original_task=original, _recursive=False)
        assert copied.origin_type == TaskOriginType.copy

        snapshot = await creator.from_snapshot(_original_task=original, _recursive=False)
        assert snapshot.origin_type == TaskOriginType.snapshot

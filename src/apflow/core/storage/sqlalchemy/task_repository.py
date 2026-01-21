"""
Task repository for task database operations

This module provides a TaskRepository class that encapsulates all database operations
for tasks. TaskManager should use TaskRepository instead of directly operating on db session.
"""

from asyncio import Task
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING, Type, Set
from apflow.core.storage.sqlalchemy.models import TaskModel, TaskOriginType, TaskModelType
from apflow.core.execution.errors import ValidationError
from sqlalchemy_session_proxy import SqlalchemySessionProxy
from apflow.logger import get_logger

if TYPE_CHECKING:
    from apflow.core.types import TaskTreeNode

logger = get_logger(__name__)


class TaskRepository():
    """
    Task repository for database operations
    
    Provides methods for:
    - Creating, updating, and deleting tasks
    - Building task trees
    - Querying tasks by various criteria
    - Managing task hierarchies
    
    TaskManager should use this repository instead of directly operating on db session.
    
    Supports custom TaskModel classes via task_model_class parameter.
    Users can pass their custom TaskModel subclass to support custom fields.
    
    Example:
        # Use default TaskModel
        repo = TaskRepository(db)
        
        # Use custom TaskModel with additional fields
        repo = TaskRepository(db, task_model_class=MyTaskModel)
        task = await repo.create_task(..., project_id="proj-123")  # Custom field
    """
    
    def __init__(
        self,
        db: Union[Session, AsyncSession],
        task_model_class: Type[TaskModelType] = TaskModel
    ):
        """
        Initialize TaskRepository
        
        Args:
            db: Database session (sync or async)
            task_model_class: Custom TaskModel class (default: TaskModel)
                Users can pass their custom TaskModel subclass that inherits TaskModel
                to add custom fields (e.g., project_id, department, etc.)
                Example: TaskRepository(db, task_model_class=MyTaskModel)
        """
        self.db = SqlalchemySessionProxy(db)
        self.task_model_class = task_model_class

    def build_task(self, **kwargs: Any) -> TaskModelType:
        """
        Build a TaskModel instance without saving to database
        
        Args:
            **kwargs: Fields to set on the task
            
        Returns:
            TaskModel instance (or custom TaskModel subclass if configured)
        """
        task = self.task_model_class.create(kwargs)
        return task
    
    async def create_task(
        self,
        name: str,
        **kwargs  # User-defined custom fields (e.g., project_id, department, etc.)
    ) -> TaskModelType:
        """
        Create a new task
        
        Args:
            name: Task name
            **kwargs: These fields will be set on the task if they exist as columns in the TaskModel
            
        Returns:
            Created TaskModel instance (or custom TaskModel subclass if configured)
        """
        
        # Create task instance using configured TaskModel class
        task = self.task_model_class.create({"name": name, **kwargs})
        
        self.db.add(task)
        
        try:
            await self.db.commit()
            await self.db.refresh(task)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating task: {str(e)}")
            raise
        
        return task
    
    async def get_task_by_id(self, task_id: str) -> Optional[TaskModelType]:
        """
        Get a task by ID using standard ORM query
        
        Args:
            task_id: Task ID
            
        Returns:
            TaskModel instance (or custom TaskModel subclass) or None if not found
        """
        try:
            stmt = select(self.task_model_class).where(self.task_model_class.id == task_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting task by id {task_id}: {str(e)}")
            raise
    
    async def get_child_tasks_by_parent_id(self, parent_id: str) -> List[TaskModelType]:
        """
        Get child tasks by parent ID
        
        Args:
            parent_id: Parent task ID
            
        Returns:
            List of child TaskModel instances (or custom TaskModel subclass), ordered by priority
        """
        try:
            stmt = select(self.task_model_class).filter(
                self.task_model_class.parent_id == parent_id
            ).order_by(self.task_model_class.priority.asc())
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting child tasks for parent {parent_id}: {str(e)}")
            return []
    
    async def get_root_task(self, task: TaskModelType) -> TaskModelType:
        """
        Get root task (traverse up the tree until parent_id is None)
        
        Args:
            task: Starting task
            
        Returns:
            Root TaskModel instance (or custom TaskModel subclass)
        """
        current_task = task
        visited_ids: Set[str] = {str(task.id)}
        
        # Traverse up to find root with cycle detection
        while current_task.parent_id:
            parent_id = str(current_task.parent_id)
            
            # Cycle detection: if we've seen this parent_id before, break to avoid infinite loop
            if parent_id in visited_ids:
                logger.warning(
                    f"Cycle detected in task tree: task {current_task.id} has parent {parent_id} "
                    f"which was already visited. Breaking to prevent infinite loop."
                )
                break
            
            visited_ids.add(parent_id)
            parent = await self.get_task_by_id(current_task.parent_id)
            if not parent:
                break
            current_task = parent
        
        return current_task
    
    async def get_all_tasks_in_tree(self, root_task: TaskModelType) -> List[TaskModelType]:
        """
        Get all tasks in the task tree (recursive)
        
        Args:
            root_task: Root task of the tree
            
        Returns:
            List of all tasks in the tree (or custom TaskModel subclass)
        """

        task_tree_id = getattr(root_task, 'task_tree_id', None)
        is_root_task = root_task.parent_id is None
        if is_root_task and task_tree_id:
            try:
                # Fast path: single query to get all tasks in tree
                all_tasks = await self.get_tasks_by_tree_id(task_tree_id)
                logger.debug(f"✅ [OPTIMIZED] Used task_tree_id fast path for task {root_task.id}")
                return all_tasks
            except (ValueError, AttributeError) as e:
                # task_tree_id exists but get_tasks_by_tree_id failed (data inconsistency)
                # Fall back to slow path
                logger.warning(
                    f"⚠️ [FALLBACK] Fast path failed for task {root_task.id} with task_tree_id={task_tree_id}: {str(e)}. "
                    f"Falling back to slow path (get_root_task + build_task_tree)."
                )

        all_tasks = [root_task]
        
        # Get all child tasks recursively
        async def get_children(parent_id: str):
            children = await self.get_child_tasks_by_parent_id(parent_id)
            for child in children:
                all_tasks.append(child)
                await get_children(child.id)
        
        await get_children(root_task.id)
        return all_tasks

    async def get_tasks_by_tree_id(self, tree_id: str) -> List[TaskModelType]:
        """
        Get tasks by task tree ID.
        All tasks in the same task tree share the same tree_id value,
        which allows efficient querying and tree reconstruction without traversing
        parent_id relationships.

        This method is optimized for recursive query scenarios where you need to
        get all tasks in a tree with a single query instead of recursive parent_id
        traversals.

        Note:
            This method does NOT validate root task existence. If you need to ensure
            a root task exists (e.g., for tree building), validate it yourself:
            parent_task = [task for task in tasks if task.parent_id is None]

        Args:
            tree_id: The tree_id value shared by all tasks in the tree.

        Returns:
            List of all tasks with the given tree_id (may include root task or not)

        """
        # CRITICAL: Use expire_all() before query to ensure fresh data in concurrent environments
        # This prevents stale data when other servers update task status in load-balanced environments
        # Avoid using refresh() as it can hang if there are database locks
        self.db.expire_all()
        stmt = select(self.task_model_class).filter(
            self.task_model_class.task_tree_id == tree_id
        ).order_by(self.task_model_class.priority.asc())
        result = await self.db.execute(stmt)
        return result.scalars().all()


    async def build_task_tree_by_tree_id(self, tree_id: str) -> "TaskTreeNode":
        """
        Build a complete task tree structure by tree_id.
        
        All tasks in the same task tree share the same tree_id value,
        which allows efficient querying and tree reconstruction without traversing
        parent_id relationships.
        
        Process:
        1. Query all tasks with the given tree_id
        2. Validate that tasks exist and root task is found
        3. Build tree structure recursively starting from root task
        
        Args:
            tree_id: The tree_id value shared by all tasks in the tree.
        
        Returns:
            TaskTreeNode representing the root of the task tree with all children recursively built.
        
        Note:
            This method assumes all tasks with the same tree_id belong to the same tree.
        """
        # Get all tasks in tree - get_tasks_by_tree_id validates data integrity
        # but does not validate root task existence (for flexibility)
        # CRITICAL: get_tasks_by_tree_id now uses expire_all() to ensure fresh data
        # in concurrent environments, but we should still refresh tasks before building tree
        # to ensure we have the absolute latest state from database
        tasks = await self.get_tasks_by_tree_id(tree_id)
        
        # CRITICAL: Refresh all tasks to ensure we have latest state from database
        # This is important in concurrent environments where task status may have changed
        # between query and tree building
        for task in tasks:
            try:
                await self.db.refresh(task)
            except Exception as refresh_error:
                # If refresh fails (e.g., task was deleted), log and continue
                logger.warning(f"Failed to refresh task {task.id} in build_task_tree_by_tree_id: {refresh_error}")

        # Find root task - required for tree building
        root_task = [task for task in tasks if task.parent_id is None]
        if not root_task:
            logger.error(f"Root task not found for tree_id {tree_id}")
            raise ValidationError(f"Root task not found for tree_id {tree_id}")
        
        # Lazy import to avoid circular dependency
        from apflow.core.types import TaskTreeNode

        # Build tree structure starting from root task
        task_tree = TaskTreeNode(task=root_task[0])

        def add_children(task: Task, task_tree: TaskTreeNode):
            """
            Recursively add child tasks to the tree structure.
            
            For each task in the flat list, if it has the current task as parent,
            add it as a child node. If the child has children (has_children=True),
            recursively build its subtree before adding.
            
            Args:
                task: Current parent task to find children for
                task_tree: Current tree node to add children to
            """
            for child in tasks:
                # Check if this task is a child of the current parent task
                if str(child.parent_id) == str(task.id):
                    if bool(child.has_children):
                        # Child has children: create subtree and recursively add grandchildren
                        child_task_tree = TaskTreeNode(task=child)
                        add_children(child, child_task_tree)
                        # CRITICAL: Add the child subtree to the parent tree
                        # This was missing in the original implementation
                        task_tree.add_child(child_task_tree)
                    else:
                        # Leaf node: add directly without recursion
                        task_tree.add_child(TaskTreeNode(task=child))

        # Start recursive tree building from root task
        add_children(root_task[0], task_tree)
        
        return task_tree
    
    async def build_task_tree(self, task: TaskModelType) -> "TaskTreeNode":
        """
        Build TaskTreeNode for a task with its children (recursive)
        
        Args:
            task: Root task (or custom TaskModel subclass)
            
        Returns:
            TaskTreeNode instance with all children recursively built
        """
        task_tree_id = getattr(task, 'task_tree_id', None)
        is_root_task = task.parent_id is None
        if is_root_task and task_tree_id:
            try:
                # Fast path: single query to get all tasks in tree
                task_tree = await self.build_task_tree_by_tree_id(task_tree_id)
                logger.debug(f"✅ [OPTIMIZED] Used task_tree_id fast path for task {task.id}")
                return task_tree
            except (ValueError, AttributeError) as e:
                # task_tree_id exists but tree build failed (data inconsistency)
                # Fall back to slow path
                logger.warning(
                    f"⚠️ [FALLBACK] Fast path failed for task {task.id} with task_tree_id={task_tree_id}: {str(e)}. "
                    f"Falling back to slow path (get_root_task + build_task_tree)."
                )
                
        # Lazy import to avoid circular dependency
        from apflow.core.types import TaskTreeNode
        
        # Get all child tasks
        child_tasks = await self.get_child_tasks_by_parent_id(task.id)
        
        # Create the main task node
        task_node = TaskTreeNode(task=task)
        
        # Add child tasks recursively
        for child_task in child_tasks:
            child_node = await self.build_task_tree(child_task)
            task_node.add_child(child_node)
        
        return task_node
    

    async def update_task(self, task_id: str, **fields: Any) -> TaskModelType:
        """
        Update arbitrary fields of a task.

        TODO: check dependencies and validate for task tree if dependencies exist

        Args:
            task_id: Task ID
            **fields: Fields to update (e.g., status="completed", inputs={...})

        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task with id {task_id} not found")

            task.update_from_dict(fields)   

            for key, _ in fields.items():
                if hasattr(task, key):
                    # Mark JSON fields as modified for SQLAlchemy change detection
                    if task.is_json_field(key):
                        flag_modified(task, key)

            await self.db.commit()
            await self.db.refresh(task)
            logger.info(f"Updated task {task_id} fields: {list(fields.keys())}")
            return task

        except Exception as e:
            logger.error(f"Error updating task {task_id}: {str(e)}")
            await self.db.rollback()
            raise

        
    async def get_completed_tasks_by_id(self, task: TaskModelType) -> Dict[str, TaskModelType]:
        """
        Get all completed tasks in the same task tree by id
        
        Args:
            task: Task to get sibling tasks for
            
        Returns:
            Dictionary mapping task ids to completed TaskModelType instances
        """
        # Get root task to find all tasks in the tree
        root_task = await self.get_root_task(task)
        
        # Get all tasks in the tree
        all_tasks = await self.get_all_tasks_in_tree(root_task)
        
        # Filter completed tasks with results
        completed_tasks = [
            t for t in all_tasks 
            if t.status == "completed" and t.result is not None
        ]
        
        # Create a map of completed tasks by id
        completed_tasks_by_id = {t.id: t for t in completed_tasks}
        
        return completed_tasks_by_id


    async def get_completed_tasks_by_ids(self, task_ids: List[str]) -> Dict[str, TaskModelType]:
        """
        Get completed tasks by a list of IDs
        
        Args:
            task_ids: List of task IDs
            
        Returns:
            Dictionary mapping task_id to TaskModel (or custom TaskModel subclass) for completed tasks
        """
        if not task_ids:
            return {}
        
        try:
            stmt = select(self.task_model_class).filter(
                self.task_model_class.id.in_(task_ids),
                self.task_model_class.status == "completed"
            )
            result = await self.db.execute(stmt)
            tasks = result.scalars().all()
            return {task.id: task for task in tasks}
            
        except Exception as e:
            logger.error(f"Error getting completed tasks by IDs: {str(e)}")
            return {}
    
    async def query_tasks(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        parent_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> List[TaskModelType]:
        """
        Query tasks with filters and pagination
        
        Args:
            user_id: Optional user ID filter
            status: Optional status filter (e.g., "completed", "pending", "in_progress", "failed")
            parent_id: Optional parent ID filter. If None, no filter. If empty string "", filter for root tasks (parent_id is None)
            limit: Maximum number of tasks to return (default: 100)
            offset: Number of tasks to skip (default: 0)
            order_by: Field to order by (default: "created_at")
            order_desc: If True, order descending; if False, order ascending (default: True)
            
        Returns:
            List of TaskModel instances (or custom TaskModel subclass) matching the criteria
        """
        try:
            # Build query
            stmt = select(self.task_model_class)
            
            # Apply filters
            if user_id is not None:
                stmt = stmt.filter(self.task_model_class.user_id == user_id)
            
            if status is not None:
                stmt = stmt.filter(self.task_model_class.status == status)
            
            # Apply parent_id filter
            if parent_id is not None:
                if parent_id == "":
                    # Empty string means filter for root tasks (parent_id is None)
                    stmt = stmt.filter(self.task_model_class.parent_id.is_(None))
                else:
                    # Specific parent_id
                    stmt = stmt.filter(self.task_model_class.parent_id == parent_id)
            
            # Apply ordering
            order_column = getattr(self.task_model_class, order_by, None)
            if order_column is not None:
                if order_desc:
                    stmt = stmt.order_by(order_column.desc())
                else:
                    stmt = stmt.order_by(order_column.asc())
            
            # Apply pagination
            stmt = stmt.offset(offset).limit(limit)
            result = await self.db.execute(stmt)
            tasks = result.scalars().all()
            
            return list(tasks)
            
        except Exception as e:
            logger.error(f"Error querying tasks: {str(e)}")
            return []
    

    async def _set_original_task_has_reference_to_true(self, original_task_id: str) -> Optional[TaskModelType]:
        """Update original task's has_references flag to True"""
        if not original_task_id:
            return None
        
        original_task = await self.get_task_by_id(original_task_id)
        if original_task and hasattr(original_task, "has_references") and not getattr(original_task, "has_references", False):
            setattr(original_task, "has_references", True)
            return original_task
        
        return None

    async def save_task_tree(self, root_node: "TaskTreeNode") -> bool:
        """Save task tree structure to database recursively"""
        try:
            changed_tasks: List[TaskModelType] = []

            # Recursively save children with proper parent_id
            child_changed_tasks = await self._save_task_tree_recursive(root_node)
            changed_tasks.extend(child_changed_tasks)
            
            self.add_tasks_in_db(changed_tasks)
            await self.db.commit()
            await self.refresh_tasks_in_db(changed_tasks)

            logger.info(f"Saved task tree: root task {root_node.task.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving task tree to database: {e}")
            self.db.rollback()
            return False
    
    async def _save_task_tree_recursive(self, parent_node: "TaskTreeNode") -> List[TaskModelType]:
        """Recursively save children tasks with proper parent_id"""
        changed_tasks: List[TaskModelType] = []

        parent_task = parent_node.task
        changed_tasks.append(parent_task)

        original_task = await self._set_original_task_has_reference_to_true(parent_task.original_task_id)
        if original_task:
            changed_tasks.append(original_task)

        for child_node in parent_node.children:
            child_task = child_node.task
            # Set parent_id to the parent task's actual ID
            child_task.parent_id = parent_node.task.id
            changed_tasks.append(child_task)

            original_task = await self._set_original_task_has_reference_to_true(child_task.original_task_id)
            if original_task:
                changed_tasks.append(original_task)
            
            # Recursively save grandchildren
            if child_node.children:
                await self._save_children_recursive(child_node)  # type: ignore

        return changed_tasks
    
    async def get_all_children_recursive(self, task_id: str) -> List[TaskModelType]:
        """
        Get all children tasks recursively (including grandchildren, etc.)
        
        Args:
            task_id: Parent task ID
            
        Returns:
            List of all child TaskModel instances (or custom TaskModel subclass) recursively
        """
        all_children = []
        
        async def collect_children(parent_id: str):
            children = await self.get_child_tasks_by_parent_id(parent_id)
            for child in children:
                all_children.append(child)
                # Recursively collect grandchildren
                await collect_children(child.id)
        
        await collect_children(task_id)
        return all_children
    
    async def delete_task(self, task_id: str) -> bool:
        """
        Physically delete a task from the database
        
        Args:
            task_id: Task ID to delete
            
        Returns:
            True if successful, False if task not found
        """
        try:
            task = await self.get_task_by_id(task_id)
            if not task:
                return False
            
                # For async session, use delete statement
            stmt = delete(self.task_model_class).where(self.task_model_class.id == task_id)
            await self.db.execute(stmt)
            await self.db.commit()
            
            logger.debug(f"Physically deleted task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {str(e)}")
            await self.db.rollback()
            return False

    async def get_task_tree_for_api(self, root_task: TaskModelType) -> "TaskTreeNode":
        """
        Get the task tree for API/CLI queries, recursively resolving link origin_type for all nodes.
        If any task (root or child) is a link, use its original task's data to build the tree, but keep allowlisted fields from the link node itself.
        The allowlist is configurable via APFLOW_TASK_LINK_KEEP_FIELDS environment variable (comma-separated).
        Args:
            root_task: The root task node to start from.
        Returns:
            TaskTreeNode for the appropriate root task, with all children resolved.
        """
        import os
        from apflow.core.types import TaskTreeNode

        # Allowlist of fields to keep from the link node itself
        default_keep_fields = [
            "id", "parent_id", "user_id", "task_tree_id", "origin_type", "created_at", "updated_at"
        ]
        keep_fields = os.getenv("APFLOW_TASK_LINK_KEEP_FIELDS")
        if keep_fields:
            keep_fields = [f.strip() for f in keep_fields.split(",") if f.strip()]
            task_fields = set(field.name for field in root_task.__table__.columns)
            # Validate keep_fields against actual task model fields
            for field in keep_fields:
                if field not in task_fields:
                    raise ValueError(f"Invalid field '{field}' in APFLOW_TASK_LINK_KEEP_FIELDS; not a valid TaskModel field.")
        else:
            keep_fields = default_keep_fields

        async def resolve_task(task: TaskModelType) -> Optional[TaskModelType]:
            # Recursively resolve link
            while getattr(task, "origin_type", None) == TaskOriginType.link and getattr(task, "original_task_id", None):
                original_task = await self.get_task_by_id(task.original_task_id)
                if not original_task:
                    logger.error(f"Original task not found for id {task.original_task_id}")
                    raise ValidationError(f"Original task not found for id {task.original_task_id}")
                task = original_task
            return task

        def merge_task(link_task: TaskModelType, original_task: TaskModelType) -> TaskModelType:
            # Use TaskModel.copy for safe copying and merging
            override = {field: getattr(link_task, field) for field in keep_fields if hasattr(link_task, field)}
            return original_task.copy(override=override)

        async def build_tree(task: TaskModelType) -> TaskTreeNode:
            if getattr(task, "origin_type", None) == TaskOriginType.link and getattr(task, "original_task_id", None):
                original_task = await resolve_task(task)
                merged_task = merge_task(task, original_task)
            else:
                merged_task = task
            node = TaskTreeNode(task=merged_task)
            child_tasks = await self.get_child_tasks_by_parent_id(merged_task.id)
            for child in child_tasks:
                child_node = await build_tree(child)
                node.add_child(child_node)
            return node

        return await build_tree(root_task)

    async def task_tree_id_exists(self, task_tree_id: str) -> bool:
        """Check if any task exists with the given task_tree_id"""
        stmt = select(self.task_model_class).filter(
            self.task_model_class.task_tree_id == task_tree_id
        ).limit(1)
        result = await self.db.execute(stmt)
        task = result.scalar_one_or_none()
        return task is not None

    async def task_has_references(
        self,
        task_id: str,
        origin_type: Optional[TaskOriginType] = None
    ) -> bool:
        """
        Check if a task is referenced by other tasks.

        Args:
            task_id: The ID of the task to check.
            origin_type: Optional origin type to filter references.

        Returns:
            True if the task is referenced, False otherwise.

        Raises:
            ValueError: If the task does not exist.
        """
        task: Optional[TaskModelType] = await self.get_task_by_id(task_id)
        if task is None:
            raise ValueError(f"Task with id {task_id} not found")

        if not hasattr(task, "has_references"):
            return False

        if not getattr(task, "has_references", False):
            return False

        filters = [self.task_model_class.original_task_id == task_id]
        if origin_type is not None:
            filters.append(self.task_model_class.origin_type == origin_type)

        stmt = select(self.task_model_class).filter(*filters).limit(1)
        result = await self.db.execute(stmt)
        reference = result.scalar_one_or_none()

        if reference is None:
            if origin_type is None:
                # only reset has_references if no origin_type filter (all references)
                logger.info(f"Resetting has_references to False for task {task_id} as no references found")
                await self.update_task(task_id, has_references=False)
            return False

        return True
    
    
    def add_tasks_in_db(self, tasks: List[TaskModelType]) -> None:
        """add tasks from database to get latest state"""
        for task in tasks:
            self.db.add(task)

    async def refresh_tasks_in_db(self, tasks: List[TaskModelType]) -> None:
        """Refresh tasks from database to get latest state"""
        for task in tasks:
            await self.db.refresh(task)

__all__ = [
    "TaskRepository",
]


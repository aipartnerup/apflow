"""
Task creation and task tree management

This module provides comprehensive functionality for creating tasks and task trees:
1. Create task trees from tasks array (JSON format)
2. Create tasks by linking to existing tasks (reference)
3. Create tasks by copying existing tasks (allows modifications)
4. Create tasks by taking archives of existing tasks (frozen, read-only)

External callers should provide tasks with resolved id and parent_id.
This module validates that dependencies exist in the array and hierarchy is correct.

"""

from typing import List, Dict, Any, Optional, Set
import uuid
import os
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from apflow.core.types import TaskTreeNode, TaskStatus
from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
from apflow.core.storage.sqlalchemy.models import TaskModel, TaskOriginType
from apflow.logger import get_logger
from apflow.core.config import get_task_model_class
from apflow.core.storage.sqlalchemy.session_proxy import SqlalchemySessionProxy

logger = get_logger(__name__)


DEFAULT_MAX_DEPTH = os.getenv("APFLOW_MAX_DEPTH", 100)
DEFAULT_MAX_DEPTH = int(DEFAULT_MAX_DEPTH) if DEFAULT_MAX_DEPTH else 100

class TaskCreator:
    """
    Task creation and task tree management
    
    This class provides comprehensive functionality for creating tasks and task trees:
    1. Create task trees from tasks array (JSON format)
    2. Create tasks by linking to existing tasks (reference)
    3. Create tasks by copying existing tasks (allows modifications)
    4. Create tasks by taking archives of existing tasks (frozen, read-only)
    
    External callers should provide tasks with resolved id and parent_id.
    This module validates that dependencies exist in the array and hierarchy is correct.
    
    Public methods:
        - create_task_tree_from_array(): Create task tree from tasks array
        - from_link(): Create task by linking to existing task (reference)
        - from_copy(): Create task by copying existing task (allows modifications)
        - from_archive(): Create task by taking archive of existing task (frozen)
        - from_mixed(): Create task tree with mixed origin types (copy + link)
    """
    
    def __init__(self, db: Session | AsyncSession):
        """
        Initialize TaskCreator
        
        Args:
            db: Database session (sync or async)
        """
        self.db = SqlalchemySessionProxy(db)
        self.task_repository = TaskRepository(db)


    async def create_task_tree_from_array(self, tasks: List[Dict[str, Any]]) -> TaskTreeNode:
        """
        Create task tree from tasks array
        Args:
            tasks: Array of task objects in JSON format. Each task must have:
                - id: Task ID (optional) - if provided, ALL tasks must have id and use id for references
                - name: Task name (required) - if id is not provided, ALL tasks must not have id, 
                    name must be unique and used for references
                - user_id: User ID (optional, can be None) - if not provided, will be None
                - priority: Priority level (optional, default: 1)
                - inputs: Execution-time input parameters (optional)
                - schemas: Task schemas (optional)
                - params: Task parameters (optional)
                - parent_id: Parent task ID or name (optional)
                    - If all tasks have id: use id value
                    - If all tasks don't have id: use name value (name must be unique)
                    - Mixed mode (some with id, some without) is not supported
                    - parent_id must reference a task within the same array, or be None for root tasks
                - dependencies: Dependencies list (optional)
                    - Each dependency must have "id" or "name" field pointing to a task in the array
                    - Will be validated to ensure the dependency exists and hierarchy is correct
                - Any other TaskModel fields
            
        Returns:
            TaskTreeNode: Root task node of the created task tree
            
        Raises:
            ValueError: If tasks array is empty, invalid, or dependencies are invalid
        """
        if not tasks:
            raise ValueError("Tasks array cannot be empty")
        
        logger.info(f"Creating task tree from {len(tasks)} tasks")
        
        # Step 1: Extract and validate task identifiers (id or name)
        # Rule: Either all tasks have id, or all tasks don't have id (use name)
        # Mixed mode is not supported for clarity and consistency
        provided_ids: Set[str] = set()
        provided_id_to_index: Dict[str, int] = {}  # provided_id -> index in array
        task_names: Set[str] = set()
        task_name_to_index: Dict[str, int] = {}  # task_name -> index in array
        
        # First pass: check if all tasks have id or all don't have id
        tasks_with_id = 0
        tasks_without_id = 0
        
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            if not task_name:
                raise ValueError(f"Task at index {index} must have a 'name' field")
            
            provided_id = task_data.get("id")
            if provided_id:
                tasks_with_id += 1
            else:
                tasks_without_id += 1
        
        # Validate: either all have id or all don't have id
        if tasks_with_id > 0 and tasks_without_id > 0:
            raise ValueError(
                "Mixed mode not supported: either all tasks must have 'id', or all tasks must not have 'id'. "
                f"Found {tasks_with_id} tasks with id and {tasks_without_id} tasks without id."
            )
        
        # Second pass: build identifier maps
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            provided_id = task_data.get("id")
            
            if provided_id:
                # Task has id - validate uniqueness
                if provided_id in provided_ids:
                    raise ValueError(f"Duplicate task id '{provided_id}' at index {index}")
                provided_ids.add(provided_id)
                provided_id_to_index[provided_id] = index
            else:
                # Task has no id - must use name, and name must be unique
                if task_name in task_names:
                    raise ValueError(
                        f"Task at index {index} has no 'id' but name '{task_name}' is not unique. "
                        f"When using name-based references, all task names must be unique."
                    )
                task_names.add(task_name)
                task_name_to_index[task_name] = index
        
        # Step 2: Validate all tasks first (parent_id, dependencies)
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            provided_id = task_data.get("id")
            
            # Validate parent_id exists in the array (if provided)
            # parent_id can be either id (if tasks have id) or name (if tasks don't have id)
            # parent_id must reference a task within the same array, or be None for root tasks
            parent_id = task_data.get("parent_id")
            if parent_id:
                if parent_id not in provided_ids and parent_id not in task_names:
                    raise ValueError(
                        f"Task '{task_name}' at index {index} has parent_id '{parent_id}' "
                        f"which is not in the tasks array (not found as id or name). "
                        f"parent_id must reference a task within the same array."
                    )
            
            # Validate dependencies exist in the array
            dependencies = task_data.get("dependencies")
            if dependencies:
                self._validate_dependencies(
                    dependencies, task_name, index, provided_ids, provided_id_to_index,
                    task_names, task_name_to_index
                )
        
        # Step 2.5: Detect circular dependencies before creating tasks
        self._detect_circular_dependencies(
            tasks, provided_ids, provided_id_to_index, task_names, task_name_to_index
        )
        
        # Step 2.6: Validate dependent task inclusion
        # Ensure all tasks that depend on tasks in the tree are also included
        self._validate_dependent_task_inclusion(
            tasks, provided_ids, task_names
        )
        
        # Step 3: Create all tasks
        created_tasks: List[TaskModel] = []
        identifier_to_task: Dict[str, TaskModel] = {}  # id or name -> TaskModel
        
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            provided_id = task_data.get("id")
            
            # user_id is optional (can be None) - get directly from task_data
            task_user_id = task_data.get("user_id")
            
            # Check if provided_id already exists in database
            # If it exists, generate a new UUID to avoid primary key conflict
            actual_id = provided_id
            if provided_id:
                # Refresh session state before query to ensure we see latest database state
                # This prevents blocking in sync sessions when there are uncommitted transactions
                self.db.expire_all()
                existing_task = await self.task_repository.get_task_by_id(provided_id)
                if existing_task:
                    # ID already exists, generate new UUID
                    import uuid
                    actual_id = str(uuid.uuid4())
                    logger.warning(
                        f"Task ID '{provided_id}' already exists in database. "
                        f"Generating new ID '{actual_id}' to avoid conflict."
                    )
                    # Update the task_data to use the new ID for internal reference tracking
                    # Note: We'll still use provided_id for identifier_to_task mapping
                    # but create the task with actual_id
            
            # Create task (parent_id and dependencies will be set in step 4)
            # Use actual_id (may be different from provided_id if conflict detected)
            logger.debug(f"Creating task: name={task_name}, provided_id={provided_id}, actual_id={actual_id}")
            task = await self.task_repository.create_task(
                name=task_name,
                user_id=task_user_id,
                parent_id=None,  # Will be set in step 4
                priority=task_data.get("priority", 1),
                dependencies=None,  # Will be set in step 4
                inputs=task_data.get("inputs"),
                schemas=task_data.get("schemas"),
                params=task_data.get("params"),
                id=actual_id,  # Use actual_id (may be auto-generated if provided_id conflicts)
                origin_type=TaskOriginType.create,
                task_tree_id=None,  # Will be set after root task is determined
            )
            
            logger.debug(f"Task created: id={task.id}, name={task.name}, provided_id={provided_id}, actual_id={actual_id}")
            
            # Verify the task was created with the expected ID
            # If actual_id was generated due to conflict, task.id should match actual_id (not provided_id)
            expected_id = actual_id if actual_id else provided_id
            if expected_id and task.id != expected_id:
                logger.error(
                    f"Task ID mismatch: expected {expected_id}, got {task.id}. "
                    f"This indicates an issue with ID assignment."
                )
                raise ValueError(
                    f"Task ID mismatch: expected {expected_id}, got {task.id}. "
                    f"Task was not created with the expected ID."
                )
            
            # Note: TaskRepository.create_task already commits and refreshes the task
            # No need to commit again here
            
            created_tasks.append(task)
            
            # Map identifier (id or name) to created task
            if provided_id:
                identifier_to_task[provided_id] = task
            else:
                # Use name as identifier when id is not provided
                identifier_to_task[task_name] = task
        
        # Step 4: Set parent_id and dependencies using actual task ids
        for index, (task_data, task) in enumerate(zip(tasks, created_tasks)):
            # Resolve parent_id (can be id or name, depending on whether tasks have id)
            # If tasks have id: parent_id should be an id
            # If tasks don't have id: parent_id should be a name (name must be unique)
            parent_id = task_data.get("parent_id")
            actual_parent_id = None
            
            if parent_id:
                # Find the actual task that corresponds to the parent_id (id or name)
                parent_task = identifier_to_task.get(parent_id)
                if parent_task:
                    actual_parent_id = parent_task.id
                    # Update parent's has_children flag
                    parent_task.has_children = True
                    # Update parent task in database
                    
                    await self.db.commit()
                    await self.db.refresh(parent_task)
                else:
                    raise ValueError(
                        f"Task '{task.name}' at index {index} has parent_id '{parent_id}' "
                        f"which does not map to any created task"
                    )
            
            # Resolve dependencies to actual task ids
            # Whether user provides id or name, we convert to actual task id
            # If user provided id, use it; otherwise use system-generated UUID
            dependencies = task_data.get("dependencies")
            actual_dependencies = None
            if dependencies:
                actual_dependencies = []
                for dep in dependencies:
                    if isinstance(dep, dict):
                        # Support both "id" and "name" for dependency reference
                        # User can provide either id or name, we'll map it to actual task id
                        dep_ref = dep.get("id") or dep.get("name")
                        if dep_ref:
                            # Find the actual task that corresponds to the dependency reference (id or name)
                            dep_task = identifier_to_task.get(dep_ref)
                            if dep_task:
                                # Use actual task id (user-provided if provided, otherwise system-generated)
                                # Final structure is always: {"id": "actual_task_id", "required": bool, "type": str}
                                actual_dependencies.append({
                                    "id": dep_task.id,  # Use actual task id (user-provided or system-generated)
                                    "required": dep.get("required", True),
                                    "type": dep.get("type", "result"),
                                })
                            else:
                                raise ValueError(
                                    f"Task '{task.name}' at index {index} has dependency reference '{dep_ref}' "
                                    f"which does not map to any created task"
                                )
                        else:
                            raise ValueError(f"Task '{task.name}' dependency must have 'id' or 'name' field")
                    else:
                        # Simple string dependency (can be id or name)
                        dep_ref = str(dep)
                        dep_task = identifier_to_task.get(dep_ref)
                        if dep_task:
                            # Use actual task id (user-provided or system-generated)
                            actual_dependencies.append({
                                "id": dep_task.id,  # Use actual task id
                                "required": True,
                                "type": "result",
                            })
                        else:
                            raise ValueError(
                                f"Task '{task.name}' at index {index} has dependency '{dep_ref}' "
                                f"which does not map to any created task"
                            )
                
                actual_dependencies = actual_dependencies if actual_dependencies else None
            
            # Update task with parent_id and dependencies
            if actual_parent_id is not None or actual_dependencies is not None:
                task.parent_id = actual_parent_id
                task.dependencies = actual_dependencies
                # Update in database
                await self.db.commit()
                await self.db.refresh(task)
        
        # Step 5: Build task tree structure
        # Find root task (task with no parent_id)
        root_tasks = [task for task in created_tasks if task.parent_id is None]
        
        if not root_tasks:
            raise ValueError(
                "No root task found (task with no parent_id). "
                "At least one task in the array must have parent_id=None or no parent_id field."
            )
        
        if len(root_tasks) > 1:
            root_task_names = [task.name for task in root_tasks]
            raise ValueError(
                f"Multiple root tasks found: {root_task_names}. "
                f"All tasks must be in a single task tree. "
                f"Only one task should have parent_id=None or no parent_id field."
            )
        
        root_task = root_tasks[0]

        # Set task_tree_id for all tasks in this newly created tree to the root task id
        for t in created_tasks:
            t.task_tree_id = root_task.id

        await self.db.commit()
        # Refresh all tasks to ensure task_tree_id is persisted
        for t in created_tasks:
            await self.db.refresh(t)

        
        # Verify all tasks are reachable from the root task (in the same tree)
        # Build a set of all task IDs that are reachable from root
        reachable_task_ids: Set[str] = {root_task.id}
        
        def collect_reachable_tasks(task_id: str):
            """Recursively collect all tasks reachable from the given task via parent_id chain"""
            for task in created_tasks:
                if task.parent_id == task_id and task.id not in reachable_task_ids:
                    reachable_task_ids.add(task.id)
                    collect_reachable_tasks(task.id)
        
        collect_reachable_tasks(root_task.id)
        
        # Check if all tasks are reachable
        all_task_ids = {task.id for task in created_tasks}
        unreachable_task_ids = all_task_ids - reachable_task_ids
        
        if unreachable_task_ids:
            unreachable_task_names = [
                task.name for task in created_tasks 
                if task.id in unreachable_task_ids
            ]
            raise ValueError(
                f"Tasks not in the same tree: {unreachable_task_names}. "
                f"All tasks must be reachable from the root task via parent_id chain. "
                f"These tasks are not connected to the root task '{root_task.name}'."
            )
        
        root_node = await self._build_task_tree(root_task, created_tasks)
        
        logger.info(f"Created task tree: root task {root_node.task.name} "
                    f"with {len(root_node.children)} direct children")
        return root_node
    
    def _validate_dependencies(
        self,
        dependencies: List[Any],
        task_name: str,
        task_index: int,
        provided_ids: Set[str],
        id_to_index: Dict[str, int],
        task_names: Set[str],
        name_to_index: Dict[str, int]
    ) -> None:
        """
        Validate dependencies exist in the array and hierarchy is correct
        
        Args:
            dependencies: Dependencies list from task data
            task_name: Name of the task (for error messages)
            task_index: Index of the task in the array
            provided_ids: Set of all provided task IDs
            id_to_index: Map of id -> index in array
            task_names: Set of all task names (for name-based references)
            name_to_index: Map of name -> index in array
            
        Raises:
            ValueError: If dependencies are invalid
        """
        for dep in dependencies:
            if isinstance(dep, dict):
                # Support both "id" and "name" for dependency reference
                dep_ref = dep.get("id") or dep.get("name")
                if not dep_ref:
                    raise ValueError(f"Task '{task_name}' dependency must have 'id' or 'name' field")
                
                # Validate dependency exists in the array (as id or name)
                dep_index = None
                if dep_ref in provided_ids:
                    dep_index = id_to_index.get(dep_ref)
                elif dep_ref in task_names:
                    dep_index = name_to_index.get(dep_ref)
                else:
                    raise ValueError(
                        f"Task '{task_name}' at index {task_index} has dependency reference '{dep_ref}' "
                        f"which is not in the tasks array (not found as id or name)"
                    )
                
                # Validate hierarchy: dependency should be at an earlier index (or same level)
                if dep_index is not None and dep_index >= task_index:
                    # This is allowed for same-level dependencies, but log a warning
                    logger.debug(
                        f"Task '{task_name}' at index {task_index} depends on task at index {dep_index}. "
                        f"This is allowed but may indicate a potential issue."
                    )
            else:
                # Simple string dependency (can be id or name)
                dep_ref = str(dep)
                if dep_ref not in provided_ids and dep_ref not in task_names:
                    raise ValueError(
                        f"Task '{task_name}' at index {task_index} has dependency '{dep_ref}' "
                        f"which is not in the tasks array (not found as id or name)"
                    )
    
    def _detect_circular_dependencies(
        self,
        tasks: List[Dict[str, Any]],
        provided_ids: Set[str],
        id_to_index: Dict[str, int],
        task_names: Set[str],
        name_to_index: Dict[str, int]
    ) -> None:
        """
        Detect circular dependencies in task array using DFS.
        
        Args:
            tasks: List of task dictionaries
            provided_ids: Set of all provided task IDs
            id_to_index: Map of id -> index in array
            task_names: Set of all task names
            name_to_index: Map of name -> index in array
            
        Raises:
            ValueError: If circular dependencies are detected
        """
        # Build dependency graph: identifier -> set of identifiers it depends on
        dependency_graph: Dict[str, Set[str]] = {}
        identifier_to_name: Dict[str, str] = {}  # identifier -> task name for error messages
        
        for index, task_data in enumerate(tasks):
            task_name = task_data.get("name")
            provided_id = task_data.get("id")
            
            # Use id if provided, otherwise use name as identifier
            identifier = provided_id if provided_id else task_name
            identifier_to_name[identifier] = task_name
            
            # Initialize empty set for this task
            dependency_graph[identifier] = set()
            
            # Collect all dependencies for this task
            dependencies = task_data.get("dependencies")
            if dependencies:
                for dep in dependencies:
                    if isinstance(dep, dict):
                        dep_ref = dep.get("id") or dep.get("name")
                        if dep_ref:
                            dependency_graph[identifier].add(dep_ref)
                    else:
                        dep_ref = str(dep)
                        dependency_graph[identifier].add(dep_ref)
        
        # DFS to detect cycles
        # visited: all nodes we've visited (completely processed)
        # rec_stack: nodes in current recursion stack (path from root, indicates potential cycle)
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
            # Only visit dependencies that exist in the graph (should have been validated already)
            node_deps = dependency_graph.get(node, set())
            for dep in node_deps:
                # Skip if dependency is not in the graph (shouldn't happen after validation, but be safe)
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
                    cycle_names = [identifier_to_name.get(id, id) for id in cycle_path]
                    raise ValueError(
                        f"Circular dependency detected: {' -> '.join(cycle_names)}. "
                        f"Tasks cannot have circular dependencies as this would cause infinite loops."
                    )
    
    def _find_dependent_tasks(
        self,
        task_identifier: str,
        all_tasks: List[Dict[str, Any]],
        provided_ids: Set[str],
        task_names: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Find all tasks that depend on the specified task identifier.
        
        Args:
            task_identifier: Task identifier (id or name) to find dependents for
            all_tasks: All tasks in the array
            provided_ids: Set of all provided task IDs
            task_names: Set of all task names
            
        Returns:
            List of tasks that depend on the specified task identifier
        """
        dependent_tasks = []
        
        for task_data in all_tasks:
            dependencies = task_data.get("dependencies")
            if not dependencies:
                continue
            
            # Check if this task depends on the specified task_identifier
            for dep in dependencies:
                if isinstance(dep, dict):
                    dep_ref = dep.get("id") or dep.get("name")
                    if dep_ref == task_identifier:
                        dependent_tasks.append(task_data)
                        break
                else:
                    dep_ref = str(dep)
                    if dep_ref == task_identifier:
                        dependent_tasks.append(task_data)
                        break
        
        return dependent_tasks
    
    def _find_transitive_dependents(
        self,
        task_identifiers: Set[str],
        all_tasks: List[Dict[str, Any]],
        provided_ids: Set[str],
        task_names: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Find all tasks that depend on any of the specified task identifiers (including transitive).
        
        Args:
            task_identifiers: Set of task identifiers (id or name) to find dependents for
            all_tasks: All tasks in the array
            provided_ids: Set of all provided task IDs
            task_names: Set of all task names
            
        Returns:
            List of tasks that depend on any of the specified task identifiers (directly or transitively)
        """
        # Track all dependent tasks found (to avoid duplicates)
        found_dependents: Set[int] = set()  # Track by index to avoid duplicates
        dependent_tasks: List[Dict[str, Any]] = []
        
        # Start with the initial set of task identifiers
        current_identifiers = task_identifiers.copy()
        processed_identifiers: Set[str] = set()
        
        # Recursively find all transitive dependents
        while current_identifiers:
            next_identifiers: Set[str] = set()
            
            for identifier in current_identifiers:
                if identifier in processed_identifiers:
                    continue
                processed_identifiers.add(identifier)
                
                # Find direct dependents
                for index, task_data in enumerate(all_tasks):
                    if index in found_dependents:
                        continue
                    
                    dependencies = task_data.get("dependencies")
                    if not dependencies:
                        continue
                    
                    # Check if this task depends on the current identifier
                    depends_on_identifier = False
                    for dep in dependencies:
                        if isinstance(dep, dict):
                            dep_ref = dep.get("id") or dep.get("name")
                            if dep_ref == identifier:
                                depends_on_identifier = True
                                break
                        else:
                            dep_ref = str(dep)
                            if dep_ref == identifier:
                                depends_on_identifier = True
                                break
                    
                    if depends_on_identifier:
                        found_dependents.add(index)
                        dependent_tasks.append(task_data)
                        
                        # Add this task's identifier to next iteration
                        task_identifier = task_data.get("id") or task_data.get("name")
                        if task_identifier and task_identifier not in processed_identifiers:
                            next_identifiers.add(task_identifier)
            
            current_identifiers = next_identifiers
        
        return dependent_tasks
    
    def _validate_dependent_task_inclusion(
        self,
        tasks: List[Dict[str, Any]],
        provided_ids: Set[str],
        task_names: Set[str]
    ) -> None:
        """
        Validate that all tasks that depend on tasks in the tree are also included.
        
        Args:
            tasks: List of task dictionaries
            provided_ids: Set of all provided task IDs
            task_names: Set of all task names
            
        Raises:
            ValueError: If dependent tasks are missing
        """
        # Collect all task identifiers in the current tree
        tree_identifiers: Set[str] = set()
        for task_data in tasks:
            provided_id = task_data.get("id")
            task_name = task_data.get("name")
            if provided_id:
                tree_identifiers.add(provided_id)
            else:
                tree_identifiers.add(task_name)
        
        # Find all tasks that depend on tasks in the tree (including transitive)
        all_dependent_tasks = self._find_transitive_dependents(
            tree_identifiers, tasks, provided_ids, task_names
        )
        
        # Check if all dependent tasks are included in the tree
        included_identifiers = tree_identifiers.copy()
        missing_dependents = []
        
        for dep_task in all_dependent_tasks:
            dep_identifier = dep_task.get("id") or dep_task.get("name")
            if dep_identifier and dep_identifier not in included_identifiers:
                missing_dependents.append(dep_task)
        
        if missing_dependents:
            missing_names = [task.get("name", "Unknown") for task in missing_dependents]
            raise ValueError(
                f"Missing dependent tasks: {missing_names}. "
                f"All tasks that depend on tasks in the tree must be included. "
                f"These tasks depend on tasks in the tree but are not included in the tasks array."
            )
    
    async def _build_task_tree(
        self,
        root_task: TaskModel,
        all_tasks: List[TaskModel]
    ) -> TaskTreeNode:
        """
        Build task tree structure from root task
        
        Args:
            root_task: Root task
            all_tasks: All created tasks
            
        Returns:
            TaskTreeNode: Root task node with children
        """
        # Create task node
        task_node = TaskTreeNode(task=root_task)
        
        # Find children (tasks with parent_id == root_task.id)
        children = [task for task in all_tasks if task.parent_id == root_task.id]
        
        # Recursively build children
        for child_task in children:
            child_node = await self._build_task_tree(child_task, all_tasks)
            task_node.add_child(child_node)
        
        return task_node
    
    def tree_to_flat_list(self, root_node: TaskTreeNode) -> List[TaskModel]:
        """
        Convert tree structure to flat list for database operations
        
        Args:
            root_node: Root task node
            
        Returns:
            List[TaskModel]: Flat list of all tasks in the tree
        """
        tasks = [root_node.task]
        
        def collect_children(node: TaskTreeNode):
            for child in node.children:
                tasks.append(child.task)
                collect_children(child)
        
        collect_children(root_node)
        return tasks
    


    async def _find_dependent_tasks_for_identifiers(
        self,
        task_identifiers: Set[str],
        all_tasks: List[TaskModel]
    ) -> List[TaskModel]:
        """
        Find all tasks that depend on any of the specified task identifiers (including transitive dependencies).
        
        Args:
            task_identifiers: Set of task identifiers (id or name) to find dependents for
            all_tasks: All tasks in the same context
            
        Returns:
            List of tasks that depend on any of the specified identifiers (directly or transitively)
        """
        if not task_identifiers:
            return []
        
        # Find tasks that directly depend on any of these identifiers
        dependent_tasks = []
        for task in all_tasks:
            dependencies = getattr(task, 'dependencies', None)
            if dependencies and isinstance(dependencies, list):
                for dep in dependencies:
                    if isinstance(dep, dict):
                        dep_id = dep.get("id")
                        if dep_id in task_identifiers:
                            dependent_tasks.append(task)
                            break
                    else:
                        # Simple string dependency
                        dep_ref = str(dep)
                        if dep_ref in task_identifiers:
                            dependent_tasks.append(task)
                            break
        
        # Recursively find tasks that depend on the dependent tasks
        all_dependent_tasks = set(dependent_tasks)
        processed_identifiers = set(task_identifiers)
        
        async def find_transitive_dependents(current_dependent_tasks: List[TaskModel]):
            """Recursively find tasks that depend on current dependent tasks"""
            new_dependents = []
            for dep_task in current_dependent_tasks:
                dep_identifiers = {str(dep_task.id)}
                
                # Only process if not already processed
                if not dep_identifiers.intersection(processed_identifiers):
                    processed_identifiers.update(dep_identifiers)
                    # Find tasks that depend on this dependent task
                    for task in all_tasks:
                        if task in all_dependent_tasks:
                            continue  # Already in the set
                        task_deps = getattr(task, 'dependencies', None)
                        if task_deps and isinstance(task_deps, list):
                            for dep in task_deps:
                                if isinstance(dep, dict):
                                    dep_id = dep.get("id")
                                    if dep_id in dep_identifiers:
                                        new_dependents.append(task)
                                        all_dependent_tasks.add(task)
                                        break
                                else:
                                    dep_ref = str(dep)
                                    if dep_ref in dep_identifiers:
                                        new_dependents.append(task)
                                        all_dependent_tasks.add(task)
                                        break
            
            if new_dependents:
                await find_transitive_dependents(new_dependents)
        
        await find_transitive_dependents(dependent_tasks)
        
        return list(all_dependent_tasks)
    
    async def _find_dependency_tasks_for_identifiers(
        self,
        task_identifiers: Set[str],
        all_tasks: List[TaskModel],
        max_depth: int = DEFAULT_MAX_DEPTH
    ) -> List[TaskModel]:
        """
        Find all tasks that the specified task identifiers depend on (upstream dependencies, including transitive).
        
        Args:
            task_identifiers: Set of task identifiers (id) to find dependencies for
            all_tasks: All tasks in the same context
            max_depth: Maximum recursion depth to prevent infinite loops (default: 100)
            
        Returns:
            List of tasks that the specified identifiers depend on (directly or transitively)
        """
        if not task_identifiers:
            return []
        
        # Build a map of task identifier to task for quick lookup
        tasks_by_identifier: Dict[str, TaskModel] = {}
        for task in all_tasks:
            task_id = str(task.id)
            tasks_by_identifier[task_id] = task
        
        # Find tasks that directly depend on any of these identifiers (these are the upstream dependencies)
        dependency_tasks = []
        processed_identifiers = set(task_identifiers)
        identifiers_to_process = set(task_identifiers)
        
        async def find_transitive_dependencies(current_identifiers: Set[str], depth: int = 0):
            """Recursively find tasks that current identifiers depend on"""
            # Prevent infinite recursion
            if depth >= max_depth:
                logger.warning(
                    f"Maximum recursion depth ({max_depth}) reached in dependency resolution. "
                    f"Stopping to prevent infinite loop."
                )
                return
            
            new_dependency_identifiers = set()
            
            # For each task with an identifier in current_identifiers, find its dependencies
            for task in all_tasks:
                task_id = str(task.id)
                
                # Check if this task is in current_identifiers
                if task_id not in current_identifiers:
                    continue
                
                # Get dependencies for this task
                dependencies = getattr(task, 'dependencies', None)
                if dependencies and isinstance(dependencies, list):
                    for dep in dependencies:
                        if isinstance(dep, dict):
                            dep_identifier = dep.get("id")
                        else:
                            dep_identifier = str(dep)
                        
                        if dep_identifier and dep_identifier not in processed_identifiers:
                            # Found a new dependency identifier
                            processed_identifiers.add(dep_identifier)
                            new_dependency_identifiers.add(dep_identifier)
                            
                            # If this dependency identifier corresponds to a task in all_tasks, add it
                            if dep_identifier in tasks_by_identifier:
                                dep_task = tasks_by_identifier[dep_identifier]
                                if dep_task not in dependency_tasks:
                                    dependency_tasks.append(dep_task)
                            else:
                                # Dependency not in all_tasks - try to find it in database
                                # This handles cases where dependencies are in different task trees
                                try:
                                    dep_task = await self.task_repository.get_task_by_id(dep_identifier)
                                    if dep_task and dep_task not in dependency_tasks:
                                        dependency_tasks.append(dep_task)
                                        # Add to tasks_by_identifier for future lookups
                                        tasks_by_identifier[dep_identifier] = dep_task
                                except Exception as e:
                                    logger.debug(
                                        f"Could not find dependency task {dep_identifier} in database: {e}. "
                                        f"It may be in a different task tree or not exist."
                                    )
            
            # Recursively process new dependency identifiers
            if new_dependency_identifiers:
                await find_transitive_dependencies(new_dependency_identifiers, depth + 1)
        
        await find_transitive_dependencies(identifiers_to_process, 0)
        
        return dependency_tasks
    
    async def _find_minimal_subtree(
        self,
        root_tree: TaskTreeNode,
        required_task_ids: Set[str]
    ) -> Optional[TaskTreeNode]:
        """
        Find minimal subtree that contains all required tasks.
        Returns None if not all required tasks are found in the tree.
        
        Args:
            root_tree: Root task tree to search in
            required_task_ids: Set of task IDs that must be included
            
        Returns:
            Minimal TaskTreeNode containing all required tasks, or None
        """
        def collect_task_ids(node: TaskTreeNode) -> Set[str]:
            """Collect all task IDs in the tree"""
            task_ids = {str(node.task.id)}
            for child in node.children:
                task_ids.update(collect_task_ids(child))
            return task_ids
        
        # Check if all required tasks are in the tree
        all_task_ids = collect_task_ids(root_tree)
        if not required_task_ids.issubset(all_task_ids):
            return None
        
        def build_minimal_subtree(node: TaskTreeNode) -> Optional[TaskTreeNode]:
            """Build minimal subtree containing required tasks"""
            # Collect task IDs in this subtree
            subtree_task_ids = collect_task_ids(node)
            
            # Check if this subtree contains any required tasks
            if not subtree_task_ids.intersection(required_task_ids):
                return None
            
            # If this node is required or has required descendants, include it
            new_node = TaskTreeNode(task=node.task)
            
            for child in node.children:
                child_subtree = build_minimal_subtree(child)
                if child_subtree:
                    new_node.add_child(child_subtree)
            
            return new_node
        
        return build_minimal_subtree(root_tree)
    

    def _tree_to_task_array(self, node: TaskTreeNode) -> List[Dict[str, Any]]:
        """
        Convert TaskTreeNode to flat task array compatible with tasks.create API.
        
        Uses TaskModel's actual fields via get_task_model_class().
        Since tasks are not saved yet, uses name-based references instead of id.
        Ensures all names are unique.
        
        Args:
            node: Task tree node
            
        Returns:
            List of task dictionaries compatible with tasks.create format
        """
        # Get TaskModel class (may be custom)
        task_model_class = get_task_model_class()
        
        # Get all column names from TaskModel
        task_columns = set(task_model_class.__table__.columns.keys())
        
        tasks = []
        name_counter = {}  # Track name usage for uniqueness
        task_to_name = {}  # task object id -> unique name
        
        # First pass: assign unique names to all tasks
        def assign_names(current_node: TaskTreeNode):
            task = current_node.task
            original_name = task.name
            
            # Generate unique name if needed
            if original_name not in name_counter:
                name_counter[original_name] = 0
                unique_name = original_name
            else:
                name_counter[original_name] += 1
                unique_name = f"{original_name}_{name_counter[original_name]}"
            
            task_to_name[id(task)] = unique_name
            
            # Recursively process children
            for child in current_node.children:
                assign_names(child)
        
        assign_names(node)
        
        # Build mappings for dependencies conversion
        # Map original task.id and original_task_id to new generated id and name
        task_id_to_new_id: Dict[str, str] = {}  # original task.id -> new generated id
        task_id_to_name: Dict[str, str] = {}  # original task.id -> name (for name-based refs)
        
        # First pass: map all task.id to their names
        def build_id_mappings(current_node: TaskTreeNode):
            task = current_node.task
            task_id_to_name[str(task.id)] = task_to_name[id(task)]
            for child in current_node.children:
                build_id_mappings(child)
        build_id_mappings(node)
        
        # Second pass: map original_task_id to name (for name-based refs fallback)
        # This allows dependencies that reference original task IDs to be converted correctly
        def map_original_task_ids(current_node: TaskTreeNode):
            task = current_node.task
            if task.original_task_id:
                original_id = str(task.original_task_id)
                # Only map if not already in the mapping (avoid overwriting existing mappings)
                # This ensures that if original_task_id matches another task's id in the tree,
                # we use that task's name, not the current task's name
                if original_id not in task_id_to_name:
                    task_id_to_name[original_id] = task_to_name[id(task)]
            for child in current_node.children:
                map_original_task_ids(child)
        map_original_task_ids(node)
        
        # Third pass: pre-generate all new IDs for all tasks (needed for dependency conversion)
        def pre_generate_ids(current_node: TaskTreeNode):
            task = current_node.task
            task_id_str = str(task.id)
            # Check if this task.id has already been mapped (should not happen in a valid tree)
            if task_id_str in task_id_to_new_id:
                # This should not happen, but if it does, reuse the existing mapping
                # This ensures we don't create duplicate IDs
                return
            new_task_id = str(uuid.uuid4())
            # Map task.id to new id
            task_id_to_new_id[task_id_str] = new_task_id
            # Also map original_task_id to new id (if exists) for dependency conversion
            # This ensures dependencies that reference original_task_id can be converted correctly
            if task.original_task_id:
                original_id = str(task.original_task_id)
                # Only map if not already mapped (avoid overwriting if multiple tasks have same original_task_id)
                if original_id not in task_id_to_new_id:
                    task_id_to_new_id[original_id] = new_task_id
            
            # IMPORTANT: Dependencies in the copied task may reference original task IDs
            # We need to map those original IDs to the new IDs of the copied tasks
            # Iterate through all tasks in the tree to build a complete mapping
            dependencies = getattr(task, 'dependencies', None)
            if dependencies:
                for dep in dependencies:
                    if isinstance(dep, dict) and "id" in dep:
                        dep_id = str(dep["id"])
                        # If this dependency ID is not yet mapped, we need to find which copied task
                        # corresponds to this original dependency ID
                        if dep_id not in task_id_to_new_id:
                            # Find the task in the tree that has this ID as its original_task_id
                            # or as its task.id (if it's a direct reference)
                            # This will be handled by iterating through all tasks
                            pass  # Will be handled in a separate pass
            for child in current_node.children:
                pre_generate_ids(child)
        pre_generate_ids(node)
        
        # Fourth pass: map dependency IDs that reference original task IDs
        # Dependencies in copied tasks may reference original task IDs from the original tree
        # We need to map those original IDs to the new IDs of the corresponding copied tasks
        # Strategy: For each dependency ID that's not yet mapped, find the task in the new tree
        # that corresponds to that original ID (by checking original_task_id or task.id)
        def find_task_by_original_id(current_node: TaskTreeNode, target_original_id: str) -> Optional[TaskTreeNode]:
            """Find a task in the tree that corresponds to the given original task ID"""
            task = current_node.task
            # Check if this task's original_task_id matches, or if task.id matches (for direct references)
            if (task.original_task_id and str(task.original_task_id) == target_original_id) or \
               str(task.id) == target_original_id:
                return current_node
            # Recursively check children
            for child in current_node.children:
                result = find_task_by_original_id(child, target_original_id)
                if result:
                    return result
            return None
        
        def map_dependency_ids(current_node: TaskTreeNode):
            """Map all dependency IDs in the tree to new task IDs"""
            task = current_node.task
            dependencies = getattr(task, 'dependencies', None)
            if dependencies:
                for dep in dependencies:
                    if isinstance(dep, dict) and "id" in dep:
                        dep_id = str(dep["id"])
                        # If this dependency ID is not yet mapped, find the corresponding task in the new tree
                        if dep_id not in task_id_to_new_id:
                            found_node = find_task_by_original_id(node, dep_id)
                            if found_node:
                                # Map the dependency ID to the new ID of the found task
                                found_new_id = task_id_to_new_id[str(found_node.task.id)]
                                task_id_to_new_id[dep_id] = found_new_id
                            # If not found, it will raise an error during conversion (which is correct)
            for child in current_node.children:
                map_dependency_ids(child)
        map_dependency_ids(node)
        
        # Fourth pass: build task array with id and name-based references
        def collect_tasks(current_node: TaskTreeNode, parent_name: Optional[str] = None, parent_id: Optional[str] = None):
            task = current_node.task
            unique_name = task_to_name[id(task)]
            
            # Build task dict using TaskModel's actual fields
            task_dict: Dict[str, Any] = {}
            
            # Get pre-generated UUID for this task (for save=False, tasks.create needs complete data)
            new_task_id = task_id_to_new_id[str(task.id)]
            task_dict["id"] = new_task_id
            
            # Handle parent_id separately (before the loop, since we skip it in the loop)
            # Use parent id (since all tasks have id now)
            # parent_id parameter is the new generated id of the parent task
            if parent_id is not None:
                task_dict["parent_id"] = parent_id
            # else: don't set parent_id (root task) - this is correct
            
            # Get all TaskModel fields and their values
            for column_name in task_columns:
                # Skip id (already set above), parent_id (handled separately above), created_at, updated_at, has_references (auto-generated or not needed for create)
                if column_name in ("id", "parent_id", "created_at", "updated_at", "has_references"):
                    continue
                
                # Get value from task
                value = getattr(task, column_name, None)
                
                # Handle special cases
                if column_name == "name":
                    # Use unique name
                    task_dict["name"] = unique_name
                elif column_name == "progress":
                    # Convert Numeric to float
                    task_dict["progress"] = float(value) if value is not None else 0.0
                elif column_name == "dependencies" and value is not None:
                    # Convert dependencies: replace original id references with new generated id
                    # Since all tasks have id now, dependencies must use id references
                    if isinstance(value, list):
                        converted_deps = []
                        for dep in value:
                            if isinstance(dep, dict):
                                dep_copy = dep.copy()
                                # Convert id to new generated id (required for id-based mode)
                                if "id" in dep_copy:
                                    dep_id = str(dep_copy["id"])
                                    if dep_id in task_id_to_new_id:
                                        # Use new generated id
                                        dep_copy["id"] = task_id_to_new_id[dep_id]
                                    else:
                                        # If not found, this is an error - dependency must be in the tree
                                        raise ValueError(
                                            f"Dependency id '{dep_id}' not found in task tree. "
                                            f"All dependencies must reference tasks within the copied tree."
                                        )
                                # If dependency has "name" but no "id", try to find it by name
                                elif "name" in dep_copy:
                                    dep_name = dep_copy["name"]
                                    # Find task with this name and use its new id
                                    found = False
                                    for orig_id, new_id in task_id_to_new_id.items():
                                        if task_id_to_name.get(orig_id) == dep_name:
                                            dep_copy["id"] = new_id
                                            del dep_copy["name"]
                                            found = True
                                            break
                                    if not found:
                                        raise ValueError(
                                            f"Dependency name '{dep_name}' not found in task tree. "
                                            f"All dependencies must reference tasks within the copied tree."
                                        )
                                converted_deps.append(dep_copy)
                            else:
                                # String or other format - try to convert
                                dep_str = str(dep)
                                if dep_str in task_id_to_new_id:
                                    converted_deps.append({"id": task_id_to_new_id[dep_str]})
                                else:
                                    # Try to find by name
                                    found = False
                                    for orig_id, new_id in task_id_to_new_id.items():
                                        if task_id_to_name.get(orig_id) == dep_str:
                                            converted_deps.append({"id": new_id})
                                            found = True
                                            break
                                    if not found:
                                        raise ValueError(
                                            f"Dependency '{dep_str}' not found in task tree. "
                                            f"All dependencies must reference tasks within the copied tree."
                                        )
                        task_dict["dependencies"] = converted_deps
                    else:
                        task_dict["dependencies"] = value
                elif value is not None:
                    # Include non-None values
                    task_dict[column_name] = value
            
            tasks.append(task_dict)
            
            # Recursively collect children
            for child in current_node.children:
                collect_tasks(child, unique_name, new_task_id)
        
        collect_tasks(node, None, None)  # Root task has no parent
        return tasks


    async def _get_original_task_for_link(self, task: TaskModel) -> TaskModel:
        """
        Recursively find the most original (non-link) task for linking.
        """
        current = task
        max_iterations = 10  # Prevent infinite loops
        iterations = 0
        while getattr(current, "origin_type", None) == TaskOriginType.link and getattr(current, "original_task_id", None):
            orig_id = current.original_task_id
            # get original task object (sync or async)
            current = await self.task_repository.get_task_by_id(orig_id)
            iterations += 1
            if iterations >= max_iterations:
                raise RuntimeError("Max iterations reached while finding original task for link. Possible circular reference.")     

        return current

    def _link_reset_fields(self) -> Dict[str, Any]:
        """
        Fields to reset when creating a linked task.
        """
        return {
            'origin_type': TaskOriginType.link,
            'result': None,
            'params': None,
            'inputs': None,
            'schemas': None,
        }
    

    async def from_link(
        self,
        _original_task: TaskModel,
        _save: bool = True,
        _recursive: bool = True,
        _auto_include_deps: bool = True,
        _include_dependents: bool = False,
        **reset_kwargs
    ) -> TaskTreeNode:
        """
        Create task(s) by linking to existing task(s) (reference)
        Only allow linking if the entire source task tree is completed.
        The status of the link will be set to the source task's status.
        
        Creates new task(s) that reference the original task. Each new task points to
        the corresponding original task via original_task_id field and has origin_type='link'.
        
        Args:
            _original_task: Original task to link to
            _save: If True, save to database. If False, return in-memory instance(s)
            _recursive: If True, link entire subtree; if False, link only original_task
            _auto_include_deps: If True, automatically include upstream dependency tasks.
                Upstream tasks will be linked to, and minimal subtree will be built to connect them.
            _include_dependents: If True, also include downstream dependent tasks (non-root only).
            **reset_kwargs: Optional fields to override (e.g., user_id="new_user")
            
        Returns:
            TaskTreeNode
        """
        # check entire task tree is completed
        task_tree = await self.task_repository.build_task_tree(_original_task)
        if task_tree.calculate_status() != TaskStatus.COMPLETED:
            raise ValueError("Only a fully completed task tree can be linked. There are unfinished tasks in the tree.")

        reset_kwargs = self._link_reset_fields()

        if not _recursive:
            reset_kwargs['parent_id'] = None  # No parent for single linked task
            reset_kwargs['dependencies'] = None  # No dependencies for single linked task
            new_task = await self._clone_task(_original_task, reset_kwargs)
            logger.info(
                f"Created linked task '{new_task.id}' referencing most original task '{_original_task.id}'"
            )
            task_tree = TaskTreeNode(task=new_task)
            if _save:
                await self.task_repository.save_task_tree(task_tree)
            return task_tree
        

        # Build original subtree and augment with dependencies as needed
        original_tree = await self.task_repository.build_task_tree(_original_task)
        if _original_task.parent_id is not None:
            # Validate no external dependencies if not root
            await self._validate_no_external_dependencies(_original_task)
            original_tree = await self._augment_subtree_with_dependencies(
                _original_task,
                original_tree,
                _auto_include_deps,
                _include_dependents,
                None,
            )
 
        # clone tree
        task_tree = await self._clone_task_tree(original_tree, reset_kwargs)
        if _save:
            await self.task_repository.save_task_tree(task_tree)
       
        return task_tree
    
    async def from_copy(
        self,
        _original_task: TaskModel,
        _save: bool = True,
        _recursive: bool = True,
        _auto_include_deps: bool = True,
        _include_dependents: bool = False,
        **reset_kwargs
    ) -> TaskTreeNode:
        """
        Create task(s) by copying from existing task(s) (allows modifications)
        
        Copies the original task and optionally its entire subtree. The copied tasks
        can be modified. If the original task is not a root task and _recursive=True,
        validates that it and its children don't depend on tasks outside the subtree,
        and automatically promotes the copied subtree to an independent tree.
        
        Args:
            _original_task: Original task to copy from
            _save: If True, return saved instances. If False, return task array
            _recursive: If True, copy entire subtree; if False, copy only original_task
            _auto_include_deps: If True, automatically include upstream dependency tasks.
                               Only used when _recursive=True. Default: True
            _include_dependents: If True, also include downstream dependent tasks
                                (tasks that depend on the copied task). Only used when
                                _recursive=True and original task is not root. Default: False
            
        Returns:
            TaskTreeNode
        """
        task_tree = await self.task_repository.build_task_tree(_original_task)
        reset_kwargs = dict(reset_kwargs)
        reset_kwargs['origin_type'] = TaskOriginType.copy
 
        if not _recursive:
            reset_kwargs['parent_id'] = None  # No parent for single linked task
            reset_kwargs['dependencies'] = None  # No dependencies for single linked task
            new_task = await self._clone_task(_original_task, reset_kwargs)
            logger.info(
                f"Created linked task '{new_task.id}' referencing most original task '{_original_task.id}'"
            )
            task_tree = TaskTreeNode(task=new_task)
            if _save:
                await self.task_repository.save_task_tree(task_tree)
            return task_tree
        

        # Build original subtree and augment with dependencies as needed
        original_tree = await self.task_repository.build_task_tree(_original_task)
        if _original_task.parent_id is not None:
            # Validate no external dependencies if not root
            await self._validate_no_external_dependencies(_original_task)
            original_tree = await self._augment_subtree_with_dependencies(
                _original_task,
                original_tree,
                _auto_include_deps,
                _include_dependents,
                None,
            )
 
        # clone tree
        task_tree = await self._clone_task_tree(original_tree, reset_kwargs)
        if _save:
            await self.task_repository.save_task_tree(task_tree)
       
        return task_tree
    
    async def from_archive(
        self,
        _original_task: TaskModel,
        _save: bool = True,
        _recursive: bool = True,
        _auto_include_deps: bool = True,
        _include_dependents: bool = False,
    ) -> TaskTreeNode:
        """
        Create frozen archive(s) from existing task(s) (read-only, immutable)
        
        Creates frozen archives of the original task and optionally its entire subtree.
        Snapshot tasks cannot be modified after creation. If the original task is not
        a root task and _recursive=True, validates no external dependencies and
        automatically promotes the archive subtree to an independent tree.
        
        Args:
            _original_task: Original task to archive
            
        Returns:
            TaskTreeNode
        """

        # check entire task tree is completed
        task_tree = await self.task_repository.build_task_tree(_original_task)
        if task_tree.calculate_status() != TaskStatus.COMPLETED:
            raise ValueError("Only a fully completed task tree can be linked. There are unfinished tasks in the tree.")

        reset_kwargs = {
            "origin_type": TaskOriginType.archive,
        }

        if not _recursive:
            _original_task.update_from_dict(reset_kwargs)
            logger.info(
                f"Archive task '{_original_task.id}'"
            )
            task_tree = TaskTreeNode(task=_original_task)
            if _save:
                self.db.add(_original_task)
                await self.db.commit()
                await self.db.refresh(_original_task)
            return task_tree
        

        # Build original subtree and augment with dependencies as needed
        original_tree = await self.task_repository.build_task_tree(_original_task)
        if _original_task.parent_id is not None:
            # Validate no external dependencies if not root
            await self._validate_no_external_dependencies(_original_task)
            original_tree = await self._augment_subtree_with_dependencies(
                _original_task,
                original_tree,
                _auto_include_deps,
                _include_dependents,
                None,
            )
 
        task_tree = original_tree.update(reset_kwargs)
        if _save:
            task_list = task_tree.to_list()
            self.task_repository.add_tasks_in_db(task_list)
            await self.db.commit()
            await self.task_repository.refresh_tasks_in_db(task_list)
       
        return task_tree
    
    async def from_mixed(
        self,
        _original_task: TaskModel,
        _save: bool = True,
        _recursive: bool = True,
        _link_task_ids: Optional[List[str]] = None,
        _auto_include_deps: bool = True,
        _include_dependents: bool = False,
        **reset_kwargs
    ) -> TaskModel | TaskTreeNode | List[Dict[str, Any]]:
        """
        Create task tree with mixed origin types (copy + link)
        
        some tasks link (reference original), others copy (allow modification).
        
        Args:
            _original_task: Original task
            _save: If True, return saved instances. If False, return task array
            _recursive: If True, apply mixed mode to entire subtree; if False, only original_task
            _link_task_ids: List of task IDs to link (reference). Tasks NOT in this list will be copied.
                           If None, all tasks will be copied (equivalent to from_copy)
            _auto_include_deps: If True, automatically include upstream dependency tasks for copied portions.
                Only applies to tasks being copied, not linked.
            _include_dependents: If True, also include downstream dependent tasks for copied portions (non-root only).
            **reset_kwargs: Fields to override for copied tasks
            
        Returns:
            TaskModel if _recursive=False,
            TaskTreeNode if _recursive=True and _save=True,
            List[Dict[str, Any]] if _save=False
        """
        if not _recursive:
            # Single task - determine if should link or copy
            if _link_task_ids and str(_original_task.id) in [str(id) for id in _link_task_ids]:
                reset_kwargs['origin_type'] = TaskOriginType.link
            else:
                reset_kwargs['origin_type'] = TaskOriginType.copy
            
            new_task = await self._clone_task(_original_task, reset_kwargs)
            logger.info(
                f"Created {reset_kwargs['origin_type']} task '{new_task.id}' referencing most original task '{_original_task.id}'"
            )
            task_tree = TaskTreeNode(task=new_task)
            if _save:
                await self.task_repository.save_task_tree(task_tree)
            return task_tree
        
        # Recursive mixed - validate and handle with dependency consideration
        # is_root = _original_task.parent_id is None
        # validate external dependencies if not auto-including dependencies
        if not _auto_include_deps:
            await self._validate_no_external_dependencies(_original_task)
        
        # Build original subtree
        original_tree = await self.task_repository.build_task_tree(_original_task)
        
        # Separate tasks into copy and link sets
        link_set = set(str(id) for id in (_link_task_ids if _link_task_ids else []))
        
        # Augment subtree with dependencies for copied portions only
        # To do so, temporarily mark linked tasks in the subtree so they are not considered
        # The augmentation helper considers the entire subtree; we emulate copied-only behavior
        # by building a subtree that excludes linked nodes when evaluating identifiers.
        mixed_tree = await self._augment_subtree_with_dependencies(
            _original_task,
            original_tree,
            _auto_include_deps,
            _include_dependents,
            link_set,
        )
        
        # Create mixed tree with selective linking
        task_tree = await self._create_mixed_tree(
            mixed_tree,
            link_set,
            reset_kwargs
        )
        
        if _save:
            await self.task_repository.save_task_tree(task_tree)

        return task_tree

    # ==================== Helper Methods ====================

    async def _augment_subtree_with_dependencies(
        self,
        original_task: TaskModel,
        original_tree: TaskTreeNode,
        auto_include_deps: bool,
        include_dependents: bool,
        excluded_identifiers: Optional[Set[str]] = None,
    ) -> TaskTreeNode:
        """Build a minimal subtree including upstream dependencies and optional dependents.
        Returns the augmented subtree if dependencies expand the set; otherwise returns the original subtree.
        """
        is_root = original_task.parent_id is None
        
        # Collect all tasks for context
        root_task = await self.task_repository.get_root_task(original_task)
        all_tasks = await self.task_repository.get_all_tasks_in_tree(root_task)
        
        # Collect IDs in the original subtree
        def collect_subtree_ids(tree_node: TaskTreeNode) -> Set[str]:
            ids = {str(tree_node.task.id)}
            if tree_node.children:
                for child in tree_node.children:
                    ids.update(collect_subtree_ids(child))
            return ids
        
        subtree_ids = collect_subtree_ids(original_tree)
        required_ids = set(subtree_ids)
        
        # Collect identifiers for dependency lookup
        task_identifiers = set()
        excluded_identifiers = excluded_identifiers or set()
        for task in all_tasks:
            if str(task.id) in subtree_ids and str(task.id) not in excluded_identifiers:
                task_identifiers.add(str(task.id))
        
        # Upstream dependencies
        if auto_include_deps and task_identifiers:
            try:
                dependency_tasks = await self._find_dependency_tasks_for_identifiers(
                    task_identifiers, all_tasks
                )
                for dep_task in dependency_tasks:
                    required_ids.add(str(dep_task.id))
            except Exception as e:
                logger.warning(
                    f"Failed to auto-include upstream dependencies: {e}. Proceeding with original subtree only."
                )
        
        # Downstream dependents (non-root only)
        if include_dependents and not is_root and task_identifiers:
            try:
                dependent_tasks = await self._find_dependent_tasks_for_identifiers(
                    task_identifiers, all_tasks
                )
                for dep_task in dependent_tasks:
                    required_ids.add(str(dep_task.id))
            except Exception as e:
                logger.warning(
                    f"Failed to include downstream dependents: {e}. Proceeding without dependents."
                )
        
        # If expanded set, build minimal subtree
        if len(required_ids) > len(subtree_ids):
            root_tree = await self.task_repository.build_task_tree(root_task)
            minimal_tree = await self._find_minimal_subtree(root_tree, required_ids)
            if minimal_tree:
                return minimal_tree
            logger.warning(
                "Failed to build minimal subtree with all required tasks. Using original subtree only."
            )
        
        return original_tree


    async def _clone_task_tree_dependency_fix(self, new_task_tree: TaskTreeNode, id_mapping: Dict[str, Any]):
        """
        Clone task tree with dependency fixing.
        Args:
            new_task_tree: Cloned task tree to fix dependencies in
            id_mapping: Mapping from old task IDs to new task IDs
        Returns:
            None (modifies new_task_tree in place)
        """

        async def _fix_dependencies_recursive(
            task_node: TaskTreeNode,
            id_mapping: Dict[str, Any],
        ):
            """Recursively fix dependencies in the cloned task node"""
            # Fix dependencies for current task
            dependencies = getattr(task_node.task, 'dependencies', None)
            if dependencies:
                missing_indexes = []
                for dep in dependencies:
                    if isinstance(dep, dict):
                        if "id" in dep:
                            dep_id = str(dep["id"])
                            if dep_id in id_mapping:
                                # Update to new ID
                                dep["id"] = id_mapping[dep_id]
                            else:
                                missing_indexes.append(dependencies.index(dep)) # Track missing IDs
                    else:
                        dep_id = str(dep)
                        if dep_id in id_mapping:
                            # Update to new ID
                            dep_index = dependencies.index(dep)
                            dependencies[dep_index] = id_mapping[dep_id]
                        else:
                            missing_indexes.append(dependencies.index(dep))  # Track missing IDs
                
                # Remove dependencies that could not be mapped
                for index in sorted(missing_indexes, reverse=True):
                    del dependencies[index]
            
            # Recursively fix children
            for child_node in task_node.children:
                await _fix_dependencies_recursive(child_node, id_mapping)

        await _fix_dependencies_recursive(new_task_tree, id_mapping)
        
    
    async def _clone_task_tree(
        self,
        original_task_tree: TaskTreeNode,
        reset_kwargs: Dict[str, Any] = {},
    ) -> TaskTreeNode:
        """
        Recursively clone task tree for entire subtree
        Core Two Steps: Pure Copy → Reset ID → Recursively Process Child Nodes

        Args:
            original_task_tree: Original task tree to clone
            reset_kwargs: Fields to override/reset in cloned tasks

        Returns:
            Cloned TaskTreeNode with updated tasks
        
        """
        
        # old task id: new task id mapping for dependency fixing
        id_mapping: Dict[str, str] = {}

        # new task tree
        new_tree = original_task_tree.copy()
    
        async def _reset_task_recursive(
            task_node: TaskTreeNode,
            reset_kwargs: Dict[str, Any],
        ) -> TaskTreeNode:
            """Recursively clone a task node and its children"""
            # Clone the task with overrides
            old_task_id = str(task_node.task.id)
            cloned_task = await self._clone_task(
                task_node.task, reset_kwargs, False
            )
            task_node.task = cloned_task
            # Update id mapping
            id_mapping[old_task_id] = str(cloned_task.id)
            # Recursively clone children
            for child in task_node.children:
                child.task.parent_id = task_node.task.id
                await _reset_task_recursive(child, reset_kwargs)

            return task_node 
        
        new_tree = await _reset_task_recursive(new_tree, reset_kwargs)

        if new_tree.task.parent_id is not None:
            new_tree.task.parent_id = None  # Promote to independent tree

        # Fix dependencies in the new tree
        await self._clone_task_tree_dependency_fix(new_tree, id_mapping)

        return new_tree

    async def _create_mixed_tree(
        self,
        original_tree: TaskTreeNode,
        link_task_ids: Set[str],
        reset_kwargs: Dict[str, Any]
    ) -> TaskTreeNode:
        """Recursively create mixed tree (copy + link)"""
        task_tree = await self._clone_task_tree(original_tree)
        reset_kwargs['origin_type'] = TaskOriginType.copy
        
        def mark_links_recursive(
            task_node: TaskTreeNode,
            link_task_ids: Set[str],
        ):
            """Recursively mark tasks as link or copy based on link_task_ids"""
            if str(task_node.task.id) in link_task_ids:
                # Mark as link
                task_node.task.update_from_dict(self._link_reset_fields())
            else:
                # Mark as copy
                task_node.task.update_from_dict(reset_kwargs)
            
            # Recursively process children
            for child in task_node.children:
                mark_links_recursive(child, link_task_ids)

        mark_links_recursive(task_tree, link_task_ids)

        return task_tree
    
    def _reset_task_fields(
        self,
        task: TaskModel,
        reset_kwargs: Dict[str, Any],
    ) -> None:
        """
        Reset specified fields on a task to their reset_kwargs values
        
        Args:
            task: Task to reset fields on
            field_names: List of field names to reset
        """
        # This method is called after the task is created with reset_kwargs
        # The reset_kwargs are already applied during task creation via _extract_field_overrides
        # This is a placeholder for any post-creation field resets if needed
        
        for field_name, field_value in reset_kwargs.items():
            if hasattr(task, field_name):
                setattr(task, field_name, field_value)
    
    async def _clone_task(
        self,
        original_task: TaskModel,
        reset_kwargs: Dict[str, Any],
        is_copy: bool = True,
    ) -> TaskModel:
        """
        Clone tasks' field overrides from reset_kwargs
        
        Args:
            original_task: Original task
            reset_kwargs: Field overrides
            is_copy: If True, return a copy; if False, update original task
            
        Returns:
            TaskModel
        """
        reset_kwargs["id"] = str(uuid.uuid4())
        reset_kwargs['has_references'] = False

        most_original_task = await self._get_original_task_for_link(original_task)
        reset_kwargs['original_task_id'] = most_original_task.id

        if is_copy:
            return original_task.copy(reset_kwargs)
        else:
            return original_task.update_from_dict(reset_kwargs)
        
    
    async def _validate_no_external_dependencies(self, task: TaskModel) -> None:
        """
        Validate that task and its subtree have no dependencies outside the subtree
        
        Args:
            task: Root task of the subtree to validate
            
        Raises:
            ValueError: If any task in the subtree depends on tasks outside the subtree
        """
        # Collect all tasks in the subtree
        subtree_tasks = await self._collect_subtree_tasks(task.id)
        subtree_task_ids = {t.id for t in subtree_tasks}
        
        # Check each task's dependencies
        for subtree_task in subtree_tasks:
            if not subtree_task.dependencies:
                continue
            for dep in subtree_task.dependencies:
                dep_id = dep.get("id")
                if not dep_id:
                    continue
                # Check if dependency is outside the subtree
                if dep_id not in subtree_task_ids:
                    raise ValueError(
                        f"Task '{subtree_task.name}' (id: {subtree_task.id}) has dependency "
                        f"on task '{dep_id}' which is outside the subtree rooted at '{task.name}' "
                        f"(id: {task.id}). Cannot copy/archive a subtree with external dependencies."
                    )
        
        logger.debug(
            f"Validated task '{task.name}' (id: {task.id}) subtree has no external dependencies"
        )
    
    async def _promote_to_independent_tree(self, root_task: TaskModel) -> None:
        """
        Promote a task subtree to an independent tree
        
        Args:
            root_task: Root task of the subtree to promote
        """
        # Set root's parent_id to None (making it a true root)
        root_task.parent_id = None
        
        # Set task_tree_id for root and all descendants
        all_tasks = await self._collect_subtree_tasks(root_task.id)
        new_tree_id = root_task.id
        
        for task in all_tasks:
            task.task_tree_id = new_tree_id
        
        # Commit changes
        await self.db.commit()
        for task in all_tasks:
            await self.db.refresh(task)
        
        logger.info(
            f"Promoted task '{root_task.name}' (id: {root_task.id}) to independent tree "
            f"with {len(all_tasks)} total tasks"
        )
    
    async def _collect_subtree_tasks(self, root_task_id: str) -> List[TaskModel]:
        """
        Collect all tasks in a subtree rooted at the given task
        
        Args:
            root_task_id: ID of the root task
            
        Returns:
            List[TaskModel]: All tasks in the subtree (including root)
        """
        # Refresh session state before query to ensure we see latest database state
        # This prevents blocking in sync sessions when there are uncommitted transactions
        self.db.expire_all()
        root_task = await self.task_repository.get_task_by_id(root_task_id)
        if not root_task:
            return []
        
        all_tasks = [root_task]
        
        async def collect_children(task_id: str):
            """Recursively collect all child tasks"""
            children = await self.task_repository.get_child_tasks_by_parent_id(task_id)
            for child in children:
                all_tasks.append(child)
                await collect_children(child.id)
        
        await collect_children(root_task_id)
        return all_tasks


__all__ = [
    "TaskCreator",
]

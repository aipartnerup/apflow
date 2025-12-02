"""
Task creation from tasks array

This module provides functionality to create task trees from tasks array (JSON format).
It is a core function that accepts a tasks array and builds a task tree structure.

External callers should provide tasks with resolved id and parent_id.
This module only validates that dependencies exist in the array and hierarchy is correct.

Usage:
    from aipartnerupflow.core.execution import TaskCreator
    
    creator = TaskCreator(db_session)
    tasks = [
        {
            "id": "task_1",  # Optional: if provided, used for references
            "name": "Task 1",  # Required: if no id, name must be unique and used for references
            "user_id": "user_123",
            "priority": 1,
            "inputs": {"url": "https://example.com"},
            "schemas": {"type": "stdio", "method": "system_info"},
        },
        {
            "id": "task_2",  # Optional: if provided, used for references
            "name": "Task 2",  # Required: if no id, name must be unique and used for references
            "user_id": "user_123",
            "parent_id": "task_1",  # If tasks have id: use id; if not: use name
            "dependencies": [{"id": "task_1", "required": True}],  # Can use id or name
        }
    ]
    task_tree = await creator.create_task_tree_from_array(tasks)
"""

from typing import List, Dict, Any, Optional, Union, Set
import copy
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from aipartnerupflow.core.execution.task_manager import TaskManager
from aipartnerupflow.core.types import TaskTreeNode
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class TaskCreator:
    """
    Task creation from tasks array
    
    This class provides functionality to create task trees from tasks array (JSON format).
    External callers should provide tasks with resolved id and parent_id.
    This module only validates that dependencies exist in the array and hierarchy is correct.
    
    Usage:
        from aipartnerupflow.core.execution import TaskCreator
        
        creator = TaskCreator(db_session)
        tasks = [
            {
                "id": "task_1",  # Optional: if provided, used for references
                "name": "Task 1",  # Required: if no id, name must be unique and used for references
                "user_id": "user_123",
                "priority": 1,
                "inputs": {"url": "https://example.com"},
                "schemas": {"type": "stdio", "method": "system_info"},
            },
            {
                "id": "task_2",  # Optional: if provided, used for references
                "name": "Task 2",  # Required: if no id, name must be unique and used for references
                "user_id": "user_123",
                "parent_id": "task_1",  # If tasks have id: use id; if not: use name
                "dependencies": [{"id": "task_1", "required": True}],  # Can use id or name
            }
        ]
        task_tree = await creator.create_task_tree_from_array(tasks)
    """
    
    def __init__(self, db: Session | AsyncSession):
        """
        Initialize TaskCreator
        
        Args:
            db: Database session (sync or async)
        """
        self.db = db
        self.task_manager = TaskManager(db)
    
    async def create_task_tree_from_array(
        self,
        tasks: List[Dict[str, Any]],
    ) -> TaskTreeNode:
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
            
            # Create task (parent_id and dependencies will be set in step 4)
            # Pass id if provided (as optional parameter)
            logger.debug(f"Creating task: name={task_name}, provided_id={provided_id}")
            task = await self.task_manager.task_repository.create_task(
                name=task_name,
                user_id=task_user_id,
                parent_id=None,  # Will be set in step 4
                priority=task_data.get("priority", 1),
                dependencies=None,  # Will be set in step 4
                inputs=task_data.get("inputs"),
                schemas=task_data.get("schemas"),
                params=task_data.get("params"),
                id=provided_id  # Optional: if None, TaskModel will auto-generate
            )
            
            logger.debug(f"Task created: id={task.id}, name={task.name}, provided_id={provided_id}")
            
            # Verify the task was created with the correct ID
            if provided_id and task.id != provided_id:
                logger.error(
                    f"Task ID mismatch: expected {provided_id}, got {task.id}. "
                    f"This indicates an issue with ID assignment."
                )
                raise ValueError(
                    f"Task ID mismatch: expected {provided_id}, got {task.id}. "
                    f"Task was not created with the specified ID."
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
                    if self.task_manager.is_async:
                        await self.db.commit()
                        await self.db.refresh(parent_task)
                    else:
                        self.db.commit()
                        self.db.refresh(parent_task)
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
                if self.task_manager.is_async:
                    await self.db.commit()
                    await self.db.refresh(task)
                else:
                    self.db.commit()
                    self.db.refresh(task)
        
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
    
    async def create_task_copy(self, original_task: TaskModel, children: bool = False) -> TaskTreeNode:
        """
        Create a copy of a task tree for re-execution.
        
        Preserves original task results while creating new execution instance.
        Automatically includes dependent tasks (tasks that depend on this task and its children,
        including transitive dependencies).
        
        Process:
        1. Get root task and all tasks in the tree for dependency lookup
        2. Build original_task's subtree (original_task + all its children)
        3. If children=True, also collect identifiers from each direct child's subtree
        4. Collect all task identifiers (id or name) from the subtree(s)
        5. Find all tasks that depend on these identifiers (including transitive dependencies)
           - Special handling for failed leaf nodes:
             * Check if original_subtree contains any failed leaf nodes
             * If failed leaf nodes exist: filter out pending dependent tasks
             * If no failed leaf nodes: copy all dependent tasks
        6. Collect all required task IDs (original_task subtree + filtered dependent tasks)
        7. Build minimal subtree containing all required tasks
        8. Copy entire tree structure
        9. Save copied tree to database
        10. Mark all original tasks as having copies
        
        Args:
            original_task: Original task to copy (can be root or any task in tree)
            children: If True, also copy each direct child task with its dependencies.
                     When copying children, tasks that depend on multiple copied tasks are
                     only copied once (deduplication by task ID).
            
        Returns:
            TaskTreeNode with copied task tree, all tasks linked to original via original_task_id
        """
        logger.info(f"Creating task copy for original task {original_task.id}, children={children}")
        
        # Step 1: Get root task and all tasks in the tree for dependency lookup
        # Note: children=True only supports dependencies within the same root tree
        root_task = await self.task_manager.task_repository.get_root_task(original_task)
        all_tasks = await self.task_manager.task_repository.get_all_tasks_in_tree(root_task)
        
        # Step 2: Build original_task's subtree (original_task + all its children)
        original_subtree = await self.task_manager.task_repository.build_task_tree(original_task)
        
        # Step 3: Collect all task identifiers (id or name) from the subtree
        task_identifiers = self._collect_task_identifiers_from_tree(original_subtree)
        
        # If children=True, also collect identifiers from each direct child's subtree
        if children:
            for child_node in original_subtree.children:
                child_identifiers = self._collect_task_identifiers_from_tree(child_node)
                task_identifiers.update(child_identifiers)
                logger.info(f"Collected {len(child_identifiers)} task identifiers from child {child_node.task.id} subtree")
        
        logger.info(f"Collected {len(task_identifiers)} total task identifiers (original_task + {'children' if children else 'no children'}): {task_identifiers}")
        
        # Step 4: Find all tasks that depend on these identifiers (including transitive dependencies)
        dependent_tasks = []
        if task_identifiers:
            all_dependent_tasks = await self._find_dependent_tasks_for_identifiers(task_identifiers, all_tasks)
            
            # Check if original_subtree contains any failed leaf nodes
            def has_failed_leaf_nodes(node: TaskTreeNode) -> bool:
                """Check if tree contains any failed leaf nodes"""
                task_status = getattr(node.task, 'status', None)
                is_leaf = not node.children
                is_failed_leaf = (task_status == "failed" and is_leaf)
                
                if is_failed_leaf:
                    return True
                
                # Recursively check children
                for child in node.children:
                    if has_failed_leaf_nodes(child):
                        return True
                
                return False
            
            has_failed_leaves = has_failed_leaf_nodes(original_subtree)
            
            if has_failed_leaves:
                # For tasks containing failed leaf nodes, only copy dependents that are NOT pending
                for dep_task in all_dependent_tasks:
                    dep_status = getattr(dep_task, 'status', None)
                    if dep_status != "pending":
                        dependent_tasks.append(dep_task)
                
                if all_dependent_tasks:
                    pending_count = len(all_dependent_tasks) - len(dependent_tasks)
                    logger.info(f"Found {len(all_dependent_tasks)} dependent tasks for subtree with failed leaf nodes, "
                              f"filtering out {pending_count} pending tasks, keeping {len(dependent_tasks)} non-pending tasks")
            else:
                # For other cases (no failed leaf nodes), copy all dependents
                dependent_tasks = all_dependent_tasks
                if dependent_tasks:
                    logger.info(f"Found {len(dependent_tasks)} dependent tasks for original_task subtree")
        
        # Step 5: Collect all required task IDs
        required_task_ids = set()
        
        # Add all tasks from original_task subtree
        def collect_subtree_task_ids(node: TaskTreeNode):
            required_task_ids.add(str(node.task.id))
            for child in node.children:
                collect_subtree_task_ids(child)
        
        collect_subtree_task_ids(original_subtree)
        
        # Add all dependent tasks
        for dep_task in dependent_tasks:
            required_task_ids.add(str(dep_task.id))
        
        logger.info(f"Total {len(required_task_ids)} tasks to copy: {len(self.tree_to_flat_list(original_subtree))} from original_task subtree + {len(dependent_tasks)} dependent tasks")
        
        # Step 6: Build minimal subtree containing all required tasks
        # Note: children=True only supports dependencies within the same root tree
        if not dependent_tasks:
            # No dependents: use original_task subtree directly
            minimal_tree = original_subtree
            logger.info(f"No dependents found, using original_task subtree directly")
        else:
            # Has dependents: find minimal subtree that includes original_task + all dependents
            # All dependents should be in the same root tree (children=True only supports same root tree)
            root_tree = await self.task_manager.task_repository.build_task_tree(root_task)
            minimal_tree = await self._find_minimal_subtree(root_tree, required_task_ids)
            
            if not minimal_tree:
                # Fallback: use original_subtree
                logger.warning(f"Could not build minimal subtree with dependents, falling back to original_task subtree")
                minimal_tree = original_subtree
        
        root_original_task_id = minimal_tree.task.id
        
        # Step 7: Copy entire tree structure
        new_tree = await self._copy_task_tree_recursive(minimal_tree, root_original_task_id, None)
        
        # Step 8: Save copied tree to database
        await self._save_copied_task_tree(new_tree, None)
        
        # Step 9: Mark all original tasks as having copies
        await self._mark_original_tasks_has_copy(minimal_tree)
        if self.task_manager.is_async:
            await self.db.commit()
        else:
            self.db.commit()
        
        logger.info(f"Created task copy: root task {new_tree.task.id} (original: {root_original_task_id}, includes {len(dependent_tasks)} dependent tasks)")
        
        return new_tree
    
    def _collect_task_identifiers_from_tree(self, node: TaskTreeNode) -> Set[str]:
        """
        Collect all task identifiers (id or name) from a task tree.
        
        Args:
            node: Task tree node
            
        Returns:
            Set of task identifiers in the tree
        """
        identifiers = set()
        # Use id as identifier (primary)
        identifiers.add(str(node.task.id))
        # Also use name if available (for dependency matching)
        if node.task.name:
            identifiers.add(node.task.name)
        
        for child_node in node.children:
            identifiers.update(self._collect_task_identifiers_from_tree(child_node))
        
        return identifiers
    
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
                        dep_name = dep.get("name")
                        if dep_id in task_identifiers or dep_name in task_identifiers:
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
                dep_id = str(dep_task.id)
                dep_name = dep_task.name if dep_task.name else None
                dep_identifiers = {dep_id}
                if dep_name:
                    dep_identifiers.add(dep_name)
                
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
                                    dep_name = dep.get("name")
                                    if dep_id in dep_identifiers or dep_name in dep_identifiers:
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
    
    async def _copy_task_tree_recursive(
        self,
        original_node: TaskTreeNode,
        root_original_task_id: str,
        parent_id: Optional[str] = None
    ) -> TaskTreeNode:
        """
        Recursively copy task tree structure.
        
        Args:
            original_node: Original task tree node to copy
            root_original_task_id: Root task ID for original_task_id linkage
            parent_id: Parent task ID (will be set after saving)
            
        Returns:
            New TaskTreeNode with copied task tree
        """
        # Create new task from original
        new_task = await self._create_task_copy_from_original(
            original_node.task,
            root_original_task_id,
            parent_id
        )
        
        # Create new task node
        new_node = TaskTreeNode(task=new_task)
        
        # Recursively copy children
        for child_node in original_node.children:
            child_new_node = await self._copy_task_tree_recursive(
                child_node,
                root_original_task_id,
                None  # parent_id will be set after saving
            )
            new_node.add_child(child_new_node)
        
        return new_node
    
    async def _create_task_copy_from_original(
        self,
        original_task: TaskModel,
        root_original_task_id: str,
        parent_id: Optional[str] = None
    ) -> TaskModel:
        """
        Create a new task instance copied from original task.
        
        Args:
            original_task: Original task to copy from
            root_original_task_id: Root task ID for original_task_id linkage
            parent_id: Parent task ID (will be set after saving)
            
        Returns:
            New TaskModel instance ready for execution
        """
        # Safely get values from SQLAlchemy columns
        schemas_value = getattr(original_task, 'schemas', None)
        dependencies_value = getattr(original_task, 'dependencies', None)
        inputs_value = getattr(original_task, 'inputs', None)
        params_value = getattr(original_task, 'params', None)
        
        return await self.task_manager.task_repository.create_task(
            name=original_task.name,
            user_id=original_task.user_id,
            parent_id=parent_id,  # Will be set to actual parent ID after saving
            priority=original_task.priority,
            dependencies=copy.deepcopy(dependencies_value) if dependencies_value else None,
            inputs=copy.deepcopy(inputs_value) if inputs_value else None,
            schemas=copy.deepcopy(schemas_value) if schemas_value else None,
            params=copy.deepcopy(params_value) if params_value else None,
            original_task_id=root_original_task_id,  # Link to root original task via kwargs
        )
    
    async def _save_copied_task_tree(self, node: TaskTreeNode, parent_id: Optional[str] = None):
        """
        Update parent_id references for copied task tree.
        Tasks are already saved by create_task, we just need to update parent_id.
        
        Args:
            node: Task tree node to update
            parent_id: Parent task ID
        """
        task = node.task
        if parent_id is not None:
            task.parent_id = parent_id
            # Update task in database
            if self.task_manager.is_async:
                await self.db.commit()
                await self.db.refresh(task)
            else:
                self.db.commit()
                self.db.refresh(task)
        
        # Recursively update children
        for child_node in node.children:
            await self._save_copied_task_tree(child_node, task.id)
    
    async def _mark_original_tasks_has_copy(self, node: TaskTreeNode):
        """
        Recursively mark all original tasks as having copies.
        
        Args:
            node: Task tree node to mark
        """
        node.task.has_copy = True
        if self.task_manager.is_async:
            await self.db.commit()
            await self.db.refresh(node.task)
        else:
            self.db.commit()
            self.db.refresh(node.task)
        
        # Recursively mark children
        for child_node in node.children:
            await self._mark_original_tasks_has_copy(child_node)


__all__ = [
    "TaskCreator",
]

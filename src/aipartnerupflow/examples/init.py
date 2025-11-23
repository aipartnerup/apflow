"""
Examples data initialization functions

This module provides functions to initialize example task data in the database.
"""

from typing import Optional
from aipartnerupflow.examples.data import get_example_tasks, EXAMPLE_USER_ID
from aipartnerupflow.core.storage import get_default_session
from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
from aipartnerupflow.core.config import get_task_model_class
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


async def check_if_examples_initialized() -> bool:
    """
    Check if examples data has already been initialized
    
    Returns:
        True if examples data exists, False otherwise
    """
    try:
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        # Check if any example tasks exist (by checking for the example user ID)
        from sqlalchemy import select, func
        
        if task_repository.is_async:
            stmt = select(func.count()).select_from(task_repository.task_model_class).filter(
                task_repository.task_model_class.user_id == EXAMPLE_USER_ID
            )
            result = await db_session.execute(stmt)
            count = result.scalar() or 0
        else:
            count = db_session.query(task_repository.task_model_class).filter(
                task_repository.task_model_class.user_id == EXAMPLE_USER_ID
            ).count()
        
        return count > 0
    except Exception as e:
        logger.warning(f"Error checking if examples are initialized: {e}")
        return False


async def init_examples_data(force: bool = False) -> int:
    """
    Initialize example task data in the database
    
    Args:
        force: If True, re-initialize even if examples already exist
        
    Returns:
        Number of tasks created
    """
    try:
        db_session = get_default_session()
        task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
        
        # Check if examples already exist
        if not force:
            if await check_if_examples_initialized():
                logger.info("Examples data already exists. Use force=True to re-initialize.")
                return 0
        
        # Get example task definitions
        example_tasks = get_example_tasks()
        
        # Create tasks in order (root tasks first, then children)
        # Sort by parent_id: None first, then by parent_id
        sorted_tasks = sorted(example_tasks, key=lambda t: (t.get("parent_id") is not None, t.get("parent_id") or ""))
        
        created_count = 0
        
        for task_data in sorted_tasks:
            try:
                # Create a copy to avoid modifying the original
                task_data_copy = task_data.copy()
                
                # Extract fields that should be set directly on the model
                task_id = task_data_copy.pop("id")
                status = task_data_copy.pop("status", "pending")
                progress = task_data_copy.pop("progress", 0.0)
                created_at = task_data_copy.pop("created_at", None)
                started_at = task_data_copy.pop("started_at", None)
                completed_at = task_data_copy.pop("completed_at", None)
                result = task_data_copy.pop("result", None)
                error = task_data_copy.pop("error", None)
                
                # Create the task
                task = await task_repository.create_task(
                    id=task_id,
                    **task_data_copy
                )
                
                # Update status and other fields that need to be set after creation
                if status != "pending":
                    await task_repository.update_task_status(
                        task_id=task.id,
                        status=status,
                        progress=progress,
                        result=result,
                        error=error,
                        started_at=started_at,
                        completed_at=completed_at
                    )
                
                # Update timestamps if provided
                if created_at:
                    task.created_at = created_at
                if started_at and not task.started_at:
                    task.started_at = started_at
                if completed_at and not task.completed_at:
                    task.completed_at = completed_at
                
                # Commit the task
                if task_repository.is_async:
                    await db_session.commit()
                    await db_session.refresh(task)
                else:
                    db_session.commit()
                    db_session.refresh(task)
                
                created_count += 1
                logger.debug(f"Created example task: {task.id} ({task.name})")
                
            except Exception as e:
                logger.warning(f"Failed to create example task {task_data.get('id', 'unknown')}: {e}")
                if task_repository.is_async:
                    await db_session.rollback()
                else:
                    db_session.rollback()
                continue
        
        logger.info(f"Initialized {created_count} example tasks")
        return created_count
        
    except Exception as e:
        logger.error(f"Error initializing examples data: {e}", exc_info=True)
        raise


def init_examples_data_sync(force: bool = False) -> int:
    """
    Synchronous wrapper for init_examples_data
    
    Args:
        force: If True, re-initialize even if examples already exist
        
    Returns:
        Number of tasks created
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is already running, we need to use a different approach
            import concurrent.futures
            import threading
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(init_examples_data(force=force))
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        else:
            return loop.run_until_complete(init_examples_data(force=force))
    except RuntimeError:
        # No event loop running, safe to use asyncio.run()
        return asyncio.run(init_examples_data(force=force))


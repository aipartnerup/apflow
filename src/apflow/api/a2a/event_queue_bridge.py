"""
Bridge between A2A EventQueue and TaskManager StreamingCallbacks
"""

import asyncio
from typing import Dict, Any
from a2a.server.events import EventQueue
from a2a.types import TaskStatusUpdateEvent, TaskStatus, TaskState
from a2a.utils import new_agent_parts_message, new_agent_text_message
from a2a.types import DataPart
from apflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class EventQueueBridge:
    """
    Bridge that converts TaskManager progress updates to A2A TaskStatusUpdateEvents
    """
    
    def __init__(self, event_queue: EventQueue, context: Any):
        """
        Initialize bridge
        
        Args:
            event_queue: A2A EventQueue
            context: RequestContext from A2A
        """
        self.event_queue = event_queue
        self.context = context
        self._update_queue = asyncio.Queue()
        self._bridge_task = None
        self.original_task_id = None  # Store original_task_id if copy_execution was used
        
        # Start background task to process updates
        self._start_bridge_task()
    
    def _start_bridge_task(self):
        """Start background task to bridge updates"""
        async def bridge_worker():
            while True:
                try:
                    update_data = await self._update_queue.get()
                    
                    if update_data is None:  # Sentinel to stop
                        break
                    
                    # Convert to A2A TaskStatusUpdateEvent
                    event = self._convert_to_task_status_event(update_data)
                    await self.event_queue.enqueue_event(event)
                    
                    self._update_queue.task_done()
                except Exception as e:
                    logger.error(f"Error in bridge worker: {str(e)}")
        
        self._bridge_task = asyncio.create_task(bridge_worker())
    
    async def put(self, update_data: Dict[str, Any]):
        """
        Put progress update to bridge
        
        Args:
            update_data: Progress update data from TaskManager
        """
        await self._update_queue.put(update_data)
    
    def _convert_to_task_status_event(self, update_data: Dict[str, Any]) -> TaskStatusUpdateEvent:
        """
        Convert TaskManager progress update to A2A TaskStatusUpdateEvent
        
        Args:
            update_data: Progress update data
            
        Returns:
            TaskStatusUpdateEvent
        """
        # Always use context.task_id for A2A protocol compliance
        # The actual task_id from update_data is stored in metadata for reference
        task_id = self.context.task_id
        if not task_id:
            raise ValueError("context.task_id is required for A2A protocol")
        
        update_type = update_data.get("type", "progress")
        status = update_data.get("status", "in_progress")
        
        # Map status to TaskState
        # TaskState enum values: submitted, working, input_required, completed, canceled, failed, rejected, auth_required, unknown
        state_map = {
            "completed": TaskState.completed,
            "failed": TaskState.failed,
            "in_progress": TaskState.working,  # Map in_progress to working
            "pending": TaskState.submitted,    # Map pending to submitted
            "cancelled": TaskState.canceled,
            "canceled": TaskState.canceled,
        }
        task_state = state_map.get(status, TaskState.working)  # Default to working for unknown statuses
        
        # Create message based on update type
        # Include actual task_id from update_data in the event data for reference
        actual_task_id = update_data.get("task_id")
        event_data = update_data.copy()
        # Add protocol identifier for A2A protocol responses
        event_data["protocol"] = "a2a"
        if actual_task_id and actual_task_id != task_id:
            # Store actual task_id in metadata for reference
            if "metadata" not in event_data:
                event_data["metadata"] = {}
            event_data["metadata"]["actual_task_id"] = actual_task_id
        
        # Add original_task_id if copy_execution was used
        if self.original_task_id:
            if "metadata" not in event_data:
                event_data["metadata"] = {}
            event_data["metadata"]["original_task_id"] = self.original_task_id
        
        if update_type == "final":
            message = new_agent_parts_message([
                DataPart(data=event_data.get("result") or event_data)
            ])
        elif update_type == "task_failed":
            message = new_agent_text_message(update_data.get("error", "Task failed"))
        else:
            # Progress or other updates
            message = new_agent_parts_message([
                DataPart(data=event_data)
            ])
        
        return TaskStatusUpdateEvent(
            task_id=task_id,  # Always use context.task_id for A2A protocol
            context_id=self.context.context_id or "unknown",
            status=TaskStatus(state=task_state, message=message),
            final=update_data.get("final", False)
        )
    
    async def close(self):
        """Close bridge and stop background task"""
        await self._update_queue.put(None)  # Sentinel to stop worker
        if self._bridge_task:
            await self._bridge_task


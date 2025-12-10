"""
Base task class with common implementations

Provides common functionality for executable tasks. You can inherit from
BaseTask to get common implementations, or implement ExecutableTask directly
for maximum flexibility.
"""

from typing import Dict, Any, Optional, Callable, Type, Union
from pydantic import BaseModel
from aipartnerupflow.core.interfaces.executable_task import ExecutableTask
from aipartnerupflow.core.utils.helpers import (
    get_input_schema as _get_input_schema,
    validate_input_schema as _validate_input_schema,
    check_input_schema as _check_input_schema
)


class BaseTask(ExecutableTask):
    """
    Base task class with common implementations (optional base class)
    
    Provides common functionality for executable tasks.
    You can inherit from BaseTask to get common implementations, or implement ExecutableTask
    directly for maximum flexibility.
    
    Inherit from BaseTask if you need:
    - Common initialization and input management
    - Streaming context support
    - Input validation utilities
    
    Implement ExecutableTask directly if you want:
    - Full control over implementation
    - Minimal dependencies
    """
    
    # Task definition properties - should be overridden by subclasses
    id: str = ""
    name: str = ""
    description: str = ""
    tags: list[str] = []
    examples: list[str] = []
    
    # Cancellation support
    # Set to True if executor supports cancellation during execution
    # Set to False if executor cannot be cancelled once execution starts
    cancelable: bool = False
    
    # Input schema for validation (can be Pydantic BaseModel or JSON schema dict)
    inputs_schema: Optional[Union[Type[BaseModel], Dict[str, Any]]] = None
    
    def __init__(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        inputs_schema: Optional[Union[Type[BaseModel], Dict[str, Any]]] = None,
        **kwargs: Any
    ):
        """
        Initialize BaseTask
        
        Args:
            inputs: Initial input parameters
            inputs_schema: Optional input schema for validation (Pydantic BaseModel or JSON schema dict)
            **kwargs: Additional configuration options
                - task_id: Task ID for cancellation checking (optional)
        """
        self.inputs: Dict[str, Any] = inputs or {}
        
        # Set input schema if provided
        if inputs_schema is not None:
            self.inputs_schema = inputs_schema
        
        # Streaming context for progress updates
        self.event_queue = None
        self.context = None
        
        # Cancellation checker callback (set by TaskManager)
        # Executor calls this function to check if task is cancelled
        # Returns True if cancelled, False otherwise
        self.cancellation_checker: Optional[Callable[[], bool]] = kwargs.get("cancellation_checker")
        
        # Initialize with any provided kwargs
        self.init(**kwargs)
    
    def init(self, **kwargs: Any) -> None:
        """Initialize task with configuration"""
        if "id" in kwargs:
            self.id = kwargs["id"]
        if "name" in kwargs:
            self.name = kwargs["name"]
        if "description" in kwargs:
            self.description = kwargs["description"]
        if "tags" in kwargs:
            self.tags = kwargs["tags"]
        if "examples" in kwargs:
            self.examples = kwargs["examples"]
        if "inputs" in kwargs:
            self.inputs = kwargs["inputs"]
        if "cancellation_checker" in kwargs:
            self.cancellation_checker = kwargs["cancellation_checker"]
        if "cancelable" in kwargs:
            self.cancelable = kwargs["cancelable"]
        if "inputs_schema" in kwargs:
            self.inputs_schema = kwargs["inputs_schema"]
    
    def set_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Set input parameters
        
        Args:
            inputs: Dictionary of inputs
        """
        self.inputs = inputs
    
    def set_streaming_context(self, event_queue: Any, context: Any) -> None:
        """
        Set streaming context for progress updates
        
        Args:
            event_queue: Event queue for streaming updates
            context: Request context
        """
        self.event_queue = event_queue
        self.context = context
    
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Get input parameter schema with metadata (required, type, description, default)
        
        Returns:
            Dictionary of parameter metadata, or empty dict if no schema defined
        """
        if self.inputs_schema:
            return _get_input_schema(self.inputs_schema)
        return {}
    
    def validate_input_schema(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate parameters using input schema
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            True if valid, False otherwise
        """
        if self.inputs_schema:
            return _validate_input_schema(self.inputs_schema, parameters)
        return True
    
    def check_input_schema(self, parameters: Dict[str, Any]) -> None:
        """
        Check parameters using input schema (raises exception if invalid)
        
        Args:
            parameters: Parameters to check
            
        Raises:
            ValueError: If validation fails
        """
        if self.inputs_schema:
            _check_input_schema(self.inputs_schema, parameters)
    
    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Optional method to provide custom demo data for this executor
        
        This method is called when use_demo=True is set in task inputs.
        Executors can override this method to provide realistic demo data
        that matches their actual execution results.
        
        Args:
            task: TaskModel instance for this task
            inputs: Input parameters for the task
        
        Returns:
            Demo result dictionary, or None to use default demo data.
            If returning a dict, it should match the format of actual execution results.
            The "demo_mode" field will be automatically added by TaskManager.
        
        Example:
            def get_demo_result(self, task, inputs):
                return {
                    "status": "completed",
                    "result": "Demo execution result",
                    "data": {"processed": True}
                }
        """
        # Default implementation: return None to use default demo data
        return None


__all__ = ["BaseTask"]


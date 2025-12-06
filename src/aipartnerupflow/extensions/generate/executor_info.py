"""
Executor Information Collector

This module collects information about available executors and their schemas
for use in LLM context when generating task trees.
"""

from typing import Dict, Any, List, Optional
from aipartnerupflow.core.extensions.registry import get_registry
from aipartnerupflow.core.extensions.types import ExtensionCategory
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


def get_available_executors() -> List[Dict[str, Any]]:
    """
    Get all registered executors with their metadata
    
    Returns:
        List of executor dictionaries containing id, name, description, and schema
    """
    registry = get_registry()
    executors = []
    
    # Get all registered executor extensions
    executor_extensions = registry.list_executors()
    
    for extension in executor_extensions:
        try:
            # Get executor metadata from extension
            executor_id = extension.id
            executor_name = extension.name
            executor_description = getattr(extension, 'description', '')
            executor_tags = getattr(extension, 'tags', [])
            executor_type = extension.type or "default"
            
            # Try to get input schema
            input_schema = None
            try:
                # Try to create a temporary instance to get schema
                # Use registry's create_executor_instance method
                temp_executor = registry.create_executor_instance(executor_id, inputs={})
                if temp_executor and hasattr(temp_executor, 'get_input_schema'):
                    input_schema = temp_executor.get_input_schema()
            except Exception as e:
                logger.debug(f"Could not get schema for executor {executor_id}: {e}")
                # Try to get schema from extension if it has the method
                if hasattr(extension, 'get_input_schema'):
                    try:
                        input_schema = extension.get_input_schema()
                    except Exception:
                        pass
                # Try to get schema from class if it's a class attribute
                if not input_schema:
                    executor_class = extension.__class__
                    if hasattr(executor_class, 'inputs_schema'):
                        input_schema = executor_class.inputs_schema
                        if hasattr(input_schema, 'model_json_schema'):
                            # Pydantic model
                            input_schema = input_schema.model_json_schema()
                        elif hasattr(input_schema, 'schema'):
                            # Pydantic v1
                            input_schema = input_schema.schema()
            
            executor_info = {
                "id": executor_id,
                "name": executor_name,
                "description": executor_description,
                "tags": executor_tags,
                "task_type": executor_type,
                "input_schema": input_schema
            }
            
            executors.append(executor_info)
            
        except Exception as e:
            logger.warning(f"Error collecting info for executor {getattr(extension, 'id', 'unknown')}: {e}")
            continue
    
    return executors


def get_executor_schema(executor_id: str) -> Optional[Dict[str, Any]]:
    """
    Get input schema for a specific executor
    
    Args:
        executor_id: Executor ID to look up
        
    Returns:
        Input schema dictionary, or None if executor not found
    """
    executors = get_available_executors()
    for executor in executors:
        if executor["id"] == executor_id:
            return executor.get("input_schema")
    return None


def format_executors_for_llm() -> str:
    """
    Format executor information for LLM context
    
    Returns:
        Formatted string containing all executor information
    """
    executors = get_available_executors()
    
    if not executors:
        return "No executors are currently registered."
    
    lines = ["Available Executors:", "=" * 80, ""]
    
    for executor in executors:
        lines.append(f"Executor ID: {executor['id']}")
        lines.append(f"Name: {executor['name']}")
        lines.append(f"Description: {executor['description']}")
        if executor.get('tags'):
            lines.append(f"Tags: {', '.join(executor['tags'])}")
        lines.append(f"Task Type: {executor['task_type']}")
        
        # Format input schema
        input_schema = executor.get('input_schema')
        if input_schema:
            lines.append("Input Schema:")
            if isinstance(input_schema, dict):
                # Format JSON schema
                properties = input_schema.get('properties', {})
                required = input_schema.get('required', [])
                
                for prop_name, prop_info in properties.items():
                    prop_type = prop_info.get('type', 'unknown')
                    prop_desc = prop_info.get('description', '')
                    is_required = prop_name in required
                    req_marker = " (required)" if is_required else " (optional)"
                    lines.append(f"  - {prop_name}: {prop_type}{req_marker}")
                    if prop_desc:
                        lines.append(f"    Description: {prop_desc}")
            else:
                lines.append(f"  {input_schema}")
        else:
            lines.append("Input Schema: Not available")
        
        lines.append("")
    
    return "\n".join(lines)


__all__ = [
    "get_available_executors",
    "get_executor_schema",
    "format_executors_for_llm",
]


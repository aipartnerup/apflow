"""
Type definitions for CrewAI features (CrewaiExecutor and BatchCrewaiExecutor)
"""

from typing import Dict, Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field
from datetime import datetime


class CrewaiExecutorState(BaseModel):
    """State class for CrewaiExecutor (LLM-based agent crews)"""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = "pending"
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BatchState(BaseModel):
    """State class for BatchCrewaiExecutor (batch execution of multiple crews)"""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = "pending"
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Backward compatibility aliases
FlowState = BatchState
CrewState = CrewaiExecutorState


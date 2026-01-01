"""
CrewAI feature for apflow

Provides LLM-based task execution via CrewAI and batch execution capabilities.

Requires: pip install apflow[crewai]
"""

from apflow.extensions.crewai.crewai_executor import CrewaiExecutor
from apflow.extensions.crewai.batch_crewai_executor import BatchCrewaiExecutor
from apflow.extensions.crewai.types import (
    CrewaiExecutorState,
    BatchState,
    # Backward compatibility aliases
    FlowState,
    CrewState,
)
# Import tools from core.tools (tools framework is now in core)
from apflow.core.tools import (
    ToolRegistry,
    get_tool_registry,
    register_tool,
    resolve_tool,
    tool_register,
)

# Backward compatibility: alias tool_register as crew_tool
crew_tool = tool_register

__all__ = [
    "CrewaiExecutor",
    "BatchCrewaiExecutor",
    "CrewaiExecutorState",
    "BatchState",
    # Backward compatibility aliases
    "FlowState",
    "CrewState",
    # Tools (from core.tools)
    "ToolRegistry",
    "get_tool_registry",
    "register_tool",
    "tool_register",
    "crew_tool",  # Backward compatibility alias
    "resolve_tool",
]


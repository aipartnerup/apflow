"""
Base Tool class for all tools

Compatible with CrewAI's BaseTool interface, but doesn't require crewai library.
Tools can be used independently or with CrewAI agents.

Performance Note: CrewAI import is deferred to keep startup time fast.
"""

from typing import Any
from abc import ABC

# Try to use CrewAI's BaseTool if available, otherwise use our own implementation
# This ensures tools are actual CrewAI BaseTool instances when CrewAI is available,
# which is required for CrewAI Agent validation.
try:
    from crewai.tools.base_tool import BaseTool as CrewAIBaseTool
    
    class BaseTool(CrewAIBaseTool, ABC):
        """
        Base class for all tools
        
        Compatible with CrewAI's BaseTool interface.
        If CrewAI is installed, inherits from CrewAI's BaseTool for full compatibility.
        This ensures tools are actual CrewAI BaseTool instances, which is required
        for CrewAI Agent validation.
        
        Subclasses should implement _run() method for synchronous execution
        and optionally _arun() for asynchronous execution.
        """
        pass
    
    # Add is_crewai_compatible method
    @classmethod
    def is_crewai_compatible(cls) -> bool:
        """
        Check if CrewAI is available for enhanced features
        
        Returns:
            True if crewai is installed and this tool can use CrewAI features
        """
        return True
    
    BaseTool.is_crewai_compatible = is_crewai_compatible
    
except ImportError:
    # CrewAI not available, use standalone implementation
    from pydantic import BaseModel, Field
    
    class BaseTool(BaseModel, ABC):
        """
        Base class for all tools (standalone implementation)
        
        This is used when CrewAI is not installed.
        Provides the same interface as CrewAI's BaseTool for compatibility.
        
        Subclasses should implement _run() method for synchronous execution
        and optionally _arun() for asynchronous execution.
        """
        name: str = Field(..., description="Tool name")
        description: str = Field(..., description="Tool description")
        
        def _run(self, *args: Any, **kwargs: Any) -> Any:
            """
            Synchronous execution - must be implemented by subclass
            """
            raise NotImplementedError("Subclass must implement _run()")
        
        async def _arun(self, *args: Any, **kwargs: Any) -> Any:
            """
            Asynchronous execution - optional, defaults to calling _run()
            """
            return self._run(*args, **kwargs)
        
        @classmethod
        def is_crewai_compatible(cls) -> bool:
            """
            Check if CrewAI is available for enhanced features
            
            Returns:
                True if crewai is installed and this tool can use CrewAI features
            """
            return False


__all__ = ["BaseTool"]

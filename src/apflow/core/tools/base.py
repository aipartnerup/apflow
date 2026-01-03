"""
Base Tool class for all tools

Compatible with CrewAI's BaseTool interface, but doesn't require crewai library.
Tools can be used independently or with CrewAI agents.

Performance Note: CrewAI import is deferred to keep startup time fast.
"""

from typing import Type, Optional, Any
from abc import ABC
from pydantic import BaseModel, Field


class BaseTool(BaseModel, ABC):
    """
    Base class for all tools
    
    Compatible with CrewAI's BaseTool interface.
    If CrewAI is installed, this tool can be used with CrewAI agents.
    If CrewAI is not installed, tool works standalone.
    
    Subclasses should implement _run() method for synchronous execution
    and optionally _arun() for asynchronous execution.
    
    Performance: CrewAI compatibility is checked at runtime, not import time,
    to keep CLI startup fast (avoids 5.4s CrewAI import).
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
        try:
            import crewai
            return True
        except ImportError:
            return False
    
    class BaseTool(ABC):
        """
        Base class for all tools (standalone implementation)
        
        This is used when CrewAI is not installed.
        Provides the same interface as CrewAI's BaseTool for compatibility.
        
        Subclasses should implement _run() method for synchronous execution
        and optionally _arun() for asynchronous execution.
        """
        name: str = ""
        description: str = ""
        args_schema: Optional[Type[BaseModel]] = None
        
        def _run(self, *args, **kwargs) -> Any:
            """
            Execute the tool (synchronous)
            
            Subclasses must implement this method.
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Tool execution result
            """
            raise NotImplementedError("Subclasses must implement _run method")
        
        def run(self, *args, **kwargs) -> Any:
            """
            Public interface for running the tool
            Delegates to _run() for compatibility with CrewAI
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Tool execution result
            """
            return self._run(*args, **kwargs)
        
        async def _arun(self, *args, **kwargs) -> Any:
            """
            Execute the tool (asynchronous) - optional
            
            Subclasses can implement this method for async execution.
            If not implemented, _run() will be used.
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Tool execution result
            """
            raise NotImplementedError("Async execution not implemented. Use _run() instead.")
        
        async def arun(self, *args, **kwargs) -> Any:
            """
            Public interface for async tool execution
            Delegates to _arun() for compatibility with CrewAI
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Tool execution result
            """
            return await self._arun(*args, **kwargs)


__all__ = ["BaseTool"]


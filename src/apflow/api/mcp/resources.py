"""
MCP Resources Definition

Defines MCP resources that expose apflow task data.
"""

from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, parse_qs
from apflow.api.mcp.adapter import TaskRoutesAdapter
from apflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class McpResource:
    """Represents an MCP resource"""
    
    def __init__(
        self,
        uri: str,
        name: str,
        description: str,
        mime_type: str = "application/json"
    ):
        self.uri = uri
        self.name = name
        self.description = description
        self.mime_type = mime_type
    
    def to_mcp_dict(self) -> Dict[str, Any]:
        """Convert to MCP resource definition format"""
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type
        }


class McpResourcesRegistry:
    """Registry of MCP resources"""
    
    def __init__(self, adapter: TaskRoutesAdapter):
        self.adapter = adapter
    
    def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources
        
        Returns:
            List of resource definitions
        """
        return [
            {
                "uri": "task://*",
                "name": "Task Resource",
                "description": "Access individual task data by ID (e.g., task://{task_id})",
                "mimeType": "application/json"
            },
            {
                "uri": "tasks://",
                "name": "Tasks List Resource",
                "description": "Access task list with optional query parameters (e.g., tasks://?status=running&limit=10)",
                "mimeType": "application/json"
            }
        ]
    
    async def read_resource(
        self,
        uri: str,
        request: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Read a resource by URI
        
        Args:
            uri: Resource URI (e.g., task://{task_id} or tasks://?status=running)
            request: Optional request object (for HTTP mode)
        
        Returns:
            Resource content in MCP format
        
        Raises:
            ValueError: If URI format is invalid
        """
        parsed = urlparse(uri)
        scheme = parsed.scheme
        
        if scheme == "task":
            # Single task resource: task://{task_id}
            task_id = parsed.netloc or parsed.path.lstrip("/")
            if not task_id:
                raise ValueError(f"Invalid task URI: {uri}. Expected task://{{task_id}}")
            
            # Get task data
            result = await self.adapter.get_task(
                {"task_id": task_id, "request_id": ""},
                request
            )
            
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": self._format_result(result)
                    }
                ]
            }
        
        elif scheme == "tasks":
            # Tasks list resource: tasks://?status=running&limit=10
            query_params = parse_qs(parsed.query)
            
            # Convert query params to dict
            params = {}
            if "status" in query_params:
                params["status"] = query_params["status"][0]
            if "limit" in query_params:
                params["limit"] = int(query_params["limit"][0])
            if "offset" in query_params:
                params["offset"] = int(query_params["offset"][0])
            
            # List tasks
            result = await self.adapter.list_tasks(
                {**params, "request_id": ""},
                request
            )
            
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": self._format_result(result)
                    }
                ]
            }
        
        else:
            raise ValueError(f"Unsupported resource scheme: {scheme}. Supported: task://, tasks://")
    
    def _format_result(self, result: Any) -> str:
        """Format result as text for MCP response"""
        import json
        if isinstance(result, dict):
            return json.dumps(result, indent=2, ensure_ascii=False)
        elif isinstance(result, list):
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            return str(result)


"""
Test McpResourcesRegistry

Tests for MCP resources registry and resource reading.
"""

import pytest
from unittest.mock import AsyncMock, patch
from apflow.api.mcp.resources import McpResourcesRegistry
from apflow.api.mcp.adapter import TaskRoutesAdapter


class TestMcpResourcesRegistry:
    """Test McpResourcesRegistry functionality"""
    
    @pytest.fixture
    def registry(self):
        """Create resources registry instance"""
        adapter = TaskRoutesAdapter()
        return McpResourcesRegistry(adapter)
    
    def test_list_resources(self, registry):
        """Test listing all resources"""
        resources = registry.list_resources()
        
        assert isinstance(resources, list)
        assert len(resources) > 0
        
        # Check resource structure
        for resource in resources:
            assert "uri" in resource
            assert "name" in resource
            assert "description" in resource
            assert "mimeType" in resource
        
        # Check for expected resources
        uris = [r["uri"] for r in resources]
        assert any("task://" in uri for uri in uris)
        assert any("tasks://" in uri for uri in uris)
    
    @pytest.mark.asyncio
    async def test_read_resource_task(self, registry):
        """Test reading a task resource"""
        mock_result = {
            "id": "test-task-id",
            "name": "test-task",
            "status": "pending"
        }
        
        with patch.object(registry.adapter, 'get_task', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_result
            
            result = await registry.read_resource("task://test-task-id")
            
            assert "contents" in result
            assert len(result["contents"]) > 0
            assert result["contents"][0]["uri"] == "task://test-task-id"
            assert result["contents"][0]["mimeType"] == "application/json"
            assert "text" in result["contents"][0]
            mock_get.assert_called_once()
            assert mock_get.call_args[0][0]["task_id"] == "test-task-id"
    
    @pytest.mark.asyncio
    async def test_read_resource_tasks_list(self, registry):
        """Test reading tasks list resource"""
        mock_result = {
            "tasks": [{"id": "task-1"}, {"id": "task-2"}],
            "total": 2
        }
        
        with patch.object(registry.adapter, 'list_tasks', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_result
            
            result = await registry.read_resource("tasks://")
            
            assert "contents" in result
            assert len(result["contents"]) > 0
            assert result["contents"][0]["uri"] == "tasks://"
            assert result["contents"][0]["mimeType"] == "application/json"
            mock_list.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_resource_tasks_with_query_params(self, registry):
        """Test reading tasks list resource with query parameters"""
        mock_result = {"tasks": [{"id": "task-1"}], "total": 1}
        
        with patch.object(registry.adapter, 'list_tasks', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_result
            
            result = await registry.read_resource("tasks://?status=running&limit=10")
            
            assert "contents" in result
            mock_list.assert_called_once()
            call_args = mock_list.call_args[0][0]
            assert call_args.get("status") == "running"
            assert call_args.get("limit") == 10
    
    @pytest.mark.asyncio
    async def test_read_resource_tasks_with_offset(self, registry):
        """Test reading tasks list resource with offset"""
        mock_result = {"tasks": [], "total": 0}
        
        with patch.object(registry.adapter, 'list_tasks', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_result
            
            result = await registry.read_resource("tasks://?offset=20&limit=10")
            
            assert "contents" in result
            call_args = mock_list.call_args[0][0]
            assert call_args.get("offset") == 20
            assert call_args.get("limit") == 10
    
    @pytest.mark.asyncio
    async def test_read_resource_invalid_uri(self, registry):
        """Test reading resource with invalid URI"""
        with pytest.raises(ValueError, match="Unsupported resource scheme"):
            await registry.read_resource("invalid://test")
    
    @pytest.mark.asyncio
    async def test_read_resource_task_missing_id(self, registry):
        """Test reading task resource with missing ID"""
        with pytest.raises(ValueError, match="Invalid task URI"):
            await registry.read_resource("task://")
    
    @pytest.mark.asyncio
    async def test_read_resource_error_handling(self, registry):
        """Test error handling in resource reading"""
        with patch.object(registry.adapter, 'get_task', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Test error")
            
            with pytest.raises(Exception, match="Test error"):
                await registry.read_resource("task://test-task-id")


"""
Test McpToolsRegistry

Tests for MCP tools registry and tool calling.
"""

import pytest
from unittest.mock import AsyncMock, patch
from apflow.api.mcp.tools import McpToolsRegistry, McpTool
from apflow.api.mcp.adapter import TaskRoutesAdapter


class TestMcpTool:
    """Test McpTool class"""
    
    def test_to_mcp_dict(self):
        """Test converting tool to MCP format"""
        tool = McpTool(
            name="test_tool",
            description="Test tool description",
            input_schema={"type": "object", "properties": {}}
        )
        
        result = tool.to_mcp_dict()
        
        assert result["name"] == "test_tool"
        assert result["description"] == "Test tool description"
        assert result["inputSchema"] == {"type": "object", "properties": {}}


class TestMcpToolsRegistry:
    """Test McpToolsRegistry functionality"""
    
    @pytest.fixture
    def registry(self):
        """Create tools registry instance"""
        adapter = TaskRoutesAdapter()
        return McpToolsRegistry(adapter)
    
    def test_list_tools(self, registry):
        """Test listing all tools"""
        tools = registry.list_tools()
        
        assert isinstance(tools, list)
        assert len(tools) > 0
        
        # Check that all tools have required fields
        tool_names = [tool["name"] for tool in tools]
        assert "execute_task" in tool_names
        assert "create_task" in tool_names
        assert "get_task" in tool_names
        assert "update_task" in tool_names
        assert "delete_task" in tool_names
        assert "list_tasks" in tool_names
        assert "get_task_status" in tool_names
        assert "cancel_task" in tool_names
        
        # Check tool structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
    
    @pytest.mark.asyncio
    async def test_call_tool_execute_task(self, registry):
        """Test calling execute_task tool"""
        mock_result = {
            "success": True,
            "root_task_id": "test-root-id"
        }
        
        with patch.object(registry.adapter, 'execute_task', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_result
            
            result = await registry.call_tool(
                "execute_task",
                {"task_id": "test-task-id"}
            )
            
            assert "content" in result
            assert len(result["content"]) > 0
            assert result["content"][0]["type"] == "text"
            mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_tool_create_task(self, registry):
        """Test calling create_task tool"""
        mock_result = {"id": "test-task-id", "name": "test-task"}
        
        with patch.object(registry.adapter, 'create_task', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_result
            
            result = await registry.call_tool(
                "create_task",
                {"tasks": [{"name": "test-task"}]}
            )
            
            assert "content" in result
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_tool_get_task(self, registry):
        """Test calling get_task tool"""
        mock_result = {"id": "test-task-id", "name": "test-task"}
        
        with patch.object(registry.adapter, 'get_task', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_result
            
            result = await registry.call_tool(
                "get_task",
                {"task_id": "test-task-id"}
            )
            
            assert "content" in result
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_tool_update_task(self, registry):
        """Test calling update_task tool"""
        mock_result = {"id": "test-task-id", "name": "updated-task"}
        
        with patch.object(registry.adapter, 'update_task', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_result
            
            result = await registry.call_tool(
                "update_task",
                {"task_id": "test-task-id", "name": "updated-task"}
            )
            
            assert "content" in result
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_tool_delete_task(self, registry):
        """Test calling delete_task tool"""
        mock_result = {"success": True, "deleted": "test-task-id"}
        
        with patch.object(registry.adapter, 'delete_task', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_result
            
            result = await registry.call_tool(
                "delete_task",
                {"task_id": "test-task-id"}
            )
            
            assert "content" in result
            mock_delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_tool_list_tasks(self, registry):
        """Test calling list_tasks tool"""
        mock_result = {"tasks": [{"id": "task-1"}], "total": 1}
        
        with patch.object(registry.adapter, 'list_tasks', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_result
            
            result = await registry.call_tool(
                "list_tasks",
                {"status": "pending"}
            )
            
            assert "content" in result
            mock_list.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_tool_get_task_status(self, registry):
        """Test calling get_task_status tool"""
        mock_result = {"task_id": "test-task-id", "status": "running"}
        
        with patch.object(registry.adapter, 'get_task_status', new_callable=AsyncMock) as mock_status:
            mock_status.return_value = mock_result
            
            result = await registry.call_tool(
                "get_task_status",
                {"task_id": "test-task-id"}
            )
            
            assert "content" in result
            mock_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_tool_cancel_task(self, registry):
        """Test calling cancel_task tool"""
        mock_result = {"success": True, "task_id": "test-task-id"}
        
        with patch.object(registry.adapter, 'cancel_task', new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = mock_result
            
            result = await registry.call_tool(
                "cancel_task",
                {"task_id": "test-task-id"}
            )
            
            assert "content" in result
            mock_cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self, registry):
        """Test calling unknown tool raises error"""
        with pytest.raises(ValueError, match="Tool not found"):
            await registry.call_tool("unknown_tool", {})
    
    @pytest.mark.asyncio
    async def test_call_tool_error_handling(self, registry):
        """Test error handling in tool calls"""
        with patch.object(registry.adapter, 'execute_task', new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = Exception("Test error")
            
            with pytest.raises(Exception, match="Test error"):
                await registry.call_tool("execute_task", {"task_id": "test-id"})


"""
Test McpExecutor

Tests for MCP (Model Context Protocol) executor functionality.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from apflow.extensions.mcp.mcp_executor import McpExecutor


class TestMcpExecutor:
    """Test McpExecutor functionality"""
    
    @pytest.mark.asyncio
    async def test_execute_list_tools_stdio(self):
        """Test listing tools via stdio transport"""
        executor = McpExecutor()
        
        # Mock MCP server response
        mock_response = {
            "jsonrpc": "2.0",
            "id": "mcp_123",
            "result": {
                "tools": [
                    {"name": "search_web", "description": "Search the web"},
                    {"name": "read_file", "description": "Read a file"}
                ]
            }
        }
        
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(
                json.dumps(mock_response).encode('utf-8'),
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await executor.execute({
                "transport": "stdio",
                "command": ["python", "-m", "mcp_server"],
                "operation": "list_tools"
            })
            
            assert result["success"] is True
            assert "tools" in result["result"]
            assert len(result["result"]["tools"]) == 2
    
    @pytest.mark.asyncio
    async def test_execute_call_tool_stdio(self):
        """Test calling a tool via stdio transport"""
        executor = McpExecutor()
        
        mock_response = {
            "jsonrpc": "2.0",
            "id": "mcp_123",
            "result": {
                "content": [
                    {"type": "text", "text": "Search results..."}
                ]
            }
        }
        
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(
                json.dumps(mock_response).encode('utf-8'),
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await executor.execute({
                "transport": "stdio",
                "command": ["python", "-m", "mcp_server"],
                "operation": "call_tool",
                "tool_name": "search_web",
                "arguments": {"query": "Python async"}
            })
            
            assert result["success"] is True
            assert "result" in result
            mock_process.communicate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_list_resources_stdio(self):
        """Test listing resources via stdio transport"""
        executor = McpExecutor()
        
        mock_response = {
            "jsonrpc": "2.0",
            "id": "mcp_123",
            "result": {
                "resources": [
                    {"uri": "file:///path/to/file.txt", "name": "file.txt"}
                ]
            }
        }
        
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(
                json.dumps(mock_response).encode('utf-8'),
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await executor.execute({
                "transport": "stdio",
                "command": ["python", "-m", "mcp_server"],
                "operation": "list_resources"
            })
            
            assert result["success"] is True
            assert "resources" in result["result"]
    
    @pytest.mark.asyncio
    async def test_execute_read_resource_stdio(self):
        """Test reading a resource via stdio transport"""
        executor = McpExecutor()
        
        mock_response = {
            "jsonrpc": "2.0",
            "id": "mcp_123",
            "result": {
                "contents": [
                    {"uri": "file:///path/to/file.txt", "mimeType": "text/plain", "text": "File content"}
                ]
            }
        }
        
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(
                json.dumps(mock_response).encode('utf-8'),
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await executor.execute({
                "transport": "stdio",
                "command": ["python", "-m", "mcp_server"],
                "operation": "read_resource",
                "resource_uri": "file:///path/to/file.txt"
            })
            
            assert result["success"] is True
            assert "contents" in result["result"]
    
    @pytest.mark.asyncio
    async def test_execute_missing_transport(self):
        """Test error when transport is missing"""
        executor = McpExecutor()
        
        with pytest.raises(ValueError, match="transport is required"):
            await executor.execute({
                "operation": "list_tools"
            })
    
    @pytest.mark.asyncio
    async def test_execute_missing_operation(self):
        """Test error when operation is missing"""
        executor = McpExecutor()
        
        with pytest.raises(ValueError, match="operation is required"):
            await executor.execute({
                "transport": "stdio"
            })
    
    @pytest.mark.asyncio
    async def test_execute_missing_command_stdio(self):
        """Test error when command is missing for stdio transport"""
        executor = McpExecutor()
        
        result = await executor.execute({
            "transport": "stdio",
            "operation": "list_tools"
        })
        
        assert result["success"] is False
        assert "command is required" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_missing_url_http(self):
        """Test error when url is missing for http transport"""
        executor = McpExecutor()
        
        with patch("apflow.extensions.mcp.mcp_executor.HTTPX_AVAILABLE", True):
            result = await executor.execute({
                "transport": "http",
                "operation": "list_tools"
            })
            
            assert result["success"] is False
            assert "url is required" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_missing_tool_name(self):
        """Test error when tool_name is missing for call_tool"""
        executor = McpExecutor()
        
        result = await executor.execute({
            "transport": "stdio",
            "command": ["python", "-m", "mcp_server"],
            "operation": "call_tool",
            "arguments": {"query": "test"}
        })
        
        assert result["success"] is False
        assert "tool_name is required" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_missing_resource_uri(self):
        """Test error when resource_uri is missing for read_resource"""
        executor = McpExecutor()
        
        result = await executor.execute({
            "transport": "stdio",
            "command": ["python", "-m", "mcp_server"],
            "operation": "read_resource"
        })
        
        assert result["success"] is False
        assert "resource_uri is required" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_unsupported_transport(self):
        """Test error for unsupported transport mode"""
        executor = McpExecutor()
        
        result = await executor.execute({
            "transport": "websocket",
            "operation": "list_tools"
        })
        
        assert result["success"] is False
        assert "Unsupported transport mode" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_unsupported_operation(self):
        """Test error for unsupported operation"""
        executor = McpExecutor()
        
        result = await executor.execute({
            "transport": "stdio",
            "command": ["python", "-m", "mcp_server"],
            "operation": "invalid_operation"
        })
        
        assert result["success"] is False
        assert "Unsupported operation" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_stdio_process_error(self):
        """Test handling stdio process errors"""
        executor = McpExecutor()
        
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(
                b"",
                b"Error: Command not found"
            ))
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process
            
            result = await executor.execute({
                "transport": "stdio",
                "command": ["invalid_command"],
                "operation": "list_tools"
            })
            
            assert result["success"] is False
            assert "MCP server error" in result["error"]
            assert result["return_code"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_stdio_invalid_json(self):
        """Test handling invalid JSON response from stdio"""
        executor = McpExecutor()
        
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(
                b"Invalid JSON response",
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await executor.execute({
                "transport": "stdio",
                "command": ["python", "-m", "mcp_server"],
                "operation": "list_tools"
            })
            
            assert result["success"] is False
            assert "Invalid JSON response" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_stdio_timeout(self):
        """Test handling stdio timeout"""
        executor = McpExecutor()
        
        with patch("asyncio.create_subprocess_exec") as mock_subprocess, \
             patch("asyncio.wait_for") as mock_wait:
            mock_process = AsyncMock()
            mock_subprocess.return_value = mock_process
            mock_wait.side_effect = asyncio.TimeoutError()
            
            result = await executor.execute({
                "transport": "stdio",
                "command": ["python", "-m", "mcp_server"],
                "operation": "list_tools",
                "timeout": 1.0
            })
            
            assert result["success"] is False
            assert "timeout" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_http_list_tools(self):
        """Test listing tools via HTTP transport"""
        executor = McpExecutor()
        
        mock_response = {
            "jsonrpc": "2.0",
            "id": "mcp_123",
            "result": {
                "tools": [
                    {"name": "search_web", "description": "Search the web"}
                ]
            }
        }
        
        with patch("apflow.extensions.mcp.mcp_executor.HTTPX_AVAILABLE", True), \
             patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            mock_http_response = MagicMock()
            mock_http_response.status_code = 200
            mock_http_response.json.return_value = mock_response
            mock_client_instance.post = AsyncMock(return_value=mock_http_response)
            
            result = await executor.execute({
                "transport": "http",
                "url": "http://localhost:8000/mcp",
                "operation": "list_tools"
            })
            
            assert result["success"] is True
            assert "tools" in result["result"]
            mock_client_instance.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_http_call_tool(self):
        """Test calling a tool via HTTP transport"""
        executor = McpExecutor()
        
        mock_response = {
            "jsonrpc": "2.0",
            "id": "mcp_123",
            "result": {
                "content": [{"type": "text", "text": "Result"}]
            }
        }
        
        with patch("apflow.extensions.mcp.mcp_executor.HTTPX_AVAILABLE", True), \
             patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            mock_http_response = MagicMock()
            mock_http_response.status_code = 200
            mock_http_response.json.return_value = mock_response
            mock_client_instance.post = AsyncMock(return_value=mock_http_response)
            
            result = await executor.execute({
                "transport": "http",
                "url": "http://localhost:8000/mcp",
                "operation": "call_tool",
                "tool_name": "search_web",
                "arguments": {"query": "test"}
            })
            
            assert result["success"] is True
            assert "result" in result
    
    @pytest.mark.asyncio
    async def test_execute_http_error_response(self):
        """Test handling HTTP error response"""
        executor = McpExecutor()
        
        mock_response = {
            "jsonrpc": "2.0",
            "id": "mcp_123",
            "error": {
                "code": -32601,
                "message": "Method not found"
            }
        }
        
        with patch("apflow.extensions.mcp.mcp_executor.HTTPX_AVAILABLE", True), \
             patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            mock_http_response = MagicMock()
            mock_http_response.status_code = 200
            mock_http_response.json.return_value = mock_response
            mock_client_instance.post = AsyncMock(return_value=mock_http_response)
            
            result = await executor.execute({
                "transport": "http",
                "url": "http://localhost:8000/mcp",
                "operation": "list_tools"
            })
            
            assert result["success"] is False
            assert "error" in result
            assert "Method not found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_http_non_200_status(self):
        """Test handling non-200 HTTP status"""
        executor = McpExecutor()
        
        with patch("apflow.extensions.mcp.mcp_executor.HTTPX_AVAILABLE", True), \
             patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            mock_http_response = MagicMock()
            mock_http_response.status_code = 500
            mock_http_response.text = "Internal Server Error"
            mock_client_instance.post = AsyncMock(return_value=mock_http_response)
            
            result = await executor.execute({
                "transport": "http",
                "url": "http://localhost:8000/mcp",
                "operation": "list_tools"
            })
            
            assert result["success"] is False
            assert result["status_code"] == 500
    
    @pytest.mark.asyncio
    async def test_execute_http_timeout(self):
        """Test handling HTTP timeout"""
        executor = McpExecutor()
        
        import httpx
        
        with patch("apflow.extensions.mcp.mcp_executor.HTTPX_AVAILABLE", True), \
             patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            
            result = await executor.execute({
                "transport": "http",
                "url": "http://localhost:8000/mcp",
                "operation": "list_tools",
                "timeout": 1.0
            })
            
            assert result["success"] is False
            assert "timeout" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_http_not_available(self):
        """Test behavior when httpx is not installed"""
        with patch("apflow.extensions.mcp.mcp_executor.HTTPX_AVAILABLE", False):
            executor = McpExecutor()
            result = await executor.execute({
                "transport": "http",
                "url": "http://localhost:8000/mcp",
                "operation": "list_tools"
            })
            
            assert result["success"] is False
            assert "httpx is not installed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_cancellation_before_execution(self):
        """Test cancellation before execution"""
        executor = McpExecutor()
        executor.cancellation_checker = lambda: True
        
        result = await executor.execute({
            "transport": "stdio",
            "command": ["python", "-m", "mcp_server"],
            "operation": "list_tools"
        })
        
        assert result["success"] is False
        assert "cancelled" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_stdio_with_env_vars(self):
        """Test stdio execution with environment variables"""
        executor = McpExecutor()
        
        mock_response = {
            "jsonrpc": "2.0",
            "id": "mcp_123",
            "result": {"tools": []}
        }
        
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(
                json.dumps(mock_response).encode('utf-8'),
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await executor.execute({
                "transport": "stdio",
                "command": ["python", "-m", "mcp_server"],
                "operation": "list_tools",
                "env": {"API_KEY": "test-key"}
            })
            
            assert result["success"] is True
            # Verify env was passed to subprocess
            call_kwargs = mock_subprocess.call_args[1]
            assert "env" in call_kwargs
            assert call_kwargs["env"]["API_KEY"] == "test-key"
    
    @pytest.mark.asyncio
    async def test_get_input_schema(self):
        """Test input schema generation"""
        executor = McpExecutor()
        schema = executor.get_input_schema()
        
        assert schema["type"] == "object"
        assert "transport" in schema["properties"]
        assert "operation" in schema["properties"]
        assert "transport" in schema["required"]
        assert "operation" in schema["required"]


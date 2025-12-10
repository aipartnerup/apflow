"""
Test automatic user_id extraction functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock
from starlette.requests import Request
from aipartnerupflow.api.routes.base import BaseRouteHandler
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel


class TestUserIDExtraction:
    """Test automatic user_id extraction from requests"""
    
    def test_extract_user_id_from_jwt_token(self):
        """Test extracting user_id from JWT token"""
        # Create mock request with JWT token
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer test_token"}
        
        # Mock verify_token_func to return payload with user_id
        def verify_token_func(token):
            if token == "test_token":
                return {"user_id": "jwt_user_123", "sub": "jwt_user_123"}
            return None
        
        handler = BaseRouteHandler(
            task_model_class=TaskModel,
            verify_token_func=verify_token_func
        )
        
        user_id = handler._extract_user_id_from_request(request)
        assert user_id == "jwt_user_123"
    
    def test_extract_user_id_from_jwt_sub(self):
        """Test extracting user_id from JWT token sub field"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer test_token"}
        
        def verify_token_func(token):
            if token == "test_token":
                return {"sub": "jwt_sub_user_456"}  # No user_id, use sub
            return None
        
        handler = BaseRouteHandler(
            task_model_class=TaskModel,
            verify_token_func=verify_token_func
        )
        
        user_id = handler._extract_user_id_from_request(request)
        assert user_id == "jwt_sub_user_456"
    
    def test_extract_user_id_no_token(self):
        """Test that None is returned when no JWT token is present"""
        request = Mock(spec=Request)
        request.headers = {}
        
        handler = BaseRouteHandler(
            task_model_class=TaskModel,
            verify_token_func=None
        )
        
        user_id = handler._extract_user_id_from_request(request)
        assert user_id is None
    
    def test_extract_user_id_invalid_token(self):
        """Test that invalid token returns None (no fallback to header for security)"""
        request = Mock(spec=Request)
        request.headers = {
            "Authorization": "Bearer invalid_token"
        }
        
        def verify_token_func(token):
            return None  # Invalid token
        
        handler = BaseRouteHandler(
            task_model_class=TaskModel,
            verify_token_func=verify_token_func
        )
        
        user_id = handler._extract_user_id_from_request(request)
        assert user_id is None
    
    def test_extract_user_id_no_verify_token_func(self):
        """Test that None is returned when verify_token_func is not provided"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer test_token"}
        
        handler = BaseRouteHandler(
            task_model_class=TaskModel,
            verify_token_func=None  # No JWT verification function
        )
        
        user_id = handler._extract_user_id_from_request(request)
        assert user_id is None
    
    def test_extract_user_id_bearer_prefix(self):
        """Test that Bearer prefix is correctly stripped"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer actual_token"}
        
        def verify_token_func(token):
            assert token == "actual_token"  # Should not include "Bearer "
            return {"user_id": "test_user"}
        
        handler = BaseRouteHandler(
            task_model_class=TaskModel,
            verify_token_func=verify_token_func
        )
        
        user_id = handler._extract_user_id_from_request(request)
        assert user_id == "test_user"


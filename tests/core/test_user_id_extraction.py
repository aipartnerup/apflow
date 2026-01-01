"""
Test automatic user_id extraction functionality
"""

from unittest.mock import Mock
from starlette.requests import Request
from apflow.api.routes.base import BaseRouteHandler
from apflow.api.a2a.server import generate_token, verify_token
from apflow.core.storage.sqlalchemy.models import TaskModel


class TestUserIDExtraction:
    """Test automatic user_id extraction from requests"""

    def test_extract_user_id_from_jwt_token(self):
        """Test extracting user_id from JWT token"""
        # Generate real JWT token using generate_token
        secret_key = "test_secret_key_for_jwt_token_generation"
        payload = {"user_id": "jwt_user_123", "sub": "jwt_user_123"}
        token = generate_token(payload, secret_key)

        # Create mock request with JWT token
        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}

        # Use real verify_token function
        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        handler = BaseRouteHandler(task_model_class=TaskModel, verify_token_func=verify_token_func)

        user_id = handler._extract_user_id_from_request(request)
        assert user_id == "jwt_user_123"

    def test_extract_user_id_from_jwt_sub(self):
        """Test extracting user_id from JWT token sub field"""
        # Generate real JWT token using generate_token
        secret_key = "test_secret_key_for_jwt_token_generation"
        payload = {"sub": "jwt_sub_user_456"}  # No user_id, use sub
        token = generate_token(payload, secret_key)

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}

        # Use real verify_token function
        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        handler = BaseRouteHandler(task_model_class=TaskModel, verify_token_func=verify_token_func)

        user_id = handler._extract_user_id_from_request(request)
        assert user_id == "jwt_sub_user_456"

    def test_extract_user_id_no_token(self):
        """Test that None is returned when no JWT token is present"""
        request = Mock(spec=Request)
        request.headers = {}

        handler = BaseRouteHandler(task_model_class=TaskModel, verify_token_func=None)

        user_id = handler._extract_user_id_from_request(request)
        assert user_id is None

    def test_extract_user_id_invalid_token(self):
        """Test that invalid token returns None (no fallback to header for security)"""
        # Use invalid token (wrong secret key)
        secret_key = "test_secret_key_for_jwt_token_generation"
        wrong_secret_key = "wrong_secret_key"
        payload = {"user_id": "test_user"}
        token = generate_token(payload, secret_key)

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}

        # Use verify_token with wrong secret key (should return None)
        def verify_token_func(token_str: str):
            return verify_token(token_str, wrong_secret_key)

        handler = BaseRouteHandler(task_model_class=TaskModel, verify_token_func=verify_token_func)

        user_id = handler._extract_user_id_from_request(request)
        assert user_id is None

    def test_extract_user_id_no_verify_token_func(self):
        """Test that None is returned when verify_token_func is not provided"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer test_token"}

        handler = BaseRouteHandler(
            task_model_class=TaskModel, verify_token_func=None  # No JWT verification function
        )

        user_id = handler._extract_user_id_from_request(request)
        assert user_id is None

    def test_extract_user_id_bearer_prefix(self):
        """Test that Bearer prefix is correctly stripped"""
        # Generate real JWT token using generate_token
        secret_key = "test_secret_key_for_jwt_token_generation"
        payload = {"user_id": "test_user"}
        token = generate_token(payload, secret_key)

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}

        # Use real verify_token function
        def verify_token_func(token_str: str):
            # Verify that Bearer prefix is stripped
            assert token_str == token  # Should not include "Bearer "
            return verify_token(token_str, secret_key)

        handler = BaseRouteHandler(task_model_class=TaskModel, verify_token_func=verify_token_func)

        user_id = handler._extract_user_id_from_request(request)
        assert user_id == "test_user"

    def test_extract_user_id_from_cookie(self):
        """Test extracting user_id from JWT token in cookie"""
        # Generate real JWT token using generate_token
        secret_key = "test_secret_key_for_jwt_token_generation"
        payload = {"user_id": "cookie_user_789", "sub": "cookie_user_789"}
        token = generate_token(payload, secret_key)

        # Create mock request with JWT token in cookie (no header)
        request = Mock(spec=Request)
        request.headers = {}  # No Authorization header
        request.cookies = {"Authorization": token}

        # Use real verify_token function
        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        handler = BaseRouteHandler(task_model_class=TaskModel, verify_token_func=verify_token_func)

        user_id = handler._extract_user_id_from_request(request)
        assert user_id == "cookie_user_789"

    def test_extract_user_id_from_cookie_with_sub(self):
        """Test extracting user_id from JWT token sub field in cookie"""
        # Generate real JWT token using generate_token
        secret_key = "test_secret_key_for_jwt_token_generation"
        payload = {"sub": "cookie_sub_user_999"}  # No user_id, use sub
        token = generate_token(payload, secret_key)

        # Create mock request with JWT token in cookie (no header)
        request = Mock(spec=Request)
        request.headers = {}  # No Authorization header
        request.cookies = {"Authorization": token}

        # Use real verify_token function
        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        handler = BaseRouteHandler(task_model_class=TaskModel, verify_token_func=verify_token_func)

        user_id = handler._extract_user_id_from_request(request)
        assert user_id == "cookie_sub_user_999"

    def test_extract_user_id_header_priority_over_cookie(self):
        """Test that Authorization header has priority over cookie"""
        # Generate two different tokens
        secret_key = "test_secret_key_for_jwt_token_generation"
        header_payload = {"user_id": "header_user", "sub": "header_user"}
        cookie_payload = {"user_id": "cookie_user", "sub": "cookie_user"}
        header_token = generate_token(header_payload, secret_key)
        cookie_token = generate_token(cookie_payload, secret_key)

        # Create mock request with both header and cookie
        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {header_token}"}
        request.cookies = {"Authorization": cookie_token}

        # Use real verify_token function
        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        handler = BaseRouteHandler(task_model_class=TaskModel, verify_token_func=verify_token_func)

        # Should use header token (priority)
        user_id = handler._extract_user_id_from_request(request)
        assert user_id == "header_user"

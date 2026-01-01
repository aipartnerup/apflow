"""
Base route handler with shared functionality for protocol-agnostic routes

This module provides the base class and shared utilities that can be used
by any protocol implementation (A2A, REST, etc.).
"""

from typing import Optional, Callable, Type, Tuple, Union
from starlette.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from apflow.core.storage.sqlalchemy.models import TaskModel
from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
from apflow.core.storage import get_default_session
from apflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class BaseRouteHandler:
    """
    Base class for protocol-agnostic route handlers

    Provides shared functionality for permission checking, user information
    extraction, and common utilities that can be used across different
    protocol implementations.
    """

    def __init__(
        self,
        task_model_class: Type[TaskModel],
        verify_token_func: Optional[Callable[[str], Optional[dict]]] = None,
        verify_permission_func: Optional[
            Callable[[str, Optional[str], Optional[list]], bool]
        ] = None,
    ):
        """
        Initialize base route handler

        Args:
            task_model_class: TaskModel class to use for database operations
            verify_token_func: Optional function to verify JWT tokens
            verify_permission_func: Optional function to verify user permissions
        """
        self.task_model_class = task_model_class
        self.verify_token_func = verify_token_func
        self.verify_permission_func = verify_permission_func

    def _get_user_info(self, request: Request) -> Tuple[Optional[str], Optional[list]]:
        """
        Extract user information from request state (set by JWT middleware)

        Args:
            request: Starlette request object

        Returns:
            Tuple of (user_id, roles):
            - user_id: User ID from JWT token payload (sub field)
            - roles: User roles from JWT token payload (roles field, optional)
        """
        user_id = getattr(request.state, "user_id", None)
        token_payload = getattr(request.state, "token_payload", None)
        roles = None
        if token_payload:
            roles = token_payload.get("roles") or token_payload.get("role")
            if roles and not isinstance(roles, list):
                roles = [roles]
        return user_id, roles

    def _extract_user_id_from_request(self, request: Request) -> Optional[str]:
        """
        Extract user_id from request JWT token

        This method extracts user_id from JWT token payload.
        Supports both Authorization header and cookie-based authentication.
        Only JWT tokens are trusted for security reasons - HTTP headers
        can be easily spoofed by clients and should not be used for
        authentication or user identification.

        Args:
            request: Starlette request object

        Returns:
            User ID string from JWT token payload, or None if not found
        """
        # Only extract from JWT token (if verify_token_func is available)
        if self.verify_token_func:
            token = None

            # Try Authorization header first (priority)
            auth_header = request.headers.get("Authorization")
            if auth_header:
                if auth_header.startswith("Bearer "):
                    token = auth_header.split(" ", 1)[1]
                else:
                    token = auth_header

            # Fallback: try cookie (for cookie-based auth)
            # Support multiple cookie names for flexibility (matching JWTAuthenticationMiddleware)
            if not token:
                token = (
                    request.cookies.get("authorization")  # Lowercase (common in web apps)
                    or request.cookies.get("Authorization")  # Uppercase (less common)
                    or request.cookies.get("auth_token")  # Alternative name
                )

            if token:
                try:
                    payload = self.verify_token_func(token)
                    if payload and "user_id" in payload:
                        return payload["user_id"]
                    # Also try "sub" field (standard JWT claim)
                    if payload and "sub" in payload:
                        return payload["sub"]
                except Exception:
                    # Token verification failed
                    pass

        return None

    def _is_admin(self, request: Request) -> bool:
        """
        Check if current user is admin

        Args:
            request: Starlette request object

        Returns:
            True if user is admin, False otherwise
        """
        if not self.verify_token_func:
            return False
        _, roles = self._get_user_info(request)
        return roles and "admin" in roles

    def _check_permission(
        self, request: Request, target_user_id: Optional[str], operation: str = "access"
    ) -> Optional[str]:
        """
        Check if user has permission to access target_user_id's resources

        Permission rules:
        1. If JWT is not enabled (no verify_token_func) and target_user_id is None:
           - Return None (no user restriction, allow all)
        2. If JWT is not enabled but target_user_id is provided:
           - Return None (no user restriction, allow all)
        3. If JWT is enabled:
           - Get authenticated user_id from request.state (set by JWT middleware)
           - If no authenticated user_id, raise error (JWT required)
           - If target_user_id is None, return authenticated_user_id (user can access their own)
           - If verify_permission_func is provided, use it to check permission
           - If verify_permission_func is not provided, use default logic:
             * Admin users (roles contains "admin") can access any user_id
             * Non-admin users can only access their own user_id

        Args:
            request: Request object with user info in state
            target_user_id: Target user ID to check permission for (None means no specific user restriction)
            operation: Operation name for logging (default: "access")

        Returns:
            Resolved user_id to use:
            - If JWT disabled: None (no user restriction)
            - If JWT enabled: authenticated_user_id (validated)

        Raises:
            ValueError: If permission is denied
        """
        # If JWT is not enabled, no permission checking needed
        if not self.verify_token_func:
            # No JWT, no user restriction - return None
            return None

        # Get user info from request state (set by JWT middleware)
        authenticated_user_id, roles = self._get_user_info(request)

        # If JWT is enabled but no authenticated user (JWT not provided or invalid)
        if not authenticated_user_id:
            # JWT is enabled but no valid token - this should not happen if middleware is working
            # But if it does, we allow it (middleware should have rejected it)
            logger.warning("JWT enabled but no authenticated user_id in request.state")
            return None

        # If target_user_id is None, permission is granted (no specific user restriction)
        # User can access their own resources (authenticated_user_id)
        if target_user_id is None:
            return authenticated_user_id

        # Check permission using verify_permission_func if provided
        if self.verify_permission_func:
            has_permission = self.verify_permission_func(
                authenticated_user_id, target_user_id, roles
            )
            if not has_permission:
                raise ValueError(
                    f"Permission denied: User {authenticated_user_id} does not have permission "
                    f"to {operation} resources for user {target_user_id}"
                )
            return authenticated_user_id

        # Default permission logic: admin can access any user_id, others can only access their own
        is_admin = roles and "admin" in roles
        if is_admin:
            # Admin can access any user_id
            logger.debug(
                f"Admin user {authenticated_user_id} accessing user {target_user_id}'s resources"
            )
            return authenticated_user_id
        elif authenticated_user_id == target_user_id:
            # User can access their own resources
            return authenticated_user_id
        else:
            # User cannot access other users' resources
            raise ValueError(
                f"Permission denied: User {authenticated_user_id} can only {operation} their own resources, "
                f"not user {target_user_id}'s resources"
            )

    def _get_task_repository(
        self, db_session: Optional[Union[Session, AsyncSession]] = None
    ) -> TaskRepository:
        """
        Create a TaskRepository instance with the configured task_model_class

        This helper method extracts the repeated pattern of creating TaskRepository
        instances with the correct task_model_class configuration.

        Args:
            db_session: Optional database session. If not provided, uses get_default_session()

        Returns:
            TaskRepository instance configured with self.task_model_class
        """
        if db_session is None:
            db_session = get_default_session()
        return TaskRepository(db_session, task_model_class=self.task_model_class)

"""
Test TaskRoutes scheduler-related endpoints

Tests cover:
- tasks.scheduled.list - List all scheduled tasks
- tasks.scheduled.due - Get due scheduled tasks
- tasks.scheduled.init - Initialize scheduled task
- tasks.scheduled.complete - Complete scheduled task run
- tasks.scheduled.export-ical - Export scheduled tasks as iCal
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from starlette.requests import Request

from apflow.api.routes.tasks import TaskRoutes
from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
from apflow.core.config import get_task_model_class


@pytest.fixture
def task_routes(use_test_db_session):
    """Create TaskRoutes instance for testing"""
    return TaskRoutes(
        task_model_class=get_task_model_class(),
        verify_token_func=None,
        verify_permission_func=None,
    )


@pytest.fixture
def mock_request():
    """Create a mock Request object"""
    request = Mock(spec=Request)
    request.state = Mock()
    request.state.user_id = None
    request.state.token_payload = None
    request.client = Mock()
    request.client.host = "127.0.0.1"
    return request


@pytest_asyncio.fixture
async def scheduled_task(use_test_db_session):
    """Create a scheduled task in database for testing"""
    task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())

    task_id = f"scheduled-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=task_id,
        name="Scheduled Test Task",
        user_id="test_user",
        status="pending",
        priority=1,
        has_children=False,
        progress=0.0,
        schemas={"method": "system_info_executor"},
        inputs={},
        schedule_type="cron",
        schedule_config={"cron": "0 * * * *"},
        schedule_enabled=True,
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    return task_id


@pytest_asyncio.fixture
async def multiple_scheduled_tasks(use_test_db_session):
    """Create multiple scheduled tasks for testing"""
    task_repository = TaskRepository(use_test_db_session, task_model_class=get_task_model_class())

    task_ids = []
    now = datetime.now(timezone.utc)

    # Due task
    task_id1 = f"sched-due-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=task_id1,
        name="Due Task",
        user_id="test_user",
        status="pending",
        priority=1,
        has_children=False,
        progress=0.0,
        schemas={"method": "system_info_executor"},
        inputs={},
        schedule_type="interval",
        schedule_config={"interval": 3600},
        schedule_enabled=True,
        next_run_at=now - timedelta(minutes=10),
    )
    task_ids.append(task_id1)

    # Future task
    task_id2 = f"sched-future-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=task_id2,
        name="Future Task",
        user_id="test_user",
        status="pending",
        priority=1,
        has_children=False,
        progress=0.0,
        schemas={"method": "system_info_executor"},
        inputs={},
        schedule_type="cron",
        schedule_config={"cron": "0 0 * * *"},
        schedule_enabled=True,
        next_run_at=now + timedelta(hours=1),
    )
    task_ids.append(task_id2)

    # Disabled task
    task_id3 = f"sched-disabled-{uuid.uuid4().hex[:8]}"
    await task_repository.create_task(
        id=task_id3,
        name="Disabled Task",
        user_id="test_user",
        status="pending",
        priority=1,
        has_children=False,
        progress=0.0,
        schemas={"method": "system_info_executor"},
        inputs={},
        schedule_type="interval",
        schedule_config={"interval": 1800},
        schedule_enabled=False,
        next_run_at=now - timedelta(minutes=5),
    )
    task_ids.append(task_id3)

    return task_ids


class TestScheduledTasksList:
    """Tests for tasks.scheduled.list endpoint"""

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks_empty(self, task_routes, mock_request):
        """Test listing scheduled tasks when none exist"""
        params = {}
        request_id = str(uuid.uuid4())

        with patch.object(task_routes, "_get_task_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.get_scheduled_tasks = AsyncMock(return_value=[])
            mock_get_repo.return_value = mock_repo

            with patch("apflow.api.routes.tasks.create_pooled_session") as mock_session:
                mock_session.return_value.__aenter__ = AsyncMock()
                mock_session.return_value.__aexit__ = AsyncMock()

                result = await task_routes.handle_scheduled_tasks_list(
                    params, mock_request, request_id
                )

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks_with_results(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test listing scheduled tasks returns tasks"""
        params = {"enabled_only": False}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_list(params, mock_request, request_id)

        assert isinstance(result, list)
        assert len(result) >= 3

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks_enabled_only(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test listing only enabled scheduled tasks"""
        params = {"enabled_only": True}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_list(params, mock_request, request_id)

        assert isinstance(result, list)
        # Only enabled tasks should be returned
        for task in result:
            assert task.get("schedule_enabled") is True

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks_filter_by_user(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test listing scheduled tasks filtered by user"""
        params = {"user_id": "test_user", "enabled_only": False}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_list(params, mock_request, request_id)

        assert isinstance(result, list)
        for task in result:
            assert task.get("user_id") == "test_user"

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks_filter_by_type(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test listing scheduled tasks filtered by schedule type"""
        params = {"schedule_type": "cron", "enabled_only": False}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_list(params, mock_request, request_id)

        assert isinstance(result, list)
        for task in result:
            assert task.get("schedule_type") == "cron"

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks_pagination(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test listing scheduled tasks with pagination"""
        params = {"limit": 2, "offset": 0, "enabled_only": False}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_list(params, mock_request, request_id)

        assert isinstance(result, list)
        assert len(result) <= 2


class TestScheduledTasksDue:
    """Tests for tasks.scheduled.due endpoint"""

    @pytest.mark.asyncio
    async def test_get_due_tasks_empty(self, task_routes, mock_request):
        """Test getting due tasks when none are due"""
        params = {}
        request_id = str(uuid.uuid4())

        with patch.object(task_routes, "_get_task_repository") as mock_get_repo:
            mock_repo = AsyncMock()
            mock_repo.get_due_scheduled_tasks = AsyncMock(return_value=[])
            mock_get_repo.return_value = mock_repo

            with patch("apflow.api.routes.tasks.create_pooled_session") as mock_session:
                mock_session.return_value.__aenter__ = AsyncMock()
                mock_session.return_value.__aexit__ = AsyncMock()

                result = await task_routes.handle_scheduled_tasks_due(
                    params, mock_request, request_id
                )

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_due_tasks_returns_due_only(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test getting due tasks returns only due tasks"""
        params = {}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_due(params, mock_request, request_id)

        assert isinstance(result, list)
        # Should only include tasks with next_run_at <= now
        now = datetime.now(timezone.utc)
        for task in result:
            if task.get("next_run_at"):
                next_run = datetime.fromisoformat(task["next_run_at"].replace("Z", "+00:00"))
                assert next_run <= now

    @pytest.mark.asyncio
    async def test_get_due_tasks_with_before_param(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test getting due tasks with custom before time"""
        future_time = datetime.now(timezone.utc) + timedelta(hours=2)
        params = {"before": future_time.isoformat()}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_due(params, mock_request, request_id)

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_due_tasks_filter_by_user(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test getting due tasks filtered by user"""
        params = {"user_id": "test_user"}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_due(params, mock_request, request_id)

        assert isinstance(result, list)
        for task in result:
            assert task.get("user_id") == "test_user"

    @pytest.mark.asyncio
    async def test_get_due_tasks_limit(self, task_routes, mock_request, multiple_scheduled_tasks):
        """Test getting due tasks with limit"""
        params = {"limit": 1}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_due(params, mock_request, request_id)

        assert isinstance(result, list)
        assert len(result) <= 1


class TestScheduledTaskInit:
    """Tests for tasks.scheduled.init endpoint"""

    @pytest.mark.asyncio
    async def test_init_scheduled_task_missing_task_id(self, task_routes, mock_request):
        """Test initializing task without task_id raises error"""
        params = {}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="task_id is required"):
            await task_routes.handle_scheduled_task_init(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_init_scheduled_task_not_found(self, task_routes, mock_request):
        """Test initializing non-existent task raises error"""
        params = {"task_id": "nonexistent-task"}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="not found"):
            await task_routes.handle_scheduled_task_init(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_init_scheduled_task_success(self, task_routes, mock_request, scheduled_task):
        """Test initializing scheduled task successfully"""
        params = {"task_id": scheduled_task}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_task_init(params, mock_request, request_id)

        assert isinstance(result, dict)
        assert result.get("id") == scheduled_task

    @pytest.mark.asyncio
    async def test_init_scheduled_task_with_from_time(
        self, task_routes, mock_request, scheduled_task
    ):
        """Test initializing scheduled task with custom from_time"""
        from_time = datetime.now(timezone.utc) + timedelta(hours=1)
        params = {"task_id": scheduled_task, "from_time": from_time.isoformat()}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_task_init(params, mock_request, request_id)

        assert isinstance(result, dict)
        assert result.get("id") == scheduled_task


class TestScheduledTaskComplete:
    """Tests for tasks.scheduled.complete endpoint"""

    @pytest.mark.asyncio
    async def test_complete_task_missing_task_id(self, task_routes, mock_request):
        """Test completing task without task_id raises error"""
        params = {}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="task_id is required"):
            await task_routes.handle_scheduled_task_complete(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_complete_task_not_found(self, task_routes, mock_request):
        """Test completing non-existent task raises error"""
        params = {"task_id": "nonexistent-task"}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="not found"):
            await task_routes.handle_scheduled_task_complete(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_complete_task_success(self, task_routes, mock_request, scheduled_task):
        """Test completing scheduled task successfully"""
        params = {"task_id": scheduled_task, "success": True}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_task_complete(params, mock_request, request_id)

        assert isinstance(result, dict)
        assert result.get("id") == scheduled_task

    @pytest.mark.asyncio
    async def test_complete_task_with_failure(self, task_routes, mock_request, scheduled_task):
        """Test completing scheduled task with failure"""
        params = {
            "task_id": scheduled_task,
            "success": False,
            "error": "Execution failed",
        }
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_task_complete(params, mock_request, request_id)

        assert isinstance(result, dict)
        assert result.get("id") == scheduled_task

    @pytest.mark.asyncio
    async def test_complete_task_with_result(self, task_routes, mock_request, scheduled_task):
        """Test completing scheduled task with result data"""
        params = {
            "task_id": scheduled_task,
            "success": True,
            "result": {"output": "Task completed successfully"},
        }
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_task_complete(params, mock_request, request_id)

        assert isinstance(result, dict)
        assert result.get("id") == scheduled_task

    @pytest.mark.asyncio
    async def test_complete_task_skip_next_run_calculation(
        self, task_routes, mock_request, scheduled_task
    ):
        """Test completing task without calculating next run"""
        params = {
            "task_id": scheduled_task,
            "success": True,
            "calculate_next_run": False,
        }
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_task_complete(params, mock_request, request_id)

        assert isinstance(result, dict)
        assert result.get("id") == scheduled_task


class TestWebhookTriggerJsonRpc:
    """Tests for tasks.webhook.trigger JSON-RPC endpoint"""

    @pytest.mark.asyncio
    async def test_webhook_trigger_missing_task_id(self, task_routes, mock_request):
        """Test webhook trigger without task_id raises error"""
        params = {}
        request_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="task_id is required"):
            await task_routes.handle_webhook_trigger(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_webhook_trigger_task_not_found(self, task_routes, mock_request):
        """Test webhook trigger for non-existent task"""
        params = {"task_id": "nonexistent-task"}
        request_id = str(uuid.uuid4())

        with patch("apflow.scheduler.gateway.webhook.WebhookGateway") as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.trigger_task = AsyncMock(
                return_value={"success": False, "error": "Task not found"}
            )
            mock_gateway_class.return_value = mock_gateway

            result = await task_routes.handle_webhook_trigger(params, mock_request, request_id)

            assert result.get("success") is False

    @pytest.mark.asyncio
    async def test_webhook_trigger_async_mode(self, task_routes, mock_request, scheduled_task):
        """Test webhook trigger in async mode"""
        params = {"task_id": scheduled_task, "async_execution": True}
        request_id = str(uuid.uuid4())

        with patch("apflow.scheduler.gateway.webhook.WebhookGateway") as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.trigger_task = AsyncMock(
                return_value={"success": True, "status": "triggered"}
            )
            mock_gateway_class.return_value = mock_gateway

            result = await task_routes.handle_webhook_trigger(params, mock_request, request_id)

            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_webhook_trigger_sync_mode(self, task_routes, mock_request, scheduled_task):
        """Test webhook trigger in sync mode"""
        params = {"task_id": scheduled_task, "async_execution": False}
        request_id = str(uuid.uuid4())

        with patch("apflow.scheduler.gateway.webhook.WebhookGateway") as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.trigger_task = AsyncMock(
                return_value={"success": True, "status": "completed"}
            )
            mock_gateway_class.return_value = mock_gateway

            result = await task_routes.handle_webhook_trigger(params, mock_request, request_id)

            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_webhook_trigger_with_signature(self, task_routes, mock_request, scheduled_task):
        """Test webhook trigger with signature validation"""
        params = {
            "task_id": scheduled_task,
            "signature": "abc123signature",
            "timestamp": "1234567890",
        }
        request_id = str(uuid.uuid4())

        with patch("apflow.scheduler.gateway.webhook.WebhookGateway") as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.trigger_task = AsyncMock(
                return_value={"success": True, "status": "triggered"}
            )
            mock_gateway_class.return_value = mock_gateway

            result = await task_routes.handle_webhook_trigger(params, mock_request, request_id)

            assert isinstance(result, dict)


class TestWebhookTriggerAdminPermission:
    """Tests for admin permission bypass in webhook trigger

    Verifies that admin users (JWT with 'admin' role) can trigger tasks
    owned by other users, while non-admin users still have their user_id
    passed for permission checking.
    """

    @pytest.mark.asyncio
    async def test_admin_user_triggers_other_users_task(self, use_test_db_session):
        """Test that admin user bypasses user_id check (user_id=None to trigger_task)"""
        from apflow.cli.jwt_token import generate_token, verify_token

        secret_key = "test_secret_webhook_admin"
        token = generate_token(
            subject="admin_user",
            secret=secret_key,
            extra_claims={"user_id": "admin_user", "roles": ["admin"]},
        )

        def verify_token_func(token_str: str) -> dict:
            return verify_token(token_str, secret_key)

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=verify_token_func,
        )

        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        request.state.user_id = "admin_user"
        request.state.token_payload = verify_token_func(token)

        with patch("apflow.scheduler.gateway.webhook.WebhookGateway") as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.trigger_task = AsyncMock(
                return_value={"success": True, "status": "triggered", "task_id": "other-user-task"}
            )
            mock_gateway_class.return_value = mock_gateway

            result = await task_routes.handle_webhook_trigger(
                {"task_id": "other-user-task"},
                request,
                str(uuid.uuid4()),
            )

            assert result["success"] is True
            # Admin should bypass: user_id=None passed to trigger_task
            mock_gateway.trigger_task.assert_called_once_with(
                task_id="other-user-task",
                user_id=None,
                execute_async=True,
            )

    @pytest.mark.asyncio
    async def test_non_admin_user_passes_own_user_id(self, use_test_db_session):
        """Test that non-admin user passes their user_id (for permission check in trigger_task)"""
        from apflow.cli.jwt_token import generate_token, verify_token

        secret_key = "test_secret_webhook_nonadmin"
        token = generate_token(
            subject="regular_user",
            secret=secret_key,
            extra_claims={"user_id": "regular_user", "roles": ["user"]},
        )

        def verify_token_func(token_str: str) -> dict:
            return verify_token(token_str, secret_key)

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=verify_token_func,
        )

        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        request.state.user_id = "regular_user"
        request.state.token_payload = verify_token_func(token)

        with patch("apflow.scheduler.gateway.webhook.WebhookGateway") as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.trigger_task = AsyncMock(
                return_value={"success": True, "status": "triggered", "task_id": "some-task"}
            )
            mock_gateway_class.return_value = mock_gateway

            await task_routes.handle_webhook_trigger(
                {"task_id": "some-task"},
                request,
                str(uuid.uuid4()),
            )

            # Non-admin: user_id should be passed for permission checking
            mock_gateway.trigger_task.assert_called_once_with(
                task_id="some-task",
                user_id="regular_user",
                execute_async=True,
            )

    @pytest.mark.asyncio
    async def test_no_jwt_user_passes_none_user_id(self, task_routes, mock_request):
        """Test that unauthenticated request passes user_id=None"""
        with patch("apflow.scheduler.gateway.webhook.WebhookGateway") as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.trigger_task = AsyncMock(
                return_value={"success": True, "status": "triggered", "task_id": "any-task"}
            )
            mock_gateway_class.return_value = mock_gateway

            await task_routes.handle_webhook_trigger(
                {"task_id": "any-task"},
                mock_request,
                str(uuid.uuid4()),
            )

            # No JWT: user_id=None (no permission restriction)
            mock_gateway.trigger_task.assert_called_once_with(
                task_id="any-task",
                user_id=None,
                execute_async=True,
            )


class TestSchedulerRoutesPermissions:
    """Tests for permission checking in scheduler routes"""

    @pytest.mark.asyncio
    async def test_list_with_user_id_checks_permission(self, task_routes, mock_request):
        """Test that listing with user_id checks permission"""
        params = {"user_id": "other_user"}
        request_id = str(uuid.uuid4())

        # Set up mock to simulate permission check
        with patch.object(task_routes, "_check_permission") as mock_check:
            with patch.object(task_routes, "_get_task_repository") as mock_get_repo:
                mock_repo = AsyncMock()
                mock_repo.get_scheduled_tasks = AsyncMock(return_value=[])
                mock_get_repo.return_value = mock_repo

                with patch("apflow.api.routes.tasks.create_pooled_session") as mock_session:
                    mock_session.return_value.__aenter__ = AsyncMock()
                    mock_session.return_value.__aexit__ = AsyncMock()

                    await task_routes.handle_scheduled_tasks_list(params, mock_request, request_id)

                    mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_due_with_user_id_checks_permission(self, task_routes, mock_request):
        """Test that getting due tasks with user_id checks permission"""
        params = {"user_id": "other_user"}
        request_id = str(uuid.uuid4())

        with patch.object(task_routes, "_check_permission") as mock_check:
            with patch.object(task_routes, "_get_task_repository") as mock_get_repo:
                mock_repo = AsyncMock()
                mock_repo.get_due_scheduled_tasks = AsyncMock(return_value=[])
                mock_get_repo.return_value = mock_repo

                with patch("apflow.api.routes.tasks.create_pooled_session") as mock_session:
                    mock_session.return_value.__aenter__ = AsyncMock()
                    mock_session.return_value.__aexit__ = AsyncMock()

                    await task_routes.handle_scheduled_tasks_due(params, mock_request, request_id)

                    mock_check.assert_called_once()


class TestSchedulerRoutesErrorHandling:
    """Tests for error handling in scheduler routes"""

    @pytest.mark.asyncio
    async def test_list_handles_database_error(self, mock_request):
        """Test that list handles database errors gracefully"""
        from apflow.api.routes.tasks import TaskRoutes
        from apflow.core.config import get_task_model_class

        # Create a fresh TaskRoutes instance for this test
        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=None,
            verify_permission_func=None,
        )

        params = {}
        request_id = str(uuid.uuid4())

        # Mock create_pooled_session to raise an error
        with patch("apflow.api.routes.tasks.create_pooled_session") as mock_session:
            mock_context = AsyncMock()
            mock_context.__aenter__.side_effect = Exception("Database connection error")
            mock_session.return_value = mock_context

            with pytest.raises(Exception, match="Database connection error"):
                await task_routes.handle_scheduled_tasks_list(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_init_handles_repository_error(self, mock_request):
        """Test that init handles repository errors gracefully"""
        from apflow.api.routes.tasks import TaskRoutes
        from apflow.core.config import get_task_model_class

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=None,
            verify_permission_func=None,
        )

        params = {"task_id": "test-task-123"}
        request_id = str(uuid.uuid4())

        # Mock create_pooled_session and repository
        with patch("apflow.api.routes.tasks.create_pooled_session") as mock_session:
            mock_db = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_db
            mock_context.__aexit__.return_value = None
            mock_session.return_value = mock_context

            # Mock the repository methods
            with patch.object(task_routes, "_get_task_repository") as mock_get_repo:
                mock_repo = AsyncMock()
                mock_task = MagicMock()
                mock_task.user_id = "test_user"
                mock_repo.get_task_by_id = AsyncMock(return_value=mock_task)
                mock_repo.initialize_schedule = AsyncMock(return_value=None)
                mock_get_repo.return_value = mock_repo

                with pytest.raises(ValueError, match="Failed to initialize"):
                    await task_routes.handle_scheduled_task_init(params, mock_request, request_id)

    @pytest.mark.asyncio
    async def test_complete_handles_repository_error(self, mock_request):
        """Test that complete handles repository errors gracefully"""
        from apflow.api.routes.tasks import TaskRoutes
        from apflow.core.config import get_task_model_class

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=None,
            verify_permission_func=None,
        )

        params = {"task_id": "test-task-123"}
        request_id = str(uuid.uuid4())

        with patch("apflow.api.routes.tasks.create_pooled_session") as mock_session:
            mock_db = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_db
            mock_context.__aexit__.return_value = None
            mock_session.return_value = mock_context

            with patch.object(task_routes, "_get_task_repository") as mock_get_repo:
                mock_repo = AsyncMock()
                mock_task = MagicMock()
                mock_task.user_id = "test_user"
                mock_repo.get_task_by_id = AsyncMock(return_value=mock_task)
                mock_repo.complete_scheduled_run = AsyncMock(return_value=None)
                mock_get_repo.return_value = mock_repo

                with pytest.raises(ValueError, match="Failed to complete"):
                    await task_routes.handle_scheduled_task_complete(
                        params, mock_request, request_id
                    )


# ============================================================================
# Integration Tests - Real database flows without mocks
# ============================================================================


class TestSchedulerRoutesIntegration:
    """Integration tests using real database without mocks"""

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks_real_flow(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test listing scheduled tasks with real database"""
        from datetime import datetime, timezone, timedelta
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class

        # Create scheduled tasks in real database
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        task_id = f"list-integ-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=task_id,
            name="Integration List Test",
            user_id="integ_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 3600},
            schedule_enabled=True,
            next_run_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Call real handler
        params = {"enabled_only": True}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_list(params, mock_request, request_id)

        assert isinstance(result, list)
        # Find our task in results
        task_ids = [t.get("id") for t in result]
        assert task_id in task_ids

    @pytest.mark.asyncio
    async def test_get_due_tasks_real_flow(self, task_routes, mock_request, use_test_db_session):
        """Test getting due tasks with real database"""
        from datetime import datetime, timezone, timedelta
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class

        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create a due task (next_run_at in the past)
        due_task_id = f"due-integ-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=due_task_id,
            name="Due Integration Test",
            user_id="integ_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 3600},
            schedule_enabled=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )

        # Create a future task (should not be returned)
        future_task_id = f"future-integ-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=future_task_id,
            name="Future Integration Test",
            user_id="integ_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 3600},
            schedule_enabled=True,
            next_run_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )

        params = {}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_due(params, mock_request, request_id)

        assert isinstance(result, list)
        task_ids = [t.get("id") for t in result]

        # Due task should be in results
        assert due_task_id in task_ids
        # Future task should NOT be in results
        assert future_task_id not in task_ids

    @pytest.mark.asyncio
    async def test_init_and_complete_scheduled_task_real_flow(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test full lifecycle: init -> complete with real database"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class

        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create scheduled task with schedule_expression (required for next_run_at calculation)
        task_id = f"lifecycle-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=task_id,
            name="Lifecycle Test Task",
            user_id="integ_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_expression="3600",  # Required for calculating next_run_at
            schedule_config={"interval": 3600},
            schedule_enabled=True,
        )

        # Step 1: Initialize schedule
        init_params = {"task_id": task_id}
        request_id = str(uuid.uuid4())

        init_result = await task_routes.handle_scheduled_task_init(
            init_params, mock_request, request_id
        )

        assert isinstance(init_result, dict)
        assert init_result.get("id") == task_id
        assert init_result.get("next_run_at") is not None

        # Step 2: Complete the scheduled run
        complete_params = {
            "task_id": task_id,
            "success": True,
            "result": {"output": "Integration test completed"},
        }

        complete_result = await task_routes.handle_scheduled_task_complete(
            complete_params, mock_request, str(uuid.uuid4())
        )

        assert isinstance(complete_result, dict)
        assert complete_result.get("id") == task_id
        # Run count should be incremented
        assert complete_result.get("run_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_scheduled_task_filters_real_flow(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test filtering by user_id and schedule_type with real database"""
        from datetime import datetime, timezone, timedelta
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class

        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create tasks for different users and types
        user1_cron = f"u1-cron-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=user1_cron,
            name="User1 Cron Task",
            user_id="user_one",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="cron",
            schedule_config={"cron": "0 * * * *"},
            schedule_enabled=True,
            next_run_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        user2_interval = f"u2-interval-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=user2_interval,
            name="User2 Interval Task",
            user_id="user_two",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 1800},
            schedule_enabled=True,
            next_run_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

        # Filter by user_id
        params = {"user_id": "user_one", "enabled_only": False}
        result = await task_routes.handle_scheduled_tasks_list(
            params, mock_request, str(uuid.uuid4())
        )

        task_ids = [t.get("id") for t in result]
        assert user1_cron in task_ids
        assert user2_interval not in task_ids

        # Filter by schedule_type
        params = {"schedule_type": "interval", "enabled_only": False}
        result = await task_routes.handle_scheduled_tasks_list(
            params, mock_request, str(uuid.uuid4())
        )

        task_ids = [t.get("id") for t in result]
        assert user2_interval in task_ids
        # user1_cron is cron type, should not be included
        for task in result:
            assert task.get("schedule_type") == "interval"

    @pytest.mark.asyncio
    async def test_complete_task_with_failure_real_flow(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test completing a task with failure status"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class

        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        task_id = f"fail-test-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=task_id,
            name="Failure Test Task",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 3600},
            schedule_enabled=True,
        )

        # Initialize first
        await task_routes.handle_scheduled_task_init(
            {"task_id": task_id}, mock_request, str(uuid.uuid4())
        )

        # Complete with failure
        complete_params = {
            "task_id": task_id,
            "success": False,
            "error": "Execution timeout",
        }

        result = await task_routes.handle_scheduled_task_complete(
            complete_params, mock_request, str(uuid.uuid4())
        )

        assert isinstance(result, dict)
        assert result.get("id") == task_id

    @pytest.mark.asyncio
    async def test_disabled_tasks_not_in_due_list(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test that disabled scheduled tasks are not returned as due"""
        from datetime import datetime, timezone, timedelta
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from apflow.core.config import get_task_model_class

        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create a disabled task that is "due"
        disabled_task_id = f"disabled-{uuid.uuid4().hex[:8]}"
        await task_repository.create_task(
            id=disabled_task_id,
            name="Disabled Due Task",
            user_id="test_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 3600},
            schedule_enabled=False,  # Disabled
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        params = {}
        result = await task_routes.handle_scheduled_tasks_due(
            params, mock_request, str(uuid.uuid4())
        )

        task_ids = [t.get("id") for t in result]
        assert disabled_task_id not in task_ids


# ============================================================================
# Export iCal Tests
# ============================================================================


class TestScheduledTasksExportIcal:
    """Tests for tasks.scheduled.export-ical endpoint"""

    @pytest.mark.asyncio
    async def test_export_ical_empty(self, task_routes, mock_request):
        """Test export iCal when no scheduled tasks exist"""
        params = {}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_export_ical(
            params, mock_request, request_id
        )

        assert result["task_count"] == 0
        assert "BEGIN:VCALENDAR" in result["ical_content"]
        assert "END:VCALENDAR" in result["ical_content"]

    @pytest.mark.asyncio
    async def test_export_ical_with_tasks(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test export iCal returns valid iCal content with scheduled tasks"""
        params = {"enabled_only": False}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_export_ical(
            params, mock_request, request_id
        )

        assert result["task_count"] >= 3
        content = result["ical_content"]
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content
        assert "BEGIN:VEVENT" in content
        assert "END:VEVENT" in content

    @pytest.mark.asyncio
    async def test_export_ical_enabled_only(
        self, task_routes, mock_request, multiple_scheduled_tasks
    ):
        """Test export iCal with enabled_only filter excludes disabled tasks"""
        # Export all
        all_result = await task_routes.handle_scheduled_tasks_export_ical(
            {"enabled_only": False}, mock_request, str(uuid.uuid4())
        )
        # Export enabled only
        enabled_result = await task_routes.handle_scheduled_tasks_export_ical(
            {"enabled_only": True}, mock_request, str(uuid.uuid4())
        )

        assert enabled_result["task_count"] < all_result["task_count"]

    @pytest.mark.asyncio
    async def test_export_ical_filter_by_user(self, task_routes, mock_request, use_test_db_session):
        """Test export iCal filtered by user_id"""
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        # Create tasks for two users
        now = datetime.now(timezone.utc)
        await task_repository.create_task(
            id=f"ical-user1-{uuid.uuid4().hex[:8]}",
            name="User1 Task",
            user_id="ical_user_one",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 3600},
            schedule_enabled=True,
            next_run_at=now + timedelta(hours=1),
        )
        await task_repository.create_task(
            id=f"ical-user2-{uuid.uuid4().hex[:8]}",
            name="User2 Task",
            user_id="ical_user_two",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="cron",
            schedule_config={"cron": "0 * * * *"},
            schedule_enabled=True,
            next_run_at=now + timedelta(hours=2),
        )

        result = await task_routes.handle_scheduled_tasks_export_ical(
            {"user_id": "ical_user_one"}, mock_request, str(uuid.uuid4())
        )

        assert result["task_count"] >= 1
        content = result["ical_content"]
        assert "User1 Task" in content
        assert "User2 Task" not in content

    @pytest.mark.asyncio
    async def test_export_ical_filter_by_schedule_type(
        self, task_routes, mock_request, use_test_db_session
    ):
        """Test export iCal filtered by schedule_type"""
        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        now = datetime.now(timezone.utc)
        await task_repository.create_task(
            id=f"ical-cron-{uuid.uuid4().hex[:8]}",
            name="Cron Only Task",
            user_id="ical_type_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="cron",
            schedule_config={"cron": "0 * * * *"},
            schedule_enabled=True,
            next_run_at=now + timedelta(hours=1),
        )
        await task_repository.create_task(
            id=f"ical-intv-{uuid.uuid4().hex[:8]}",
            name="Interval Only Task",
            user_id="ical_type_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 1800},
            schedule_enabled=True,
            next_run_at=now + timedelta(minutes=30),
        )

        result = await task_routes.handle_scheduled_tasks_export_ical(
            {"schedule_type": "cron", "user_id": "ical_type_user"},
            mock_request,
            str(uuid.uuid4()),
        )

        assert result["task_count"] >= 1
        content = result["ical_content"]
        assert "Cron Only Task" in content
        assert "Interval Only Task" not in content

    @pytest.mark.asyncio
    async def test_export_ical_custom_calendar_name(
        self, task_routes, mock_request, scheduled_task
    ):
        """Test export iCal with custom calendar name"""
        params = {"calendar_name": "My Custom Calendar", "enabled_only": False}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_export_ical(
            params, mock_request, request_id
        )

        assert "My Custom Calendar" in result["ical_content"]

    @pytest.mark.asyncio
    async def test_export_ical_with_base_url(self, task_routes, mock_request, scheduled_task):
        """Test export iCal includes task URLs when base_url is provided"""
        params = {
            "base_url": "https://api.example.com",
            "enabled_only": False,
        }
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_export_ical(
            params, mock_request, request_id
        )

        content = result["ical_content"]
        assert "https://api.example.com/tasks/" in content

    @pytest.mark.asyncio
    async def test_export_ical_ical_format_validity(
        self, task_routes, mock_request, scheduled_task
    ):
        """Test export iCal produces valid iCal structure"""
        params = {"enabled_only": False}
        request_id = str(uuid.uuid4())

        result = await task_routes.handle_scheduled_tasks_export_ical(
            params, mock_request, request_id
        )

        content = result["ical_content"]
        # Verify iCal structure
        assert content.startswith("BEGIN:VCALENDAR")
        assert content.strip().endswith("END:VCALENDAR")
        assert "VERSION:2.0" in content
        assert "PRODID:" in content
        # Each VEVENT should have required fields
        assert "DTSTART:" in content
        assert "DTEND:" in content
        assert "UID:" in content
        assert "SUMMARY:" in content

    @pytest.mark.asyncio
    async def test_export_ical_limit(self, task_routes, mock_request, multiple_scheduled_tasks):
        """Test export iCal respects limit parameter"""
        result = await task_routes.handle_scheduled_tasks_export_ical(
            {"limit": 1, "enabled_only": False}, mock_request, str(uuid.uuid4())
        )

        assert result["task_count"] <= 1


class TestExportIcalPermissions:
    """Tests for permission checking in export-ical endpoint"""

    @pytest.mark.asyncio
    async def test_non_admin_user_sees_own_tasks_only(self, use_test_db_session):
        """Test non-admin user can only export their own tasks"""
        from apflow.cli.jwt_token import generate_token, verify_token

        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        now = datetime.now(timezone.utc)
        await task_repository.create_task(
            id=f"ical-perm-mine-{uuid.uuid4().hex[:8]}",
            name="My Task",
            user_id="regular_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 3600},
            schedule_enabled=True,
            next_run_at=now + timedelta(hours=1),
        )
        await task_repository.create_task(
            id=f"ical-perm-other-{uuid.uuid4().hex[:8]}",
            name="Other User Task",
            user_id="other_user",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 3600},
            schedule_enabled=True,
            next_run_at=now + timedelta(hours=2),
        )

        # Set up JWT for non-admin user
        secret_key = "test_secret_for_ical_perm"
        token = generate_token(
            subject="regular_user",
            secret=secret_key,
            extra_claims={"user_id": "regular_user", "roles": ["user"]},
        )

        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=verify_token_func,
        )

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}
        request.cookies = {}
        request.state = Mock()
        request.state.user_id = "regular_user"
        request.state.token_payload = verify_token_func(token)

        result = await task_routes.handle_scheduled_tasks_export_ical(
            {}, request, str(uuid.uuid4())
        )

        content = result["ical_content"]
        assert "My Task" in content
        assert "Other User Task" not in content

    @pytest.mark.asyncio
    async def test_admin_user_sees_all_tasks(self, use_test_db_session):
        """Test admin user can export all users' tasks"""
        from apflow.cli.jwt_token import generate_token, verify_token

        task_repository = TaskRepository(
            use_test_db_session, task_model_class=get_task_model_class()
        )

        now = datetime.now(timezone.utc)
        await task_repository.create_task(
            id=f"ical-admin-u1-{uuid.uuid4().hex[:8]}",
            name="Admin View Task A",
            user_id="user_alpha",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="interval",
            schedule_config={"interval": 3600},
            schedule_enabled=True,
            next_run_at=now + timedelta(hours=1),
        )
        await task_repository.create_task(
            id=f"ical-admin-u2-{uuid.uuid4().hex[:8]}",
            name="Admin View Task B",
            user_id="user_beta",
            status="pending",
            priority=1,
            has_children=False,
            progress=0.0,
            schemas={"method": "system_info_executor"},
            inputs={},
            schedule_type="cron",
            schedule_config={"cron": "0 * * * *"},
            schedule_enabled=True,
            next_run_at=now + timedelta(hours=2),
        )

        # Set up JWT for admin user
        secret_key = "test_secret_for_ical_admin"
        token = generate_token(
            subject="admin_user",
            secret=secret_key,
            extra_claims={"user_id": "admin_user", "roles": ["admin"]},
        )

        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=verify_token_func,
        )

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}
        request.cookies = {}
        request.state = Mock()
        request.state.user_id = "admin_user"
        request.state.token_payload = verify_token_func(token)

        result = await task_routes.handle_scheduled_tasks_export_ical(
            {}, request, str(uuid.uuid4())
        )

        content = result["ical_content"]
        assert "Admin View Task A" in content
        assert "Admin View Task B" in content

    @pytest.mark.asyncio
    async def test_non_admin_cannot_export_other_user(self, use_test_db_session):
        """Test non-admin user cannot export other user's tasks by specifying user_id"""
        from apflow.cli.jwt_token import generate_token, verify_token

        secret_key = "test_secret_for_ical_deny"
        token = generate_token(
            subject="regular_user",
            secret=secret_key,
            extra_claims={"user_id": "regular_user", "roles": ["user"]},
        )

        def verify_token_func(token_str: str):
            return verify_token(token_str, secret_key)

        task_routes = TaskRoutes(
            task_model_class=get_task_model_class(),
            verify_token_func=verify_token_func,
        )

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}
        request.cookies = {}
        request.state = Mock()
        request.state.user_id = "regular_user"
        request.state.token_payload = verify_token_func(token)

        with pytest.raises(ValueError, match="Permission denied"):
            await task_routes.handle_scheduled_tasks_export_ical(
                {"user_id": "other_user"}, request, str(uuid.uuid4())
            )

"""
Tests for Webhook API endpoints

Tests cover:
- REST endpoint: POST /webhook/trigger/{task_id}
- JSON-RPC endpoint: tasks.webhook.trigger
- JWT bypass for webhook paths
- Webhook signature validation
"""

import pytest
import hmac
import hashlib
import time
import os
from unittest.mock import AsyncMock, MagicMock, patch


class TestJWTMiddlewareWebhookBypass:
    """Tests for JWT middleware bypassing webhook paths"""

    def test_public_path_prefixes_includes_webhook(self):
        """Test that /webhook/ is in PUBLIC_PATH_PREFIXES"""
        from apflow.api.a2a.custom_starlette_app import JWTAuthenticationMiddleware

        assert "/webhook/" in JWTAuthenticationMiddleware.PUBLIC_PATH_PREFIXES

    def test_webhook_path_should_bypass_jwt(self):
        """Test that webhook paths bypass JWT authentication check"""
        from apflow.api.a2a.custom_starlette_app import JWTAuthenticationMiddleware

        # Verify the path prefix matching logic
        test_paths = [
            "/webhook/trigger/abc123",
            "/webhook/trigger/task-with-dashes",
            "/webhook/other-endpoint",
        ]

        for path in test_paths:
            # Check if path starts with any public prefix
            bypasses_jwt = any(
                path.startswith(prefix)
                for prefix in JWTAuthenticationMiddleware.PUBLIC_PATH_PREFIXES
            )
            assert bypasses_jwt, f"Path {path} should bypass JWT"

    def test_non_webhook_path_requires_jwt(self):
        """Test that non-webhook paths don't bypass JWT"""
        from apflow.api.a2a.custom_starlette_app import JWTAuthenticationMiddleware

        test_paths = [
            "/tasks",
            "/system",
            "/api/tasks",
            "/webhookfake/trigger",  # No trailing slash after webhook
        ]

        for path in test_paths:
            bypasses_jwt = any(
                path.startswith(prefix)
                for prefix in JWTAuthenticationMiddleware.PUBLIC_PATH_PREFIXES
            )
            assert not bypasses_jwt, f"Path {path} should NOT bypass JWT"


class TestWebhookSignatureValidation:
    """Tests for webhook signature validation"""

    def test_validate_signature_no_secret(self):
        """Test signature validation when no secret is configured"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        config = WebhookConfig(secret_key=None)
        gateway = WebhookGateway(config)

        # Should return True when no secret configured
        assert gateway.validate_signature(b"any payload", "any signature") is True

    def test_validate_signature_with_secret_valid(self):
        """Test signature validation with valid signature"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        secret = "test-secret-key"
        config = WebhookConfig(secret_key=secret)
        gateway = WebhookGateway(config)

        payload = b'{"task_id": "abc123"}'
        timestamp = "1234567890"

        # Compute correct signature
        message = f"{timestamp}.".encode() + payload
        expected_sig = hmac.new(
            secret.encode(), message, hashlib.sha256
        ).hexdigest()

        assert gateway.validate_signature(payload, expected_sig, timestamp) is True

    def test_validate_signature_with_secret_invalid(self):
        """Test signature validation with invalid signature"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        config = WebhookConfig(secret_key="test-secret")
        gateway = WebhookGateway(config)

        payload = b'{"task_id": "abc123"}'
        timestamp = "1234567890"

        assert gateway.validate_signature(payload, "invalid-signature", timestamp) is False

    def test_validate_signature_without_timestamp(self):
        """Test signature validation without timestamp"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        secret = "test-secret"
        config = WebhookConfig(secret_key=secret)
        gateway = WebhookGateway(config)

        payload = b'{"task_id": "abc123"}'

        # Compute signature without timestamp
        expected_sig = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        assert gateway.validate_signature(payload, expected_sig, None) is True


class TestWebhookRequestValidation:
    """Tests for webhook request validation"""

    @pytest.mark.asyncio
    async def test_validate_request_no_restrictions(self):
        """Test request validation with no restrictions"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        config = WebhookConfig()
        gateway = WebhookGateway(config)

        result = await gateway.validate_request(client_ip="192.168.1.100")
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_request_ip_allowed(self):
        """Test request validation with allowed IP"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        config = WebhookConfig(allowed_ips=["10.0.0.1", "10.0.0.2"])
        gateway = WebhookGateway(config)

        result = await gateway.validate_request(client_ip="10.0.0.1")
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_request_ip_denied(self):
        """Test request validation with denied IP"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        config = WebhookConfig(allowed_ips=["10.0.0.1", "10.0.0.2"])
        gateway = WebhookGateway(config)

        result = await gateway.validate_request(client_ip="192.168.1.100")
        assert result["valid"] is False
        assert "IP not allowed" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_request_rate_limit_ok(self):
        """Test request validation within rate limit"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        config = WebhookConfig(rate_limit=10)
        gateway = WebhookGateway(config)

        # First 10 requests should pass
        for i in range(10):
            result = await gateway.validate_request(client_ip="10.0.0.1")
            assert result["valid"] is True, f"Request {i+1} should be allowed"

    @pytest.mark.asyncio
    async def test_validate_request_rate_limit_exceeded(self):
        """Test request validation exceeding rate limit"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        config = WebhookConfig(rate_limit=5)
        gateway = WebhookGateway(config)

        # First 5 requests should pass
        for _ in range(5):
            await gateway.validate_request(client_ip="10.0.0.1")

        # 6th request should fail
        result = await gateway.validate_request(client_ip="10.0.0.1")
        assert result["valid"] is False
        assert "Rate limit" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_request_missing_signature(self):
        """Test request validation with missing signature when secret is configured"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        config = WebhookConfig(secret_key="test-secret")
        gateway = WebhookGateway(config)

        result = await gateway.validate_request(
            client_ip="10.0.0.1",
            payload=b"test payload",
            signature=None,  # Missing signature
        )
        assert result["valid"] is False
        assert "Missing signature" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_request_invalid_signature(self):
        """Test request validation with invalid signature"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        config = WebhookConfig(secret_key="test-secret")
        gateway = WebhookGateway(config)

        result = await gateway.validate_request(
            client_ip="10.0.0.1",
            payload=b"test payload",
            signature="invalid-signature",
            timestamp="1234567890",
        )
        assert result["valid"] is False
        assert "Invalid signature" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_request_valid_signature(self):
        """Test request validation with valid signature"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        secret = "test-secret"
        config = WebhookConfig(secret_key=secret)
        gateway = WebhookGateway(config)

        payload = b'{"task_id": "abc123"}'
        timestamp = "1234567890"
        message = f"{timestamp}.".encode() + payload
        signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

        result = await gateway.validate_request(
            client_ip="10.0.0.1",
            payload=payload,
            signature=signature,
            timestamp=timestamp,
        )
        assert result["valid"] is True


class TestWebhookTriggerHandler:
    """Tests for webhook trigger handler in TaskRoutes"""

    @pytest.mark.asyncio
    async def test_handle_webhook_trigger_missing_task_id(self):
        """Test webhook trigger with missing task_id"""
        from apflow.api.routes.tasks import TaskRoutes
        from apflow.core.storage.sqlalchemy.models import TaskModel
        from unittest.mock import MagicMock

        routes = TaskRoutes(task_model_class=TaskModel)
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        # Should raise ValueError for missing task_id
        with pytest.raises(ValueError, match="task_id is required"):
            await routes.handle_webhook_trigger({}, request, "test-request-id")

    @pytest.mark.asyncio
    async def test_handle_webhook_trigger_with_task_id(self):
        """Test webhook trigger with valid task_id via WebhookGateway directly"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig
        from unittest.mock import MagicMock, patch, AsyncMock

        config = WebhookConfig()  # No restrictions
        gateway = WebhookGateway(config)

        # Mock task
        mock_task = MagicMock()
        mock_task.id = "test-task-123"
        mock_task.user_id = None

        with patch("apflow.core.storage.create_pooled_session") as mock_session:
            mock_db = AsyncMock()
            mock_repo = MagicMock()
            mock_repo.get_task_by_id = AsyncMock(return_value=mock_task)
            mock_repo.mark_scheduled_task_running = AsyncMock(return_value=mock_task)

            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("apflow.core.storage.sqlalchemy.task_repository.TaskRepository", return_value=mock_repo):
                with patch.object(gateway, "_execute_task_background", new_callable=AsyncMock):
                    result = await gateway.trigger_task("test-task-123", execute_async=True)

        assert result["success"] is True
        assert result["task_id"] == "test-task-123"

    @pytest.mark.asyncio
    async def test_handle_webhook_trigger_validation_failed(self):
        """Test webhook trigger when validation fails via WebhookGateway directly"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        # Configure gateway with IP restrictions
        config = WebhookConfig(allowed_ips=["10.0.0.1"])
        gateway = WebhookGateway(config)

        # Validate request from disallowed IP
        result = await gateway.validate_request(client_ip="192.168.1.100")

        assert result["valid"] is False
        assert "IP not allowed" in result["error"]


class TestWebhookEnvironmentConfig:
    """Tests for webhook environment variable configuration"""

    def test_webhook_config_from_environment(self):
        """Test that webhook config can be loaded from environment variables"""
        # Set environment variables
        with patch.dict(os.environ, {
            "APFLOW_WEBHOOK_SECRET": "env-secret-key",
            "APFLOW_WEBHOOK_ALLOWED_IPS": "10.0.0.1,10.0.0.2,10.0.0.3",
            "APFLOW_WEBHOOK_RATE_LIMIT": "50",
        }):
            secret = os.getenv("APFLOW_WEBHOOK_SECRET")
            allowed_ips_str = os.getenv("APFLOW_WEBHOOK_ALLOWED_IPS")
            allowed_ips = allowed_ips_str.split(",") if allowed_ips_str else None
            rate_limit = int(os.getenv("APFLOW_WEBHOOK_RATE_LIMIT", "0"))

            assert secret == "env-secret-key"
            assert allowed_ips == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
            assert rate_limit == 50

    def test_webhook_config_defaults(self):
        """Test webhook config defaults when no environment variables set"""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            secret = os.getenv("APFLOW_WEBHOOK_SECRET")
            allowed_ips_str = os.getenv("APFLOW_WEBHOOK_ALLOWED_IPS")
            allowed_ips = allowed_ips_str.split(",") if allowed_ips_str else None
            rate_limit = int(os.getenv("APFLOW_WEBHOOK_RATE_LIMIT", "0"))

            assert secret is None
            assert allowed_ips is None
            assert rate_limit == 0


class TestWebhookGatewayTrigger:
    """Tests for WebhookGateway trigger_task method"""

    @pytest.mark.asyncio
    async def test_trigger_task_not_found(self):
        """Test triggering a non-existent task"""
        from apflow.scheduler.gateway.webhook import WebhookGateway

        gateway = WebhookGateway()

        # Mock the database to return no task
        with patch("apflow.core.storage.create_pooled_session") as mock_session:
            mock_db = AsyncMock()
            mock_repo = MagicMock()
            mock_repo.get_task_by_id = AsyncMock(return_value=None)

            # Setup context manager
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("apflow.core.storage.sqlalchemy.task_repository.TaskRepository", return_value=mock_repo):
                result = await gateway.trigger_task("non-existent-task")

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_trigger_task_async_mode(self):
        """Test triggering task in async mode"""
        from apflow.scheduler.gateway.webhook import WebhookGateway

        gateway = WebhookGateway()

        # Mock task
        mock_task = MagicMock()
        mock_task.id = "test-task-123"
        mock_task.user_id = None

        with patch("apflow.core.storage.create_pooled_session") as mock_session:
            mock_db = AsyncMock()
            mock_repo = MagicMock()
            mock_repo.get_task_by_id = AsyncMock(return_value=mock_task)
            mock_repo.mark_scheduled_task_running = AsyncMock(return_value=mock_task)

            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("apflow.core.storage.sqlalchemy.task_repository.TaskRepository", return_value=mock_repo):
                with patch.object(gateway, "_execute_task_background", new_callable=AsyncMock):
                    result = await gateway.trigger_task("test-task-123", execute_async=True)

            assert result["success"] is True
            assert result["status"] == "triggered"


class TestWebhookHelperFunctions:
    """Tests for webhook helper functions"""

    def test_generate_cron_config(self):
        """Test cron config generation"""
        from apflow.scheduler.gateway.webhook import generate_cron_config

        cron = generate_cron_config(
            task_id="task-123",
            schedule_expression="0 9 * * 1-5",
            webhook_url="https://api.example.com/webhook/trigger/task-123"
        )

        assert "0 9 * * 1-5" in cron
        assert "curl" in cron
        assert "https://api.example.com/webhook/trigger/task-123" in cron
        assert "task-123" in cron

    def test_generate_kubernetes_cronjob(self):
        """Test Kubernetes CronJob manifest generation"""
        from apflow.scheduler.gateway.webhook import generate_kubernetes_cronjob

        manifest = generate_kubernetes_cronjob(
            task_id="task-abc-123",
            task_name="Daily Backup",
            schedule_expression="0 2 * * *",
            webhook_url="https://api.example.com/webhook/trigger/task-abc-123",
            namespace="production"
        )

        assert manifest["apiVersion"] == "batch/v1"
        assert manifest["kind"] == "CronJob"
        assert manifest["metadata"]["namespace"] == "production"
        assert manifest["spec"]["schedule"] == "0 2 * * *"
        assert "task-abc-123" in manifest["metadata"]["labels"]["task-id"]

        # Check container args include the webhook URL
        container = manifest["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
        assert "https://api.example.com/webhook/trigger/task-abc-123" in container["args"]

    def test_generate_webhook_url(self):
        """Test webhook URL generation"""
        from apflow.scheduler.gateway.webhook import WebhookGateway

        gateway = WebhookGateway()
        url_info = gateway.generate_webhook_url(
            task_id="my-task-id",
            base_url="https://api.example.com"
        )

        assert url_info["url"] == "https://api.example.com/webhook/trigger/my-task-id"
        assert url_info["method"] == "POST"

    def test_generate_webhook_url_with_trailing_slash(self):
        """Test webhook URL generation with trailing slash in base URL"""
        from apflow.scheduler.gateway.webhook import WebhookGateway

        gateway = WebhookGateway()
        url_info = gateway.generate_webhook_url(
            task_id="task-123",
            base_url="https://api.example.com/"  # Trailing slash
        )

        # Should not have double slashes
        assert url_info["url"] == "https://api.example.com/webhook/trigger/task-123"


class TestWebhookIntegration:
    """Integration tests for webhook functionality"""

    def test_full_webhook_signature_flow(self):
        """Test full signature generation and validation flow"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        secret = "production-webhook-secret"
        config = WebhookConfig(secret_key=secret)
        gateway = WebhookGateway(config)

        # Simulate what an external scheduler would do
        task_id = "scheduled-task-001"
        timestamp = str(int(time.time()))
        payload = f'{{"task_id": "{task_id}"}}'.encode()

        # Generate signature (external scheduler side)
        message = f"{timestamp}.".encode() + payload
        signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

        # Validate signature (apflow side)
        is_valid = gateway.validate_signature(payload, signature, timestamp)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_webhook_with_all_security_features(self):
        """Test webhook with all security features enabled"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        secret = "test-secret"
        config = WebhookConfig(
            secret_key=secret,
            allowed_ips=["10.0.0.1", "10.0.0.2"],
            rate_limit=100,
        )
        gateway = WebhookGateway(config)

        # Prepare valid request
        payload = b'{"task_id": "task-123"}'
        timestamp = str(int(time.time()))
        message = f"{timestamp}.".encode() + payload
        signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

        # Validate request
        result = await gateway.validate_request(
            client_ip="10.0.0.1",
            payload=payload,
            signature=signature,
            timestamp=timestamp,
        )

        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_webhook_rejection_scenarios(self):
        """Test various webhook rejection scenarios"""
        from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig

        secret = "test-secret"
        config = WebhookConfig(
            secret_key=secret,
            allowed_ips=["10.0.0.1"],
            rate_limit=2,
        )
        gateway = WebhookGateway(config)

        payload = b'{"task_id": "task-123"}'
        timestamp = str(int(time.time()))
        message = f"{timestamp}.".encode() + payload
        valid_signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

        # Test 1: Wrong IP
        result = await gateway.validate_request(
            client_ip="192.168.1.1",
            payload=payload,
            signature=valid_signature,
            timestamp=timestamp,
        )
        assert result["valid"] is False
        assert "IP" in result["error"]

        # Test 2: Wrong signature
        result = await gateway.validate_request(
            client_ip="10.0.0.1",
            payload=payload,
            signature="wrong-signature",
            timestamp=timestamp,
        )
        assert result["valid"] is False
        assert "signature" in result["error"].lower()

        # Test 3: Rate limit exceeded
        # First two requests should pass
        for _ in range(2):
            await gateway.validate_request(
                client_ip="10.0.0.1",
                payload=payload,
                signature=valid_signature,
                timestamp=timestamp,
            )

        # Third request should fail
        result = await gateway.validate_request(
            client_ip="10.0.0.1",
            payload=payload,
            signature=valid_signature,
            timestamp=timestamp,
        )
        assert result["valid"] is False
        assert "Rate limit" in result["error"]

"""
Test SendEmailExecutor

Tests for email sending via Resend API and SMTP providers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apflow.core.execution.errors import ConfigurationError, ValidationError
from apflow.extensions.email.send_email_executor import SendEmailExecutor


class TestSendEmailExecutorValidation:
    """Test input validation for SendEmailExecutor"""

    @pytest.mark.asyncio
    async def test_execute_missing_provider(self):
        """Test error when provider is missing"""
        executor = SendEmailExecutor()

        with pytest.raises(ValidationError, match="provider is required"):
            await executor.execute(
                {"to": "a@b.com", "subject": "Hi", "from_email": "x@y.com", "body": "text"}
            )

    @pytest.mark.asyncio
    async def test_execute_missing_to(self):
        """Test error when to is missing"""
        executor = SendEmailExecutor()

        with pytest.raises(ValidationError, match="to is required"):
            await executor.execute(
                {"provider": "resend", "subject": "Hi", "from_email": "x@y.com", "body": "text"}
            )

    @pytest.mark.asyncio
    async def test_execute_missing_subject(self):
        """Test error when subject is missing"""
        executor = SendEmailExecutor()

        with pytest.raises(ValidationError, match="subject is required"):
            await executor.execute(
                {"provider": "resend", "to": "a@b.com", "from_email": "x@y.com", "body": "text"}
            )

    @pytest.mark.asyncio
    async def test_execute_missing_from_email(self):
        """Test error when from_email is missing"""
        executor = SendEmailExecutor()

        with pytest.raises(ValidationError, match="from_email is required"):
            await executor.execute(
                {"provider": "resend", "to": "a@b.com", "subject": "Hi", "body": "text"}
            )

    @pytest.mark.asyncio
    async def test_execute_missing_body_and_html(self):
        """Test error when neither body nor html is provided"""
        executor = SendEmailExecutor()

        with pytest.raises(ValidationError, match="Either body or html"):
            await executor.execute(
                {
                    "provider": "resend",
                    "to": "a@b.com",
                    "subject": "Hi",
                    "from_email": "x@y.com",
                }
            )

    @pytest.mark.asyncio
    async def test_execute_unknown_provider(self):
        """Test error for unknown provider"""
        executor = SendEmailExecutor()

        with pytest.raises(ValidationError, match="Unknown provider 'invalid'"):
            await executor.execute(
                {
                    "provider": "invalid",
                    "to": "a@b.com",
                    "subject": "Hi",
                    "from_email": "x@y.com",
                    "body": "text",
                }
            )


class TestResendProvider:
    """Test Resend email provider"""

    def _base_inputs(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "provider": "resend",
            "api_key": "re_test_key",
            "to": ["user@example.com"],
            "subject": "Test Subject",
            "from_email": "sender@example.com",
            "body": "Hello World",
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_resend_success(self):
        """Test successful email send via Resend"""
        executor = SendEmailExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_123"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await executor.execute(self._base_inputs())

            assert result["success"] is True
            assert result["provider"] == "resend"
            assert result["message_id"] == "msg_123"
            assert result["status_code"] == 200
            mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_resend_html_email(self):
        """Test sending HTML email via Resend"""
        executor = SendEmailExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_456"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await executor.execute(self._base_inputs(body=None, html="<h1>Hello</h1>"))

            assert result["success"] is True
            call_kwargs = mock_instance.post.call_args[1]
            assert call_kwargs["json"]["html"] == "<h1>Hello</h1>"
            assert "text" not in call_kwargs["json"]

    @pytest.mark.asyncio
    async def test_resend_with_cc_bcc(self):
        """Test sending email with cc and bcc via Resend"""
        executor = SendEmailExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_789"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await executor.execute(
                self._base_inputs(
                    cc=["cc@example.com"],
                    bcc=["bcc@example.com"],
                )
            )

            assert result["success"] is True
            call_kwargs = mock_instance.post.call_args[1]
            assert call_kwargs["json"]["cc"] == ["cc@example.com"]
            assert call_kwargs["json"]["bcc"] == ["bcc@example.com"]

    @pytest.mark.asyncio
    async def test_resend_with_reply_to(self):
        """Test sending email with reply_to via Resend"""
        executor = SendEmailExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_rt"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await executor.execute(self._base_inputs(reply_to="reply@example.com"))

            assert result["success"] is True
            call_kwargs = mock_instance.post.call_args[1]
            assert call_kwargs["json"]["reply_to"] == "reply@example.com"

    @pytest.mark.asyncio
    async def test_resend_api_error(self):
        """Test handling Resend API error response"""
        executor = SendEmailExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = '{"message": "Invalid email"}'

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await executor.execute(self._base_inputs())

            assert result["success"] is False
            assert result["provider"] == "resend"
            assert result["status_code"] == 422
            assert "Invalid email" in result["error"]

    @pytest.mark.asyncio
    async def test_resend_missing_api_key(self):
        """Test error when api_key is missing for resend provider"""
        executor = SendEmailExecutor()

        with pytest.raises(ValidationError, match="api_key is required"):
            await executor.execute(self._base_inputs(api_key=None))

    @pytest.mark.asyncio
    async def test_resend_string_to_normalized(self):
        """Test that a string 'to' field is normalized to a list"""
        executor = SendEmailExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "msg_str"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post = AsyncMock(return_value=mock_response)

            result = await executor.execute(self._base_inputs(to="single@example.com"))

            assert result["success"] is True
            call_kwargs = mock_instance.post.call_args[1]
            assert call_kwargs["json"]["to"] == ["single@example.com"]


class TestSmtpProvider:
    """Test SMTP email provider"""

    def _base_inputs(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "provider": "smtp",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "user",
            "smtp_password": "pass",
            "to": ["user@example.com"],
            "subject": "Test Subject",
            "from_email": "sender@example.com",
            "body": "Hello World",
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_smtp_success(self):
        """Test successful email send via SMTP"""
        executor = SendEmailExecutor()

        with (
            patch("apflow.extensions.email.send_email_executor.AIOSMTPLIB_AVAILABLE", True),
            patch("apflow.extensions.email.send_email_executor.aiosmtplib") as mock_aiosmtplib,
        ):
            mock_aiosmtplib.send = AsyncMock()

            result = await executor.execute(self._base_inputs())

            assert result["success"] is True
            assert result["provider"] == "smtp"
            assert "user@example.com" in result["message"]
            mock_aiosmtplib.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_smtp_html_email(self):
        """Test sending HTML email via SMTP"""
        executor = SendEmailExecutor()

        with (
            patch("apflow.extensions.email.send_email_executor.AIOSMTPLIB_AVAILABLE", True),
            patch("apflow.extensions.email.send_email_executor.aiosmtplib") as mock_aiosmtplib,
        ):
            mock_aiosmtplib.send = AsyncMock()

            result = await executor.execute(self._base_inputs(body=None, html="<h1>Hello</h1>"))

            assert result["success"] is True
            call_kwargs = mock_aiosmtplib.send.call_args[1]
            msg = call_kwargs["message"]
            assert msg.get_content_type() == "text/html"

    @pytest.mark.asyncio
    async def test_smtp_html_with_text_fallback(self):
        """Test sending HTML email with text fallback via SMTP"""
        executor = SendEmailExecutor()

        with (
            patch("apflow.extensions.email.send_email_executor.AIOSMTPLIB_AVAILABLE", True),
            patch("apflow.extensions.email.send_email_executor.aiosmtplib") as mock_aiosmtplib,
        ):
            mock_aiosmtplib.send = AsyncMock()

            result = await executor.execute(self._base_inputs(html="<h1>Hello</h1>"))

            assert result["success"] is True
            call_kwargs = mock_aiosmtplib.send.call_args[1]
            msg = call_kwargs["message"]
            # multipart/alternative when both body and html provided
            assert msg.get_content_type() == "multipart/alternative"

    @pytest.mark.asyncio
    async def test_smtp_with_cc_bcc(self):
        """Test sending email with cc and bcc via SMTP"""
        executor = SendEmailExecutor()

        with (
            patch("apflow.extensions.email.send_email_executor.AIOSMTPLIB_AVAILABLE", True),
            patch("apflow.extensions.email.send_email_executor.aiosmtplib") as mock_aiosmtplib,
        ):
            mock_aiosmtplib.send = AsyncMock()

            result = await executor.execute(
                self._base_inputs(
                    cc=["cc@example.com"],
                    bcc=["bcc@example.com"],
                )
            )

            assert result["success"] is True
            call_kwargs = mock_aiosmtplib.send.call_args[1]
            msg = call_kwargs["message"]
            assert "cc@example.com" in msg["Cc"]
            # bcc should not be in headers but should be in recipients
            recipients = call_kwargs["recipients"]
            assert "bcc@example.com" in recipients
            assert "cc@example.com" in recipients

    @pytest.mark.asyncio
    async def test_smtp_missing_host(self):
        """Test error when smtp_host is missing"""
        executor = SendEmailExecutor()

        with patch("apflow.extensions.email.send_email_executor.AIOSMTPLIB_AVAILABLE", True):
            with pytest.raises(ValidationError, match="smtp_host is required"):
                await executor.execute(self._base_inputs(smtp_host=None))

    @pytest.mark.asyncio
    async def test_smtp_aiosmtplib_unavailable(self):
        """Test error when aiosmtplib is not installed"""
        executor = SendEmailExecutor()

        with patch("apflow.extensions.email.send_email_executor.AIOSMTPLIB_AVAILABLE", False):
            with pytest.raises(ConfigurationError, match="aiosmtplib is not installed"):
                await executor.execute(self._base_inputs())

    @pytest.mark.asyncio
    async def test_smtp_tls_disabled(self):
        """Test SMTP with TLS disabled"""
        executor = SendEmailExecutor()

        with (
            patch("apflow.extensions.email.send_email_executor.AIOSMTPLIB_AVAILABLE", True),
            patch("apflow.extensions.email.send_email_executor.aiosmtplib") as mock_aiosmtplib,
        ):
            mock_aiosmtplib.send = AsyncMock()

            result = await executor.execute(self._base_inputs(smtp_use_tls=False))

            assert result["success"] is True
            call_kwargs = mock_aiosmtplib.send.call_args[1]
            assert "start_tls" not in call_kwargs


class TestSchemaAndDemo:
    """Test schema methods and demo results"""

    def test_get_input_schema(self):
        """Test input schema contains required fields"""
        executor = SendEmailExecutor()
        schema = executor.get_input_schema()

        assert schema["type"] == "object"
        assert "provider" in schema["required"]
        assert "to" in schema["required"]
        assert "subject" in schema["required"]
        assert "from_email" in schema["required"]
        assert "api_key" in schema["properties"]
        assert "smtp_host" in schema["properties"]

    def test_get_output_schema(self):
        """Test output schema contains expected fields"""
        executor = SendEmailExecutor()
        schema = executor.get_output_schema()

        assert schema["type"] == "object"
        assert "success" in schema["required"]
        assert "provider" in schema["required"]
        assert "message_id" in schema["properties"]
        assert "error" in schema["properties"]

    def test_get_demo_result_resend(self):
        """Test demo result for resend provider"""
        executor = SendEmailExecutor()
        result = executor.get_demo_result(
            task=None, inputs={"provider": "resend", "to": ["demo@example.com"]}
        )

        assert result is not None
        assert result["success"] is True
        assert result["provider"] == "resend"
        assert "message_id" in result

    def test_get_demo_result_smtp(self):
        """Test demo result for smtp provider"""
        executor = SendEmailExecutor()
        result = executor.get_demo_result(
            task=None, inputs={"provider": "smtp", "to": ["demo@example.com"]}
        )

        assert result is not None
        assert result["success"] is True
        assert result["provider"] == "smtp"
        assert "message" in result

    def test_get_demo_result_string_to(self):
        """Test demo result handles string to field"""
        executor = SendEmailExecutor()
        result = executor.get_demo_result(
            task=None, inputs={"provider": "resend", "to": "demo@example.com"}
        )

        assert result is not None
        assert result["success"] is True

    def test_executor_attributes(self):
        """Test executor class attributes"""
        executor = SendEmailExecutor()
        assert executor.id == "send_email_executor"
        assert executor.type == "email"
        assert executor.cancelable is False

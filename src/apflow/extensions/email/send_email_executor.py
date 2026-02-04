"""
Send Email Executor for sending emails via Resend API or SMTP.

This executor supports two email providers:
- Resend: Cloud email API via HTTP
- SMTP: Traditional SMTP protocol via aiosmtplib (optional dependency)
"""

import httpx
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Union

from apflow.core.base import BaseTask
from apflow.core.execution.errors import ConfigurationError, ValidationError
from apflow.core.extensions.decorators import executor_register
from apflow.logger import get_logger

logger = get_logger(__name__)

try:
    import aiosmtplib

    AIOSMTPLIB_AVAILABLE = True
except ImportError:
    aiosmtplib = None  # type: ignore[assignment]
    AIOSMTPLIB_AVAILABLE = False
    logger.warning(
        "aiosmtplib is not installed. SMTP email provider will not be available. "
        "Install it with: pip install apflow[email]"
    )


@executor_register()
class SendEmailExecutor(BaseTask):
    """
    Executor for sending emails via Resend API or SMTP.

    Supports two providers:
    - "resend": Uses Resend HTTP API (requires api_key)
    - "smtp": Uses SMTP protocol via aiosmtplib (requires smtp_host, etc.)

    Example usage in task schemas:
    {
        "schemas": {
            "method": "send_email_executor"
        },
        "inputs": {
            "provider": "resend",
            "api_key": "re_xxx",
            "to": ["user@example.com"],
            "from_email": "noreply@example.com",
            "subject": "Hello",
            "body": "Hello World"
        }
    }
    """

    id = "send_email_executor"
    name = "Send Email Executor"
    description = "Send emails via Resend API or SMTP"
    tags = ["email", "notification", "smtp", "resend"]
    examples = [
        "Send transactional email via Resend",
        "Send notification email via SMTP",
        "Send HTML email with cc/bcc recipients",
    ]

    cancelable: bool = False

    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "email"

    def _normalize_recipients(self, value: Union[str, List[str], None]) -> List[str]:
        """Normalize recipient field to a list of strings."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send an email using the specified provider.

        Args:
            inputs: Dictionary containing:
                - provider: "resend" or "smtp" (required)
                - to: Recipient email(s), str or list (required)
                - subject: Email subject (required)
                - from_email: Sender email address (required)
                - body: Plain text body (required if html not provided)
                - html: HTML body (optional, alternative to body)
                - cc: CC recipients, str or list (optional)
                - bcc: BCC recipients, str or list (optional)
                - reply_to: Reply-to address (optional)
                - timeout: Request timeout in seconds (default: 30)
                Resend-specific:
                - api_key: Resend API key (required for resend)
                SMTP-specific:
                - smtp_host: SMTP server hostname (required for smtp)
                - smtp_port: SMTP server port (default: 587)
                - smtp_username: SMTP auth username (optional)
                - smtp_password: SMTP auth password (optional)
                - smtp_use_tls: Whether to use STARTTLS (default: True)

        Returns:
            Dictionary with send results.
        """
        provider = inputs.get("provider")
        if not provider:
            raise ValidationError(f"[{self.id}] provider is required")

        to = inputs.get("to")
        if not to:
            raise ValidationError(f"[{self.id}] to is required")

        subject = inputs.get("subject")
        if not subject:
            raise ValidationError(f"[{self.id}] subject is required")

        from_email = inputs.get("from_email")
        if not from_email:
            raise ValidationError(f"[{self.id}] from_email is required")

        body = inputs.get("body")
        html = inputs.get("html")
        if not body and not html:
            raise ValidationError(f"[{self.id}] Either body or html must be provided")

        if provider == "resend":
            return await self._send_via_resend(inputs)
        elif provider == "smtp":
            return await self._send_via_smtp(inputs)
        else:
            raise ValidationError(
                f"[{self.id}] Unknown provider '{provider}'. Supported: 'resend', 'smtp'"
            )

    async def _send_via_resend(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Send email via Resend HTTP API."""
        api_key = inputs.get("api_key")
        if not api_key:
            raise ValidationError(f"[{self.id}] api_key is required for resend provider")

        to_list = self._normalize_recipients(inputs.get("to"))
        cc_list = self._normalize_recipients(inputs.get("cc"))
        bcc_list = self._normalize_recipients(inputs.get("bcc"))
        timeout = inputs.get("timeout", 30)

        payload: Dict[str, Any] = {
            "from": inputs["from_email"],
            "to": to_list,
            "subject": inputs["subject"],
        }

        if inputs.get("html"):
            payload["html"] = inputs["html"]
        if inputs.get("body"):
            payload["text"] = inputs["body"]
        if cc_list:
            payload["cc"] = cc_list
        if bcc_list:
            payload["bcc"] = bcc_list
        if inputs.get("reply_to"):
            payload["reply_to"] = inputs["reply_to"]

        logger.info(f"Sending email via Resend to {to_list}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

        if 200 <= response.status_code < 300:
            response_data = response.json()
            return {
                "success": True,
                "provider": "resend",
                "message_id": response_data.get("id"),
                "status_code": response.status_code,
            }
        else:
            return {
                "success": False,
                "provider": "resend",
                "status_code": response.status_code,
                "error": response.text,
            }

    async def _send_via_smtp(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Send email via SMTP using aiosmtplib."""
        if not AIOSMTPLIB_AVAILABLE:
            raise ConfigurationError(
                f"[{self.id}] aiosmtplib is not installed. "
                "Install it with: pip install apflow[email]"
            )

        smtp_host = inputs.get("smtp_host")
        if not smtp_host:
            raise ValidationError(f"[{self.id}] smtp_host is required for smtp provider")

        smtp_port = inputs.get("smtp_port", 587)
        smtp_username = inputs.get("smtp_username")
        smtp_password = inputs.get("smtp_password")
        smtp_use_tls = inputs.get("smtp_use_tls", True)
        timeout = inputs.get("timeout", 30)

        to_list = self._normalize_recipients(inputs.get("to"))
        cc_list = self._normalize_recipients(inputs.get("cc"))
        bcc_list = self._normalize_recipients(inputs.get("bcc"))

        msg = EmailMessage()
        msg["From"] = inputs["from_email"]
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = inputs["subject"]

        if cc_list:
            msg["Cc"] = ", ".join(cc_list)
        if inputs.get("reply_to"):
            msg["Reply-To"] = inputs["reply_to"]

        body = inputs.get("body")
        html = inputs.get("html")

        if body:
            msg.set_content(body)
        if html:
            if body:
                msg.add_alternative(html, subtype="html")
            else:
                msg.set_content(html, subtype="html")

        all_recipients = to_list + cc_list + bcc_list

        logger.info(f"Sending email via SMTP ({smtp_host}:{smtp_port}) to {to_list}")

        send_kwargs: Dict[str, Any] = {
            "message": msg,
            "hostname": smtp_host,
            "port": smtp_port,
            "recipients": all_recipients,
            "timeout": timeout,
        }

        if smtp_use_tls:
            send_kwargs["start_tls"] = True
        if smtp_username:
            send_kwargs["username"] = smtp_username
        if smtp_password:
            send_kwargs["password"] = smtp_password

        await aiosmtplib.send(**send_kwargs)  # type: ignore[possibly-undefined]

        return {
            "success": True,
            "provider": "smtp",
            "message": f"Email sent to {', '.join(to_list)}",
        }

    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo email send result."""
        provider = inputs.get("provider", "resend")
        to = inputs.get("to", ["demo@example.com"])
        if isinstance(to, str):
            to = [to]

        if provider == "smtp":
            return {
                "success": True,
                "provider": "smtp",
                "message": f"Email sent to {', '.join(to)}",
                "_demo_sleep": 0.3,
            }

        return {
            "success": True,
            "provider": "resend",
            "message_id": "demo-msg-id-123",
            "status_code": 200,
            "_demo_sleep": 0.3,
        }

    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema."""
        return {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["resend", "smtp"],
                    "description": "Email provider to use",
                },
                "to": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "Recipient email address(es)",
                },
                "subject": {"type": "string", "description": "Email subject line"},
                "from_email": {"type": "string", "description": "Sender email address"},
                "body": {"type": "string", "description": "Plain text email body"},
                "html": {"type": "string", "description": "HTML email body"},
                "cc": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "CC recipient email address(es)",
                },
                "bcc": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "BCC recipient email address(es)",
                },
                "reply_to": {"type": "string", "description": "Reply-to email address"},
                "timeout": {
                    "type": "number",
                    "description": "Request timeout in seconds (default: 30)",
                    "default": 30,
                },
                "api_key": {
                    "type": "string",
                    "description": "Resend API key (required for resend provider)",
                },
                "smtp_host": {
                    "type": "string",
                    "description": "SMTP server hostname (required for smtp provider)",
                },
                "smtp_port": {
                    "type": "integer",
                    "description": "SMTP server port (default: 587)",
                    "default": 587,
                },
                "smtp_username": {
                    "type": "string",
                    "description": "SMTP authentication username",
                },
                "smtp_password": {
                    "type": "string",
                    "description": "SMTP authentication password",
                },
                "smtp_use_tls": {
                    "type": "boolean",
                    "description": "Whether to use STARTTLS (default: true)",
                    "default": True,
                },
            },
            "required": ["provider", "to", "subject", "from_email"],
        }

    def get_output_schema(self) -> Dict[str, Any]:
        """Return output result schema."""
        return {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "description": "Whether the email was sent successfully",
                },
                "provider": {
                    "type": "string",
                    "description": "Email provider used (resend or smtp)",
                },
                "message_id": {
                    "type": "string",
                    "description": "Message ID from provider (resend only)",
                },
                "status_code": {
                    "type": "integer",
                    "description": "HTTP status code (resend only)",
                },
                "message": {
                    "type": "string",
                    "description": "Success/error message",
                },
                "error": {
                    "type": "string",
                    "description": "Error details (on failure)",
                },
            },
            "required": ["success", "provider"],
        }

# Email Executor Guide

The `send_email_executor` provides email sending capabilities via two providers:
- **Resend**: Cloud email API via HTTP (recommended for simplicity)
- **SMTP**: Traditional SMTP protocol (for self-hosted or existing mail servers)

## Installation

For SMTP support, install the email extras:

```bash
pip install apflow[email]
```

Resend provider works out of the box (uses HTTP).

## Quick Start

### Using Environment Variables (Recommended)

Configure once in `.env`, then send emails with minimal input:

```bash
# .env file
RESEND_API_KEY=re_xxxxxxxxxxxxx
FROM_EMAIL=noreply@example.com
```

```bash
# Send email with just recipient, subject, and body
apflow run - <<EOF
{
  "id": "send-welcome",
  "name": "Send Welcome Email",
  "schemas": {"method": "send_email_executor"},
  "inputs": {
    "to": "user@example.com",
    "subject": "Welcome!",
    "body": "Welcome to our service!"
  }
}
EOF
```

### Explicit Configuration

Override env vars or use without them:

```bash
apflow run - <<EOF
{
  "id": "send-notification",
  "name": "Send Notification",
  "schemas": {"method": "send_email_executor"},
  "inputs": {
    "provider": "resend",
    "api_key": "re_xxxxxxxxxxxxx",
    "to": "user@example.com",
    "from_email": "noreply@example.com",
    "subject": "Order Shipped",
    "body": "Your order has been shipped!"
  }
}
EOF
```

## Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RESEND_API_KEY` | string | - | Resend API key |
| `SMTP_HOST` | string | - | SMTP server hostname |
| `SMTP_PORT` | integer | 587 | SMTP server port |
| `SMTP_USERNAME` | string | - | SMTP auth username |
| `SMTP_PASSWORD` | string | - | SMTP auth password |
| `SMTP_USE_TLS` | string | true | Use STARTTLS ("true"/"false") |
| `FROM_EMAIL` | string | - | Default sender email |

**Priority:** Input values always override environment variables.

**Auto-Detection:** If `provider` is not specified:
- `RESEND_API_KEY` set → uses `resend`
- `SMTP_HOST` set → uses `smtp`

## Input Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | string | No* | `"resend"` or `"smtp"` (auto-detected from env) |
| `to` | string/array | Yes | Recipient email(s) |
| `subject` | string | Yes | Email subject |
| `from_email` | string | No* | Sender email (falls back to `FROM_EMAIL` env) |
| `body` | string | No** | Plain text body |
| `html` | string | No** | HTML body |
| `cc` | string/array | No | CC recipients |
| `bcc` | string/array | No | BCC recipients |
| `reply_to` | string | No | Reply-to address |
| `timeout` | float | No | Request timeout in seconds (default: 30) |
| `api_key` | string | No* | Resend API key (falls back to `RESEND_API_KEY` env) |
| `smtp_host` | string | No* | SMTP hostname (falls back to `SMTP_HOST` env) |
| `smtp_port` | integer | No | SMTP port (falls back to `SMTP_PORT` env, default: 587) |
| `smtp_username` | string | No | SMTP username (falls back to `SMTP_USERNAME` env) |
| `smtp_password` | string | No | SMTP password (falls back to `SMTP_PASSWORD` env) |
| `smtp_use_tls` | boolean | No | Use STARTTLS (falls back to `SMTP_USE_TLS` env) |

\* Required unless provided via environment variable
\** At least one of `body` or `html` is required

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether email was sent successfully |
| `provider` | string | Provider used (`resend` or `smtp`) |
| `message_id` | string | Message ID (Resend only) |
| `status_code` | integer | HTTP status code (Resend only) |
| `message` | string | Success message (SMTP only) |
| `error` | string | Error details (on failure) |

## Examples

### Example 1: Simple Text Email (Resend)

```bash
# With env vars: RESEND_API_KEY, FROM_EMAIL
apflow run - <<EOF
{
  "id": "simple-email",
  "name": "Simple Email",
  "schemas": {"method": "send_email_executor"},
  "inputs": {
    "to": "user@example.com",
    "subject": "Hello",
    "body": "This is a simple text email."
  }
}
EOF
```

### Example 2: HTML Email with CC/BCC

```json
{
  "id": "html-email",
  "name": "HTML Email",
  "schemas": {"method": "send_email_executor"},
  "inputs": {
    "to": ["primary@example.com", "secondary@example.com"],
    "cc": "manager@example.com",
    "bcc": ["audit@example.com"],
    "subject": "Monthly Report",
    "html": "<h1>Monthly Report</h1><p>Please find the report attached.</p>",
    "body": "Monthly Report\n\nPlease find the report attached.",
    "reply_to": "reports@example.com"
  }
}
```

### Example 3: SMTP Configuration

```bash
# .env file for SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com
```

```json
{
  "id": "smtp-email",
  "name": "SMTP Email",
  "schemas": {"method": "send_email_executor"},
  "inputs": {
    "to": "recipient@example.com",
    "subject": "Test via SMTP",
    "body": "This email was sent via SMTP."
  }
}
```

### Example 4: Task Tree with Email Notification

```json
{
  "id": "workflow-with-email",
  "name": "Data Processing with Email Notification",
  "schemas": {"method": "aggregate_results_executor"},
  "children": [
    {
      "id": "fetch-data",
      "name": "Fetch Data",
      "schemas": {"method": "rest_executor"},
      "inputs": {
        "method": "GET",
        "url": "https://api.example.com/data"
      }
    },
    {
      "id": "notify-complete",
      "name": "Send Completion Email",
      "schemas": {"method": "send_email_executor"},
      "inputs": {
        "to": "admin@example.com",
        "subject": "Data Processing Complete",
        "body": "The data processing workflow has completed successfully."
      },
      "dependencies": ["fetch-data"]
    }
  ]
}
```

### Example 5: Python API Usage

```python
import asyncio
from apflow.extensions.email import SendEmailExecutor

async def send_email():
    executor = SendEmailExecutor()

    # With env vars configured, minimal input needed
    result = await executor.execute({
        "to": "user@example.com",
        "subject": "Hello from Python",
        "body": "This email was sent using the Python API."
    })

    if result["success"]:
        print(f"Email sent! Message ID: {result.get('message_id')}")
    else:
        print(f"Failed to send: {result.get('error')}")

asyncio.run(send_email())
```

## Provider Comparison

| Feature | Resend | SMTP |
|---------|--------|------|
| Setup Complexity | Low (just API key) | Medium (host, port, auth) |
| Dependency | None (uses HTTP) | `aiosmtplib` |
| Message ID | Yes | No |
| Deliverability | High (managed service) | Depends on server |
| Cost | Free tier available | Free (self-hosted) |
| Best For | Transactional emails | Existing mail servers |

## Troubleshooting

### "provider is required" Error

**Cause:** No provider specified and no env vars set.

**Solution:** Either:
1. Set `RESEND_API_KEY` or `SMTP_HOST` environment variable
2. Specify `provider` in task inputs

### "api_key is required for resend provider" Error

**Cause:** Using Resend without API key.

**Solution:** Either:
1. Set `RESEND_API_KEY` environment variable
2. Provide `api_key` in task inputs

### "aiosmtplib is not installed" Error

**Cause:** SMTP provider requires optional dependency.

**Solution:** Install email extras:
```bash
pip install apflow[email]
```

### SMTP Connection Timeout

**Cause:** Wrong host/port or firewall blocking.

**Solutions:**
1. Verify `SMTP_HOST` and `SMTP_PORT` are correct
2. Check firewall allows outbound connections
3. Try port 465 (SSL) or 25 (no encryption) if 587 fails
4. Increase `timeout` value in inputs

### Gmail "Less secure app" Error

**Cause:** Gmail blocks basic auth.

**Solution:** Use App Passwords:
1. Enable 2-Factor Authentication on Google Account
2. Generate App Password: Google Account → Security → App Passwords
3. Use the generated password as `SMTP_PASSWORD`

## See Also

- [Environment Variables Reference](../guides/environment-variables.md#email-extension)
- [Task Orchestration Guide](../guides/task-orchestration.md)
- [REST Executor Guide](../examples/real-world.md)

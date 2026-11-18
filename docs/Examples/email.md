# Sending an Automated Email

This example shows how to create an Elysia tool that prepares an email and, after explicit user approval, sends it using Python's standard-library SMTP client.

!!! warning "Sending email is an external action"
    Use a test mailbox first. The example defaults to preview-only mode and never sends a message unless `approved=True` is supplied. Do not put passwords in source code or logs.

## Setup

Install Elysia following the [setup guide](../setting_up.md), and configure the language model credentials for your provider. For SMTP delivery, set these environment variables in your shell or local `.env` (if your application loads it):

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=sender@example.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=sender@example.com
```

Replace the example values with your mail provider's settings. Use an application-specific credential where supported, and never commit real credentials. The SMTP server must support TLS on the configured port.

## Create the tool

An Elysia tool is an async Python function decorated with `@tool`. The model can propose the recipient, subject and body, but sending requires a separate approval flag. For safety, the tool defaults to returning a preview.

```python
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

from elysia import tool


@tool
async def send_email(to_address: str, subject: str, body: str, approved: bool = False):
    """Preview an email or send it after the user explicitly approves."""
    _, parsed_address = parseaddr(to_address)
    if not parsed_address or "@" not in parsed_address or parsed_address != to_address.strip():
        return {"status": "invalid_recipient", "to": to_address}

    preview = {"to": parsed_address, "subject": subject, "body": body}
    if not approved:
        return {"status": "preview_only", **preview}

    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        return {"status": "configuration_missing", "missing": missing, **preview}

    try:
        port = int(os.environ["SMTP_PORT"])
    except ValueError:
        return {"status": "configuration_invalid", "field": "SMTP_PORT", **preview}

    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = parsed_address
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=context) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        return {"status": "send_failed", "error": type(exc).__name__, **preview}

    return {"status": "sent", **preview}
```

## Run with Elysia

Register the tool with your Elysia tree and keep the first call in preview mode:

```python
from elysia import Tree

elysia = Tree(tools=[send_email])

response = await elysia.async_run(
    "Draft an email to teammate@example.com with subject 'Project update' and say that the report is ready for review. Preview it only; do not send it."
)
print(response)
```

A preview can look like:

```python
{
    "status": "preview_only",
    "to": "teammate@example.com",
    "subject": "Project update",
    "body": "The report is ready for review.",
}
```

## Complete the approval flow

After the user approves the exact preview, trusted application code should make the sending call. Keep and validate the complete preview instead of accepting replacement fields during approval:

```python
async def send_approved_preview(preview: dict, approved: bool):
    if not approved:
        return {"status": "approval_required", **preview}

    required_fields = {"status", "to", "subject", "body"}
    if set(preview) != required_fields or preview.get("status") != "preview_only":
        return {"status": "invalid_preview"}

    return await send_email(
        to_address=preview["to"],
        subject=preview["subject"],
        body=preview["body"],
        approved=True,
    )


approved_preview = {
    "status": "preview_only",
    "to": "teammate@example.com",
    "subject": "Project update",
    "body": "The report is ready for review.",
}

result = await send_approved_preview(approved_preview, approved=True)
print(result)
```

If SMTP accepts the message, the result has status `sent`.

## Test safely without sending mail

The most useful tests mock the SMTP client so the example can exercise both delivery and failure behavior without contacting a real server:

```python
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def smtp_env(monkeypatch):
    values = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "465",
        "SMTP_USERNAME": "sender@example.com",
        "SMTP_PASSWORD": "test-password",
        "SMTP_FROM": "sender@example.com",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


@pytest.mark.asyncio
async def test_preview_does_not_connect_to_smtp():
    with patch("smtplib.SMTP_SSL") as smtp_ssl:
        result = await send_email(
            "teammate@example.com", "Project update", "Ready for review."
        )

    assert result["status"] == "preview_only"
    smtp_ssl.assert_not_called()


@pytest.mark.asyncio
async def test_approved_preview_sends(smtp_env):
    smtp = MagicMock()
    smtp_ssl = MagicMock()
    smtp_ssl.return_value.__enter__.return_value = smtp

    preview = {
        "status": "preview_only",
        "to": "teammate@example.com",
        "subject": "Project update",
        "body": "Ready for review.",
    }

    with patch("smtplib.SMTP_SSL", smtp_ssl):
        result = await send_approved_preview(preview, approved=True)

    assert result["status"] == "sent"
    smtp.login.assert_called_once_with("sender@example.com", "test-password")
    smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_smtp_failure_is_reported(smtp_env):
    smtp_ssl = MagicMock()
    smtp_ssl.return_value.__enter__.side_effect = smtplib.SMTPException("test failure")

    with patch("smtplib.SMTP_SSL", smtp_ssl):
        result = await send_email(
            "teammate@example.com", "Test", "Failure path", approved=True
        )

    assert result["status"] == "send_failed"
    assert result["error"] == "SMTPException"
```

Also test the validation paths directly: invalid recipients should return `invalid_recipient`, missing environment settings should return `configuration_missing`, a non-integer port should return `configuration_invalid`, and a changed preview should return `invalid_preview`.

## Troubleshooting

- **`invalid_recipient`**: Pass a single plain email address such as `name@example.com`.
- **`invalid_preview`**: Pass the exact stored preview returned before approval; do not add, remove, or replace fields.
- **`approval_required`**: The application has not recorded explicit user approval yet.
- **`configuration_missing`**: Set every required `SMTP_*` environment variable before an approved send.
- **`configuration_invalid`**: Make sure `SMTP_PORT` is an integer such as `465`.
- **`send_failed`**: Check the SMTP host, port, credentials, TLS support, and provider policy.
- **`preview_only`**: Expected behavior when approval has not been provided.
- **`sent`**: The SMTP server accepted the message for delivery; check the recipient mailbox to verify receipt.

## Production considerations

Before using this pattern in production:

- restrict recipients with an allowlist or application-level authorization;
- rate-limit sends and add idempotency protection;
- keep credentials in a secret manager rather than source code;
- preserve the exact user-approved recipient, subject, and body between preview and send;
- prefer your provider's production authentication method, such as OAuth or a managed relay; and
- record useful audit metadata without logging credentials or sensitive message content.

The important boundary is that Elysia may help **prepare** the message, while trusted application code owns final approval and delivery. Avoid bulk or unsolicited sending.

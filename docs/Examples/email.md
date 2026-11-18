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

Register the tool with your Elysia tree and ask Elysia to prepare a message. The first call should remain preview-only:

```python
from elysia import Tree

elysia = Tree(tools=[send_email])

response = await elysia.async_run(
    "Draft an email to teammate@example.com with subject 'Project update' and say that the report is ready for review. Preview it only; do not send it."
)
print(response)
```

Your application should display the exact returned recipient, subject, and body to the user. Explicit approval must come from trusted UI or application state rather than being inferred from free-form model output.

## Complete the approval flow

A stronger approval flow stores the preview server-side and lets the approval action refer to it by ID. This avoids accepting replacement recipient, subject, or body fields during approval.

```python
import secrets

pending_previews: dict[str, dict] = {}


def store_preview(preview: dict) -> str:
    required_fields = {"status", "to", "subject", "body"}
    if set(preview) != required_fields or preview.get("status") != "preview_only":
        raise ValueError("Only complete preview_only responses can be stored")

    preview_id = secrets.token_urlsafe(16)
    pending_previews[preview_id] = dict(preview)
    return preview_id


async def approve_and_send(preview_id: str):
    preview = pending_previews.pop(preview_id, None)
    if preview is None:
        return {"status": "invalid_or_used_preview"}

    return await send_email(
        to_address=preview["to"],
        subject=preview["subject"],
        body=preview["body"],
        approved=True,
    )
```

For example, after displaying the exact preview to the user:

```python
preview = await send_email(
    to_address="teammate@example.com",
    subject="Project update",
    body="The report is ready for review.",
)

preview_id = store_preview(preview)

# Call only after an explicit user action, such as clicking a Send button.
result = await approve_and_send(preview_id)
print(result)
```

If SMTP accepts the message, the result has status `sent`. Because `pop()` consumes the stored preview before sending, the same approval ID cannot accidentally be reused for a second send.

## Test the example without sending real email

The approval boundary and SMTP behavior can be tested with `pytest` and `unittest.mock` without contacting a mail server:

```python
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_preview_does_not_open_smtp():
    with patch("smtplib.SMTP_SSL") as smtp_ssl:
        result = await send_email(
            "teammate@example.com",
            "Project update",
            "The report is ready for review.",
        )

    assert result["status"] == "preview_only"
    smtp_ssl.assert_not_called()


@pytest.mark.asyncio
async def test_approved_preview_sends_once(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test-password")
    monkeypatch.setenv("SMTP_FROM", "sender@example.com")

    smtp = MagicMock()
    smtp.__enter__.return_value = smtp

    with patch("smtplib.SMTP_SSL", return_value=smtp):
        preview = await send_email("teammate@example.com", "Test", "Hello")
        preview_id = store_preview(preview)
        result = await approve_and_send(preview_id)

    assert result["status"] == "sent"
    smtp.login.assert_called_once_with("sender@example.com", "test-password")
    smtp.send_message.assert_called_once()

    second_result = await approve_and_send(preview_id)
    assert second_result["status"] == "invalid_or_used_preview"
```

You can also verify the defensive paths directly:

```python
assert (await send_email("not-an-email-address", "Test", "No send", approved=True))["status"] == "invalid_recipient"

saved_password = os.environ.pop("SMTP_PASSWORD", None)
try:
    result = await send_email("teammate@example.com", "Test", "Configuration check", approved=True)
    assert result["status"] == "configuration_missing"
    assert "SMTP_PASSWORD" in result["missing"]
finally:
    if saved_password is not None:
        os.environ["SMTP_PASSWORD"] = saved_password
```

## Troubleshooting

- **`invalid_recipient`**: Pass a single plain email address such as `name@example.com`.
- **`invalid_or_used_preview`**: The approval ID does not exist or has already been consumed.
- **`configuration_missing`**: Set every required `SMTP_*` environment variable before an approved send.
- **`configuration_invalid`**: Make sure `SMTP_PORT` is an integer such as `465`.
- **`send_failed`**: Check the SMTP host, port, credentials, TLS support, and provider policy. The tool reports only the exception type so credentials and server details are not leaked into model-visible output.
- **`preview_only`**: Expected behavior before explicit approval.
- **`sent`**: The SMTP server accepted the message for delivery. Check the recipient mailbox to verify receipt.

## Production considerations

This example intentionally keeps the implementation small. Before using the pattern in a production application:

- keep pending previews in durable server-side storage rather than an in-memory dictionary;
- associate each preview with the authenticated user and expire it after a short period;
- restrict recipients with an allowlist or application-level authorization;
- rate-limit sends and add idempotency protection;
- keep credentials in a secret manager rather than source code;
- record useful audit metadata without logging credentials or sensitive message content; and
- prefer provider-supported production authentication such as OAuth or a managed SMTP relay.

The important boundary is that Elysia may help **prepare** a message, while trusted application code owns approval and delivery. Avoid bulk or unsolicited sending.

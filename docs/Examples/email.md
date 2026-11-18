# Sending an Automated Email

This example uses Elysia to **draft** an email and trusted application code to send it via SMTP **only after explicit user approval**. The model-facing tool cannot send mail.

!!! warning "Email delivery is an external action"
    Test with a mailbox you control. Never put SMTP credentials in source code, logs, or a model prompt. The examples below do not send mail unless the application explicitly invokes the approval handler.

## Setup

Follow the [setup guide](../setting_up.md) to install and configure Elysia. For delivery, configure these environment variables in your application environment (a `.env` file only works if your application loads it):

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=sender@example.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=sender@example.com
```

Use your provider's actual settings and an application-specific credential where supported. This example uses implicit TLS (`SMTP_SSL`, usually port 465), not STARTTLS.

## Drafting tool and trusted delivery code

Only `draft_email` is registered with Elysia. `approve_and_send` is **not** a model tool: call it only from a trusted, authenticated application handler after displaying the exact draft and recording an explicit Send action.

```python
import os
import re
import secrets
import smtplib
import ssl
from email.message import EmailMessage

from elysia import Tree, tool


# Demonstration-only storage. Use durable, user-scoped storage in production.
pending_previews: dict[str, dict[str, str]] = {}


def valid_address(address: str) -> bool:
    # Deliberately accepts one simple mailbox, not a display name or address list.
    return bool(re.fullmatch(r"[^\s@,;<>\r\n]+@[^\s@,;<>\r\n]+\.[^\s@,;<>\r\n]+", address))


@tool
async def draft_email(to_address: str, subject: str, body: str):
    """Prepare an email preview; this tool never sends email."""
    if not valid_address(to_address):
        return {"status": "invalid_recipient"}
    if not subject or "\r" in subject or "\n" in subject:
        return {"status": "invalid_subject"}
    return {"status": "preview_only", "to": to_address, "subject": subject, "body": body}


def store_preview(preview: dict) -> str:
    """Store the exact preview displayed to the authenticated user."""
    if (set(preview) != {"status", "to", "subject", "body"}
            or preview["status"] != "preview_only"
            or not valid_address(preview["to"])
            or not preview["subject"]
            or "\r" in preview["subject"]
            or "\n" in preview["subject"]):
        raise ValueError("Invalid preview")
    preview_id = secrets.token_urlsafe(24)
    pending_previews[preview_id] = dict(preview)
    return preview_id


async def approve_and_send(preview_id: str):
    """Trusted application handler; never expose this function as an Elysia tool."""
    # Consume once, before attempting delivery, to prevent repeat sends.
    preview = pending_previews.pop(preview_id, None)
    if preview is None:
        return {"status": "invalid_or_used_preview"}

    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        return {"status": "configuration_missing", "missing": missing}
    try:
        port = int(os.environ["SMTP_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError("out of range")
    except ValueError:
        return {"status": "configuration_invalid", "field": "SMTP_PORT"}

    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = preview["to"]
    message["Subject"] = preview["subject"]
    message.set_content(preview["body"])

    try:
        with smtplib.SMTP_SSL(
            os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=15
        ) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        # Avoid returning server diagnostics or credentials to the model.
        return {"status": "send_failed"}
    return {"status": "sent"}
```

## Run with Elysia

```python
elysia = Tree(tools=[draft_email])
response = await elysia.async_run(
    "Draft an email to teammate@example.com with subject 'Project update' "
    "and body 'The report is ready for review.' Do not send it."
)
print(response)
```

Elysia's response format depends on the configured tree and model. Extract the actual `draft_email` tool result, then display its `to`, `subject`, and `body` fields to the user. Do **not** treat arbitrary model prose as an approved preview.

For an isolated demonstration of the application approval handler:

```python
preview = await draft_email(
    "teammate@example.com", "Project update", "The report is ready for review."
)
preview_id = store_preview(preview)

# Show preview to the user here. Only an authenticated Send-button handler,
# after explicit approval of this exact preview, may execute the next line:
# result = await approve_and_send(preview_id)
# print(result)
```

The send call is intentionally commented out. When SMTP accepts a message, the handler returns `sent`; this does not guarantee inbox delivery. The preview ID is single-use, including when sending fails. A real application must tie it to the authenticated user and enforce expiration.

## Test without contacting SMTP

Save the implementation in your application module (for example `email_example.py`) and use this illustrative pytest file. Install `pytest` and `pytest-asyncio` for the async tests.

```python
from unittest.mock import MagicMock, patch

import pytest
from email_example import draft_email, store_preview, approve_and_send, pending_previews


@pytest.mark.asyncio
async def test_draft_never_sends():
    with patch("smtplib.SMTP_SSL") as smtp_ssl:
        preview = await draft_email("teammate@example.com", "Hello", "Test body")
    assert preview["status"] == "preview_only"
    smtp_ssl.assert_not_called()


@pytest.mark.asyncio
async def test_approval_sends_only_once(monkeypatch):
    pending_previews.clear()
    for key, value in {
        "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465",
        "SMTP_USERNAME": "sender@example.com", "SMTP_PASSWORD": "fake-test-secret",
        "SMTP_FROM": "sender@example.com",
    }.items():
        monkeypatch.setenv(key, value)

    preview = await draft_email("teammate@example.com", "Hello", "Test body")
    preview_id = store_preview(preview)
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    with patch("smtplib.SMTP_SSL", return_value=smtp):
        result = await approve_and_send(preview_id)
    assert result["status"] == "sent"
    smtp.login.assert_called_once_with("sender@example.com", "fake-test-secret")
    smtp.send_message.assert_called_once()
    assert (await approve_and_send(preview_id))["status"] == "invalid_or_used_preview"


@pytest.mark.asyncio
async def test_invalid_input_and_missing_configuration(monkeypatch):
    assert (await draft_email("bad address", "Hi", "Body"))["status"] == "invalid_recipient"
    assert (await draft_email("a@example.com", "bad\nsubject", "Body"))["status"] == "invalid_subject"
    preview_id = store_preview(await draft_email("a@example.com", "Hi", "Body"))
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    assert (await approve_and_send(preview_id))["status"] == "configuration_missing"
```

## Troubleshooting

- `invalid_recipient`: Supply one plain mailbox address.
- `invalid_subject`: Supply a nonempty single-line subject.
- `invalid_or_used_preview`: The approval token is missing or already consumed.
- `configuration_missing`: Set all five SMTP environment variables.
- `configuration_invalid`: Supply a valid integer SMTP port.
- `send_failed`: Check the SMTP host, TLS port, credentials, and provider policy outside the model context.
- `preview_only`: Draft created; nothing was sent.
- `sent`: The SMTP server accepted the message; confirm receipt separately.

## Production considerations

- Keep approval and SMTP delivery outside all model-accessible tools.
- Store previews durably, associate them with the authenticated user, expire them, and enforce authorization at approval time.
- Use an atomic single-use token transition, idempotency protection, rate limits, and recipient restrictions.
- Store credentials in a secret manager; prefer provider-supported OAuth or a managed relay when appropriate.
- Record audit metadata without storing secrets or sensitive message bodies.
- Avoid bulk or unsolicited email.

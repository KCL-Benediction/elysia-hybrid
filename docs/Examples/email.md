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
    """Preview an email or send it after the user explicitly approves.

    Args:
        to_address: Recipient email address.
        subject: Subject line.
        body: Plain-text email content.
        approved: True only after the user has reviewed and approved the exact message.
    """
    address = parseaddr(to_address)[1]
    if not address or address != to_address or "@" not in address:
        return {"status": "invalid_recipient"}

    preview = {"to": address, "subject": subject, "body": body}
    if not approved:
        return {"status": "preview_only", **preview}

    required = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        return {"status": "configuration_missing", "variables": missing}

    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = address
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP_SSL(
            os.environ["SMTP_HOST"],
            int(os.getenv("SMTP_PORT", "465")),
            context=ssl.create_default_context(),
            timeout=20,
        ) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError):
        return {"status": "delivery_failed", "to": address}

    return {"status": "sent", "to": address, "subject": subject}
```

The returned dictionary makes the result available to Elysia. In preview mode, it contains the proposed message; in send mode, it reports whether the SMTP server accepted the message. Acceptance does not guarantee final delivery.

## Run with Elysia

```python
from elysia import Tree

tree = Tree()
tree.add_tool(send_email)

response, objects = tree(
    "Draft a short, friendly email to teammate@example.com "
    "with subject 'Project update' saying that the draft is ready for review. "
    "Preview it only; do not send."
)
print(response)
```

A preview result will look similar to this:

```python
{
    "status": "preview_only",
    "to": "teammate@example.com",
    "subject": "Project update",
    "body": "Hi, the draft is ready for your review. Thanks!",
}
```

Review the recipient, subject, and body before any actual send. For a real application, keep approval outside the language model: display the preview to the user, capture an explicit confirmation, and call the function from trusted application code with `approved=True` and the **exact approved fields**. Do not allow a model-generated tool argument alone to count as user approval.

```python
# Example only: run after your UI has captured explicit user approval.
result = await send_email(
    to_address="teammate@example.com",
    subject="Project update",
    body="Hi, the draft is ready for your review. Thanks!",
    approved=True,
)
print(result)
```

If the SMTP server accepts the message, the result is:

```python
{
    "status": "sent",
    "to": "teammate@example.com",
    "subject": "Project update",
}
```

## Try the failure paths

Before relying on actual SMTP delivery, you can verify the example's safe behavior without sending anything:

```python
# Invalid recipient: rejected before any SMTP connection is attempted.
result = await send_email(
    to_address="not-an-email-address",
    subject="Test",
    body="This should not be sent.",
    approved=True,
)
assert result["status"] == "invalid_recipient"

# No approval: always returns a preview and does not connect to SMTP.
result = await send_email(
    to_address="teammate@example.com",
    subject="Test",
    body="Preview only.",
)
assert result["status"] == "preview_only"

# Missing configuration: reports exactly which settings are absent.
# Temporarily unset one required SMTP variable before running this check.
# result = await send_email(
#     to_address="teammate@example.com",
#     subject="Test",
#     body="Configuration check.",
#     approved=True,
# )
# assert result["status"] == "configuration_missing"
```

These checks make it easy to confirm the approval boundary before you configure real credentials.

## Troubleshooting

- **`invalid_recipient`**: Pass a single plain email address such as `name@example.com`.
- **`configuration_missing`**: Set all required SMTP environment variables.
- **`delivery_failed`**: Check the server hostname, TLS port, credentials, and provider permissions. The tool deliberately does not return sensitive exception details.
- **`preview_only`**: Expected behavior when approval has not been provided.
- **`sent`**: The SMTP server accepted the message for delivery; check the recipient mailbox to verify receipt.

## Production considerations

This example intentionally keeps the implementation small. Before using the pattern in a production application:

- restrict recipients with an allowlist or application-level authorization;
- rate-limit sends and prevent accidental loops or duplicate deliveries;
- keep credentials in a secret manager rather than source code;
- record useful audit metadata without logging credentials or sensitive message content;
- preserve the exact user-approved recipient, subject, and body between preview and send; and
- handle provider-specific requirements such as application passwords, OAuth, or SMTP relay policies.

The important boundary is that Elysia may help **prepare** the message, while trusted application code owns the final approval and delivery step. Avoid bulk or unsolicited sending.

## Next steps

Once the preview flow works locally, try these extensions:

1. Add a small application or UI layer that stores the exact preview and requires a user confirmation before calling `send_email(..., approved=True)`.
2. Add tests that mock `smtplib.SMTP_SSL` so preview, configuration, successful-send, and failure paths can be verified without contacting a real mail server.
3. Replace password-based SMTP authentication with your provider's preferred production authentication method, such as OAuth or a managed relay.
4. Add application-level recipient authorization and rate limits before exposing the tool to end users.

This keeps the example useful as a starting point while preserving a clear rule: the model can draft an email, but only trusted application code should authorize delivery.

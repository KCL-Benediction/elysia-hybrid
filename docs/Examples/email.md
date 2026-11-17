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
        approved: True only after the user has reviewed and approved this exact message.
    """
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

The returned dictionary is deliberate: Elysia can show the preview to the user before your application allows a second, approved call.

## Run with Elysia

Register the tool with your Elysia tree, then ask Elysia to prepare a message. Keep the first call in preview mode:

```python
from elysia import Tree

elysia = Tree(tools=[send_email])

response = await elysia.async_run(
    "Draft an email to teammate@example.com with subject 'Project update' and say that the report is ready for review. Preview it only; do not send it."
)
print(response)
```

Your application should display the returned recipient, subject and body to the user. Do not automatically turn a model statement such as "looks good" into `approved=True`; the approval should come from an explicit UI or application action.

For example, the preview returned by the tool can look like this:

```python
{
    "status": "preview_only",
    "to": "teammate@example.com",
    "subject": "Project update",
    "body": "The report is ready for review.",
}
```

## Complete the approval flow

After the user approves the exact preview, trusted application code should make the sending call. Keep the complete preview returned by `send_email`, including its status, and validate it before extracting the approved fields. This prevents replacement fields from being introduced between preview and send:

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


# Store the exact preview returned by send_email and shown to the user.
approved_preview = {
    "status": "preview_only",
    "to": "teammate@example.com",
    "subject": "Project update",
    "body": "The report is ready for review.",
}

result = await send_approved_preview(approved_preview, approved=True)
print(result)
```

If SMTP accepts the message, the result is:

```python
{
    "status": "sent",
    "to": "teammate@example.com",
    "subject": "Project update",
    "body": "The report is ready for review.",
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

# Application approval is also required by the helper.
result = await send_approved_preview(
    {
        "status": "preview_only",
        "to": "teammate@example.com",
        "subject": "Test",
        "body": "Still preview only.",
    },
    approved=False,
)
assert result["status"] == "approval_required"

# A modified or malformed preview is rejected before any SMTP connection.
result = await send_approved_preview(
    {
        "status": "preview_only",
        "to": "teammate@example.com",
        "subject": "Test",
        "body": "Unexpected replacement body.",
        "extra": "not part of the approved preview",
    },
    approved=True,
)
assert result["status"] == "invalid_preview"

# Missing configuration: reports exactly which settings are absent without connecting.
saved_password = os.environ.pop("SMTP_PASSWORD", None)
try:
    result = await send_email(
        to_address="teammate@example.com",
        subject="Test",
        body="Configuration check.",
        approved=True,
    )
    assert result["status"] == "configuration_missing"
    assert "SMTP_PASSWORD" in result["missing"]
finally:
    if saved_password is not None:
        os.environ["SMTP_PASSWORD"] = saved_password
```

These checks make it easy to confirm the approval boundary before you configure real credentials.

## Troubleshooting

- **`invalid_recipient`**: Pass a single plain email address such as `name@example.com`.
- **`invalid_preview`**: Pass the exact stored preview returned before approval; do not add, remove, or replace fields.
- **`approval_required`**: The application has not recorded explicit user approval yet.
- **`configuration_missing`**: Set every required `SMTP_*` environment variable before an approved send.
- **`configuration_invalid`**: Make sure `SMTP_PORT` is an integer such as `465`.
- **`send_failed`**: Check the SMTP host, port, credentials, TLS support, and provider policy. The tool reports only the exception type so credentials and server details are not leaked into model-visible output.
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

1. Store previews server-side and expose an approval endpoint that accepts only the preview ID, not replacement message fields.
2. Add tests that mock `smtplib.SMTP_SSL` so preview, approval, configuration, successful-send, and failure paths can be verified without contacting a real mail server.
3. Replace password-based SMTP authentication with your provider's preferred production authentication method, such as OAuth or a managed relay.
4. Add application-level recipient authorization, rate limits, and idempotency protection before exposing the tool to end users.

This keeps the example useful as a starting point while preserving a clear rule: the model can draft an email, but only trusted application code should authorize delivery.

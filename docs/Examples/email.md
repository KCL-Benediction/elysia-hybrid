# Sending an Automated Email

This example uses an Elysia tool to **preview** an email, then sends it through SMTP only after a trusted application handler records explicit user approval. The LLM-accessible tool cannot send messages.

!!! warning "External action"
    Use a test mailbox. Never commit credentials, and never let an LLM tool call decide whether approval was granted.

## Setup

Install Elysia using the [setup guide](../setting_up.md) and configure your LLM provider. For approved delivery, configure these environment variables in your process (or a local `.env` if your application explicitly loads it):

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=sender@example.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=sender@example.com
```

Replace the placeholders with your provider's settings. This example uses implicit TLS (`SMTP_SSL`), typically on port 465, and does not support STARTTLS on port 587. Use an app-specific password where supported.

## Run the example

The runnable source is [`email_example.py`](email_example.py):

```bash
python docs/Examples/email_example.py
```

It registers `send_email` as an Elysia tool and asks Elysia to prepare an email. The tool always returns a preview and never opens an SMTP connection:

```python
{
    "status": "preview_only",
    "to": "teammate@example.com",
    "subject": "Project update",
    "body": "The report is ready for review.",
}
```

The LLM response may include other presentation text. Your application should retain the structured preview returned by the tool rather than reconstructing an email from model prose.

## Complete the approval flow

Your **trusted application** must display the recipient, subject, and body to the user, retain that exact preview, and capture an explicit confirmation. Only then call the non-tool helper:

```python
from docs.Examples.email_example import send_approved_preview

# `stored_preview` is the exact preview saved by your application.
# `user_confirmed` comes from your trusted UI, not from model output.
result = await send_approved_preview(stored_preview, approved=user_confirmed)
print(result["status"])
```

This is an illustrative snippet for an existing async application, not a standalone script. Do not pass arbitrary model-provided dictionaries to the approval handler. A production system should bind the approved preview to a user/session and prevent replay or modification between preview and delivery.

Possible statuses include `preview_only`, `approval_required`, `invalid_preview`, `invalid_recipient`, `invalid_subject`, `invalid_body`, `configuration_missing`, `configuration_invalid`, `send_failed`, and `sent`. `sent` means the SMTP server accepted the message, not that the recipient read it.

## Test without sending email

The offline tests mock SMTP and cover preview-only behavior, missing approval, successful approved delivery, invalid previews, configuration errors, and SMTP failures:

```bash
pytest tests/test_email_example.py -q
```

## Production considerations

- Restrict recipients and authenticate/authorize the approver.
- Persist an immutable approved preview and add idempotency and rate limits.
- Store SMTP credentials in a secret manager; never log passwords or sensitive message bodies.
- Prefer OAuth or a managed relay when required by your provider.
- Audit approval and delivery metadata without recording sensitive content.
- Avoid bulk or unsolicited messages.

**Security boundary:** Elysia drafts; trusted application code approves and delivers.

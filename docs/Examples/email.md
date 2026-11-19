# Sending an Automated Email

This example demonstrates a safe email workflow using Elysia: an LLM can **draft and preview** a message, while a separate, trusted application handler sends the approved preview over SMTP.

!!! warning "Sending email is an external action"
    The model-accessible tool never sends email. Do not expose the approval handler as a tool, accept approval from an LLM, or send without a human reviewing the exact recipient, subject and body. Use a test mailbox first.

## Setup

Install Elysia using the [setup guide](../setting_up.md). Set up your model provider, then configure the SMTP environment for optional delivery:

```bash
export SMTP_HOST=smtp.example.com
export SMTP_PORT=465
export SMTP_USERNAME=sender@example.com
export SMTP_PASSWORD=your-app-password
export SMTP_FROM=sender@example.com
```

These are placeholders, not working credentials. Use your provider's implicit-TLS SMTP endpoint (commonly port 465) and an application-specific credential where supported. Never commit credentials. A `.env` file is only effective if your application loads it into the process environment.

## Run the preview

The runnable companion is [`email_example.py`](email_example.py). It registers **only** `preview_email` with Elysia:

```python
from elysia import Tree
from email_example import preview_email

async def draft():
    tree = Tree(tools=[preview_email])
    return await tree.async_run(
        "Draft an email to teammate@example.com with subject 'Project update' "
        "saying the report is ready for review. Preview only; do not send."
    )
```

From the repository root, after installing dependencies and configuring your model provider:

```bash
python docs/Examples/email_example.py
```

The preview tool returns a structured result such as:

```python
{
    "status": "preview_only",
    "to": "teammate@example.com",
    "subject": "Project update",
    "body": "The report is ready for review.",
}
```

The Elysia run response may wrap the tool result. Extract the structured preview in your application and store it server-side. Do not treat arbitrary model text as a trusted preview.

## Approve and send

Display the stored preview to the user. Once the user explicitly approves **that exact preview**, the trusted application approval handler can call:

```python
from email_example import send_approved_preview

# `stored_preview` must be the preview saved by trusted application code.
# `user_approved` must come from the application's authenticated UI.
result = await send_approved_preview(stored_preview, approved=user_approved)
print(result)
```

Do not register `send_approved_preview` as an Elysia tool. The example does not implement a UI or persistent approval store: those are application responsibilities. In production, bind approval to the authenticated user and an immutable preview identifier, and consume it once to prevent replay. The example's boolean alone is not an authorization mechanism.

The handler validates the preview and configuration, connects using SMTP over TLS, and reports `sent` if the SMTP server accepts the message. This does not guarantee inbox delivery.

## Test without sending mail

Run the accompanying mocked tests:

```bash
pytest tests/no_reqs/test_email_example.py -q
```

Tests cover preview-only behavior, approval rejection, invalid input, configuration errors, successful mocked SMTP delivery and SMTP failures. No real email is sent by these tests.

## Troubleshooting

| Status | Meaning |
| --- | --- |
| `preview_only` | Draft returned; no SMTP connection attempted. |
| `invalid_recipient` / `invalid_message` | Recipient or subject/body failed validation. |
| `approval_required` | Trusted approval has not been recorded. |
| `invalid_preview` | Stored preview has unexpected or invalid fields. |
| `configuration_missing` | One or more `SMTP_*` settings are absent. |
| `configuration_invalid` | Port or sender address is invalid. |
| `send_failed` | SMTP connection, authentication or delivery request failed. |
| `sent` | SMTP server accepted the message, not necessarily delivered. |

## Production considerations

Use recipient authorization or an allowlist, rate limits, idempotency, audit metadata without sensitive message bodies, and a secret manager for credentials. Support your provider's recommended authentication method, such as OAuth or a managed relay. Never use this example for bulk or unsolicited sending.

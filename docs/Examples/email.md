# Sending an Automated Email

This example demonstrates **preview first, send only after explicit approval**. The Elysia agent can draft an email but cannot invoke SMTP delivery. See the runnable [email_example.py](email_example.py) and its [tests](../../tests/test_email_example.py).

!!! warning "Sending email is an external action"
    Never register the sending function as an Elysia tool. The application must authenticate the approving user and verify the exact preview they approved. Use a test mailbox before enabling real delivery.

## Setup

Install Elysia as described in the [setup guide](../setting_up.md), including your LLM provider credentials. To **send** approved messages, configure these environment variables in the application process:

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=sender@example.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=sender@example.com
```

Replace placeholders with your provider's SMTP-over-TLS settings. Keep credentials out of source control and logs. No SMTP configuration is needed for preview-only use.

## Preview an email

The model sees only `preview_email`, which validates the recipient and subject and returns a draft without connecting to SMTP:

```python
from elysia import Tree
from docs.Examples.email_example import preview_email

tree = Tree(tools=[preview_email])
response = await tree.async_run(
    "Draft an email to teammate@example.com with subject 'Project update' "
    "saying the report is ready for review. Preview only; do not send."
)
print(response)
```

Run the complete example from the repository root:

```bash
python docs/Examples/email_example.py
```

A tool preview has the form:

```python
{
    "status": "preview_only",
    "to": "teammate@example.com",
    "subject": "Project update",
    "body": "The report is ready for review."
}
```

The tree response may wrap the tool result; your application must extract and store the exact preview before displaying it for approval.

## Deliver only after trusted approval

`send_approved_preview` is **not** decorated with `@tool` and must never be added to the tree. A trusted UI or server handler should:

1. Authenticate the user and store the preview associated with that user/session.
2. Display the exact recipient, subject, and body for review.
3. Collect explicit approval of that exact stored preview, without accepting replacement message fields in the approval request.
4. Call the sending function from trusted code:

```python
from docs.Examples.email_example import send_approved_preview

# Only in a trusted handler after verifying the authenticated user's approval:
result = await send_approved_preview(stored_preview, approved=True)
print(result)
```

The function validates the preview and SMTP configuration, connects using TLS, and returns `sent` when the SMTP server accepts the message. `sent` does not guarantee final mailbox delivery. This sample does not implement the UI, authenticated approval storage, or replay protection; those belong to the hosting application.

## Test without sending email

The tests mock SMTP and cover preview-only behavior, recipient and header validation, approval requirements, configuration errors, successful delivery, and SMTP failures:

```bash
pytest -q tests/test_email_example.py
```

No real email is sent by these tests.

## Result statuses

| Status | Meaning |
| --- | --- |
| `preview_only` | Draft prepared; no message sent. |
| `invalid_recipient` | Recipient is not a single plain address. |
| `invalid_subject` / `invalid_body` | Draft content is invalid. |
| `approval_required` | No trusted approval was supplied. |
| `invalid_preview` | Stored preview shape or content is invalid. |
| `configuration_missing` | Required SMTP setting is absent. |
| `configuration_invalid` | SMTP port or sender address is invalid. |
| `send_failed` | SMTP connection, authentication, or delivery call failed. |
| `sent` | SMTP server accepted the message. |

## Production considerations

Restrict allowed recipients, rate-limit and deduplicate sends, secure credentials, record audit metadata without sensitive content, and consider OAuth or a managed email provider. Ensure the preview cannot be swapped or replayed between approval and delivery. Elysia prepares the draft; **trusted application code controls delivery**.

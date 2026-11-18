"""Runnable companion to docs/Examples/email.md.

Configure SMTP_* environment variables only when sending real mail.
Approval must come from trusted application code, never from an LLM tool call.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

from elysia import Tree, tool


@tool
async def send_email(to_address: str, subject: str, body: str, approved: bool = False):
    """Preview a single-recipient email; send only with explicit approval."""
    _, recipient = parseaddr(to_address)
    if not recipient or "@" not in recipient or recipient != to_address.strip():
        return {"status": "invalid_recipient", "to": to_address}

    preview = {"to": recipient, "subject": subject, "body": body}
    if not approved:
        return {"status": "preview_only", **preview}

    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        return {"status": "configuration_missing", "missing": missing, **preview}
    try:
        port = int(os.environ["SMTP_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError("invalid port")
    except ValueError:
        return {"status": "configuration_invalid", "field": "SMTP_PORT", **preview}

    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP_SSL(
            os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=15
        ) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        return {"status": "send_failed", "error": type(exc).__name__, **preview}
    return {"status": "sent", **preview}


async def send_approved_preview(preview: dict, approved: bool):
    """Call only from a trusted approval handler using its stored preview."""
    if not approved:
        return {"status": "approval_required"}
    if not isinstance(preview, dict) or set(preview) != {"status", "to", "subject", "body"} or preview.get("status") != "preview_only":
        return {"status": "invalid_preview"}
    return await send_email(
        to_address=preview["to"], subject=preview["subject"],
        body=preview["body"], approved=True,
    )


async def main():
    tree = Tree(tools=[send_email])
    response = await tree.async_run(
        "Draft an email to teammate@example.com with subject 'Project update' "
        "saying the report is ready for review. Preview only; do not send."
    )
    print(response)
    # Do not call send_approved_preview here: approval belongs in a trusted UI.


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

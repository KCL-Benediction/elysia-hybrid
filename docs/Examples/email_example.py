"""Runnable companion to docs/Examples/email.md.

The model can only preview mail. Sending is available exclusively to trusted
application code after the user approves the exact stored preview.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

from elysia import Tree, tool


def _valid_address(address: str) -> bool:
    if not isinstance(address, str) or any(c in address for c in "\r\n"):
        return False
    display, parsed = parseaddr(address)
    return not display and parsed == address and address.count("@") == 1 and all(address.split("@"))


@tool
async def preview_email(to_address: str, subject: str, body: str):
    """Prepare an email for human review; never send it."""
    if not _valid_address(to_address):
        return {"status": "invalid_recipient", "to": to_address}
    if not isinstance(subject, str) or any(c in subject for c in "\r\n"):
        return {"status": "invalid_subject"}
    if not isinstance(body, str):
        return {"status": "invalid_body"}
    return {"status": "preview_only", "to": to_address, "subject": subject, "body": body}


async def send_approved_preview(preview: dict, approved: bool = False):
    """Call only from a trusted UI handler with its stored, user-approved preview.

    Never register this function as an Elysia tool or accept approval from model output.
    """
    if not approved:
        return {"status": "approval_required"}
    if not isinstance(preview, dict) or set(preview) != {"status", "to", "subject", "body"} or preview.get("status") != "preview_only":
        return {"status": "invalid_preview"}
    recipient, subject, body = preview["to"], preview["subject"], preview["body"]
    if not _valid_address(recipient) or not isinstance(subject, str) or any(c in subject for c in "\r\n") or not isinstance(body, str):
        return {"status": "invalid_preview"}

    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        return {"status": "configuration_missing", "missing": missing}
    try:
        port = int(os.environ["SMTP_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError("port out of range")
    except ValueError:
        return {"status": "configuration_invalid", "field": "SMTP_PORT"}
    if not _valid_address(os.environ["SMTP_FROM"]):
        return {"status": "configuration_invalid", "field": "SMTP_FROM"}

    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=15) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        return {"status": "send_failed", "error": type(exc).__name__}
    return {"status": "sent", "to": recipient, "subject": subject}


async def main():
    tree = Tree(tools=[preview_email])
    response = await tree.async_run(
        "Draft an email to teammate@example.com with subject 'Project update' "
        "saying the report is ready for review. Preview only; do not send."
    )
    print(response)
    # A trusted UI must capture and store the exact preview, display it to the
    # user, record explicit approval, then call send_approved_preview itself.


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

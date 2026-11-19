"""Email preview and explicitly approved SMTP delivery example.

Run with ``python docs/Examples/email_example.py`` after configuring Elysia.
Only trusted application code should invoke ``send_approved_preview``.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

from elysia import Tree, tool


def _valid_address(address: str) -> bool:
    if not isinstance(address, str) or not address or "\r" in address or "\n" in address:
        return False
    display_name, parsed = parseaddr(address)
    return not display_name and parsed == address and parsed.count("@") == 1


@tool
async def preview_email(to_address: str, subject: str, body: str):
    """Prepare an email for review. This model-accessible tool never sends mail."""
    if not _valid_address(to_address):
        return {"status": "invalid_recipient", "to": to_address}
    if not isinstance(subject, str) or "\r" in subject or "\n" in subject:
        return {"status": "invalid_subject"}
    if not isinstance(body, str):
        return {"status": "invalid_body"}
    return {"status": "preview_only", "to": to_address, "subject": subject, "body": body}


async def send_approved_preview(preview: dict, approved: bool = False):
    """Send a stored, user-approved preview from a trusted UI or handler only.

    Never register this function as an Elysia tool or accept approval from the model.
    """
    if not approved:
        return {"status": "approval_required"}
    if not isinstance(preview, dict) or set(preview) != {"status", "to", "subject", "body"} or preview.get("status") != "preview_only":
        return {"status": "invalid_preview"}
    to_address, subject, body = preview["to"], preview["subject"], preview["body"]
    if not _valid_address(to_address) or not isinstance(subject, str) or "\r" in subject or "\n" in subject or not isinstance(body, str):
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
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=15) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        return {"status": "send_failed", "error": type(exc).__name__}
    return {"status": "sent", "to": to_address, "subject": subject}


async def main():
    tree = Tree(tools=[preview_email])
    response = await tree.async_run(
        "Draft an email to teammate@example.com with subject 'Project update' "
        "saying the report is ready for review. Preview only; do not send."
    )
    print(response)
    # A trusted UI must store the exact preview, display it, and collect approval.
    # Only then should it call send_approved_preview(stored_preview, approved=True).


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

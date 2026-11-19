"""Email preview and explicitly approved SMTP delivery example.

Run with ``python docs/Examples/email_example.py`` after configuring Elysia.
Only trusted application code should call ``send_approved_preview``.
"""

import os
import re
import smtplib
import ssl
from email.message import EmailMessage

from elysia import Tree, tool


_EMAIL = re.compile(r"^[^\s@<>;,\r\n]+@[^\s@<>;,\r\n]+\.[^\s@<>;,\r\n]+$")


def valid_address(address: str) -> bool:
    return isinstance(address, str) and bool(_EMAIL.fullmatch(address))


def valid_header(value: str) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\r" not in value and "\n" not in value


@tool
async def preview_email(to_address: str, subject: str, body: str):
    """Prepare an email preview; this LLM-accessible tool never sends mail."""
    if not valid_address(to_address):
        return {"status": "invalid_recipient", "to": to_address}
    if not valid_header(subject) or not isinstance(body, str):
        return {"status": "invalid_message"}
    return {"status": "preview_only", "to": to_address, "subject": subject, "body": body}


async def send_approved_preview(preview: dict, approved: bool = False):
    """Send a stored preview only when a trusted UI has recorded approval.

    Do not expose this function as an Elysia tool or allow model-supplied approval.
    """
    if not approved:
        return {"status": "approval_required"}
    if (
        not isinstance(preview, dict)
        or set(preview) != {"status", "to", "subject", "body"}
        or preview.get("status") != "preview_only"
        or not valid_address(preview["to"])
        or not valid_header(preview["subject"])
        or not isinstance(preview["body"], str)
    ):
        return {"status": "invalid_preview"}

    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        return {"status": "configuration_missing", "missing": missing}
    try:
        port = int(os.environ["SMTP_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError("out of range")
    except ValueError:
        return {"status": "configuration_invalid", "field": "SMTP_PORT"}
    if not valid_address(os.environ["SMTP_FROM"]):
        return {"status": "configuration_invalid", "field": "SMTP_FROM"}

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
    except (OSError, smtplib.SMTPException) as exc:
        return {"status": "send_failed", "error": type(exc).__name__}
    return {"status": "sent"}


async def main():
    tree = Tree(tools=[preview_email])
    response = await tree.async_run(
        "Draft an email to teammate@example.com with subject 'Project update' "
        "saying the report is ready for review. Preview only; do not send."
    )
    print(response)
    # In a real app, store the exact preview and display it in a trusted UI.
    # Only that UI's approval handler should call send_approved_preview.


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

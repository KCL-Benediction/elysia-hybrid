"""Safe email preview and explicitly approved SMTP delivery example.

Run with: python docs/Examples/email_example.py
Configure SMTP_* only for actual delivery. Never expose send_approved_preview
as an LLM tool: invoke it from a trusted application approval handler.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

from elysia import Tree, tool


def _valid_address(value: str) -> bool:
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    name, address = parseaddr(value)
    return not name and address == value and address.count("@") == 1 and all(address.split("@")) and not any(c in value for c in "\r\n,;")


@tool
async def preview_email(to_address: str, subject: str, body: str):
    """Prepare a single-recipient email without sending it."""
    if not _valid_address(to_address):
        return {"status": "invalid_recipient", "to": to_address}
    if not isinstance(subject, str) or not subject.strip() or any(c in subject for c in "\r\n"):
        return {"status": "invalid_subject"}
    if not isinstance(body, str):
        return {"status": "invalid_body"}
    return {"status": "preview_only", "to": to_address, "subject": subject, "body": body}


async def send_approved_preview(preview: dict, approved: bool = False):
    """Trusted application entry point, never register this as an LLM tool.

    The application must authenticate the approving user and verify that the
    exact preview was shown to that user before invoking this function.
    """
    if not approved:
        return {"status": "approval_required"}
    if not isinstance(preview, dict) or set(preview) != {"status", "to", "subject", "body"} or preview.get("status") != "preview_only":
        return {"status": "invalid_preview"}
    validated = await preview_email(preview["to"], preview["subject"], preview["body"])
    if validated != preview:
        return {"status": "invalid_preview"}

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
    if not _valid_address(os.environ["SMTP_FROM"]):
        return {"status": "configuration_invalid", "field": "SMTP_FROM", **preview}

    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = preview["to"]
    message["Subject"] = preview["subject"]
    message.set_content(preview["body"])
    try:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=15) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        return {"status": "send_failed", "error": type(exc).__name__, **preview}
    return {"status": "sent", **preview}


async def main():
    tree = Tree(tools=[preview_email])
    response = await tree.async_run(
        "Draft an email to teammate@example.com with subject 'Project update' "
        "saying the report is ready for review. Preview only; do not send."
    )
    print(response)
    # A trusted UI must collect approval of the exact preview before sending.


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

"""Email preview and explicitly approved SMTP delivery example.

Run with: python docs/Examples/email_example.py
Only trusted application code should invoke send_approved_preview after user approval.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

from elysia import Tree, tool


def valid_address(address: str) -> bool:
    if not isinstance(address, str) or "\n" in address or "\r" in address:
        return False
    name, parsed = parseaddr(address)
    return not name and parsed == address and parsed.count("@") == 1 and all(parsed.split("@"))


@tool
async def send_email(to_address: str, subject: str, body: str):
    """Prepare an email preview. This model-callable tool NEVER sends mail."""
    if not valid_address(to_address):
        return {"status": "invalid_recipient", "to": to_address}
    if not isinstance(subject, str) or "\n" in subject or "\r" in subject:
        return {"status": "invalid_subject"}
    if not isinstance(body, str):
        return {"status": "invalid_body"}
    return {"status": "preview_only", "to": to_address, "subject": subject, "body": body}


async def send_approved_preview(preview: dict, approved: bool = False):
    """Trusted application entry point; pass a stored, user-approved preview."""
    if not approved:
        return {"status": "approval_required"}
    if not isinstance(preview, dict) or set(preview) != {"status", "to", "subject", "body"} or preview.get("status") != "preview_only":
        return {"status": "invalid_preview"}
    expected = await send_email(preview["to"], preview["subject"], preview["body"])
    if expected != preview:
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
    if not valid_address(os.environ["SMTP_FROM"]):
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
    return {**preview, "status": "sent"}


async def main():
    tree = Tree(tools=[send_email])
    response = await tree.async_run(
        "Draft an email to teammate@example.com with subject 'Project update' "
        "saying the report is ready for review. Preview only; do not send."
    )
    print(response)
    # The application must store the exact preview and obtain explicit approval
    # in its own UI before calling send_approved_preview(preview, approved=True).


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

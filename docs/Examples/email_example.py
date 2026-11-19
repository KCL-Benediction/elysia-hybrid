"""Runnable companion to docs/Examples/email.md.

The model can only preview mail. A trusted application handler must approve
and deliver a stored preview; never expose the delivery function as an LLM tool.
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
    name, parsed = parseaddr(address)
    return not name and parsed == address.strip() and parsed.count("@") == 1


@tool
async def preview_email(to_address: str, subject: str, body: str):
    """Prepare an email without connecting to SMTP or accepting approval."""
    if not _valid_address(to_address):
        return {"status": "invalid_recipient", "to": to_address}
    if not isinstance(subject, str) or "\r" in subject or "\n" in subject:
        return {"status": "invalid_subject"}
    if not isinstance(body, str):
        return {"status": "invalid_body"}
    return {"status": "preview_only", "to": to_address.strip(), "subject": subject, "body": body}


async def send_email(to_address: str, subject: str, body: str, approved: bool = False):
    """Trusted application API, deliberately NOT registered as an Elysia tool."""
    preview = await preview_email(to_address, subject, body)
    if preview["status"] != "preview_only":
        return preview
    if not approved:
        return preview

    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        return {"status": "configuration_missing", "missing": missing, **{k: preview[k] for k in ("to", "subject", "body")}}
    try:
        port = int(os.environ["SMTP_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError("invalid port")
    except ValueError:
        return {"status": "configuration_invalid", "field": "SMTP_PORT", **{k: preview[k] for k in ("to", "subject", "body")}}

    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = preview["to"]
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP_SSL(
            os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=15
        ) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        return {"status": "send_failed", "error": type(exc).__name__, **{k: preview[k] for k in ("to", "subject", "body")}}
    return {"status": "sent", **{k: preview[k] for k in ("to", "subject", "body")}}


async def send_approved_preview(preview: dict, approved: bool):
    """Only call from a trusted approval handler using its stored preview."""
    if not approved:
        return {"status": "approval_required"}
    if (
        not isinstance(preview, dict)
        or set(preview) != {"status", "to", "subject", "body"}
        or preview.get("status") != "preview_only"
    ):
        return {"status": "invalid_preview"}
    return await send_email(preview["to"], preview["subject"], preview["body"], approved=True)


async def main():
    tree = Tree(tools=[preview_email])
    response = await tree.async_run(
        "Draft an email to teammate@example.com with subject 'Project update' "
        "saying the report is ready for review. Preview only; do not send."
    )
    print(response)
    # Only trusted UI code may invoke send_approved_preview with a stored preview.


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

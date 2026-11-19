"""No network connections are made by these tests."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SPEC = importlib.util.spec_from_file_location(
    "email_example", Path(__file__).resolve().parents[1] / "docs/Examples/email_example.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


@pytest.fixture
def smtp_env(monkeypatch):
    for key, value in {
        "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465",
        "SMTP_USERNAME": "sender@example.com", "SMTP_PASSWORD": "test-password",
        "SMTP_FROM": "sender@example.com",
    }.items():
        monkeypatch.setenv(key, value)


@pytest.mark.asyncio
async def test_preview_never_sends():
    with patch("smtplib.SMTP_SSL") as smtp:
        preview = await module.preview_email("to@example.com", "Update", "Ready")
    assert preview == {"status": "preview_only", "to": "to@example.com", "subject": "Update", "body": "Ready"}
    smtp.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("recipient", ["bad", "A <a@example.com>", "a@example.com,b@example.com", "a@example.com\nBcc: x@y.com"])
async def test_invalid_recipients(recipient):
    result = await module.preview_email(recipient, "Hi", "Body")
    assert result["status"] == "invalid_recipient"


@pytest.mark.asyncio
async def test_subject_header_injection_rejected():
    result = await module.preview_email("to@example.com", "Hi\nBcc: x@y.com", "Body")
    assert result["status"] == "invalid_subject"


@pytest.mark.asyncio
async def test_approval_required_and_invalid_preview():
    preview = await module.preview_email("to@example.com", "Update", "Ready")
    assert (await module.send_approved_preview(preview))["status"] == "approval_required"
    assert (await module.send_approved_preview({**preview, "extra": True}, True))["status"] == "invalid_preview"


@pytest.mark.asyncio
async def test_approved_delivery(smtp_env):
    preview = await module.preview_email("to@example.com", "Update", "Ready")
    with patch("smtplib.SMTP_SSL") as smtp_ssl:
        result = await module.send_approved_preview(preview, True)
    assert result["status"] == "sent"
    smtp = smtp_ssl.return_value.__enter__.return_value
    smtp.login.assert_called_once_with("sender@example.com", "test-password")
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "to@example.com"
    assert message["Subject"] == "Update"


@pytest.mark.asyncio
async def test_missing_config(monkeypatch):
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)
    preview = await module.preview_email("to@example.com", "Update", "Ready")
    assert (await module.send_approved_preview(preview, True))["status"] == "configuration_missing"


@pytest.mark.asyncio
async def test_invalid_port(smtp_env, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "99999")
    preview = await module.preview_email("to@example.com", "Update", "Ready")
    assert (await module.send_approved_preview(preview, True))["status"] == "configuration_invalid"


@pytest.mark.asyncio
async def test_smtp_failure(smtp_env):
    import smtplib
    preview = await module.preview_email("to@example.com", "Update", "Ready")
    with patch("smtplib.SMTP_SSL", side_effect=smtplib.SMTPException("offline")):
        result = await module.send_approved_preview(preview, True)
    assert result["status"] == "send_failed"
    assert result["error"] == "SMTPException"

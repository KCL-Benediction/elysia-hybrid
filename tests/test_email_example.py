"""No real SMTP connections are made by these tests."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


spec = importlib.util.spec_from_file_location(
    "email_example", Path(__file__).resolve().parents[1] / "docs/Examples/email_example.py"
)
email_example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(email_example)


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
        result = await email_example.preview_email("teammate@example.com", "Update", "Ready")
    assert result["status"] == "preview_only"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_approval_required():
    preview = {"status": "preview_only", "to": "teammate@example.com", "subject": "Update", "body": "Ready"}
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await email_example.send_approved_preview(preview)
    assert result["status"] == "approval_required"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_approved_send(smtp_env):
    preview = {"status": "preview_only", "to": "teammate@example.com", "subject": "Update", "body": "Ready"}
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await email_example.send_approved_preview(preview, approved=True)
    assert result["status"] == "sent"
    smtp.return_value.__enter__.return_value.send_message.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("preview", [
    {"status": "preview_only", "to": "teammate@example.com", "subject": "Update"},
    {"status": "preview_only", "to": "teammate@example.com", "subject": "Bad\nHeader", "body": "Ready"},
    {"status": "preview_only", "to": "invalid", "subject": "Update", "body": "Ready"},
])
async def test_invalid_preview_never_sends(smtp_env, preview):
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await email_example.send_approved_preview(preview, approved=True)
    assert result["status"] == "invalid_preview"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_smtp_failure(smtp_env):
    preview = {"status": "preview_only", "to": "teammate@example.com", "subject": "Update", "body": "Ready"}
    with patch("smtplib.SMTP_SSL", side_effect=OSError("offline")):
        result = await email_example.send_approved_preview(preview, approved=True)
    assert result == {"status": "send_failed", "error": "OSError"}

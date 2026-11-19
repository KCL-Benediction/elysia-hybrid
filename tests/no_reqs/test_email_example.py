"""SMTP-free checks for the documentation email example."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


EXAMPLE = Path(__file__).resolve().parents[2] / "docs" / "Examples" / "email_example.py"
spec = importlib.util.spec_from_file_location("email_example", EXAMPLE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def smtp_env(monkeypatch):
    for name, value in {
        "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465",
        "SMTP_USERNAME": "sender@example.com", "SMTP_PASSWORD": "test-only",
        "SMTP_FROM": "sender@example.com",
    }.items():
        monkeypatch.setenv(name, value)


@pytest.mark.asyncio
async def test_preview_never_sends():
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await module.preview_email("teammate@example.com", "Update", "Ready")
    assert result["status"] == "preview_only"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_approval_required(smtp_env):
    preview = await module.preview_email("teammate@example.com", "Update", "Ready")
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await module.send_approved_preview(preview)
    assert result["status"] == "approval_required"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_approved_send(smtp_env):
    preview = await module.preview_email("teammate@example.com", "Update", "Ready")
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await module.send_approved_preview(preview, approved=True)
    assert result["status"] == "sent"
    smtp.return_value.__enter__.return_value.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_invalid_preview_does_not_send(smtp_env):
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await module.send_approved_preview({"status": "preview_only", "to": "x@example.com", "subject": "Hi\nBcc: x@example.com", "body": "hello"}, approved=True)
    assert result["status"] == "invalid_preview"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_missing_configuration(monkeypatch):
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)
    preview = await module.preview_email("teammate@example.com", "Update", "Ready")
    assert (await module.send_approved_preview(preview, approved=True))["status"] == "configuration_missing"


@pytest.mark.asyncio
async def test_smtp_failure(smtp_env):
    preview = await module.preview_email("teammate@example.com", "Update", "Ready")
    with patch("smtplib.SMTP_SSL", side_effect=OSError("offline")):
        result = await module.send_approved_preview(preview, approved=True)
    assert result == {"status": "send_failed", "error": "OSError"}

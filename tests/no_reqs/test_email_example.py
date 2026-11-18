"""Offline tests for the documented email example."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


SPEC = importlib.util.spec_from_file_location(
    "email_example", Path(__file__).resolve().parents[2] / "docs/Examples/email_example.py"
)
example = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(example)


@pytest.mark.asyncio
async def test_preview_never_connects():
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await example.send_email("teammate@example.com", "Update", "Ready")
    assert result["status"] == "preview_only"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_approval_required():
    result = await example.send_approved_preview({}, approved=False)
    assert result["status"] == "approval_required"


@pytest.mark.asyncio
async def test_changed_preview_rejected():
    result = await example.send_approved_preview(
        {"status": "preview_only", "to": "a@example.com", "subject": "x", "body": "y", "extra": "changed"},
        approved=True,
    )
    assert result["status"] == "invalid_preview"


@pytest.mark.asyncio
async def test_approved_send_uses_smtp(monkeypatch):
    for key, value in {
        "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465",
        "SMTP_USERNAME": "sender@example.com", "SMTP_PASSWORD": "test-secret",
        "SMTP_FROM": "sender@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    smtp = MagicMock()
    with patch("smtplib.SMTP_SSL") as factory:
        factory.return_value.__enter__.return_value = smtp
        result = await example.send_approved_preview(
            {"status": "preview_only", "to": "a@example.com", "subject": "x", "body": "y"},
            approved=True,
        )
    assert result["status"] == "sent"
    smtp.login.assert_called_once_with("sender@example.com", "test-secret")
    smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_invalid_port(monkeypatch):
    for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.setenv(key, "test")
    monkeypatch.setenv("SMTP_PORT", "not-a-port")
    result = await example.send_email("a@example.com", "x", "y", approved=True)
    assert result["status"] == "configuration_invalid"

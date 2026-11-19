"""Offline tests for the documented email example."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


SPEC = importlib.util.spec_from_file_location(
    "email_example", Path(__file__).resolve().parents[1] / "docs/Examples/email_example.py"
)
example = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(example)


@pytest.fixture
def smtp_env(monkeypatch):
    for key, value in {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "465",
        "SMTP_USERNAME": "sender@example.com",
        "SMTP_PASSWORD": "test-password",
        "SMTP_FROM": "sender@example.com",
    }.items():
        monkeypatch.setenv(key, value)


@pytest.mark.asyncio
async def test_preview_never_connects():
    with patch("smtplib.SMTP_SSL") as smtp:
        preview = await example.send_email("teammate@example.com", "Update", "Ready")
    assert preview == {"status": "preview_only", "to": "teammate@example.com", "subject": "Update", "body": "Ready"}
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_approval_required(smtp_env):
    preview = await example.send_email("teammate@example.com", "Update", "Ready")
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await example.send_approved_preview(preview)
    assert result["status"] == "approval_required"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_approved_send(smtp_env):
    preview = await example.send_email("teammate@example.com", "Update", "Ready")
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await example.send_approved_preview(preview, approved=True)
    assert result["status"] == "sent"
    smtp.return_value.__enter__.return_value.login.assert_called_once_with("sender@example.com", "test-password")
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert message["To"] == "teammate@example.com"
    assert message["Subject"] == "Update"


@pytest.mark.asyncio
async def test_invalid_preview_cannot_send(smtp_env):
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await example.send_approved_preview({"status": "preview_only", "to": "bad\naddress", "subject": "X", "body": "Y"}, True)
    assert result["status"] == "invalid_preview"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_missing_config(monkeypatch):
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)
    preview = await example.send_email("teammate@example.com", "Update", "Ready")
    assert (await example.send_approved_preview(preview, True))["status"] == "configuration_missing"


@pytest.mark.asyncio
async def test_invalid_port(smtp_env, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "70000")
    preview = await example.send_email("teammate@example.com", "Update", "Ready")
    assert (await example.send_approved_preview(preview, True))["status"] == "configuration_invalid"


@pytest.mark.asyncio
async def test_smtp_failure(smtp_env):
    preview = await example.send_email("teammate@example.com", "Update", "Ready")
    with patch("smtplib.SMTP_SSL", side_effect=OSError("offline")):
        result = await example.send_approved_preview(preview, True)
    assert result["status"] == "send_failed"
    assert result["error"] == "OSError"

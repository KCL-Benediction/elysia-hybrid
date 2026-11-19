"""SMTP example tests: no network access or real mail required."""

import importlib.util
import smtplib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def example():
    path = Path(__file__).resolve().parents[2] / "docs" / "Examples" / "email_example.py"
    spec = importlib.util.spec_from_file_location("email_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
async def test_preview_never_sends(example):
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await example.preview_email("to@example.com", "Hello", "Body")
    assert result == {"status": "preview_only", "to": "to@example.com", "subject": "Hello", "body": "Body"}
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_input(example):
    assert (await example.preview_email("a@example.com,b@example.com", "Hello", "Body"))["status"] == "invalid_recipient"
    assert (await example.preview_email("to@example.com", "Hello\r\nBcc: other@example.com", "Body"))["status"] == "invalid_message"


@pytest.mark.asyncio
async def test_approval_required(example):
    with patch("smtplib.SMTP_SSL") as smtp:
        assert (await example.send_approved_preview({}, approved=False))["status"] == "approval_required"
    smtp.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_preview(example):
    preview = {"status": "preview_only", "to": "to@example.com", "subject": "Hi", "body": "Body", "extra": True}
    assert (await example.send_approved_preview(preview, approved=True))["status"] == "invalid_preview"


@pytest.mark.asyncio
async def test_missing_configuration(example, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    preview = {"status": "preview_only", "to": "to@example.com", "subject": "Hi", "body": "Body"}
    assert (await example.send_approved_preview(preview, approved=True))["status"] == "configuration_missing"


@pytest.mark.asyncio
async def test_bad_port(example, smtp_env, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "99999")
    preview = {"status": "preview_only", "to": "to@example.com", "subject": "Hi", "body": "Body"}
    assert (await example.send_approved_preview(preview, approved=True))["status"] == "configuration_invalid"


@pytest.mark.asyncio
async def test_approved_send(example, smtp_env):
    preview = {"status": "preview_only", "to": "to@example.com", "subject": "Hi", "body": "Body"}
    with patch("smtplib.SMTP_SSL") as smtp:
        result = await example.send_approved_preview(preview, approved=True)
    assert result["status"] == "sent"
    client = smtp.return_value.__enter__.return_value
    client.login.assert_called_once_with("sender@example.com", "test-password")
    message = client.send_message.call_args.args[0]
    assert message["To"] == "to@example.com"
    assert message["Subject"] == "Hi"


@pytest.mark.asyncio
async def test_smtp_failure(example, smtp_env):
    preview = {"status": "preview_only", "to": "to@example.com", "subject": "Hi", "body": "Body"}
    with patch("smtplib.SMTP_SSL", side_effect=smtplib.SMTPException("failure")):
        result = await example.send_approved_preview(preview, approved=True)
    assert result == {"status": "send_failed", "error": "SMTPException"}

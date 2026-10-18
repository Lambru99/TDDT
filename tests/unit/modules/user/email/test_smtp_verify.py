"""Tests for user.email.smtp_verify module."""

from unittest.mock import MagicMock, patch
import pytest

from tddt.core.config import Settings
from tddt.core.entity import Email
from tddt.core.http import HttpClient
from tddt.modules.user.email.smtp_verify import UserSmtpVerifyModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_smtp_verify_active_attribute(http_client):
    mod = UserSmtpVerifyModule(http_client, Settings())
    assert mod.active is True


def test_smtp_verify_verifies_email(http_client):
    mod = UserSmtpVerifyModule(http_client, Settings())
    email = Email(value="valid@target.org", confidence=0.5)

    mock_mx_answer = MagicMock()
    mock_mx_item = MagicMock()
    mock_mx_item.exchange.to_text.return_value = "mail.target.org."
    mock_mx_answer.__iter__.return_value = [mock_mx_item]

    mock_smtp_inst = MagicMock()
    mock_smtp_inst.ehlo.return_value = (250, b"OK")
    mock_smtp_inst.mail.return_value = (250, b"OK")

    def mock_rcpt(candidate):
        if "xyz99824nonexistent" in candidate:
            return (550, b"No such user")
        if candidate == "valid@target.org":
            return (250, b"OK")
        return (550, b"User unknown")

    mock_smtp_inst.rcpt.side_effect = mock_rcpt

    with patch("dns.resolver.resolve", return_value=mock_mx_answer), \
         patch("smtplib.SMTP", return_value=mock_smtp_inst):
        entities = list(mod.run([email]))

    assert len(entities) == 1
    assert entities[0].confidence == 0.9
    assert entities[0].metadata.get("smtp_verified") is True

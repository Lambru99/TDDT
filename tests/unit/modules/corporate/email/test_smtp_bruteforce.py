"""Tests for email.smtp_bruteforce module."""

from unittest.mock import MagicMock, patch
import pytest

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.smtp_bruteforce import SmtpBruteforceModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_smtp_bruteforce_produces_verified_emails_on_mock_smtp(http_client):
    mod = SmtpBruteforceModule(http_client, Settings())
    domain = Domain(value="example.com", metadata={"naming_pattern": "{name}.{surname}"})

    mock_mx_answer = MagicMock()
    mock_mx_item = MagicMock()
    mock_mx_item.exchange.to_text.return_value = "mail.example.com."
    mock_mx_answer.__iter__.return_value = [mock_mx_item]

    mock_smtp_inst = MagicMock()
    # connect/ehlo/mail return success
    mock_smtp_inst.ehlo.return_value = (250, b"OK")
    mock_smtp_inst.mail.return_value = (250, b"OK")

    def mock_rcpt(candidate):
        # Catch-all probe: return 550 (not catch-all)
        if "xyz99824nonexistent" in candidate:
            return (550, b"User unknown")
        # Valid user:
        if candidate == "mario.rossi@example.com":
            return (250, b"Recipient OK")
        return (550, b"User unknown")

    mock_smtp_inst.rcpt.side_effect = mock_rcpt

    with patch("dns.resolver.resolve", return_value=mock_mx_answer), \
         patch("smtplib.SMTP", return_value=mock_smtp_inst):
        # Run module with limited wordlist entries for speed in test
        entities = list(mod._probe_candidates(domain, "mail.example.com", ["mario rossi", "john doe"]))

    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "mario.rossi@example.com" in emails
    assert all(e.metadata.get("verified") is True for e in entities)


def test_smtp_bruteforce_aborts_on_catch_all(http_client):
    mod = SmtpBruteforceModule(http_client, Settings())
    domain = Domain(value="example.com", metadata={"naming_pattern": "{name}.{surname}"})

    mock_smtp_inst = MagicMock()
    mock_smtp_inst.ehlo.return_value = (250, b"OK")
    mock_smtp_inst.mail.return_value = (250, b"OK")
    # Catch-all returns 250 on random probe!
    mock_smtp_inst.rcpt.return_value = (250, b"OK")

    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        entities = list(mod._probe_candidates(domain, "mail.example.com", ["mario rossi"]))

    # Should detect catch-all and produce 0 emails
    assert len(entities) == 0


@pytest.mark.active
def test_smtp_bruteforce_active_marker(http_client):
    # Marker test ensuring active marker is attached
    mod = SmtpBruteforceModule(http_client, Settings())
    assert mod.active is True

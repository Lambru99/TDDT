"""Tests for email.google_dork module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.google_dork import GoogleDorkEmailModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_google_dork_finds_emails(http_client):
    mod = GoogleDorkEmailModule(http_client, Settings())
    domain = Domain(value="example.com", source_module="seed")

    html = """
    <html>
      <div>Found email: press@example.com and careers@example.com</div>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.google.com/search?q=%22%40example.com%22",
        body=html,
        status=200,
    )
    entities = list(mod.run([domain]))

    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "press@example.com" in emails
    assert "careers@example.com" in emails


@responses.activate
def test_google_dork_empty(http_client):
    mod = GoogleDorkEmailModule(http_client, Settings())
    domain = Domain(value="empty.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.google.com/search?q=%22%40empty.com%22",
        body="<html><div>No results</div></html>",
        status=200,
    )
    entities = list(mod.run([domain]))

    assert len(entities) == 0


@responses.activate
def test_google_dork_429_logs_warning(http_client, caplog):
    mod = GoogleDorkEmailModule(http_client, Settings())
    domain = Domain(value="blocked.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.google.com/search?q=%22%40blocked.com%22",
        status=429,
    )
    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("429" in record.message or "rate limit" in record.message.lower() for record in caplog.records)

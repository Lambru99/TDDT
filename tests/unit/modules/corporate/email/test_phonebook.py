"""Tests for email.phonebook module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.phonebook import PhonebookEmailModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_phonebook_finds_emails(http_client):
    mod = PhonebookEmailModule(http_client, Settings())
    domain = Domain(value="example.com")

    html = """
    <html>
      <div id="results">
        <span>info@example.com</span>
        <span>cto@example.com</span>
      </div>
    </html>
    """
    responses.add(
        responses.GET,
        "https://phonebook.cz/?search=example.com&type=2",
        body=html,
        status=200,
    )

    entities = list(mod.run([domain]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "info@example.com" in emails
    assert "cto@example.com" in emails


@responses.activate
def test_phonebook_detects_login_page_and_warns(http_client, caplog):
    mod = PhonebookEmailModule(http_client, Settings())
    domain = Domain(value="example.com")

    login_html = """
    <html>
      <title>Login - Phonebook.cz</title>
      <form action="/login" method="post">
        <input type="text" name="username">
        <input type="password" name="password">
        <button type="submit">Sign in</button>
      </form>
    </html>
    """
    responses.add(
        responses.GET,
        "https://phonebook.cz/?search=example.com&type=2",
        body=login_html,
        status=200,
    )

    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("login" in r.message.lower() or "auth" in r.message.lower() for r in caplog.records)


@responses.activate
def test_phonebook_403_logs_warning(http_client, caplog):
    mod = PhonebookEmailModule(http_client, Settings())
    domain = Domain(value="example.com")

    responses.add(
        responses.GET,
        "https://phonebook.cz/?search=example.com&type=2",
        status=403,
    )

    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("403" in r.message or "forbidden" in r.message.lower() for r in caplog.records)

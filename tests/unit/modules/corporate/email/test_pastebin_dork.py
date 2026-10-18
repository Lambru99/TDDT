"""Tests for email.pastebin_dork module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.pastebin_dork import PastebinDorkEmailModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_pastebin_dork_finds_emails(http_client):
    mod = PastebinDorkEmailModule(http_client, Settings())
    domain = Domain(value="example.com", source_module="seed")

    html = """
    <html>
      <li class="b_algo">
        <h2><a href="https://pastebin.com/raw/xyz">Dump</a></h2>
        <p>Leaked admin: sysadmin@example.com was listed here.</p>
      </li>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=site%3Apastebin.com+%22%40example.com%22&first=0",
        body=html,
        status=200,
    )
    entities = list(mod.run([domain]))

    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "sysadmin@example.com" in emails


@responses.activate
def test_pastebin_dork_empty(http_client):
    mod = PastebinDorkEmailModule(http_client, Settings())
    domain = Domain(value="empty.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=site%3Apastebin.com+%22%40empty.com%22&first=0",
        body="<html><div>No pastes</div></html>",
        status=200,
    )
    entities = list(mod.run([domain]))

    assert len(entities) == 0


@responses.activate
def test_pastebin_dork_403_logs_warning(http_client, caplog):
    mod = PastebinDorkEmailModule(http_client, Settings())
    domain = Domain(value="forbidden.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=site%3Apastebin.com+%22%40forbidden.com%22&first=0",
        status=403,
    )
    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("403" in record.message or "forbidden" in record.message.lower() for record in caplog.records)

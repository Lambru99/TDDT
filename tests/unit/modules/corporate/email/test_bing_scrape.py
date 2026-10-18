"""Tests for email.bing_scrape module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.bing_scrape import BingScrapeModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_bing_scrape_finds_emails(http_client):
    mod = BingScrapeModule(http_client, Settings())
    domain = Domain(value="example.com", source_module="seed")

    html = """
    <html>
      <body>
        <div class="b_caption">Contact us at alice@example.com or bob@example.com for info.</div>
        <div>Another text with ignore@otherdomain.com</div>
      </body>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=%22%40example.com%22&first=0",
        body=html,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=%22example.com%22+email+OR+mail&first=0",
        body="<html><body>No results</body></html>",
        status=200,
    )
    entities = list(mod.run([domain]))

    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails
    assert "ignore@otherdomain.com" not in emails


@responses.activate
def test_bing_scrape_empty(http_client):
    mod = BingScrapeModule(http_client, Settings())
    domain = Domain(value="empty.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=%22%40empty.com%22&first=0",
        body="<html><body>No emails found</body></html>",
        status=200,
    )
    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=%22empty.com%22+email+OR+mail&first=0",
        body="<html><body>Empty</body></html>",
        status=200,
    )
    entities = list(mod.run([domain]))

    assert len(entities) == 0


@responses.activate
def test_bing_scrape_403_logs_warning(http_client, caplog):
    mod = BingScrapeModule(http_client, Settings())
    domain = Domain(value="forbidden.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=%22%40forbidden.com%22&first=0",
        status=403,
    )
    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=%22forbidden.com%22+email+OR+mail&first=0",
        status=403,
    )
    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("403" in record.message or "forbidden" in record.message.lower() for record in caplog.records)

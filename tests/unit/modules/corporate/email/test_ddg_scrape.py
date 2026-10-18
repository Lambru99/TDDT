"""Tests for email.ddg_scrape module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.ddg_scrape import DuckDuckGoScrapeModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_ddg_scrape_finds_emails(http_client):
    mod = DuckDuckGoScrapeModule(http_client, Settings())
    domain = Domain(value="example.com", source_module="seed")

    html = """
    <div class="result__body">
      Reach out at support@example.com or security@example.com
    </div>
    """
    responses.add(
        responses.POST,
        "https://html.duckduckgo.com/html/",
        body=html,
        status=200,
    )
    entities = list(mod.run([domain]))

    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "support@example.com" in emails
    assert "security@example.com" in emails


@responses.activate
def test_ddg_scrape_empty(http_client):
    mod = DuckDuckGoScrapeModule(http_client, Settings())
    domain = Domain(value="empty.com", source_module="seed")

    responses.add(
        responses.POST,
        "https://html.duckduckgo.com/html/",
        body="<div>No results found</div>",
        status=200,
    )
    entities = list(mod.run([domain]))

    assert len(entities) == 0


@responses.activate
def test_ddg_scrape_403_logs_warning(http_client, caplog):
    mod = DuckDuckGoScrapeModule(http_client, Settings())
    domain = Domain(value="rate-limited.com", source_module="seed")

    responses.add(
        responses.POST,
        "https://html.duckduckgo.com/html/",
        status=403,
    )
    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("403" in record.message or "rate limit" in record.message.lower() for record in caplog.records)

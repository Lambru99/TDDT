"""Tests for email.wayback_scrape module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Email, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.wayback_scrape import WaybackScrapeEmailModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_wayback_scrape_zero_traffic_with_body_metadata(http_client):
    mod = WaybackScrapeEmailModule(http_client, Settings())
    url_entity = URL(
        value="https://web.archive.org/web/20200101/https://example.com/about",
        metadata={
            "domain": "example.com",
            "body": "Contact archive-user@example.com for historical questions.",
        },
    )

    # Note: no responses.add - should NOT make any HTTP calls!
    entities = list(mod.run([url_entity]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "archive-user@example.com" in emails


@responses.activate
def test_wayback_scrape_fetches_when_body_missing(http_client):
    mod = WaybackScrapeEmailModule(http_client, Settings())
    url = "https://web.archive.org/web/20210101/https://example.com/contact"
    url_entity = URL(
        value=url,
        metadata={"domain": "example.com"},
    )

    responses.add(
        responses.GET,
        url,
        body="<html><body>Email: webmaster@example.com</body></html>",
        status=200,
    )

    entities = list(mod.run([url_entity]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "webmaster@example.com" in emails

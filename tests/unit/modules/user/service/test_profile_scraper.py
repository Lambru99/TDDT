"""Tests for user service profile_scraper module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import FullName, Service, Website
from tddt.core.http import HttpClient
from tddt.modules.user.service.profile_scraper import ServiceProfileScraperModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_profile_scraper_scrapes_bio_and_website(http_client):
    mod = ServiceProfileScraperModule(http_client, Settings())
    service = Service(
        value="https://github.com/torvalds",
        metadata={"platform": "github"},
    )

    html = """
    <html>
      <meta property="profile:username" content="torvalds">
      <span class="p-name vcard-fullname">Linus Torvalds</span>
      <a rel="nofollow me" href="https://kernel.org">Website</a>
    </html>
    """
    responses.add(
        responses.GET,
        "https://github.com/torvalds",
        body=html,
        status=200,
    )

    entities = list(mod.run([service]))
    names = [e for e in entities if isinstance(e, FullName)]
    websites = [e for e in entities if isinstance(e, Website)]

    assert any(n.value == "Linus Torvalds" for n in names)
    assert any("kernel.org" in w.value for w in websites)


@responses.activate
def test_profile_scraper_resolves_url_from_metadata(http_client):
    """Service identifier in value, URL in metadata: the scraper must probe
    metadata["url"], not the identifier."""
    mod = ServiceProfileScraperModule(http_client, Settings())
    service = Service(
        value="GitHub:torvalds",
        metadata={"url": "https://github.com/torvalds", "site": "GitHub"},
    )

    html = """
    <html>
      <span class="p-name vcard-fullname">Linus Torvalds</span>
    </html>
    """
    responses.add(
        responses.GET, "https://github.com/torvalds", body=html, status=200,
    )

    entities = list(mod.run([service]))
    names = [e for e in entities if isinstance(e, FullName)]
    assert any(n.value == "Linus Torvalds" for n in names)


@responses.activate
def test_profile_scraper_skips_service_without_probe_url(http_client, caplog):
    """A Service without a resolvable URL must be skipped silently."""
    import logging
    mod = ServiceProfileScraperModule(http_client, Settings())
    service = Service(value="gravatar:user@example.com", metadata={"site": "gravatar"})

    with caplog.at_level(logging.WARNING, logger="tddt.modules.user.service.profile_scraper"):
        entities = list(mod.run([service]))

    assert entities == []
    assert len(responses.calls) == 0
    assert not any(
        "No connection adapters" in r.message or "HTTP error" in r.message
        for r in caplog.records
    )

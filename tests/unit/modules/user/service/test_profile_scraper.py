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

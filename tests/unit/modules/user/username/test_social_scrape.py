"""Tests for user.username.social_scrape module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Email, Service, URL
from tddt.core.http import HttpClient
from tddt.modules.user.username.social_scrape import SocialScrapeModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_social_scrape_extracts_links_and_emails_via_nitter(http_client):
    mod = SocialScrapeModule(http_client, Settings())
    service = Service(
        value="Twitter:techlead",
        metadata={"site": "Twitter", "username": "techlead"},
    )

    nitter_html = """
    <html>
      <div class="profile-bio">
        Tech enthusiast. Contact me: lead@techcompany.com. My site: https://techlead.io/blog
      </div>
    </html>
    """
    responses.add(
        responses.GET,
        "https://nitter.net/techlead",
        body=nitter_html,
        status=200,
    )

    entities = list(mod.run([service]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    urls = [e.value for e in entities if isinstance(e, URL)]

    assert "lead@techcompany.com" in emails
    assert any("techlead.io" in u for u in urls)

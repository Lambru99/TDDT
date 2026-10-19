"""Tests for user.username.social_scrape module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Email, Service, URL, Username
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
      <footer>
        <a href="https://liberapay.com/zedeus">Donate</a>
        <a href="https://patreon.com/nitter">Patreon</a>
        Contact: zedeus@pm.me
      </footer>
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
    # Nitter infrastructure must NOT leak through
    assert "zedeus@pm.me" not in emails
    assert not any("liberapay.com/zedeus" in u for u in urls)
    assert not any("patreon.com/nitter" in u for u in urls)


@responses.activate
def test_social_scrape_skips_nitter_notice_page(http_client):
    """When Nitter returns a splash/notice page with no profile, yield nothing."""
    mod = SocialScrapeModule(http_client, Settings())
    entity = Username(value="Lambru99")

    notice_html = """
    <html><body>
      <h1>nitter.net</h1>
      <p>UPDATE: X Corp sent cease and desist letters.</p>
      <p>Contact: zedeus@pm.me</p>
      <a href="https://liberapay.com/zedeus">Liberapay</a>
      <a href="https://ko-fi.com/zedeus">Ko-fi</a>
    </body></html>
    """
    responses.add(
        responses.GET,
        "https://nitter.net/Lambru99",
        body=notice_html,
        status=200,
    )

    entities = list(mod.run([entity]))
    assert entities == []


@responses.activate
def test_social_scrape_filters_nitter_infra_from_bio(http_client):
    """Even if infra links somehow appear inside the bio zone, they get filtered."""
    mod = SocialScrapeModule(http_client, Settings())
    entity = Username(value="someuser")

    nitter_html = """
    <html>
      <div class="profile-bio">
        I love nitter! https://patreon.com/nitter https://ko-fi.com/zedeus
        Also check https://mysite.com and me@example.com
      </div>
    </html>
    """
    responses.add(
        responses.GET,
        "https://nitter.net/someuser",
        body=nitter_html,
        status=200,
    )

    entities = list(mod.run([entity]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    urls = [e.value for e in entities if isinstance(e, URL)]

    assert "me@example.com" in emails
    assert any("mysite.com" in u for u in urls)
    assert not any("patreon.com/nitter" in u for u in urls)
    assert not any("ko-fi.com/zedeus" in u for u in urls)

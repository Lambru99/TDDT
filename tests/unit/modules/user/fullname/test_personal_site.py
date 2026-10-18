"""Tests for user fullname personal_site discovery module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, FullName, URL
from tddt.core.http import HttpClient
from tddt.modules.user.fullname.personal_site import FullNamePersonalSiteModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_fullname_personal_site_finds_domains(http_client):
    mod = FullNamePersonalSiteModule(http_client, Settings())
    name = FullName(value="Alice Smith")

    html = """
    <html>
      <a href="https://alicesmith.me">Alice Smith's Homepage</a>
      <a href="https://asmith.dev/about">About Me</a>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.google.com/search?q=%22Alice+Smith%22+%28site%3A.me+OR+site%3A.dev+OR+site%3A.bio+OR+site%3A.info+OR+site%3A.blog+OR+site%3A.io%29",
        body=html,
        status=200,
    )

    entities = list(mod.run([name]))
    domains = [e for e in entities if isinstance(e, Domain)]
    assert len(domains) >= 1
    domain_values = [d.value for d in domains]
    assert "alicesmith.me" in domain_values or "asmith.dev" in domain_values

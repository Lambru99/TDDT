from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, TrackerID
from tddt.core.http import HttpClient
from tddt.modules.corporate.analytics.reverse import AnalyticsReverseModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("html.duckduckgo.com", 1000.0)
    return client


@responses.activate
def test_analytics_reverse_finds_correlated_domains(http_client):
    url = "https://html.duckduckgo.com/html/"
    html = """
    <html>
      <body>
        <a class="result__a" href="https://partner-company.com/page">Partner</a>
        <a class="result__a" href="https://affiliated-service.org/about">Affiliate</a>
        <a class="result__a" href="https://duckduckgo.com/something">Ignore Search Engine</a>
      </body>
    </html>
    """
    responses.add(responses.POST, url, body=html, status=200)

    mod = AnalyticsReverseModule(http_client, Settings())
    tracker = TrackerID(value="UA-12345678-1")
    domains = list(mod.run([tracker]))

    values = {d.value for d in domains if isinstance(d, Domain)}
    assert "partner-company.com" in values
    assert "affiliated-service.org" in values
    assert "duckduckgo.com" not in values
    assert all(d.parent_id == tracker.id for d in domains)


@responses.activate
def test_analytics_reverse_empty_on_no_results(http_client):
    url = "https://html.duckduckgo.com/html/"
    responses.add(responses.POST, url, body="<html><body>No results</body></html>", status=200)

    mod = AnalyticsReverseModule(http_client, Settings())
    tracker = TrackerID(value="UA-99999999-9")
    domains = list(mod.run([tracker]))
    assert domains == []

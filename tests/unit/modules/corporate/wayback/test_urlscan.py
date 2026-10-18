from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.wayback.urlscan import UrlscanModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("urlscan.io", 1000.0)
    return client


@responses.activate
def test_urlscan_finds_urls(http_client):
    url = "https://urlscan.io/api/v1/search/"
    data = {
        "results": [
            {"page": {"url": "https://example.com/checkout"}},
            {"page": {"url": "https://example.com/portal.zip"}},
        ]
    }
    responses.add(responses.GET, url, json=data, status=200)

    mod = UrlscanModule(http_client, Settings())
    domain = Domain(value="example.com")
    urls = list(mod.run([domain]))

    values = {u.value for u in urls if isinstance(u, URL)}
    assert "https://example.com/checkout" in values
    assert "https://example.com/portal.zip" in values
    juicy = {u.value for u in urls if u.metadata.get("juicy")}
    assert "https://example.com/portal.zip" in juicy


@responses.activate
def test_urlscan_empty_when_no_results(http_client):
    url = "https://urlscan.io/api/v1/search/"
    responses.add(responses.GET, url, json={"results": []}, status=200)

    mod = UrlscanModule(http_client, Settings())
    urls = list(mod.run([Domain(value="empty.example.com")]))
    assert urls == []

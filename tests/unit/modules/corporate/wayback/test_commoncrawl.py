from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.wayback.commoncrawl import CommonCrawlModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("index.commoncrawl.org", 1000.0)
    return client


@responses.activate
def test_commoncrawl_queries_latest_index(http_client):
    collinfo_url = "https://index.commoncrawl.org/collinfo.json"
    responses.add(
        responses.GET,
        collinfo_url,
        json=[{"id": "CC-MAIN-2024-10", "cdx-api": "https://index.commoncrawl.org/CC-MAIN-2024-10-index"}],
        status=200,
    )
    cdx_url = "https://index.commoncrawl.org/CC-MAIN-2024-10-index"
    ndjson_body = (
        '{"url": "https://example.com/page1"}\n'
        '{"url": "https://example.com/secret.env"}\n'
    )
    responses.add(responses.GET, cdx_url, body=ndjson_body, status=200)

    mod = CommonCrawlModule(http_client, Settings())
    domain = Domain(value="example.com")
    urls = list(mod.run([domain]))

    values = {u.value for u in urls if isinstance(u, URL)}
    assert "https://example.com/page1" in values
    assert "https://example.com/secret.env" in values
    juicy = {u.value for u in urls if u.metadata.get("juicy")}
    assert "https://example.com/secret.env" in juicy


@responses.activate
def test_commoncrawl_empty_when_no_collinfo(http_client):
    responses.add(responses.GET, "https://index.commoncrawl.org/collinfo.json", json=[], status=200)

    mod = CommonCrawlModule(http_client, Settings())
    urls = list(mod.run([Domain(value="empty.example.com")]))
    assert urls == []

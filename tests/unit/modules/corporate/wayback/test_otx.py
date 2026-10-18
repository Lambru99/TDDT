from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.wayback.otx import OtxWaybackModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False, otx="TEST_OTX_KEY")
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("otx.alienvault.com", 1000.0)
    return client


@responses.activate
def test_otx_wayback_finds_urls(http_client):
    url = "https://otx.alienvault.com/api/v1/indicators/domain/example.com/url_list"
    data = {
        "url_list": [
            {"url": "https://example.com/login.php"},
            {"url": "https://example.com/db.dump"},
        ],
        "has_next": False,
    }
    responses.add(responses.GET, url, json=data, status=200)

    mod = OtxWaybackModule(http_client, http_client.settings)
    domain = Domain(value="example.com")
    urls = list(mod.run([domain]))

    values = {u.value for u in urls if isinstance(u, URL)}
    assert "https://example.com/login.php" in values
    assert "https://example.com/db.dump" in values
    juicy = {u.value for u in urls if u.metadata.get("juicy")}
    assert "https://example.com/db.dump" in juicy


@responses.activate
def test_otx_wayback_empty_when_no_urls(http_client):
    url = "https://otx.alienvault.com/api/v1/indicators/domain/clean.example.com/url_list"
    responses.add(responses.GET, url, json={"url_list": [], "has_next": False}, status=200)

    mod = OtxWaybackModule(http_client, http_client.settings)
    urls = list(mod.run([Domain(value="clean.example.com")]))
    assert urls == []

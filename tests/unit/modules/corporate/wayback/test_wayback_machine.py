from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.wayback.wayback_machine import WaybackMachineModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("web.archive.org", 1000.0)
    return client


@responses.activate
def test_wayback_machine_finds_historical_urls(http_client):
    url = "https://web.archive.org/cdx/search/cdx"
    fixture = [
        ["original"],
        ["https://example.com/api/v1/users"],
        ["https://example.com/backup.sql"],
        ["https://sub.example.com/config.json"],
    ]
    responses.add(responses.GET, url, json=fixture, status=200)

    mod = WaybackMachineModule(http_client, Settings())
    domain = Domain(value="example.com")
    urls = list(mod.run([domain]))

    values = {u.value for u in urls if isinstance(u, URL)}
    assert "https://example.com/api/v1/users" in values
    assert "https://example.com/backup.sql" in values
    assert "https://sub.example.com/config.json" in values

    # Check juicy detection flag on backup.sql and config.json
    juicy = {u.value for u in urls if u.metadata.get("juicy")}
    assert "https://example.com/backup.sql" in juicy
    assert "https://sub.example.com/config.json" in juicy


@responses.activate
def test_wayback_machine_empty_on_no_records(http_client):
    url = "https://web.archive.org/cdx/search/cdx"
    responses.add(responses.GET, url, json=[["original"]], status=200)

    mod = WaybackMachineModule(http_client, Settings())
    urls = list(mod.run([Domain(value="empty.example.com")]))
    assert urls == []

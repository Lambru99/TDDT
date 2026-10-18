from __future__ import annotations

import pytest

from tddt.core.config import Settings
from tddt.core.entity import Subdomain, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.subdomain.wayback_extract import WaybackExtractSubdomain


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_wayback_extract_produces_subdomain_with_domain_metadata(http_client):
    mod = WaybackExtractSubdomain(http_client, Settings())
    urls = [
        URL(value="https://assets.example.com/logo.png", metadata={"domain": "example.com"}),
        URL(value="https://docs.example.com/api/v1", metadata={"domain": "example.com"}),
        URL(value="https://example.com/index.html", metadata={"domain": "example.com"}),
        URL(value="https://evil-example.com/phish", metadata={"domain": "example.com"}),
    ]
    results = list(mod.run(urls))

    values = {r.value for r in results}
    assert values == {"assets.example.com", "docs.example.com"}
    assert all(isinstance(r, Subdomain) for r in results)
    assert all(r.source_module == "corporate.subdomain.wayback_extract" for r in results)


def test_wayback_extract_produces_subdomain_without_domain_metadata(http_client):
    mod = WaybackExtractSubdomain(http_client, Settings())
    urls = [
        URL(value="https://portal.service.company.com/login"),
        URL(value="https://google.com/search"),
        URL(value="https://192.168.1.1/admin"),
    ]
    results = list(mod.run(urls))

    values = {r.value for r in results}
    assert "portal.service.company.com" in values
    assert "google.com" not in values
    assert "192.168.1.1" not in values


def test_wayback_extract_empty_on_known_empty(http_client):
    mod = WaybackExtractSubdomain(http_client, Settings())
    urls = [
        URL(value="https://example.com/about", metadata={"domain": "example.com"}),
    ]
    results = list(mod.run(urls))
    assert results == []

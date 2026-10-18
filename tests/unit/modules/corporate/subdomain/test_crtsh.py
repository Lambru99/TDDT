from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Subdomain
from tddt.core.http import HttpClient
from tddt.modules.corporate.subdomain.crtsh import CrtshSubdomain


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("crt.sh", 1000.0)
    return client


@responses.activate
def test_crtsh_produces_subdomains_on_fixture(http_client):
    url = "https://crt.sh/?q=%.example.com&output=json"
    fixture_data = [
        {"name_value": "sub1.example.com\nsub2.example.com"},
        {"name_value": "*.sub3.example.com"},
        {"name_value": "example.com"},
    ]
    responses.add(responses.GET, url, json=fixture_data, status=200)

    mod = CrtshSubdomain(http_client, Settings())
    domain = Domain(value="example.com")
    results = list(mod.run([domain]))

    values = {r.value for r in results}
    assert "sub1.example.com" in values
    assert "sub2.example.com" in values
    assert "sub3.example.com" in values
    assert all(isinstance(r, Subdomain) for r in results)
    assert all(r.parent_id == domain.id for r in results)
    assert all(r.source_module == "corporate.subdomain.crtsh" for r in results)


@responses.activate
def test_crtsh_returns_empty_on_known_empty(http_client):
    url = "https://crt.sh/?q=%.empty-target.com&output=json"
    responses.add(responses.GET, url, json=[], status=200)

    mod = CrtshSubdomain(http_client, Settings())
    results = list(mod.run([Domain(value="empty-target.com")]))
    assert results == []


@responses.activate
def test_crtsh_retry_on_404_does_not_loop(http_client):
    url = "https://crt.sh/?q=%.notfound.com&output=json"
    responses.add(responses.GET, url, status=404)

    mod = CrtshSubdomain(http_client, Settings())
    results = list(mod.run([Domain(value="notfound.com")]))
    assert results == []
    # Assert only called once, no loop
    assert len(responses.calls) == 1

from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Subdomain
from tddt.core.http import HttpClient
from tddt.modules.corporate.subdomain.hackertarget import HackerTargetSubdomain


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("api.hackertarget.com", 1000.0)
    return client


@responses.activate
def test_hackertarget_produces_subdomains_on_fixture(http_client):
    url = "https://api.hackertarget.com/hostsearch/?q=example.com"
    body = "mail.example.com,1.2.3.4\nvpn.example.com,1.2.3.5\nexample.com,1.2.3.6\n"
    responses.add(responses.GET, url, body=body, status=200)

    mod = HackerTargetSubdomain(http_client, Settings())
    domain = Domain(value="example.com")
    results = list(mod.run([domain]))

    values = {r.value for r in results}
    assert "mail.example.com" in values
    assert "vpn.example.com" in values
    assert all(isinstance(r, Subdomain) for r in results)
    assert all(r.parent_id == domain.id for r in results)
    assert all(r.source_module == "corporate.subdomain.hackertarget" for r in results)


@responses.activate
def test_hackertarget_returns_empty_on_known_empty(http_client):
    url = "https://api.hackertarget.com/hostsearch/?q=empty-target.com"
    responses.add(responses.GET, url, body="No records found", status=200)

    mod = HackerTargetSubdomain(http_client, Settings())
    results = list(mod.run([Domain(value="empty-target.com")]))
    assert results == []


@responses.activate
def test_hackertarget_handles_quota_exceeded(http_client):
    url = "https://api.hackertarget.com/hostsearch/?q=example.com"
    responses.add(responses.GET, url, body="API count exceeded - Increase Quota with Membership", status=200)

    mod = HackerTargetSubdomain(http_client, Settings())
    results = list(mod.run([Domain(value="example.com")]))
    assert results == []

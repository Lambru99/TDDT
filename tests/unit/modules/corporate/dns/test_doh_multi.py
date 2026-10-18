from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, IPAddress
from tddt.core.http import HttpClient
from tddt.modules.corporate.dns.doh_multi import DohMultiModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("cloudflare-dns.com", 1000.0)
    client.rate_limiter.configure("dns.google", 1000.0)
    client.rate_limiter.configure("dns.quad9.net", 1000.0)
    client.rate_limiter.configure("dns.nextdns.io", 1000.0)
    return client


@responses.activate
def test_doh_multi_resolves_ips(http_client):
    responses.add(
        responses.GET,
        "https://cloudflare-dns.com/dns-query?name=example.com&type=A",
        json={"Answer": [{"name": "example.com", "type": 1, "data": "93.184.216.34"}]},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://dns.google/resolve?name=example.com&type=A",
        json={"Answer": [{"name": "example.com", "type": 1, "data": "93.184.216.34"}]},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://dns.quad9.net/dns-query?name=example.com&type=A",
        json={"Answer": [{"name": "example.com", "type": 1, "data": "93.184.216.34"}]},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://dns.nextdns.io/dns-query?name=example.com&type=A",
        json={"Answer": [{"name": "example.com", "type": 1, "data": "93.184.216.34"}]},
        status=200,
    )

    mod = DohMultiModule(http_client, Settings())
    domain = Domain(value="example.com")
    results = list(mod.run([domain]))

    ips = [r for r in results if isinstance(r, IPAddress)]
    assert len(ips) >= 1
    assert any(ip.value == "93.184.216.34" for ip in ips)
    assert all(ip.parent_id == domain.id for ip in ips)


@responses.activate
def test_doh_multi_fallback_when_some_resolvers_fail(http_client):
    # Cloudflare fails with 500
    responses.add(
        responses.GET,
        "https://cloudflare-dns.com/dns-query?name=example.com&type=A",
        status=500,
    )
    # Google succeeds
    responses.add(
        responses.GET,
        "https://dns.google/resolve?name=example.com&type=A",
        json={"Answer": [{"name": "example.com", "type": 1, "data": "93.184.216.34"}]},
        status=200,
    )
    # Quad9 returns empty
    responses.add(
        responses.GET,
        "https://dns.quad9.net/dns-query?name=example.com&type=A",
        json={},
        status=200,
    )
    # NextDNS fails
    responses.add(
        responses.GET,
        "https://dns.nextdns.io/dns-query?name=example.com&type=A",
        status=502,
    )

    mod = DohMultiModule(http_client, Settings())
    domain = Domain(value="example.com")
    results = list(mod.run([domain]))

    ips = [r for r in results if isinstance(r, IPAddress)]
    assert len(ips) == 1
    assert ips[0].value == "93.184.216.34"

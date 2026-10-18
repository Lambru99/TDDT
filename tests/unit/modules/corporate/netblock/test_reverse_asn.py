from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import IPAddress
from tddt.core.http import HttpClient
from tddt.modules.corporate.netblock.reverse_asn import ReverseAsnModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("api.hackertarget.com", 1000.0)
    client.rate_limiter.configure("bgp.he.net", 1000.0)
    return client


@responses.activate
def test_reverse_asn_enriches_from_hackertarget(http_client):
    url = "https://api.hackertarget.com/aslookup/?q=93.184.216.34"
    body = '"93.184.216.34","15133","MCI Communications Services, Inc. d/b/a Verizon Business","93.184.216.0/24"'
    responses.add(responses.GET, url, body=body, status=200)

    mod = ReverseAsnModule(http_client, Settings())
    ip = IPAddress(value="93.184.216.34")
    results = list(mod.run([ip]))

    assert ip.metadata.get("asn") == "15133"
    assert ip.metadata.get("bgp_prefix") == "93.184.216.0/24"
    assert len(results) >= 1


@responses.activate
def test_reverse_asn_handles_429_gracefully(http_client):
    url = "https://api.hackertarget.com/aslookup/?q=93.184.216.34"
    responses.add(responses.GET, url, status=429)

    mod = ReverseAsnModule(http_client, Settings())
    ip = IPAddress(value="93.184.216.34")
    results = list(mod.run([ip]))
    assert results == []


@responses.activate
def test_reverse_asn_handles_quota_exceeded(http_client):
    url = "https://api.hackertarget.com/aslookup/?q=93.184.216.34"
    responses.add(responses.GET, url, body="API count exceeded", status=200)

    mod = ReverseAsnModule(http_client, Settings())
    ip = IPAddress(value="93.184.216.34")
    results = list(mod.run([ip]))
    assert results == []

from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import IPAddress
from tddt.core.http import HttpClient
from tddt.modules.corporate.netblock.ipapi import IpApiModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("ip-api.com", 1000.0)
    return client


@responses.activate
def test_ipapi_uses_https_and_enriches_batch(http_client):
    """Bug §2.6: verify ip-api URL uses HTTPS and processes up to 100 IPs in batch."""
    url = "https://ip-api.com/batch"
    responses.add(
        responses.POST,
        url,
        json=[
            {
                "status": "success",
                "query": "93.184.216.34",
                "countryCode": "US",
                "isp": "EDGECAST",
                "org": "MCI Communications Services, Inc. d/b/a Verizon Business",
                "as": "AS15133 MCI Communications Services, Inc. d/b/a Verizon Business",
            },
            {
                "status": "success",
                "query": "1.1.1.1",
                "countryCode": "AU",
                "isp": "Cloudflare, Inc.",
                "org": "APNIC and Cloudflare DNS Resolver Project",
                "as": "AS13335 CLOUDFLARENET",
            },
        ],
        status=200,
    )

    mod = IpApiModule(http_client, Settings())
    ip1 = IPAddress(value="93.184.216.34")
    ip2 = IPAddress(value="1.1.1.1")
    results = list(mod.run([ip1, ip2]))

    # Verify call went to https
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == "https://ip-api.com/batch"

    # Verify metadata was enriched
    assert ip1.metadata.get("country") == "US"
    assert ip1.metadata.get("isp") == "EDGECAST"
    assert "AS15133" in ip1.metadata.get("asn", "")
    assert ip2.metadata.get("country") == "AU"
    assert "AS13335" in ip2.metadata.get("asn", "")


@responses.activate
def test_ipapi_handles_429_gracefully(http_client):
    responses.add(responses.POST, "https://ip-api.com/batch", status=429)

    mod = IpApiModule(http_client, Settings())
    ip = IPAddress(value="93.184.216.34")
    results = list(mod.run([ip]))
    assert results == []

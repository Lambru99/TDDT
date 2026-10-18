from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Subdomain
from tddt.core.http import HttpClient
from tddt.modules.corporate.subdomain.otx_passive_dns import OtxPassiveDnsSubdomain


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("otx.alienvault.com", 1000.0)
    return client


@responses.activate
def test_otx_produces_subdomains_on_fixture(http_client):
    url = "https://otx.alienvault.com/api/v1/indicators/domain/example.com/passive_dns"
    fixture_data = {
        "passive_dns": [
            {"hostname": "dev.example.com"},
            {"hostname": "*.stage.example.com"},
            {"hostname": "example.com"},
            {"hostname": "otherdomain.com"},
        ]
    }
    responses.add(responses.GET, url, json=fixture_data, status=200)

    mod = OtxPassiveDnsSubdomain(http_client, Settings())
    domain = Domain(value="example.com")
    results = list(mod.run([domain]))

    values = {r.value for r in results}
    assert "dev.example.com" in values
    assert "stage.example.com" in values
    assert "otherdomain.com" not in values
    assert all(isinstance(r, Subdomain) for r in results)
    assert all(r.parent_id == domain.id for r in results)
    assert all(r.source_module == "corporate.subdomain.otx_passive_dns" for r in results)


@responses.activate
def test_otx_returns_empty_on_known_empty(http_client):
    url = "https://otx.alienvault.com/api/v1/indicators/domain/empty-target.com/passive_dns"
    responses.add(responses.GET, url, json={"passive_dns": []}, status=200)

    mod = OtxPassiveDnsSubdomain(http_client, Settings())
    results = list(mod.run([Domain(value="empty-target.com")]))
    assert results == []


@responses.activate
def test_otx_handles_error_response(http_client):
    url = "https://otx.alienvault.com/api/v1/indicators/domain/error.com/passive_dns"
    responses.add(responses.GET, url, status=500)

    mod = OtxPassiveDnsSubdomain(http_client, Settings())
    results = list(mod.run([Domain(value="error.com")]))
    assert results == []

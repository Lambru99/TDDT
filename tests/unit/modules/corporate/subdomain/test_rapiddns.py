from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Subdomain
from tddt.core.http import HttpClient
from tddt.modules.corporate.subdomain.rapiddns import RapidDnsSubdomain


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("rapiddns.io", 1000.0)
    return client


@responses.activate
def test_rapiddns_produces_subdomains_on_fixture(http_client):
    url = "https://rapiddns.io/subdomain/example.com?modules=subdomain"
    html_body = """
    <html>
      <body>
        <table>
          <tr><td>1</td><td>app.example.com</td><td>1.2.3.4</td></tr>
          <tr><td>2</td><td>*.admin.example.com</td><td>1.2.3.5</td></tr>
          <tr><td>3</td><td>example.com</td><td>1.2.3.6</td></tr>
          <tr><td>4</td><td>unrelated.com</td><td>1.2.3.7</td></tr>
        </table>
      </body>
    </html>
    """
    responses.add(responses.GET, url, body=html_body, status=200)

    mod = RapidDnsSubdomain(http_client, Settings())
    domain = Domain(value="example.com")
    results = list(mod.run([domain]))

    values = {r.value for r in results}
    assert "app.example.com" in values
    assert "admin.example.com" in values
    assert "unrelated.com" not in values
    assert all(isinstance(r, Subdomain) for r in results)
    assert all(r.parent_id == domain.id for r in results)
    assert all(r.source_module == "corporate.subdomain.rapiddns" for r in results)


@responses.activate
def test_rapiddns_returns_empty_on_known_empty(http_client):
    url = "https://rapiddns.io/subdomain/empty-target.com?modules=subdomain"
    responses.add(responses.GET, url, body="<html><body>No results</body></html>", status=200)

    mod = RapidDnsSubdomain(http_client, Settings())
    results = list(mod.run([Domain(value="empty-target.com")]))
    assert results == []


@responses.activate
def test_rapiddns_handles_http_error(http_client):
    url = "https://rapiddns.io/subdomain/error.com?modules=subdomain"
    responses.add(responses.GET, url, status=500)

    mod = RapidDnsSubdomain(http_client, Settings())
    results = list(mod.run([Domain(value="error.com")]))
    assert results == []

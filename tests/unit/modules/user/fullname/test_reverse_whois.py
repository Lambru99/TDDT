"""Tests for user fullname reverse_whois module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, FullName
from tddt.core.http import HttpClient
from tddt.modules.user.fullname.reverse_whois import FullNameReverseWhoisModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_fullname_reverse_whois_finds_domains(http_client):
    mod = FullNameReverseWhoisModule(http_client, Settings())
    name = FullName(value="John Doe")

    html = """
    <html>
      <table id="domain-table">
        <tr><td>domainone.com</td><td>2021-01-01</td></tr>
        <tr><td>domaintwo.org</td><td>2020-05-12</td></tr>
      </table>
    </html>
    """
    responses.add(
        responses.GET,
        "https://viewdns.info/reversewhois/?q=John+Doe",
        body=html,
        status=200,
    )

    entities = list(mod.run([name]))
    domains = [e for e in entities if isinstance(e, Domain)]
    domain_values = {d.value for d in domains}
    assert "domainone.com" in domain_values
    assert "domaintwo.org" in domain_values

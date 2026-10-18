from __future__ import annotations

from unittest.mock import MagicMock, patch

import dns.exception
import pytest

from tddt.core.config import Settings
from tddt.core.entity import Domain, Subdomain
from tddt.core.http import HttpClient
from tddt.modules.corporate.dns.axfr_attempt import AxfrAttemptModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_axfr_gracefully_fails_when_refused(http_client):
    mod = AxfrAttemptModule(http_client, Settings())
    domain = Domain(value="example.com")

    # Mock NS lookup to return ns1.example.com
    mock_ns = MagicMock()
    mock_ns.__str__.return_value = "ns1.example.com."

    with (
        patch("dns.resolver.resolve", return_value=[mock_ns]),
        patch("dns.zone.from_xfr", side_effect=dns.exception.FormError("Refused")),
    ):
        results = list(mod.run([domain]))
    assert results == []


def test_axfr_produces_subdomains_when_successful(http_client):
    mod = AxfrAttemptModule(http_client, Settings())
    domain = Domain(value="zonetransfer.me")

    mock_ns = MagicMock()
    mock_ns.__str__.return_value = "nsztm1.digi.ninja."

    # Mock zone with nodes
    mock_zone = MagicMock()
    mock_zone.nodes.keys.return_value = [
        MagicMock(__str__=lambda s: "intranet"),
        MagicMock(__str__=lambda s: "vpn"),
        MagicMock(__str__=lambda s: "@"),
    ]

    with (
        patch("dns.resolver.resolve", return_value=[mock_ns]),
        patch("dns.zone.from_xfr", return_value=mock_zone),
    ):
        results = list(mod.run([domain]))

    values = {r.value for r in results}
    assert "intranet.zonetransfer.me" in values
    assert "vpn.zonetransfer.me" in values
    assert all(isinstance(r, Subdomain) for r in results)
    assert all(r.source_module == "corporate.dns.axfr_attempt" for r in results)

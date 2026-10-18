from __future__ import annotations

from unittest.mock import MagicMock, patch

import dns.resolver
import pytest

from tddt.core.config import Settings
from tddt.core.entity import DNSRecord, Domain, Subdomain
from tddt.core.http import HttpClient
from tddt.modules.corporate.dns.wildcard_detector import WildcardDetectorModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_wildcard_sets_flag_and_lowers_subdomain_confidence(http_client):
    """Review Focus #1: wildcard target detection sets metadata flag and lowers confidence."""
    mod = WildcardDetectorModule(http_client, Settings())
    domain = Domain(value="wildcard-example.com")

    # Mock DNS resolution to succeed for any random query
    mock_ans = MagicMock()
    mock_ans.__str__.return_value = "1.2.3.4"

    with patch("dns.resolver.resolve", return_value=[mock_ans]):
        results = list(mod.run([domain]))

    assert domain.metadata.get("wildcard_dns") is True
    assert domain.metadata.get("wildcard_ips") == ["1.2.3.4"]

    dns_records = [r for r in results if isinstance(r, DNSRecord)]
    assert len(dns_records) >= 1
    assert dns_records[0].metadata.get("wildcard") is True

    # Test helper method to adjust/check subdomain confidence under wildcard
    sub = Subdomain(value="anything.wildcard-example.com", confidence=1.0)
    adjusted_sub = mod.adjust_subdomain_for_wildcard(sub, domain)
    assert adjusted_sub.confidence < 0.5
    assert adjusted_sub.metadata.get("wildcard_suspect") is True


def test_wildcard_negative_when_nxdomain(http_client):
    mod = WildcardDetectorModule(http_client, Settings())
    domain = Domain(value="clean-example.com")

    with patch("dns.resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
        results = list(mod.run([domain]))

    assert domain.metadata.get("wildcard_dns") is False
    assert results == []

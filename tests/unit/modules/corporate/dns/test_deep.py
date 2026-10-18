from __future__ import annotations

from unittest.mock import MagicMock, patch

import dns.resolver
import pytest

from tddt.core.config import Settings
from tddt.core.entity import DNSRecord, Domain, Subdomain
from tddt.core.http import HttpClient
from tddt.modules.corporate.dns.deep import DnsDeepModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_dns_deep_spf_and_dmarc_evaluation(http_client):
    mod = DnsDeepModule(http_client, Settings())
    domain = Domain(value="example.com")

    def mock_resolve(qname, rtype, **kwargs):
        qstr = str(qname)
        if qstr == "example.com" and rtype == "TXT":
            mock_txt = MagicMock()
            mock_txt.__str__.return_value = '"v=spf1 include:_spf.google.com -all"'
            return [mock_txt]
        if qstr == "_dmarc.example.com" and rtype == "TXT":
            mock_dmarc = MagicMock()
            mock_dmarc.__str__.return_value = '"v=DMARC1; p=reject; sp=reject"'
            return [mock_dmarc]
        if qstr == "example.com" and rtype == "MX":
            mock_mx = MagicMock()
            mock_mx.__str__.return_value = "10 mail.example.com."
            return [mock_mx]
        if qstr == "example.com" and rtype == "NS":
            mock_ns = MagicMock()
            mock_ns.__str__.return_value = "ns1.example.com."
            return [mock_ns]
        raise dns.resolver.NXDOMAIN()

    with patch("dns.resolver.resolve", side_effect=mock_resolve):
        results = list(mod.run([domain]))

    dns_records = [r for r in results if isinstance(r, DNSRecord)]
    subdomains = [r for r in results if isinstance(r, Subdomain)]

    # Check SPF evaluation
    spf_records = [r for r in dns_records if r.metadata.get("type") == "SPF"]
    assert len(spf_records) == 1
    assert spf_records[0].metadata["strength"] == "Fail (-all) — strict"

    # Check DMARC evaluation
    dmarc_records = [r for r in dns_records if r.metadata.get("type") == "DMARC"]
    assert len(dmarc_records) == 1
    assert dmarc_records[0].metadata["policy"] == "reject"
    assert dmarc_records[0].metadata["strength"] == "Reject — strict protection"

    # Check derived subdomains from MX and NS
    sub_values = {s.value for s in subdomains}
    assert "mail.example.com" in sub_values
    assert "ns1.example.com" in sub_values


def test_dns_deep_spf_flavors(http_client):
    mod = DnsDeepModule(http_client, Settings())
    assert mod.evaluate_spf("v=spf1 ~all")["strength"] == "SoftFail (~all) — medium"
    assert mod.evaluate_spf("v=spf1 -all")["strength"] == "Fail (-all) — strict"
    assert mod.evaluate_spf("v=spf1 +all")["strength"] == "Pass (+all) — DANGEROUS: accepts all"
    assert mod.evaluate_spf("v=spf1 ?all")["strength"] == "Neutral (?all) — weak"


def test_dns_deep_graceful_on_nxdomain(http_client):
    mod = DnsDeepModule(http_client, Settings())
    domain = Domain(value="nonexistent.example.com")

    with patch("dns.resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
        results = list(mod.run([domain]))
    assert results == []

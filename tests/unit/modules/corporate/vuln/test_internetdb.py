"""Tests for vuln.internetdb module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import CVE, IPAddress, Port
from tddt.core.http import HttpClient
from tddt.modules.corporate.vuln.internetdb import InternetDbModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_internetdb_few_ports_high_confidence_and_cves_emitted(http_client):
    """Bug §2.3 fix: CVE entities always emitted when vulns present."""
    mod = InternetDbModule(http_client, Settings())
    ip = IPAddress(value="1.2.3.4")

    payload = {
        "ip": "1.2.3.4",
        "ports": [80, 443],
        "vulns": ["CVE-2021-34527", "CVE-2022-26134"],
        "tags": ["cloud"],
    }
    responses.add(
        responses.GET,
        "https://internetdb.shodan.io/1.2.3.4",
        json=payload,
        status=200,
    )

    entities = list(mod.run([ip]))
    ports = [e for e in entities if isinstance(e, Port)]
    cves = [e for e in entities if isinstance(e, CVE)]

    assert len(ports) == 2
    assert all(p.confidence == 0.9 for p in ports)
    assert all(p.metadata.get("verified") is True for p in ports)

    assert len(cves) == 2
    cve_vals = {c.value for c in cves}
    assert "CVE-2021-34527" in cve_vals
    assert "CVE-2022-26134" in cve_vals


@responses.activate
def test_internetdb_many_ports_drops_confidence(http_client):
    """Bug §2.4 fix: >= 100 ports drops confidence to 0.5 and verified=False."""
    mod = InternetDbModule(http_client, Settings())
    ip = IPAddress(value="5.6.7.8")

    payload = {
        "ip": "5.6.7.8",
        "ports": list(range(1, 105)),  # 104 ports (>= 100)
        "vulns": [],
        "tags": [],
    }
    responses.add(
        responses.GET,
        "https://internetdb.shodan.io/5.6.7.8",
        json=payload,
        status=200,
    )

    entities = list(mod.run([ip]))
    ports = [e for e in entities if isinstance(e, Port)]

    assert len(ports) == 104
    assert all(p.confidence == 0.5 for p in ports)
    assert all(p.metadata.get("verified") is False for p in ports)


@responses.activate
def test_internetdb_404_empty(http_client):
    mod = InternetDbModule(http_client, Settings())
    ip = IPAddress(value="9.9.9.9")

    responses.add(
        responses.GET,
        "https://internetdb.shodan.io/9.9.9.9",
        status=404,
    )

    entities = list(mod.run([ip]))
    assert len(entities) == 0

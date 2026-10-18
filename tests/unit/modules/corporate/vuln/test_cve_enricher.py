"""Tests for vuln.cve_enricher module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import CVE, Finding
from tddt.core.http import HttpClient
from tddt.modules.corporate.vuln.cve_enricher import CveEnricherModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_cve_enricher_enriches_cve(http_client):
    mod = CveEnricherModule(http_client, Settings())
    cve = CVE(value="CVE-2021-34527")

    data = {
        "id": "CVE-2021-34527",
        "cvss": 9.8,
        "summary": "Windows Print Spooler Remote Code Execution Vulnerability (PrintNightmare).",
    }
    responses.add(
        responses.GET,
        "https://cve.circl.lu/api/cve/CVE-2021-34527",
        json=data,
        status=200,
    )

    entities = list(mod.run([cve]))
    findings = [e for e in entities if isinstance(e, Finding)]
    assert len(findings) == 1
    assert findings[0].value == "CVE-2021-34527"
    assert findings[0].metadata.get("cvss") == 9.8
    assert "PrintNightmare" in findings[0].metadata.get("summary", "")


@responses.activate
def test_cve_enricher_404_empty(http_client):
    mod = CveEnricherModule(http_client, Settings())
    cve = CVE(value="CVE-9999-99999")

    responses.add(
        responses.GET,
        "https://cve.circl.lu/api/cve/CVE-9999-99999",
        status=404,
    )

    entities = list(mod.run([cve]))
    assert len(entities) == 0

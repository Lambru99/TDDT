from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Finding, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.web.cors_misconfig import CorsMisconfigModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_cors_misconfig_detects_arbitrary_origin_reflection(http_client):
    url = "https://api.example.com/data"
    headers = {
        "Access-Control-Allow-Origin": "https://evil.com",
        "Access-Control-Allow-Credentials": "true",
    }
    responses.add(responses.GET, url, headers=headers, status=200)

    mod = CorsMisconfigModule(http_client, Settings())
    url_ent = URL(value=url)
    findings = list(mod.run([url_ent]))

    assert len(findings) == 1
    f = findings[0]
    assert isinstance(f, Finding)
    assert f.metadata["type"] == "cors_misconfiguration"
    assert f.metadata["acao"] == "https://evil.com"
    assert f.metadata["credentials"] == "true"
    assert f.metadata["severity"] == "high"


@responses.activate
def test_cors_misconfig_ignores_safe_origin(http_client):
    url = "https://safe.example.com"
    headers = {
        "Access-Control-Allow-Origin": "https://example.com",
    }
    responses.add(responses.GET, url, headers=headers, status=200)

    mod = CorsMisconfigModule(http_client, Settings())
    findings = list(mod.run([URL(value=url)]))
    assert findings == []

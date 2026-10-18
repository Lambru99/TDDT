from __future__ import annotations

import pytest

from tddt.core.config import Settings
from tddt.core.entity import Finding, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.web.security_headers import SecurityHeadersModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_security_headers_identifies_missing_headers(http_client):
    mod = SecurityHeadersModule(http_client, Settings())
    # URL with some headers present, others missing
    url_ent = URL(
        value="https://secure.example.com",
        metadata={
            "headers": {
                "Server": "nginx",
                "X-Frame-Options": "DENY",
            }
        },
    )
    findings = list(mod.run([url_ent]))

    missing = {f.metadata["header"] for f in findings if isinstance(f, Finding)}
    assert "Strict-Transport-Security" in missing
    assert "Content-Security-Policy" in missing
    assert "X-Content-Type-Options" in missing
    assert "X-Frame-Options" not in missing
    assert all(f.parent_id == url_ent.id for f in findings)


def test_security_headers_clean_when_all_present(http_client):
    mod = SecurityHeadersModule(http_client, Settings())
    url_ent = URL(
        value="https://hardened.example.com",
        metadata={
            "headers": {
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "Content-Security-Policy": "default-src 'self'",
                "X-Frame-Options": "DENY",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Permissions-Policy": "camera=()",
            }
        },
    )
    findings = list(mod.run([url_ent]))
    assert findings == []

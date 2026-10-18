from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tddt.core.config import Settings
from tddt.core.entity import Finding, Subdomain
from tddt.core.http import HttpClient
from tddt.core.module import applicable
from tddt.modules.corporate.web.cors_misconfig import CorsMisconfigModule
from tddt.modules.corporate.web.takeover_verifier import TakeoverVerifierModule
from tddt.modules.corporate.web.tls_deep import TlsDeepModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_tls_deep_detects_deprecated_tls(http_client):
    mod = TlsDeepModule(http_client, Settings())
    sub = Subdomain(value="legacy.example.com")

    # Mock test_protocol_version to simulate supporting TLS 1.0 and TLS 1.1
    with patch.object(mod, "_test_protocol_version", side_effect=lambda host, ver: ver in ("TLSv1", "TLSv1.1")):
        findings = list(mod.run([sub]))

    versions = {f.metadata["protocol"] for f in findings if isinstance(f, Finding)}
    assert "TLSv1" in versions
    assert "TLSv1.1" in versions
    assert all(f.metadata["type"] == "deprecated_tls" for f in findings)


def test_tls_deep_clean_on_modern_tls(http_client):
    mod = TlsDeepModule(http_client, Settings())
    sub = Subdomain(value="modern.example.com")

    # Modern server refuses old protocols
    with patch.object(mod, "_test_protocol_version", return_value=False):
        findings = list(mod.run([sub]))
    assert findings == []


def test_active_modules_excluded_in_light_mode():
    """All Task 3.5 modules are active=True and excluded when allow_active=False."""
    settings = Settings()

    app_active = applicable(
        entity_type=Subdomain,
        mode="corporate",
        keyless_only=False,
        allow_active=False,
        settings=settings,
    )

    assert TakeoverVerifierModule not in app_active
    assert CorsMisconfigModule not in app_active
    assert TlsDeepModule not in app_active

from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import DNSRecord, TakeoverFinding
from tddt.core.http import HttpClient
from tddt.modules.corporate.web.takeover_verifier import TakeoverVerifierModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_takeover_verifier_detects_unclaimed_service(http_client):
    """Bug §2.2 fix: CNAME to unclaimed GitHub Pages with fingerprint emits TakeoverFinding."""
    cname_target = "unclaimed.github.io"
    subdomain = "docs.example.com"
    error_body = "<html><body>There isn't a GitHub Pages site here</body></html>"

    responses.add(
        responses.GET,
        f"https://{subdomain}",
        body=error_body,
        status=404,
    )

    mod = TakeoverVerifierModule(http_client, Settings())
    dns_rec = DNSRecord(
        value=f"{subdomain}:CNAME:{cname_target}",
        metadata={"type": "CNAME", "record": cname_target, "domain": subdomain},
    )
    findings = list(mod.run([dns_rec]))

    assert len(findings) == 1
    tf = findings[0]
    assert isinstance(tf, TakeoverFinding)
    assert tf.metadata["service"] == "GitHub Pages"
    assert tf.metadata["cname"] == cname_target
    assert tf.parent_id == dns_rec.id


@responses.activate
def test_takeover_verifier_ignores_live_claimed_site(http_client):
    """Bug §2.2 fix: CNAME to claimed/live GitHub Pages (fingerprint absent) produces NO finding."""
    cname_target = "liveproject.github.io"
    subdomain = "blog.example.com"
    live_body = "<html><head><title>My Live Blog</title></head><body>Welcome!</body></html>"

    responses.add(
        responses.GET,
        f"https://{subdomain}",
        body=live_body,
        status=200,
    )

    mod = TakeoverVerifierModule(http_client, Settings())
    dns_rec = DNSRecord(
        value=f"{subdomain}:CNAME:{cname_target}",
        metadata={"type": "CNAME", "record": cname_target, "domain": subdomain},
    )
    findings = list(mod.run([dns_rec]))

    # Fingerprint absent -> NOT vulnerable
    assert findings == []


def test_takeover_verifier_ignores_irrelevant_records(http_client):
    mod = TakeoverVerifierModule(http_client, Settings())
    dns_rec = DNSRecord(
        value="example.com:MX:10 mail.example.com",
        metadata={"type": "MX", "record": "mail.example.com", "domain": "example.com"},
    )
    findings = list(mod.run([dns_rec]))
    assert findings == []

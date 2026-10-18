from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Subdomain, Technology, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.web.http_inspector import HttpInspectorModule
from tddt.modules.corporate.web.tech_fingerprint import TechFingerprintModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_tech_fingerprint_reuses_inspector_response_single_call(http_client):
    """Bug §2.secondary: http_inspector + tech_fingerprint together make exactly ONE outbound call."""
    url = "https://app.example.com"
    html = """
    <html>
      <head>
        <meta name="generator" content="WordPress 6.4.2" />
      </head>
      <body>
        <div id="__reactFiber$123"></div>
      </body>
    </html>
    """
    headers = {"Server": "nginx/1.24.0", "X-Powered-By": "PHP/8.2"}
    responses.add(responses.GET, url, body=html, headers=headers, status=200)

    # 1. HttpInspector inspects subdomain
    inspector = HttpInspectorModule(http_client, Settings())
    sub = Subdomain(value="app.example.com")
    urls = list(inspector.run([sub]))
    assert len(urls) == 1
    url_entity = urls[0]

    # Exactly 1 call was made
    assert len(responses.calls) == 1

    # 2. TechFingerprint consumes the URL entity
    fingerprinter = TechFingerprintModule(http_client, Settings())
    techs = list(fingerprinter.run([url_entity]))

    # STILL exactly 1 call was made — no re-fetch!
    assert len(responses.calls) == 1

    tech_names = {t.value for t in techs}
    assert "WordPress" in tech_names
    assert "React" in tech_names
    assert "nginx" in tech_names or "Nginx" in tech_names
    assert "PHP" in tech_names
    assert all(isinstance(t, Technology) for t in techs)
    assert all(t.parent_id == url_entity.id for t in techs)


def test_tech_fingerprint_from_metadata_alone(http_client):
    mod = TechFingerprintModule(http_client, Settings())
    url_ent = URL(
        value="https://shop.example.com",
        metadata={
            "body": '<script src="https://cdn.shopify.com/theme.js"></script>',
            "headers": {"Server": "Cloudflare"},
        },
    )
    techs = list(mod.run([url_ent]))
    tech_names = {t.value for t in techs}
    assert "Shopify" in tech_names
    assert "Cloudflare" in tech_names

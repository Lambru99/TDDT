from __future__ import annotations

import codecs
import mmh3
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Technology
from tddt.core.http import HttpClient
from tddt.modules.corporate.web.favicon_recon import FaviconReconModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False, verify_tls=True)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_favicon_recon_detects_spring_boot(http_client):
    # Dummy favicon byte content
    fake_favicon = b"SPRING_BOOT_FAVICON_CONTENT"
    # Calculate its murmurhash3 over base64
    b64 = codecs.encode(fake_favicon, "base64")
    fav_hash = mmh3.hash(b64)

    # Mock /favicon.ico
    responses.add(
        responses.GET,
        "https://app.example.com/favicon.ico",
        body=fake_favicon,
        status=200,
    )

    mod = FaviconReconModule(http_client, Settings())
    # Add fake hash to signatures for testing
    mod.signatures[fav_hash] = "Spring Boot"

    domain = Domain(value="app.example.com")
    results = list(mod.run([domain]))

    assert len(results) == 1
    tech = results[0]
    assert isinstance(tech, Technology)
    assert tech.value == "Spring Boot"
    assert tech.metadata["category"] == "favicon"
    assert tech.metadata["hash"] == fav_hash
    assert tech.parent_id == domain.id


@responses.activate
def test_favicon_recon_handles_404(http_client):
    responses.add(
        responses.GET,
        "https://empty.example.com/favicon.ico",
        status=404,
    )
    responses.add(
        responses.GET,
        "http://empty.example.com/favicon.ico",
        status=404,
    )

    mod = FaviconReconModule(http_client, Settings())
    results = list(mod.run([Domain(value="empty.example.com")]))
    assert results == []

"""Tests for user service avatar_hasher module."""

import hashlib
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Service, URL
from tddt.core.http import HttpClient
from tddt.modules.user.service.avatar_hasher import ServiceAvatarHasherModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_avatar_hasher_hashes_profile_image(http_client):
    mod = ServiceAvatarHasherModule(http_client, Settings())
    service = Service(value="https://github.com/alice")

    html = """
    <html>
      <meta property="og:image" content="https://avatars.githubusercontent.com/u/12345?v=4">
    </html>
    """
    responses.add(
        responses.GET,
        "https://github.com/alice",
        body=html,
        status=200,
    )

    image_bytes = b"\x89PNG\r\n\x1a\nfakeimagebytes"
    expected_sha = hashlib.sha256(image_bytes).hexdigest()

    responses.add(
        responses.GET,
        "https://avatars.githubusercontent.com/u/12345?v=4",
        body=image_bytes,
        status=200,
    )

    entities = list(mod.run([service]))
    urls = [e for e in entities if isinstance(e, URL)]
    assert len(urls) == 1
    assert "avatars.githubusercontent.com" in urls[0].value
    assert urls[0].metadata.get("avatar_sha256") == expected_sha


@responses.activate
def test_avatar_hasher_resolves_url_from_metadata(http_client):
    """Service.value is an identifier ("GitHub:Lambru99") — the probe URL
    lives in metadata["url"]. Must dispatch there, not to the identifier."""
    mod = ServiceAvatarHasherModule(http_client, Settings())
    service = Service(
        value="GitHub:Lambru99",
        metadata={"url": "https://github.com/Lambru99", "site": "GitHub"},
    )

    html = (
        '<html><meta property="og:image" '
        'content="https://avatars.githubusercontent.com/u/42"></html>'
    )
    responses.add(
        responses.GET, "https://github.com/Lambru99", body=html, status=200,
    )
    responses.add(
        responses.GET,
        "https://avatars.githubusercontent.com/u/42",
        body=b"\x89PNGfake",
        status=200,
    )

    entities = list(mod.run([service]))
    urls = [e for e in entities if isinstance(e, URL)]
    assert len(urls) == 1
    assert "avatars.githubusercontent.com" in urls[0].value


@responses.activate
def test_avatar_hasher_skips_service_without_probe_url(http_client, caplog):
    """A Service with neither a URL-valued value nor metadata["url"] must be
    skipped silently (no WARNING, no HTTP call, no exception)."""
    import logging
    mod = ServiceAvatarHasherModule(http_client, Settings())
    service = Service(value="spotify:user@example.com", metadata={"site": "spotify"})

    with caplog.at_level(logging.WARNING, logger="tddt.modules.user.service.avatar_hasher"):
        entities = list(mod.run([service]))

    assert entities == []
    assert len(responses.calls) == 0
    assert not any(
        "No connection adapters" in r.message or "HTTP error" in r.message
        for r in caplog.records
    )

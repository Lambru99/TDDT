"""Tests for breach.gravatar module."""

import hashlib
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Email, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.breach.gravatar import GravatarModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_gravatar_finds_profile_on_200(http_client):
    mod = GravatarModule(http_client, Settings())
    email = Email(value="user@example.com")
    email_hash = hashlib.md5(b"user@example.com").hexdigest()

    url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
    responses.add(
        responses.GET,
        url,
        body=b"fake-image-bytes",
        status=200,
        content_type="image/jpeg",
    )

    entities = list(mod.run([email]))
    urls = [e for e in entities if isinstance(e, URL)]
    assert len(urls) == 1
    assert email_hash in urls[0].value
    assert urls[0].metadata.get("source") == "gravatar"


@responses.activate
def test_gravatar_empty_on_404(http_client):
    mod = GravatarModule(http_client, Settings())
    email = Email(value="nobody@example.com")
    email_hash = hashlib.md5(b"nobody@example.com").hexdigest()

    url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
    responses.add(
        responses.GET,
        url,
        status=404,
    )

    entities = list(mod.run([email]))
    assert len(entities) == 0

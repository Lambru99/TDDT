"""Tests for user.username.service_validator module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Service
from tddt.core.http import HttpClient
from tddt.modules.user.username.service_validator import ServiceValidatorModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_service_validator_promotes_on_valid_profile(http_client):
    mod = ServiceValidatorModule(http_client, Settings())
    service = Service(
        value="GitHub:bob",
        confidence=0.5,
        metadata={"url": "https://github.com/bob", "username": "bob"},
    )

    html = """
    <html>
      <head>
        <meta property="og:image" content="https://avatars.githubusercontent.com/u/12345">
        <meta name="description" content="Open source developer and security enthusiast">
      </head>
      <body>
        <span class="p-name">Bob Developer</span>
        <span class="p-nickname">bob</span>
      </body>
    </html>
    """
    responses.add(
        responses.GET,
        "https://github.com/bob",
        body=html,
        status=200,
    )

    entities = list(mod.run([service]))
    assert len(entities) == 1
    validated = entities[0]
    assert validated.confidence == 0.7
    assert validated.metadata.get("validated") is True
    assert validated.metadata.get("avatar_url") == "https://avatars.githubusercontent.com/u/12345"
    assert "Open source" in validated.metadata.get("bio", "")


@responses.activate
def test_service_validator_degrades_on_soft_404(http_client):
    """Bug FP killer: 200 OK returning 'User not found' degrades confidence to 0.1."""
    mod = ServiceValidatorModule(http_client, Settings())
    service = Service(
        value="FakeSite:ghost",
        confidence=0.5,
        metadata={"url": "https://fakesite.com/ghost", "username": "ghost"},
    )

    html = """
    <html>
      <body>
        <div class="message">404: User not found or profile does not exist</div>
      </body>
    </html>
    """
    responses.add(
        responses.GET,
        "https://fakesite.com/ghost",
        body=html,
        status=200,
    )

    entities = list(mod.run([service]))
    assert len(entities) == 1
    degraded = entities[0]
    assert degraded.confidence == 0.1
    assert degraded.metadata.get("soft_404") is True

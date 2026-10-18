"""Tests for user.phone.social_probe module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Phone, Service
from tddt.core.http import HttpClient
from tddt.modules.user.phone.social_probe import PhoneSocialProbeModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_social_probe_is_active(http_client):
    mod = PhoneSocialProbeModule(http_client, Settings())
    assert mod.active is True


@responses.activate
def test_social_probe_probes_services(http_client):
    mod = PhoneSocialProbeModule(http_client, Settings())
    phone = Phone(value="+14155552671")

    # Mock WhatsApp check
    responses.add(
        responses.GET,
        "https://api.whatsapp.com/send?phone=14155552671",
        body="<html><body>Continue to Chat</body></html>",
        status=200,
    )

    entities = list(mod.run([phone]))
    assert len(entities) >= 1
    assert any(isinstance(e, Service) and "whatsapp" in e.value.lower() for e in entities)

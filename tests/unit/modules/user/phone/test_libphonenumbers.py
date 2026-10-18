"""Tests for user.phone.libphonenumbers module."""

import pytest

from tddt.core.config import Settings
from tddt.core.entity import Phone
from tddt.core.http import HttpClient
from tddt.modules.user.phone.libphonenumbers import PhoneLibphonenumbersModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_phone_libphonenumbers_enrichment(http_client):
    mod = PhoneLibphonenumbersModule(http_client, Settings())
    phone = Phone(value="+14155552671", confidence=0.5)

    entities = list(mod.run([phone]))
    assert len(entities) == 1
    p = entities[0]
    assert isinstance(p, Phone)
    assert p.value == "+14155552671"
    assert p.confidence >= 0.8
    assert "country" in p.metadata or "valid" in p.metadata

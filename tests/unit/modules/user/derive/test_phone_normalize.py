"""Tests for user.derive.phone_normalize module."""

import pytest

from tddt.core.config import Settings
from tddt.core.entity import Phone
from tddt.core.http import HttpClient
from tddt.modules.user.derive.phone_normalize import PhoneNormalizeModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_phone_normalize_valid_e164(http_client):
    mod = PhoneNormalizeModule(http_client, Settings())
    phone = Phone(value="+39 06 69874561")

    entities = list(mod.run([phone]))
    phones = [e for e in entities if isinstance(e, Phone)]
    assert len(phones) == 1
    assert phones[0].value == "+390669874561"
    assert phones[0].confidence == 1.0


def test_phone_normalize_invalid_returns_nothing(http_client):
    mod = PhoneNormalizeModule(http_client, Settings())
    invalid_phone = Phone(value="not-a-phone-number-123")

    entities = list(mod.run([invalid_phone]))
    assert len(entities) == 0

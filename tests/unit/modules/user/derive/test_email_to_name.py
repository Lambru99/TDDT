"""Tests for user.derive.email_to_name module."""

import pytest

from tddt.core.config import Settings
from tddt.core.entity import Email, FullName
from tddt.core.http import HttpClient
from tddt.modules.user.derive.email_to_name import EmailToNameModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_email_to_name_extracts_full_name(http_client):
    mod = EmailToNameModule(http_client, Settings())
    email = Email(value="mario.rossi@example.com")

    entities = list(mod.run([email]))
    names = [e for e in entities if isinstance(e, FullName)]
    assert len(names) == 1
    assert names[0].value == "Mario Rossi"
    assert names[0].confidence == 0.3


def test_email_to_name_ignores_generic(http_client):
    mod = EmailToNameModule(http_client, Settings())
    email = Email(value="admin@example.com")

    entities = list(mod.run([email]))
    assert len(entities) == 0

"""Tests for user.derive.fullname_to_username module."""

import pytest

from tddt.core.config import Settings
from tddt.core.entity import FullName, Username
from tddt.core.http import HttpClient
from tddt.modules.user.derive.fullname_to_username import FullnameToUsernameModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_fullname_to_username_produces_at_least_15_variants(http_client):
    mod = FullnameToUsernameModule(http_client, Settings())
    fullname = FullName(value="Mario Rossi")

    entities = list(mod.run([fullname]))
    usernames = [e for e in entities if isinstance(e, Username)]

    # Plan requirement: 15 variants from "Mario Rossi"
    assert len(usernames) >= 15
    values = {u.value for u in usernames}
    assert "mariorossi" in values
    assert "mario.rossi" in values
    assert "mrossi" in values
    assert "m_rossi" in values
    assert all(u.confidence == 0.3 for u in usernames)

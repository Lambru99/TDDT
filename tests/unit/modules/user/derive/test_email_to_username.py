"""Tests for user.derive.email_to_username module."""

import pytest

from tddt.core.config import Settings
from tddt.core.entity import Email, Username
from tddt.core.http import HttpClient
from tddt.modules.user.derive.email_to_username import EmailToUsernameModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_email_to_username_produces_at_least_15_candidates(http_client):
    mod = EmailToUsernameModule(http_client, Settings())
    email = Email(value="mario.rossi@example.it")

    entities = list(mod.run([email]))
    usernames = [e for e in entities if isinstance(e, Username)]

    # Plan requirement: 15 username candidates from mario.rossi@x.it
    assert len(usernames) >= 15
    values = {u.value for u in usernames}
    assert "mario.rossi" in values
    assert "mariorossi" in values
    assert "mrossi" in values
    assert "mario_rossi" in values
    assert all(u.confidence == 0.3 for u in usernames)

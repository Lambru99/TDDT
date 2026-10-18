"""Tests for user.email.holehe module."""

from unittest.mock import patch
import pytest

from tddt.core.config import Settings
from tddt.core.entity import Email, Service
from tddt.core.http import HttpClient
from tddt.modules.user.email.holehe import HoleheModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_holehe_finds_registered_services(http_client):
    mod = HoleheModule(http_client, Settings())
    email = Email(value="test@example.com")

    mock_results = [
        {"name": "twitter", "exists": True, "rate_limit": False},
        {"name": "instagram", "exists": True, "rate_limit": False},
        {"name": "spotify", "exists": False, "rate_limit": False},
    ]

    with patch.object(mod, "_run_holehe", return_value=mock_results):
        entities = list(mod.run([email]))

    services = [e for e in entities if isinstance(e, Service)]
    assert len(services) == 2
    sites = {s.metadata.get("site") for s in services}
    assert "twitter" in sites
    assert "instagram" in sites
    assert all(s.metadata.get("exists") is True for s in services)

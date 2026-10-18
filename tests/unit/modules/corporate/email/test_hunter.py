"""Tests for email.hunter module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email, Finding
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.hunter import HunterEmailModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_hunter_missing_key_skips(http_client):
    settings = Settings(hunter="")
    mod = HunterEmailModule(http_client, settings)
    domain = Domain(value="example.com")
    entities = list(mod.run([domain]))
    assert len(entities) == 0


@responses.activate
def test_hunter_with_key_finds_emails_and_pattern(http_client):
    settings = Settings(hunter="hunter_dummy_key_123")
    mod = HunterEmailModule(http_client, settings)
    domain = Domain(value="example.com")

    api_resp = {
        "data": {
            "pattern": "{first}.{last}",
            "emails": [
                {"value": "john.doe@example.com", "first_name": "John", "last_name": "Doe"},
                {"value": "jane.smith@example.com", "first_name": "Jane", "last_name": "Smith"},
            ],
        }
    }
    responses.add(
        responses.GET,
        "https://api.hunter.io/v2/domain-search?domain=example.com&api_key=hunter_dummy_key_123&limit=100",
        json=api_resp,
        status=200,
    )

    entities = list(mod.run([domain]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    findings = [e for e in entities if isinstance(e, Finding)]

    assert "john.doe@example.com" in emails
    assert "jane.smith@example.com" in emails
    assert len(findings) == 1
    assert findings[0].metadata.get("pattern") == "{first}.{last}"
    assert domain.metadata.get("naming_pattern") == "{first}.{last}"


@responses.activate
def test_hunter_401_logs_warning(http_client, caplog):
    settings = Settings(hunter="invalid_key")
    mod = HunterEmailModule(http_client, settings)
    domain = Domain(value="example.com")

    responses.add(
        responses.GET,
        "https://api.hunter.io/v2/domain-search?domain=example.com&api_key=invalid_key&limit=100",
        status=401,
        json={"errors": [{"details": "Invalid API key"}]},
    )

    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("401" in r.message or "invalid" in r.message.lower() for r in caplog.records)

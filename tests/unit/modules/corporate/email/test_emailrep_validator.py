"""Tests for email.emailrep_validator module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.emailrep_validator import EmailRepValidatorModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_emailrep_validator_boosts_deliverable_email(http_client):
    mod = EmailRepValidatorModule(http_client, Settings())
    email = Email(value="valid.user@example.com", confidence=0.5)

    data = {
        "email": "valid.user@example.com",
        "reputation": "high",
        "suspicious": False,
        "deliverable": True,
    }
    responses.add(
        responses.GET,
        "https://emailrep.io/valid.user@example.com",
        json=data,
        status=200,
    )

    entities = list(mod.run([email]))
    assert len(entities) == 1
    assert entities[0].confidence > 0.5
    assert entities[0].metadata.get("deliverable") is True


@responses.activate
def test_emailrep_validator_degrades_suspicious_email(http_client):
    mod = EmailRepValidatorModule(http_client, Settings())
    email = Email(value="spammer@example.com", confidence=0.5)

    data = {
        "email": "spammer@example.com",
        "reputation": "low",
        "suspicious": True,
        "deliverable": False,
    }
    responses.add(
        responses.GET,
        "https://emailrep.io/spammer@example.com",
        json=data,
        status=200,
    )

    entities = list(mod.run([email]))
    assert len(entities) == 1
    assert entities[0].confidence < 0.5


@responses.activate
def test_emailrep_validator_429_logs_warning(http_client, caplog):
    mod = EmailRepValidatorModule(http_client, Settings())
    email = Email(value="rate.limited@example.com", confidence=0.5)

    responses.add(
        responses.GET,
        "https://emailrep.io/rate.limited@example.com",
        status=429,
    )

    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([email]))

    assert len(entities) == 0
    assert any("429" in r.message or "rate limit" in r.message.lower() for r in caplog.records)

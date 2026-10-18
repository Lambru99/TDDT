"""Tests for breach.dehashed_scrape module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Breach, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.breach.dehashed_scrape import DehashedScrapeModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_dehashed_scrape_missing_key_skips(http_client):
    settings = Settings(dehashed="")
    mod = DehashedScrapeModule(http_client, settings)
    email = Email(value="user@example.com")
    entities = list(mod.run([email]))
    assert len(entities) == 0


@responses.activate
def test_dehashed_scrape_finds_breaches(http_client):
    settings = Settings(dehashed="dehashed_key_xyz")
    mod = DehashedScrapeModule(http_client, settings)
    email = Email(value="user@example.com")

    payload = {
        "entries": [
            {"database_name": "Collection #1", "email": "user@example.com", "username": "user123"},
            {"database_name": "ExploitIn", "email": "user@example.com", "username": "u123"},
        ]
    }
    responses.add(
        responses.GET,
        "https://api.dehashed.com/search?query=email%3Auser%40example.com",
        json=payload,
        status=200,
    )

    entities = list(mod.run([email]))
    breaches = [e for e in entities if isinstance(e, Breach)]
    assert len(breaches) == 2
    names = {b.value for b in breaches}
    assert "Collection #1" in names
    assert "ExploitIn" in names


@responses.activate
def test_dehashed_scrape_401_logs_warning(http_client, caplog):
    settings = Settings(dehashed="invalid_key")
    mod = DehashedScrapeModule(http_client, settings)
    email = Email(value="test@example.com")

    responses.add(
        responses.GET,
        "https://api.dehashed.com/search?query=email%3Atest%40example.com",
        status=401,
    )

    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([email]))

    assert len(entities) == 0
    assert any("401" in r.message or "unauthorized" in r.message.lower() for r in caplog.records)

"""Tests for breach.hibp_scrape module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Breach, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.breach.hibp_scrape import HibpScrapeModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_hibp_scrape_missing_key_skips(http_client):
    settings = Settings(hibp="")
    mod = HibpScrapeModule(http_client, settings)
    email = Email(value="victim@example.com")
    entities = list(mod.run([email]))
    assert len(entities) == 0


@responses.activate
def test_hibp_scrape_finds_breaches(http_client):
    settings = Settings(hibp="test_hibp_key")
    mod = HibpScrapeModule(http_client, settings)
    email = Email(value="victim@example.com")

    breaches = [
        {
            "Name": "Adobe",
            "Title": "Adobe",
            "Domain": "adobe.com",
            "BreachDate": "2013-10-04",
            "PwnCount": 152445165,
            "DataClasses": ["Email addresses", "Password hints", "Passwords", "Usernames"],
        },
        {
            "Name": "LinkedIn",
            "Title": "LinkedIn",
            "Domain": "linkedin.com",
            "BreachDate": "2012-05-05",
            "PwnCount": 164611595,
            "DataClasses": ["Email addresses", "Passwords"],
        },
    ]
    responses.add(
        responses.GET,
        "https://haveibeenpwned.com/api/v3/breachedaccount/victim%40example.com?truncateResponse=false",
        json=breaches,
        status=200,
    )

    entities = list(mod.run([email]))
    breach_entities = [e for e in entities if isinstance(e, Breach)]
    assert len(breach_entities) == 2
    names = {b.value for b in breach_entities}
    assert "Adobe" in names
    assert "LinkedIn" in names


@responses.activate
def test_hibp_scrape_404_empty(http_client):
    settings = Settings(hibp="test_hibp_key")
    mod = HibpScrapeModule(http_client, settings)
    email = Email(value="clean@example.com")

    responses.add(
        responses.GET,
        "https://haveibeenpwned.com/api/v3/breachedaccount/clean%40example.com?truncateResponse=false",
        status=404,
    )

    entities = list(mod.run([email]))
    assert len(entities) == 0


@responses.activate
def test_hibp_scrape_403_logs_warning(http_client, caplog):
    settings = Settings(hibp="invalid_key")
    mod = HibpScrapeModule(http_client, settings)
    email = Email(value="test@example.com")

    responses.add(
        responses.GET,
        "https://haveibeenpwned.com/api/v3/breachedaccount/test%40example.com?truncateResponse=false",
        status=403,
    )

    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([email]))

    assert len(entities) == 0
    assert any("403" in r.message or "forbidden" in r.message.lower() for r in caplog.records)

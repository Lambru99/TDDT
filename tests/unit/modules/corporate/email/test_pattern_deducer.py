"""Tests for email.pattern_deducer module."""

import pytest

from tddt.core.config import Settings
from tddt.core.entity import Email, Finding
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.pattern_deducer import PatternDeducerModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_pattern_deducer_initial_surname(http_client):
    mod = PatternDeducerModule(http_client, Settings())
    emails = [
        Email(value="m.rossi@example.com"),
        Email(value="l.bianchi@example.com"),
        Email(value="g.verdi@example.com"),
        Email(value="info@example.com"),  # generic ignored
    ]

    findings = list(mod.run(emails))
    assert len(findings) == 1
    assert isinstance(findings[0], Finding)
    assert findings[0].metadata.get("pattern") == "{initial}.{surname}"


def test_pattern_deducer_name_surname(http_client):
    mod = PatternDeducerModule(http_client, Settings())
    emails = [
        Email(value="mario.rossi@example.com"),
        Email(value="luigi.bianchi@example.com"),
        Email(value="giuseppe.verdi@example.com"),
        Email(value="support@example.com"),
    ]

    findings = list(mod.run(emails))
    assert len(findings) == 1
    assert findings[0].metadata.get("pattern") == "{name}.{surname}"


def test_pattern_deducer_empty_when_only_generic(http_client):
    mod = PatternDeducerModule(http_client, Settings())
    emails = [
        Email(value="info@example.com"),
        Email(value="admin@example.com"),
    ]

    findings = list(mod.run(emails))
    assert len(findings) == 0

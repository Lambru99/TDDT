"""Tests for email.crtsh_san module."""

import json
import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.crtsh_san import CrtShSanModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_crtsh_san_finds_emails(http_client):
    mod = CrtShSanModule(http_client, Settings())
    domain = Domain(value="example.com", source_module="seed")

    records = [
        {"common_name": "admin@example.com", "name_value": "admin@example.com\nwww.example.com"},
        {"common_name": "example.com", "name_value": "hostmaster@example.com\nwebmaster@example.com"},
    ]
    responses.add(
        responses.GET,
        "https://crt.sh/?q=%25.example.com&output=json",
        body=json.dumps(records),
        status=200,
        content_type="application/json",
    )
    entities = list(mod.run([domain]))

    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "admin@example.com" in emails
    assert "hostmaster@example.com" in emails
    assert "webmaster@example.com" in emails


@responses.activate
def test_crtsh_san_empty(http_client):
    mod = CrtShSanModule(http_client, Settings())
    domain = Domain(value="empty.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://crt.sh/?q=%25.empty.com&output=json",
        body="[]",
        status=200,
        content_type="application/json",
    )
    entities = list(mod.run([domain]))

    assert len(entities) == 0


@responses.activate
def test_crtsh_san_503_logs_warning(http_client, caplog):
    mod = CrtShSanModule(http_client, Settings())
    domain = Domain(value="busy.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://crt.sh/?q=%25.busy.com&output=json",
        status=503,
    )
    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("503" in record.message or "busy" in record.message.lower() for record in caplog.records)

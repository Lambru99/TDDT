"""Tests for email.theharvester_asian module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.theharvester_asian import TheHarvesterAsianModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_theharvester_asian_finds_emails(http_client):
    mod = TheHarvesterAsianModule(http_client, Settings())
    domain = Domain(value="example.com", source_module="seed")

    html = """
    <html>
      <div class="result">
        <span>Contact baidu-lead@example.com for Asia Pacific enquiries</span>
      </div>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.baidu.com/s?wd=%40example.com",
        body=html,
        status=200,
    )
    entities = list(mod.run([domain]))

    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "baidu-lead@example.com" in emails


@responses.activate
def test_theharvester_asian_empty(http_client):
    mod = TheHarvesterAsianModule(http_client, Settings())
    domain = Domain(value="empty.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.baidu.com/s?wd=%40empty.com",
        body="<html><div>No content</div></html>",
        status=200,
    )
    entities = list(mod.run([domain]))

    assert len(entities) == 0


@responses.activate
def test_theharvester_asian_403_logs_warning(http_client, caplog):
    mod = TheHarvesterAsianModule(http_client, Settings())
    domain = Domain(value="blocked.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.baidu.com/s?wd=%40blocked.com",
        status=403,
    )
    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("403" in record.message or "blocked" in record.message.lower() for record in caplog.records)

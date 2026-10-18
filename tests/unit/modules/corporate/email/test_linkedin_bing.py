"""Tests for email.linkedin_bing module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email, FullName
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.linkedin_bing import LinkedInBingModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_linkedin_bing_finds_people_and_emails(http_client):
    mod = LinkedInBingModule(http_client, Settings())
    domain = Domain(value="example.com", source_module="seed")

    html = """
    <html>
      <li class="b_algo">
        <h2><a href="https://www.linkedin.com/in/jane-doe-123">Jane Doe - Chief Technology Officer - Example Corp | LinkedIn</a></h2>
        <div class="b_caption">Jane Doe leads engineering. Email: jane.doe@example.com</div>
      </li>
      <li class="b_algo">
        <h2><a href="https://www.linkedin.com/in/john-smith">John Smith - Security Engineer | LinkedIn</a></h2>
        <div class="b_caption">Working on defense.</div>
      </li>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=site%3Alinkedin.com%2Fin%2F+%22example.com%22&first=0",
        body=html,
        status=200,
    )
    entities = list(mod.run([domain]))

    names = [e.value for e in entities if isinstance(e, FullName)]
    emails = [e.value for e in entities if isinstance(e, Email)]

    assert "Jane Doe" in names
    assert "John Smith" in names
    assert "jane.doe@example.com" in emails


@responses.activate
def test_linkedin_bing_empty(http_client):
    mod = LinkedInBingModule(http_client, Settings())
    domain = Domain(value="empty.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=site%3Alinkedin.com%2Fin%2F+%22empty.com%22&first=0",
        body="<html><div>No results</div></html>",
        status=200,
    )
    entities = list(mod.run([domain]))

    assert len(entities) == 0


@responses.activate
def test_linkedin_bing_403_logs_warning(http_client, caplog):
    mod = LinkedInBingModule(http_client, Settings())
    domain = Domain(value="forbidden.com", source_module="seed")

    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=site%3Alinkedin.com%2Fin%2F+%22forbidden.com%22&first=0",
        status=403,
    )
    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("403" in record.message or "forbidden" in record.message.lower() for record in caplog.records)

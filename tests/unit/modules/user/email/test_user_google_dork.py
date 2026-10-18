"""Tests for user.email.google_dork module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Document, Email, Service, URL
from tddt.core.http import HttpClient
from tddt.modules.user.email.google_dork import UserGoogleDorkModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_user_google_dork_finds_urls_documents_and_services(http_client):
    mod = UserGoogleDorkModule(http_client, Settings())
    email = Email(value="john.doe@example.com")

    html = """
    <html>
      <a href="https://example.com/cv.pdf">Resume</a>
      <a href="https://github.com/johndoe">GitHub Profile</a>
      <a href="https://blog.johndoe.com/post-1">Personal Post</a>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.google.com/search?q=%22john.doe%40example.com%22",
        body=html,
        status=200,
    )

    entities = list(mod.run([email]))
    docs = [e for e in entities if isinstance(e, Document)]
    services = [e for e in entities if isinstance(e, Service)]
    urls = [e for e in entities if isinstance(e, URL)]

    assert len(docs) == 1
    assert "cv.pdf" in docs[0].value
    assert len(services) == 1
    assert "github.com/johndoe" in services[0].value
    assert len(urls) >= 1

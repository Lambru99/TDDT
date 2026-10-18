"""Tests for user fullname search engine dork modules."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import FullName, Service, URL
from tddt.core.http import HttpClient
from tddt.modules.user.fullname.bing_dork import FullNameBingDorkModule
from tddt.modules.user.fullname.google_dork import FullNameGoogleDorkModule
from tddt.modules.user.fullname.linkedin_bing import FullNameLinkedinBingModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_fullname_google_dork(http_client):
    mod = FullNameGoogleDorkModule(http_client, Settings())
    name = FullName(value="John Doe")

    html = """
    <html>
      <a href="https://github.com/johndoe">GitHub</a>
      <a href="https://example.org/about-john">About</a>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.google.com/search?q=%22John+Doe%22",
        body=html,
        status=200,
    )

    entities = list(mod.run([name]))
    assert any(isinstance(e, Service) and "github.com/johndoe" in e.value for e in entities)
    assert any(isinstance(e, URL) and "example.org" in e.value for e in entities)


@responses.activate
def test_fullname_bing_dork(http_client):
    mod = FullNameBingDorkModule(http_client, Settings())
    name = FullName(value="John Doe")

    html = """
    <html>
      <a href="https://twitter.com/johndoe">Twitter</a>
      <a href="https://example.com/team">Team</a>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=%22John+Doe%22",
        body=html,
        status=200,
    )

    entities = list(mod.run([name]))
    assert any(isinstance(e, Service) and "twitter.com/johndoe" in e.value for e in entities)
    assert any(isinstance(e, URL) and "example.com" in e.value for e in entities)


@responses.activate
def test_fullname_linkedin_bing(http_client):
    mod = FullNameLinkedinBingModule(http_client, Settings())
    name = FullName(value="John Doe")

    html = """
    <html>
      <a href="https://www.linkedin.com/in/john-doe-12345">Profile</a>
      <a href="https://bing.com/other">Other</a>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.bing.com/search?q=site%3Alinkedin.com%2Fin%2F+%22John+Doe%22",
        body=html,
        status=200,
    )

    entities = list(mod.run([name]))
    assert len(entities) == 1
    assert isinstance(entities[0], Service)
    assert "linkedin.com/in/john-doe-12345" in entities[0].value

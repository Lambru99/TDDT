"""Tests for user.phone.google_dork module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Phone, Service, URL
from tddt.core.http import HttpClient
from tddt.modules.user.phone.google_dork import PhoneGoogleDorkModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_phone_google_dork_finds_urls_and_services(http_client):
    mod = PhoneGoogleDorkModule(http_client, Settings())
    phone = Phone(value="+14155552671")

    html = """
    <html>
      <a href="https://wa.me/14155552671">WhatsApp</a>
      <a href="https://yellowpages.com/biz/123">YellowPages</a>
    </html>
    """
    responses.add(
        responses.GET,
        "https://www.google.com/search?q=%22%2B14155552671%22",
        body=html,
        status=200,
    )

    entities = list(mod.run([phone]))
    assert any(isinstance(e, Service) and "wa.me" in e.value for e in entities)
    assert any(isinstance(e, URL) and "yellowpages.com" in e.value for e in entities)

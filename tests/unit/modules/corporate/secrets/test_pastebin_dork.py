from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.secrets.pastebin_dork import PastebinDorkModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("html.duckduckgo.com", 1000.0)
    return client


@responses.activate
def test_pastebin_dork_finds_pastes(http_client):
    url = "https://html.duckduckgo.com/html/"
    html = """
    <html>
      <body>
        <a class="result__a" href="https://pastebin.com/aB12cD34">Leaked config for example.com</a>
        <a class="result__a" href="https://pastebin.com/xyz98765">Credentials dump</a>
        <a class="result__a" href="https://duckduckgo.com/search">Search link</a>
      </body>
    </html>
    """
    responses.add(responses.POST, url, body=html, status=200)

    mod = PastebinDorkModule(http_client, Settings())
    domain = Domain(value="example.com")
    results = list(mod.run([domain]))

    urls = [r for r in results if isinstance(r, URL)]
    assert len(urls) == 2
    values = {u.value for u in urls}
    assert "https://pastebin.com/aB12cD34" in values
    assert "https://pastebin.com/xyz98765" in values
    assert all(u.parent_id == domain.id for u in urls)


@responses.activate
def test_pastebin_dork_empty(http_client):
    url = "https://html.duckduckgo.com/html/"
    responses.add(responses.POST, url, body="<html><body>No results</body></html>", status=200)

    mod = PastebinDorkModule(http_client, Settings())
    results = list(mod.run([Domain(value="clean.example.com")]))
    assert results == []

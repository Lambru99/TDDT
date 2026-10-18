from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Secret, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.secrets.github_dork import GithubDorkModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("api.github.com", 1000.0)
    return client


@responses.activate
def test_github_dork_finds_code_leaks(http_client):
    url = "https://api.github.com/search/code"
    data = {
        "items": [
            {
                "html_url": "https://github.com/org/repo/blob/main/.env",
                "name": ".env",
                "repository": {"full_name": "org/repo"},
            }
        ]
    }
    responses.add(responses.GET, url, json=data, status=200)

    mod = GithubDorkModule(http_client, Settings())
    domain = Domain(value="example.com")
    results = list(mod.run([domain]))

    urls = [r for r in results if isinstance(r, URL)]
    assert len(urls) >= 1
    assert "https://github.com/org/repo/blob/main/.env" in {u.value for u in urls}


@responses.activate
def test_github_dork_handles_rate_limit(http_client):
    responses.add(responses.GET, "https://api.github.com/search/code", status=403)

    mod = GithubDorkModule(http_client, Settings())
    results = list(mod.run([Domain(value="example.com")]))
    assert results == []

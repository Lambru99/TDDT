from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.secrets.gitlab_dork import GitlabDorkModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    client = HttpClient(s, cache_path=tmp_path / "cache.sqlite")
    client.rate_limiter.configure("gitlab.com", 1000.0)
    return client


@responses.activate
def test_gitlab_dork_finds_projects(http_client):
    url = "https://gitlab.com/api/v4/projects"
    data = [
        {
            "id": 12345,
            "web_url": "https://gitlab.com/group/example-internal",
            "name": "example-internal",
        }
    ]
    responses.add(responses.GET, url, json=data, status=200)

    mod = GitlabDorkModule(http_client, Settings())
    domain = Domain(value="example.com")
    results = list(mod.run([domain]))

    urls = [r for r in results if isinstance(r, URL)]
    assert len(urls) == 1
    assert urls[0].value == "https://gitlab.com/group/example-internal"


@responses.activate
def test_gitlab_dork_empty(http_client):
    url = "https://gitlab.com/api/v4/projects"
    responses.add(responses.GET, url, json=[], status=200)

    mod = GitlabDorkModule(http_client, Settings())
    results = list(mod.run([Domain(value="empty.example.com")]))
    assert results == []

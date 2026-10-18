"""Tests for user.email.github_commit_search module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Email, Service, Username
from tddt.core.http import HttpClient
from tddt.modules.user.email.github_commit_search import GithubCommitSearchModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_github_commit_search_finds_user_and_service(http_client):
    settings = Settings(github="token123")
    mod = GithubCommitSearchModule(http_client, settings)
    email = Email(value="author@example.com")

    payload = {
        "items": [
            {
                "author": {
                    "login": "octoauthor",
                    "id": 12345,
                },
                "commit": {
                    "author": {
                        "name": "Octo Author",
                        "email": "author@example.com",
                    }
                },
            }
        ]
    }
    responses.add(
        responses.GET,
        "https://api.github.com/search/commits?q=author-email%3Aauthor%40example.com",
        json=payload,
        status=200,
    )

    entities = list(mod.run([email]))
    usernames = [e for e in entities if isinstance(e, Username)]
    services = [e for e in entities if isinstance(e, Service)]

    assert len(usernames) == 1
    assert usernames[0].value == "octoauthor"
    assert len(services) == 1
    assert services[0].value == "GitHub:octoauthor"

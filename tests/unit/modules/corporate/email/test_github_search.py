"""Tests for email.github_search module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.github_search import GithubSearchModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_github_search_finds_emails(http_client):
    settings = Settings(github="ghp_testtoken12345")
    mod = GithubSearchModule(http_client, settings)
    domain = Domain(value="example.com")

    search_resp = {
        "items": [
            {
                "html_url": "https://github.com/org/repo/blob/main/config.json",
            }
        ]
    }
    responses.add(
        responses.GET,
        "https://api.github.com/search/code?q=%22example.com%22+in%3Afile&per_page=30",
        json=search_resp,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://raw.githubusercontent.com/org/repo/main/config.json",
        body='{"admin": "devops@example.com"}',
        status=200,
    )

    entities = list(mod.run([domain]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "devops@example.com" in emails


@responses.activate
def test_github_search_unauthenticated_rate_limit_logs_warning(http_client, caplog):
    settings = Settings(github="")
    mod = GithubSearchModule(http_client, settings)
    domain = Domain(value="example.com")

    responses.add(
        responses.GET,
        "https://api.github.com/search/code?q=%22example.com%22+in%3Afile&per_page=30",
        status=403,
        json={"message": "API rate limit exceeded"},
    )

    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("rate limit" in r.message.lower() and "unauthenticated" in r.message.lower() for r in caplog.records)

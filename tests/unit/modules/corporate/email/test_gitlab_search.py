"""Tests for email.gitlab_search module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email
from tddt.core.http import HttpClient
from tddt.modules.corporate.email.gitlab_search import GitlabSearchModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_gitlab_search_finds_emails(http_client):
    mod = GitlabSearchModule(http_client, Settings())
    domain = Domain(value="example.com")

    projects = [
        {"description": "Repo maintained by maintainer@example.com"},
        {"description": "Secondary project"},
    ]
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects?search=example.com",
        json=projects,
        status=200,
    )

    entities = list(mod.run([domain]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "maintainer@example.com" in emails


@responses.activate
def test_gitlab_search_empty(http_client):
    mod = GitlabSearchModule(http_client, Settings())
    domain = Domain(value="empty.com")

    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects?search=empty.com",
        json=[],
        status=200,
    )

    entities = list(mod.run([domain]))
    assert len(entities) == 0


@responses.activate
def test_gitlab_search_403_logs_warning(http_client, caplog):
    mod = GitlabSearchModule(http_client, Settings())
    domain = Domain(value="blocked.com")

    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects?search=blocked.com",
        status=403,
    )

    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("403" in r.message or "forbidden" in r.message.lower() for r in caplog.records)

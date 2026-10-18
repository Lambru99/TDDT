"""Tests for user.username.gitlab_profile module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Email, Username, Website
from tddt.core.http import HttpClient
from tddt.modules.user.username.gitlab_profile import GitlabProfileModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_gitlab_profile_extracts_email_and_website(http_client):
    mod = GitlabProfileModule(http_client, Settings())
    user = Username(value="gluser", confidence=0.7)

    users_data = [
        {
            "username": "gluser",
            "name": "GL User",
            "public_email": "gluser@example.org",
            "website_url": "https://gluser.dev",
        }
    ]
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/users?username=gluser",
        json=users_data,
        status=200,
    )

    entities = list(mod.run([user]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    websites = [e.value for e in entities if isinstance(e, Website)]

    assert "gluser@example.org" in emails
    assert "https://gluser.dev" in websites


@responses.activate
def test_gitlab_profile_empty_on_unknown_user(http_client):
    mod = GitlabProfileModule(http_client, Settings())
    user = Username(value="nonexistent", confidence=0.7)

    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/users?username=nonexistent",
        json=[],
        status=200,
    )

    entities = list(mod.run([user]))
    assert len(entities) == 0

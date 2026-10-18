"""Tests for user.username.github_profile module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Email, FullName, Organization, Username, Website
from tddt.core.http import HttpClient
from tddt.modules.user.username.github_profile import GithubProfileModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_github_profile_extracts_profile_fields(http_client):
    mod = GithubProfileModule(http_client, Settings())
    user = Username(value="octocat", confidence=0.7)

    profile_data = {
        "login": "octocat",
        "name": "Monalisa Octocat",
        "company": "GitHub",
        "blog": "https://github.blog",
        "email": "octocat@github.com",
    }
    responses.add(
        responses.GET,
        "https://api.github.com/users/octocat",
        json=profile_data,
        status=200,
    )

    entities = list(mod.run([user]))
    names = [e.value for e in entities if isinstance(e, FullName)]
    emails = [e.value for e in entities if isinstance(e, Email)]
    orgs = [e.value for e in entities if isinstance(e, Organization)]
    sites = [e.value for e in entities if isinstance(e, Website)]

    assert "Monalisa Octocat" in names
    assert "octocat@github.com" in emails
    assert "GitHub" in orgs
    assert "https://github.blog" in sites


@responses.activate
def test_github_profile_falls_back_to_events_for_email(http_client):
    mod = GithubProfileModule(http_client, Settings())
    user = Username(value="developer", confidence=0.7)

    profile_data = {
        "login": "developer",
        "name": "Dev User",
        "company": "",
        "blog": "",
        "email": None,  # Hidden email on profile
    }
    responses.add(
        responses.GET,
        "https://api.github.com/users/developer",
        json=profile_data,
        status=200,
    )

    events_data = [
        {
            "type": "PushEvent",
            "payload": {
                "commits": [
                    {
                        "author": {
                            "email": "dev.user@gmail.com",
                            "name": "Dev User",
                        }
                    }
                ]
            },
        }
    ]
    responses.add(
        responses.GET,
        "https://api.github.com/users/developer/events/public",
        json=events_data,
        status=200,
    )

    entities = list(mod.run([user]))
    emails = [e.value for e in entities if isinstance(e, Email)]
    assert "dev.user@gmail.com" in emails

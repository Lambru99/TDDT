"""Tests for user.username.quick_validator module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Username
from tddt.core.http import HttpClient
from tddt.modules.user.username.quick_validator import QuickValidatorModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_quick_validator_min_confidence(http_client):
    mod = QuickValidatorModule(http_client, Settings())
    assert mod.min_confidence == 0.3


@responses.activate
def test_quick_validator_promotes_existing_username(http_client):
    mod = QuickValidatorModule(http_client, Settings())
    candidate = Username(value="torvalds", confidence=0.3)

    # 1. GitHub returns 200
    responses.add(
        responses.GET,
        "https://api.github.com/users/torvalds",
        json={"login": "torvalds", "id": 1024025},
        status=200,
    )
    # 2. GitLab returns 200 with matching user
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/users?username=torvalds",
        json=[{"username": "torvalds"}],
        status=200,
    )
    # 3. Keybase returns 200
    responses.add(
        responses.GET,
        "https://keybase.io/_/api/1.0/user/lookup.json?username=torvalds",
        json={"them": {"id": "123"}},
        status=200,
    )
    # 4. Reddit 404
    responses.add(
        responses.GET,
        "https://www.reddit.com/user/torvalds/about.json",
        status=404,
    )
    # 5. HN 200
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/user/torvalds.json",
        json={"id": "torvalds"},
        status=200,
    )

    entities = list(mod.run([candidate]))
    assert len(entities) == 1
    assert entities[0].confidence == 0.6
    assert entities[0].metadata.get("quick_validated") is True


@responses.activate
def test_quick_validator_degrades_nonsense_username(http_client):
    mod = QuickValidatorModule(http_client, Settings())
    candidate = Username(value="xyz999nonexistentuser888", confidence=0.3)

    responses.add(responses.GET, "https://api.github.com/users/xyz999nonexistentuser888", status=404)
    responses.add(responses.GET, "https://gitlab.com/api/v4/users?username=xyz999nonexistentuser888", json=[], status=200)
    responses.add(responses.GET, "https://keybase.io/_/api/1.0/user/lookup.json?username=xyz999nonexistentuser888", status=404)
    responses.add(responses.GET, "https://www.reddit.com/user/xyz999nonexistentuser888/about.json", status=404)
    responses.add(responses.GET, "https://hacker-news.firebaseio.com/v0/user/xyz999nonexistentuser888.json", body="null", status=200)

    entities = list(mod.run([candidate]))
    assert len(entities) == 1
    assert entities[0].confidence == 0.1
    assert entities[0].metadata.get("quick_validated") is False

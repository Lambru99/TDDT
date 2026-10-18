"""Tests for user.email breach/gravatar/emailrep adapters."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Breach, Email, URL
from tddt.core.http import HttpClient
from tddt.modules.user.email.dehashed_scrape import UserDehashedScrapeModule
from tddt.modules.user.email.emailrep_validator import UserEmailRepValidatorModule
from tddt.modules.user.email.gravatar import UserGravatarModule
from tddt.modules.user.email.hibp_scrape import UserHibpScrapeModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_user_hibp_adapter(http_client):
    settings = Settings(hibp="key123")
    mod = UserHibpScrapeModule(http_client, settings)
    email = Email(value="victim@example.com")

    responses.add(
        responses.GET,
        "https://haveibeenpwned.com/api/v3/breachedaccount/victim%40example.com?truncateResponse=false",
        json=[{"Name": "Dropbox"}],
        status=200,
    )

    entities = list(mod.run([email]))
    assert any(isinstance(e, Breach) and e.value == "Dropbox" for e in entities)


@responses.activate
def test_user_gravatar_adapter(http_client):
    mod = UserGravatarModule(http_client, Settings())
    email = Email(value="user@example.com")

    responses.add(
        responses.GET,
        "https://www.gravatar.com/avatar/b58996c504c5638798eb6b511e6f49af?d=404",
        status=200,
        body=b"avatar",
    )

    entities = list(mod.run([email]))
    assert any(isinstance(e, URL) and "gravatar.com" in e.value for e in entities)


@responses.activate
def test_user_emailrep_adapter(http_client):
    mod = UserEmailRepValidatorModule(http_client, Settings())
    email = Email(value="valid@example.com", confidence=0.5)

    responses.add(
        responses.GET,
        "https://emailrep.io/valid@example.com",
        json={"deliverable": True, "suspicious": False},
        status=200,
    )

    entities = list(mod.run([email]))
    assert len(entities) == 1
    assert entities[0].confidence > 0.5

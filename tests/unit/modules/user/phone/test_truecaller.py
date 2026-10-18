"""Tests for user.phone.truecaller_scrape module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import FullName, Phone
from tddt.core.http import HttpClient
from tddt.modules.user.phone.truecaller_scrape import PhoneTruecallerScrapeModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_truecaller_requires_key(http_client):
    mod = PhoneTruecallerScrapeModule(http_client, Settings())
    assert mod.requires_key == "truecaller"


@responses.activate
def test_truecaller_finds_name(http_client):
    settings = Settings(truecaller="auth-token-xyz")
    mod = PhoneTruecallerScrapeModule(http_client, settings)
    phone = Phone(value="+14155552671")

    responses.add(
        responses.GET,
        "https://search5-noneu.truecaller.com/v2/search?q=%2B14155552671",
        json={"data": [{"name": "Jane Doe", "phones": [{"e164Format": "+14155552671"}]}]},
        status=200,
    )

    entities = list(mod.run([phone]))
    names = [e for e in entities if isinstance(e, FullName)]
    assert len(names) == 1
    assert names[0].value == "Jane Doe"

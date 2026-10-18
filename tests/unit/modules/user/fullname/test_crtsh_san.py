"""Tests for user fullname crtsh_san module."""

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Domain, FullName
from tddt.core.http import HttpClient
from tddt.modules.user.fullname.crtsh_san import FullNameCrtshSanModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_fullname_crtsh_san_finds_domains(http_client):
    mod = FullNameCrtshSanModule(http_client, Settings())
    name = FullName(value="Alice Smith")

    responses.add(
        responses.GET,
        "https://crt.sh/?q=Alice+Smith&output=json",
        json=[
            {"common_name": "alicesmith.com", "name_value": "alicesmith.com\nwww.alicesmith.com"},
            {"common_name": "asmith-consulting.org", "name_value": "asmith-consulting.org"},
        ],
        status=200,
    )

    entities = list(mod.run([name]))
    domains = [e for e in entities if isinstance(e, Domain)]
    domain_values = {d.value for d in domains}
    assert "alicesmith.com" in domain_values
    assert "asmith-consulting.org" in domain_values

"""Tests for user.username.whatsmyname module."""

import json
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Service, Username
from tddt.core.http import HttpClient
from tddt.modules.user.username.whatsmyname import WhatsMyNameModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_whatsmyname_min_confidence(http_client):
    mod = WhatsMyNameModule(http_client, Settings())
    assert mod.min_confidence == 0.5


@responses.activate
def test_whatsmyname_discovers_services_from_wmn_db(http_client, tmp_path):
    # Prepare custom wmn.json
    wmn_data = {
        "sites": [
            {
                "name": "GitHub",
                "uri_check": "https://github.com/{account}",
                "e_code": 200,
                "m_string": "Not Found",
                "category": "coding",
            },
            {
                "name": "DockerHub",
                "uri_check": "https://hub.docker.com/u/{account}",
                "e_code": 200,
                "m_string": "user not found",
                "category": "dev",
            },
        ]
    }
    db_file = tmp_path / "wmn.json"
    db_file.write_text(json.dumps(wmn_data))

    mod = WhatsMyNameModule(http_client, Settings(), db_path=db_file)
    user = Username(value="alice", confidence=0.6)

    # Mock responses
    responses.add(
        responses.GET,
        "https://github.com/alice",
        body="<html><body><h1>alice</h1></body></html>",
        status=200,
    )
    responses.add(
        responses.GET,
        "https://hub.docker.com/u/alice",
        body="<html><body>user not found</body></html>",  # contains m_string -> not found
        status=200,
    )

    entities = list(mod.run([user]))
    services = [e for e in entities if isinstance(e, Service)]

    assert len(services) == 1
    assert services[0].value == "GitHub:alice"
    assert services[0].confidence == 0.5
    assert services[0].metadata.get("site") == "GitHub"
    assert services[0].metadata.get("url") == "https://github.com/alice"

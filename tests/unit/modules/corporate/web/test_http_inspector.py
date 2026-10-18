from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Subdomain, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.web.http_inspector import HttpInspectorModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False, verify_tls=True)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


@responses.activate
def test_http_inspector_produces_url_with_response_metadata(http_client):
    url = "https://sub.example.com"
    html = "<html><head><title>Test App</title></head><body><h1>Hello</h1></body></html>"
    headers = {"Server": "nginx/1.24.0", "Content-Type": "text/html"}
    responses.add(responses.GET, url, body=html, headers=headers, status=200)

    mod = HttpInspectorModule(http_client, Settings())
    sub = Subdomain(value="sub.example.com")
    results = list(mod.run([sub]))

    assert len(results) == 1
    url_ent = results[0]
    assert isinstance(url_ent, URL)
    assert url_ent.value == "https://sub.example.com"
    assert url_ent.metadata["title"] == "Test App"
    assert url_ent.metadata["server"] == "nginx/1.24.0"
    assert url_ent.metadata["body"] == html
    assert "Server" in url_ent.metadata["headers"]


@responses.activate
def test_http_inspector_falls_back_to_http(http_client):
    # https fails with connection error
    responses.add(
        responses.GET,
        "https://sub.example.com",
        body=Exception("Connection refused"),
    )
    # http succeeds
    responses.add(
        responses.GET,
        "http://sub.example.com",
        body="<html><title>Plain HTTP</title></html>",
        status=200,
    )

    mod = HttpInspectorModule(http_client, Settings())
    sub = Subdomain(value="sub.example.com")
    results = list(mod.run([sub]))

    assert len(results) == 1
    assert results[0].value == "http://sub.example.com"
    assert results[0].metadata["title"] == "Plain HTTP"


@responses.activate
def test_http_inspector_unreachable(http_client):
    responses.add(responses.GET, "https://dead.example.com", body=Exception("Connection refused"))
    responses.add(responses.GET, "http://dead.example.com", body=Exception("Connection refused"))

    mod = HttpInspectorModule(http_client, Settings())
    sub = Subdomain(value="dead.example.com")
    results = list(mod.run([sub]))
    assert results == []

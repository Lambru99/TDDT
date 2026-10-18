from __future__ import annotations

import time

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.http import DEFAULT_HOST_RATES, UA_POOL, HttpClient


@pytest.fixture
def tmp_cache(tmp_path):
    return tmp_path / "http_cache.sqlite"


@pytest.fixture
def settings_default():
    return Settings()


@pytest.fixture
def settings_no_cache():
    s = Settings()
    s.cache_enabled = False
    return s


# ──────────────────────────────────────────────────────────────────────────────
# Basic GET
# ──────────────────────────────────────────────────────────────────────────────


@responses.activate
def test_get_200_returns_response(settings_default, tmp_cache):
    responses.add(responses.GET, "https://example.test/ok", json={"ok": True}, status=200)
    client = HttpClient(settings_default, cache_path=tmp_cache)
    r = client.get("https://example.test/ok", host_hint="rate_disabled.test")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


# ──────────────────────────────────────────────────────────────────────────────
# Retry configuration (behavior tested in Phase 5 integration tests —
# the `responses` library mocks at the adapter level, bypassing urllib3.Retry)
# ──────────────────────────────────────────────────────────────────────────────


def test_retry_adapter_configured(settings_no_cache, tmp_cache):
    client = HttpClient(settings_no_cache, cache_path=tmp_cache)
    adapter = client.session.get_adapter("https://example.test/")
    retry = adapter.max_retries
    assert retry.total == 3
    assert 429 in retry.status_forcelist
    assert 500 in retry.status_forcelist
    assert 502 in retry.status_forcelist
    assert 503 in retry.status_forcelist
    assert 504 in retry.status_forcelist


def test_retry_honors_retry_after_header(settings_no_cache, tmp_cache):
    client = HttpClient(settings_no_cache, cache_path=tmp_cache)
    adapter = client.session.get_adapter("https://example.test/")
    assert adapter.max_retries.respect_retry_after_header is True


def test_retry_backoff_factor(settings_no_cache, tmp_cache):
    client = HttpClient(settings_no_cache, cache_path=tmp_cache)
    adapter = client.session.get_adapter("https://example.test/")
    assert adapter.max_retries.backoff_factor == 0.5


# ──────────────────────────────────────────────────────────────────────────────
# Cache
# ──────────────────────────────────────────────────────────────────────────────


@responses.activate
def test_cache_hits_second_call(settings_default, tmp_cache):
    responses.add(responses.GET, "https://example.test/cached", json={"v": 1}, status=200)
    client = HttpClient(settings_default, cache_path=tmp_cache)
    r1 = client.get("https://example.test/cached", host_hint="rate_disabled.test")
    r2 = client.get("https://example.test/cached", host_hint="rate_disabled.test")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert len(responses.calls) == 1  # second call served from cache


@responses.activate
def test_no_cache_when_disabled(settings_no_cache, tmp_cache):
    responses.add(responses.GET, "https://example.test/x", json={"v": 1}, status=200)
    responses.add(responses.GET, "https://example.test/x", json={"v": 2}, status=200)
    client = HttpClient(settings_no_cache, cache_path=tmp_cache)
    client.get("https://example.test/x", host_hint="rate_disabled.test")
    client.get("https://example.test/x", host_hint="rate_disabled.test")
    assert len(responses.calls) == 2


# ──────────────────────────────────────────────────────────────────────────────
# TLS verify + proxy + UA
# ──────────────────────────────────────────────────────────────────────────────


def test_tls_verify_default_true(settings_default, tmp_cache):
    client = HttpClient(settings_default, cache_path=tmp_cache)
    assert client.session.verify is True


def test_insecure_flag_disables_verify(tmp_cache):
    s = Settings()
    s.verify_tls = False
    client = HttpClient(s, cache_path=tmp_cache)
    assert client.session.verify is False


def test_proxy_passed_to_session(tmp_cache):
    s = Settings()
    s.proxy = "http://localhost:8080"
    client = HttpClient(s, cache_path=tmp_cache)
    assert client.session.proxies.get("http") == "http://localhost:8080"
    assert client.session.proxies.get("https") == "http://localhost:8080"


def test_user_agent_from_pool(settings_default, tmp_cache):
    client = HttpClient(settings_default, cache_path=tmp_cache)
    assert client.session.headers["User-Agent"] in UA_POOL


# ──────────────────────────────────────────────────────────────────────────────
# Rate limit
# ──────────────────────────────────────────────────────────────────────────────


@responses.activate
def test_rate_limit_enforced_per_host(settings_no_cache, tmp_cache):
    """4 GETs to a host configured at 2 req/s take >=1.0s total."""
    responses.add(responses.GET, "https://slow.test/x", status=200, body="ok")
    responses.add(responses.GET, "https://slow.test/x", status=200, body="ok")
    responses.add(responses.GET, "https://slow.test/x", status=200, body="ok")
    responses.add(responses.GET, "https://slow.test/x", status=200, body="ok")
    client = HttpClient(settings_no_cache, cache_path=tmp_cache)
    client.rate_limiter.configure("slow.test", 2.0)
    start = time.monotonic()
    for _ in range(4):
        client.get("https://slow.test/x")
    elapsed = time.monotonic() - start
    assert elapsed >= 1.0


def test_default_host_rates_registered(settings_default, tmp_cache):
    """Pre-registered host rates per spec §6.1."""
    client = HttpClient(settings_default, cache_path=tmp_cache)
    for host in ["crt.sh", "api.github.com", "ip-api.com", "web.archive.org"]:
        assert host in DEFAULT_HOST_RATES


def test_github_token_boosts_github_rate(tmp_cache):
    s = Settings()
    s.github = "ghp_test"
    client = HttpClient(s, cache_path=tmp_cache)
    # With token, api.github.com rate is boosted to 10 req/s (vs 2 keyless).
    assert client.rate_limiter._rates["api.github.com"] >= 10.0  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────


def test_get_client_requires_init():
    from tddt.core import http as http_module

    http_module.reset_client()
    with pytest.raises(RuntimeError):
        http_module.get_client()


def test_init_and_get_client_returns_same_instance(settings_default, tmp_cache):
    from tddt.core import http as http_module

    http_module.reset_client()
    c = http_module.init_client(settings_default, cache_path=tmp_cache)
    assert http_module.get_client() is c
    http_module.reset_client()

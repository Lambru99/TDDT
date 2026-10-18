"""Shared HTTP client: session + retry + rate-limit + cache + UA pool.

Thread-safe for concurrent use from a ThreadPoolExecutor. Rate limits are
host-scoped; the client extracts the host from the URL unless `host_hint` is
passed explicitly (useful for CDN-fronted endpoints that share a backend).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from tddt.core.config import Settings
from tddt.core.logger import get_logger
from tddt.core.rate_limit import RateLimiter

_log = get_logger(__name__)


UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
    "Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]


# Pre-registered host rate limits (req/sec) per spec §6.1.
DEFAULT_HOST_RATES: dict[str, float] = {
    "crt.sh": 0.5,
    "bing.com": 1.0,
    "www.bing.com": 1.0,
    "duckduckgo.com": 1.0,
    "html.duckduckgo.com": 1.0,
    "api.github.com": 2.0,
    "ip-api.com": 0.75,
    "web.archive.org": 1.0,
    "index.commoncrawl.org": 1.0,
    "otx.alienvault.com": 1.0,
    "urlscan.io": 1.0,
    "internetdb.shodan.io": 1.0,
    "api.hunter.io": 1.0,
    "phonebook.cz": 1.0,
    "rapiddns.io": 1.0,
    "buckets.grayhatwarfare.com": 1.0,
    "services.nvd.nist.gov": 1.0,
}

_RETRY_STATUSES = (429, 500, 502, 503, 504)


class HttpClient:
    """Session wrapper with retry adapter + cache + per-host rate limiting.

    Rate limit is enforced BEFORE the HTTP call (blocking). Cache (if enabled)
    is in front of the HTTP adapter: a cache hit skips both the rate limiter
    and the network.
    """

    def __init__(
        self,
        settings: Settings,
        cache_path: Path | None = None,
    ) -> None:
        self.settings = settings
        self.session = self._build_session(settings, cache_path)
        self.rate_limiter = RateLimiter(DEFAULT_HOST_RATES.copy())
        if settings.github:
            # Authenticated GitHub rate is 10 req/s (5000/h).
            self.rate_limiter.configure("api.github.com", 10.0)

    # ── Session construction ────────────────────────────────────────────────

    def _build_session(
        self,
        settings: Settings,
        cache_path: Path | None,
    ) -> requests.Session:
        if settings.cache_enabled and cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            session: requests.Session = requests_cache.CachedSession(
                str(cache_path.with_suffix("")),
                backend="sqlite",
                expire_after=1800,  # 30 min default (host-level TTL in a later task)
                allowable_methods=("GET", "HEAD"),
                allowable_codes=(200,),
            )
        else:
            session = requests.Session()

        retry = Retry(
            total=3,
            status_forcelist=list(_RETRY_STATUSES),
            backoff_factor=0.5,
            respect_retry_after_header=True,
            allowed_methods=frozenset(["GET", "HEAD", "OPTIONS", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        session.verify = settings.verify_tls
        if settings.proxy:
            session.proxies.update({"http": settings.proxy, "https": settings.proxy})

        session.headers["User-Agent"] = random.choice(UA_POOL)
        session.headers["Accept"] = "application/json, text/html, */*"

        return session

    # ── Request methods ─────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        url: str,
        host_hint: str | None = None,
        **kw: Any,
    ) -> requests.Response:
        parsed = urlparse(url)
        host = host_hint or parsed.hostname or ""
        if host:
            self.rate_limiter.acquire(host)
        kw.setdefault("timeout", self.settings.timeout)
        # Log without the query string: API keys and tokens often live there.
        safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.scheme else url
        _log.debug("%s %s", method, safe_url)
        return self.session.request(method, url, **kw)

    def get(self, url: str, host_hint: str | None = None, **kw: Any) -> requests.Response:
        return self._request("GET", url, host_hint=host_hint, **kw)

    def post(self, url: str, host_hint: str | None = None, **kw: Any) -> requests.Response:
        return self._request("POST", url, host_hint=host_hint, **kw)

    def head(self, url: str, host_hint: str | None = None, **kw: Any) -> requests.Response:
        return self._request("HEAD", url, host_hint=host_hint, **kw)

    def close(self) -> None:
        self.session.close()


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_client: HttpClient | None = None


def init_client(settings: Settings, cache_path: Path | None = None) -> HttpClient:
    global _client
    if _client is not None:
        _client.close()
    _client = HttpClient(settings, cache_path=cache_path)
    return _client


def get_client() -> HttpClient:
    if _client is None:
        raise RuntimeError("HttpClient not initialized; call init_client() first")
    return _client


def reset_client() -> None:
    """Testing helper: tear down the singleton."""
    global _client
    if _client is not None:
        _client.close()
        _client = None

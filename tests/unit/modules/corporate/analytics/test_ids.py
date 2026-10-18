from __future__ import annotations

import pytest

from tddt.core.config import Settings
from tddt.core.entity import TrackerID, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.analytics.ids import AnalyticsIdsModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_analytics_ids_extracts_trackers(http_client):
    mod = AnalyticsIdsModule(http_client, Settings())
    html = """
    <html>
      <head>
        <script>
          gtag('config', 'UA-12345678-1');
          gtag('config', 'G-ABCDEF1234');
        </script>
        <script src="https://www.googletagmanager.com/gtm.js?id=GTM-ABCD123"></script>
        <script data-ad-client="pub-1234567890123456" async src="https://pagead2.googlesyndication.com"></script>
      </head>
      <body></body>
    </html>
    """
    url_ent = URL(
        value="https://example.com",
        metadata={"body": html, "headers": {}},
    )
    trackers = list(mod.run([url_ent]))

    values = {t.value for t in trackers if isinstance(t, TrackerID)}
    assert "UA-12345678-1" in values
    assert "G-ABCDEF1234" in values
    assert "GTM-ABCD123" in values
    assert "pub-1234567890123456" in values
    assert all(t.parent_id == url_ent.id for t in trackers)


def test_analytics_ids_empty_when_no_trackers(http_client):
    mod = AnalyticsIdsModule(http_client, Settings())
    url_ent = URL(
        value="https://clean.example.com",
        metadata={"body": "<html><body>Clean page</body></html>", "headers": {}},
    )
    trackers = list(mod.run([url_ent]))
    assert trackers == []

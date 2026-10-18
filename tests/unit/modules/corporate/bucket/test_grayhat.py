"""Tests for bucket.grayhat module."""

import logging
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Bucket, Domain
from tddt.core.http import HttpClient
from tddt.modules.corporate.bucket.grayhat import GrayhatBucketModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_grayhat_missing_key_skips(http_client):
    settings = Settings(grayhat="")
    mod = GrayhatBucketModule(http_client, settings)
    domain = Domain(value="example.com")
    entities = list(mod.run([domain]))
    assert len(entities) == 0


@responses.activate
def test_grayhat_finds_buckets(http_client):
    settings = Settings(grayhat="gh_test_key_123")
    mod = GrayhatBucketModule(http_client, settings)
    domain = Domain(value="example.com")

    payload = {
        "buckets": [
            {
                "bucket": "example-backup",
                "cloud": "aws",
                "url": "https://example-backup.s3.amazonaws.com/",
            },
            {
                "bucket": "example-assets",
                "cloud": "gcp",
                "url": "https://storage.googleapis.com/example-assets/",
            },
        ]
    }
    responses.add(
        responses.GET,
        "https://buckets.grayhatwarfare.com/api/v1/buckets/example.com",
        json=payload,
        status=200,
    )

    entities = list(mod.run([domain]))
    buckets = [e for e in entities if isinstance(e, Bucket)]
    assert len(buckets) == 2
    urls = {b.value for b in buckets}
    assert "https://example-backup.s3.amazonaws.com/" in urls
    assert "https://storage.googleapis.com/example-assets/" in urls


@responses.activate
def test_grayhat_403_logs_warning(http_client, caplog):
    settings = Settings(grayhat="invalid_key")
    mod = GrayhatBucketModule(http_client, settings)
    domain = Domain(value="example.com")

    responses.add(
        responses.GET,
        "https://buckets.grayhatwarfare.com/api/v1/buckets/example.com",
        status=403,
    )

    with caplog.at_level(logging.WARNING):
        entities = list(mod.run([domain]))

    assert len(entities) == 0
    assert any("403" in r.message or "forbidden" in r.message.lower() for r in caplog.records)

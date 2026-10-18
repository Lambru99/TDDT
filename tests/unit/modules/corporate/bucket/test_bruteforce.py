"""Tests for bucket.bruteforce module."""

import time
import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Bucket, Domain
from tddt.core.http import HttpClient
from tddt.modules.corporate.bucket.bruteforce import BucketBruteforceModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_bucket_bruteforce_active_attribute(http_client):
    mod = BucketBruteforceModule(http_client, Settings())
    assert mod.active is True


@responses.activate
def test_bucket_bruteforce_discovers_open_and_protected_buckets(http_client):
    mod = BucketBruteforceModule(http_client, Settings())
    domain = Domain(value="acme.com")

    # Mock candidate URLs
    responses.add(
        responses.GET,
        "https://acme.s3.amazonaws.com/",
        body="<ListBucketResult>files...</ListBucketResult>",
        status=200,
    )
    responses.add(
        responses.GET,
        "https://acme-backup.s3.amazonaws.com/",
        status=403,
    )
    responses.add(
        responses.GET,
        "https://storage.googleapis.com/acme/",
        status=404,
    )

    entities = list(mod._probe_urls(domain, [
        "https://acme.s3.amazonaws.com/",
        "https://acme-backup.s3.amazonaws.com/",
        "https://storage.googleapis.com/acme/",
    ]))

    buckets = [e for e in entities if isinstance(e, Bucket)]
    assert len(buckets) == 2
    by_url = {b.value: b for b in buckets}
    assert by_url["https://acme.s3.amazonaws.com/"].metadata.get("status") == 200
    assert by_url["https://acme-backup.s3.amazonaws.com/"].metadata.get("status") == 403


@responses.activate
def test_bucket_bruteforce_100_urls_parallel_under_10s(http_client):
    """Bug §2.12 fix verification: 100 candidate URLs tried concurrently in < 10s."""
    mod = BucketBruteforceModule(http_client, Settings())
    domain = Domain(value="target.com")

    # Generate 100 test URLs
    test_urls = [f"https://target-test-{i}.s3.amazonaws.com/" for i in range(100)]

    def delayed_callback(request):
        time.sleep(0.02)  # 20ms delay each. Serially: 100 * 0.02s = 2.0s minimum.
        return (404, {}, "Not Found")

    for url in test_urls:
        responses.add_callback(
            responses.GET,
            url,
            callback=delayed_callback,
        )

    start = time.monotonic()
    entities = list(mod._probe_urls(domain, test_urls, max_workers=20))
    elapsed = time.monotonic() - start

    assert elapsed < 10.0, f"Expected 100 URLs to complete in <10s with 20 threads, took {elapsed:.2f}s"
    assert len(entities) == 0

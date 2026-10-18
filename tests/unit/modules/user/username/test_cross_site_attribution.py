"""Tests for user.username.cross_site_attribution module."""

import pytest

from tddt.core.config import Settings
from tddt.core.entity import Service
from tddt.core.http import HttpClient
from tddt.modules.user.username.cross_site_attribution import CrossSiteAttributionModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_cross_site_attribution_batch_size(http_client):
    mod = CrossSiteAttributionModule(http_client, Settings())
    assert mod.batch_size == 0


def test_cross_site_attribution_boosts_cluster_of_3_or_more(http_client):
    """Cluster boost with 3 Services sharing avatar hash -> all confidence +0.3."""
    mod = CrossSiteAttributionModule(http_client, Settings())

    s1 = Service(
        value="GitHub:user",
        confidence=0.6,
        metadata={"avatar_hash": "hash_abc_123", "site": "GitHub"},
    )
    s2 = Service(
        value="GitLab:user",
        confidence=0.6,
        metadata={"avatar_hash": "hash_abc_123", "site": "GitLab"},
    )
    s3 = Service(
        value="Reddit:user",
        confidence=0.6,
        metadata={"avatar_hash": "hash_abc_123", "site": "Reddit"},
    )
    s4 = Service(
        value="SoloSite:user",
        confidence=0.5,
        metadata={"avatar_hash": "different_hash", "site": "SoloSite"},
    )

    entities = list(mod.run([s1, s2, s3, s4]))
    by_val = {s.value: s for s in entities if isinstance(s, Service)}

    # The 3 in the cluster boosted from 0.6 -> 0.9 (+0.3)
    assert by_val["GitHub:user"].confidence == 0.9
    assert by_val["GitLab:user"].confidence == 0.9
    assert by_val["Reddit:user"].confidence == 0.9
    assert by_val["GitHub:user"].metadata.get("cluster_size") == 3

    # SoloSite remains unboosted (cluster size 1 < 3)
    assert by_val["SoloSite:user"].confidence == 0.5

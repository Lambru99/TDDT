"""Cross-site attribution and identity clustering module (Core FP killer layer 3)."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Service
from tddt.core.module import BaseModule, register_module


@register_module(
    name="user.username.cross_site_attribution",
    mode=["user"],
    consumes=[Service],
    produces=[Service],
    batch_size=0,
    active=False,
    requires_key=None,
)
class CrossSiteAttributionModule(BaseModule):
    """Clusters validated services by avatar hash and bio, boosting high-confidence matches."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        services: list[Service] = [e for e in entities if isinstance(e, Service)]
        if not services:
            return

        # Cluster by avatar_hash
        avatar_clusters: dict[str, list[Service]] = defaultdict(list)
        for s in services:
            h = s.metadata.get("avatar_hash")
            if h:
                avatar_clusters[h].append(s)

        boosted_ids: dict[str, int] = {}
        for h, cluster in avatar_clusters.items():
            if len(cluster) >= 3:
                for s in cluster:
                    boosted_ids[s.id] = len(cluster)

        for s in services:
            if s.id in boosted_ids:
                cluster_size = boosted_ids[s.id]
                new_conf = round(min(1.0, s.confidence + 0.3), 3)
                meta = dict(s.metadata)
                meta["cluster_size"] = cluster_size
                yield dataclasses.replace(s, confidence=new_conf, metadata=meta)
            else:
                yield s

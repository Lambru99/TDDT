"""Analytics and tracking ID extraction module.

Consumes URL entities, reuses cached HTML body (or fetches if absent), and
extracts Google Analytics (UA, G-Tag), Google Tag Manager (GTM), and
AdSense publisher IDs using regex patterns.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, TrackerID, URL
from tddt.core.module import BaseModule, register_module

TRACKER_PATTERNS = {
    "UA-Code": r"UA-\d{4,10}-\d{1,4}",
    "G-Tag": r"G-[A-Z0-9]{6,12}",
    "AdSense": r"pub-\d{10,20}",
    "GTM": r"GTM-[A-Z0-9]{4,10}",
}


@register_module(
    name="corporate.analytics.ids",
    mode=["corporate"],
    consumes=[URL],
    produces=[TrackerID],
    active=False,
    requires_key=None,
)
class AnalyticsIdsModule(BaseModule):
    """Extracts tracking and analytics IDs from page markup."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, URL):
                continue

            body: str = entity.metadata.get("body", "")
            if not body:
                try:
                    resp = self.client.get(entity.value)
                    body = resp.text
                except Exception:
                    self.log.debug("analytics_ids failed to fetch %s", entity.value)
                    continue

            seen: set[str] = set()
            for tracker_type, pattern in TRACKER_PATTERNS.items():
                matches = re.findall(pattern, body)
                for tid in matches:
                    if tid not in seen:
                        seen.add(tid)
                        yield TrackerID(
                            value=tid,
                            parent_id=entity.id,
                            source_module=self.name,
                            metadata={"type": tracker_type, "url": entity.value},
                        )

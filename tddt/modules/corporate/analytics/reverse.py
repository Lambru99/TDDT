"""Reverse tracker search module.

Queries public search (DuckDuckGo HTML) with tracking IDs (UA, GTM, AdSense)
to find other domains owned or operated by the same organization.
Produces Domain entities.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Domain, TrackerID
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.analytics.reverse",
    mode=["corporate"],
    consumes=[TrackerID],
    produces=[Domain],
    active=False,
    requires_key=None,
)
class AnalyticsReverseModule(BaseModule):
    """Discovers correlated domains via reverse tracking ID search."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, TrackerID):
                continue
            tid = entity.value.strip()

            url = "https://html.duckduckgo.com/html/"
            data = {"q": f'"{tid}"'}

            try:
                resp = self.client.post(url, data=data, host_hint="html.duckduckgo.com")
            except Exception:
                self.log.warning("analytics_reverse request failed for %s", tid, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.debug("analytics_reverse status %d for %s", resp.status_code, tid)
                continue

            try:
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception:
                self.log.debug("HTML parsing failed in analytics_reverse for %s", tid)
                continue

            seen: set[str] = set()
            for link in soup.find_all("a", class_="result__a"):
                href = link.get("href", "")
                if href and href.startswith("http"):
                    parsed = urlparse(href)
                    host = (parsed.hostname or "").strip().lower()
                    if host and "duckduckgo" not in host and host not in seen:
                        seen.add(host)
                        yield Domain(
                            value=host,
                            parent_id=entity.id,
                            source_module=self.name,
                            metadata={"via_tracker": tid},
                        )

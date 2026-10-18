"""Common Crawl CDX archive harvester module.

Discovers historical URLs indexed by Common Crawl.
Identifies juicy and sensitive file extensions.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, URL
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.wayback.wayback_machine import is_juicy


@register_module(
    name="corporate.wayback.commoncrawl",
    mode=["corporate"],
    consumes=[Domain],
    produces=[URL],
    active=False,
    requires_key=None,
)
class CommonCrawlModule(BaseModule):
    """Harvests historical URLs from Common Crawl index."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            try:
                info_resp = self.client.get(
                    "https://index.commoncrawl.org/collinfo.json",
                    host_hint="index.commoncrawl.org",
                    timeout=10,
                )
                if info_resp.status_code != 200:
                    continue
                indexes = info_resp.json()
                if not indexes or not isinstance(indexes, list):
                    continue
                latest_api = indexes[0].get("cdx-api")
                if not latest_api:
                    continue
            except Exception:
                self.log.debug("Failed to fetch Common Crawl index metadata")
                continue

            params = {
                "url": f"*.{domain}/*",
                "output": "json",
                "fl": "url",
                "filter": "status:200",
                "limit": 1000,
                "collapse": "urlkey",
            }

            try:
                resp = self.client.get(latest_api, params=params, host_hint="index.commoncrawl.org")
            except Exception:
                self.log.warning("Common Crawl query failed for %s", domain, exc_info=True)
                continue

            if resp.status_code != 200:
                continue

            seen: set[str] = set()
            for line in resp.text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    u = obj.get("url", "").strip()
                    if u and u not in seen:
                        seen.add(u)
                        yield URL(
                            value=u,
                            parent_id=entity.id,
                            source_module=self.name,
                            metadata={
                                "domain": domain,
                                "source": "commoncrawl",
                                "juicy": is_juicy(u),
                            },
                        )
                except Exception:
                    self.log.debug("Failed to parse Common Crawl JSON line: %s", line[:50])

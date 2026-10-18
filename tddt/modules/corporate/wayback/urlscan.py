"""urlscan.io search archive harvester module.

Discovers scanned URLs from urlscan.io free public search API.
Optionally uses URLScan API key if configured.
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, URL
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.wayback.wayback_machine import is_juicy


@register_module(
    name="corporate.wayback.urlscan",
    mode=["corporate"],
    consumes=[Domain],
    produces=[URL],
    active=False,
    requires_key=None,
)
class UrlscanModule(BaseModule):
    """Harvests URLs from public urlscan.io scan history."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            url = "https://urlscan.io/api/v1/search/"
            headers = {"Content-Type": "application/json"}
            api_key = getattr(self.settings, "urlscan", None)
            if api_key:
                headers["API-Key"] = api_key

            params = {
                "q": f"domain:{domain}",
                "size": 100,
            }

            try:
                resp = self.client.get(
                    url,
                    headers=headers,
                    params=params,
                    host_hint="urlscan.io",
                )
            except Exception:
                self.log.warning("urlscan query failed for %s", domain, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.debug("urlscan status %d for %s", resp.status_code, domain)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("urlscan invalid JSON for %s", domain)
                continue

            results = data.get("results", [])
            seen: set[str] = set()
            for r in results:
                if not isinstance(r, dict):
                    continue
                page_info = r.get("page", {})
                u = page_info.get("url", "").strip()
                if u and u not in seen:
                    seen.add(u)
                    yield URL(
                        value=u,
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={
                            "domain": domain,
                            "source": "urlscan",
                            "juicy": is_juicy(u),
                        },
                    )

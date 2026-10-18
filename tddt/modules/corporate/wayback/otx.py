"""AlienVault OTX URL list harvester module.

Discovers historical URLs indexed by AlienVault OTX for target domains.
Requires an optional OTX API key (configured in settings.otx).
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, URL
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.wayback.wayback_machine import is_juicy


@register_module(
    name="corporate.wayback.otx",
    mode=["corporate"],
    consumes=[Domain],
    produces=[URL],
    active=False,
    requires_key="otx",
)
class OtxWaybackModule(BaseModule):
    """Harvests historical URLs from AlienVault OTX."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        api_key = getattr(self.settings, "otx", None)

        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            url = f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/url_list"
            headers = {}
            if api_key:
                headers["X-OTX-API-KEY"] = api_key

            seen: set[str] = set()
            page = 1
            while page <= 5:
                try:
                    resp = self.client.get(
                        url,
                        headers=headers,
                        params={"limit": 500, "page": page},
                        host_hint="otx.alienvault.com",
                    )
                except Exception:
                    self.log.warning("OTX url_list request failed for %s", domain, exc_info=True)
                    break

                if resp.status_code != 200:
                    break

                try:
                    data = resp.json()
                except Exception:
                    self.log.debug("OTX invalid JSON for %s", domain)
                    break

                url_list = data.get("url_list", [])
                if not url_list:
                    break

                for entry in url_list:
                    if not isinstance(entry, dict):
                        continue
                    u = entry.get("url", "").strip()
                    if u and u not in seen:
                        seen.add(u)
                        yield URL(
                            value=u,
                            parent_id=entity.id,
                            source_module=self.name,
                            metadata={
                                "domain": domain,
                                "source": "otx",
                                "juicy": is_juicy(u),
                            },
                        )

                if not data.get("has_next"):
                    break
                page += 1

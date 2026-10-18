"""ip-api.com batch geolocation and ASN enrichment module.

Enriches IPAddress entities with country, ISP, organization, and ASN information
using the batch endpoint.
Fixes bug §2.6: HTTPS is strictly required for ip-api.com queries.
Processes up to 100 IPs per batch request.
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, IPAddress
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.netblock.ipapi",
    mode=["corporate"],
    consumes=[IPAddress],
    produces=[IPAddress],
    active=False,
    requires_key=None,
    batch_size=100,
)
class IpApiModule(BaseModule):
    """Enriches IPAddress entities via https://ip-api.com/batch."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        ip_map: dict[str, IPAddress] = {}
        for entity in entities:
            if isinstance(entity, IPAddress):
                ip_map[entity.value.strip()] = entity

        if not ip_map:
            return

        url = "https://ip-api.com/batch"
        fields = "status,message,query,countryCode,isp,org,as"
        payload = [{"query": ip, "fields": fields} for ip in ip_map]

        try:
            resp = self.client.post(url, json=payload, host_hint="ip-api.com")
        except Exception:
            self.log.warning("ipapi batch request failed", exc_info=True)
            return

        if resp.status_code == 429:
            self.log.warning("ipapi rate limit (429) hit; backing off")
            return

        if resp.status_code != 200:
            self.log.warning("ipapi returned unexpected status %d", resp.status_code)
            return

        try:
            items = resp.json()
        except Exception:
            self.log.warning("ipapi returned invalid JSON", exc_info=True)
            return

        if not isinstance(items, list):
            return

        for item in items:
            if not isinstance(item, dict):
                continue
            query_ip = item.get("query", "").strip()
            entity = ip_map.get(query_ip)
            if not entity:
                continue

            if item.get("status") == "success":
                entity.metadata.update(
                    {
                        "country": item.get("countryCode"),
                        "isp": item.get("isp"),
                        "org": item.get("org"),
                        "asn": item.get("as"),
                    }
                )
            else:
                entity.metadata["ipapi_status"] = item.get("message", "unknown")
            yield entity

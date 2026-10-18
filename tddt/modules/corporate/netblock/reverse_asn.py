"""Reverse ASN and BGP prefix expansion module.

Queries HackerTarget AS lookup for IPAddress entities to extract ASN,
autonomous system organization, and BGP network prefix.
Gracefully handles rate limits (429 and quota exhaustion).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, IPAddress
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.netblock.reverse_asn",
    mode=["corporate"],
    consumes=[IPAddress],
    produces=[IPAddress],
    active=False,
    requires_key=None,
    batch_size=1,
)
class ReverseAsnModule(BaseModule):
    """Enriches IPAddress entities with ASN and BGP prefix information."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, IPAddress):
                continue
            ip = entity.value.strip()
            url = f"https://api.hackertarget.com/aslookup/?q={ip}"

            try:
                resp = self.client.get(url, host_hint="api.hackertarget.com")
            except Exception:
                self.log.warning("reverse_asn query failed for %s", ip, exc_info=True)
                continue

            if resp.status_code == 429:
                self.log.warning("reverse_asn rate limit (429) hit for %s", ip)
                continue

            if resp.status_code != 200:
                self.log.warning("reverse_asn returned status %d for %s", resp.status_code, ip)
                continue

            text = resp.text
            if "API count exceeded" in text:
                self.log.warning("reverse_asn API quota exceeded for %s", ip)
                continue

            try:
                reader = csv.reader(io.StringIO(text))
                for row in reader:
                    # Expected format: "IP", "AS", "AS Name", "BGP Prefix"
                    if len(row) >= 4:
                        asn = row[1].strip().lstrip("AS")
                        as_name = row[2].strip()
                        bgp_prefix = row[3].strip()
                        entity.metadata.update(
                            {
                                "asn": asn,
                                "as_name": as_name,
                                "bgp_prefix": bgp_prefix,
                            }
                        )
                        yield entity
                        break
            except Exception:
                self.log.warning("Failed to parse reverse_asn output for %s", ip, exc_info=True)

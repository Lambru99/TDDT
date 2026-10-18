"""AlienVault OTX passive DNS subdomain enumeration module.

Queries AlienVault OTX free passive DNS API for known subdomains.
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Subdomain
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.subdomain.otx_passive_dns",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Subdomain],
    active=False,
    requires_key=None,
)
class OtxPassiveDnsSubdomain(BaseModule):
    """Enumerates subdomains using AlienVault OTX passive DNS."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()
            url = f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns"
            try:
                resp = self.client.get(url, host_hint="otx.alienvault.com")
            except Exception:
                self.log.warning("otx_passive_dns request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.warning("otx_passive_dns returned status %d for %s", resp.status_code, domain)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.warning("otx_passive_dns returned invalid JSON for %s", domain, exc_info=True)
                continue

            if not isinstance(data, dict):
                continue

            records = data.get("passive_dns", [])
            seen: set[str] = set()
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                hostname = rec.get("hostname", "").strip().lower()
                while hostname.startswith("*."):
                    hostname = hostname[2:]
                hostname = hostname.strip()
                if hostname and hostname.endswith("." + domain) and hostname not in seen:
                    seen.add(hostname)
                    yield Subdomain(
                        value=hostname,
                        parent_id=entity.id,
                        source_module=self.name,
                    )

"""crt.sh Certificate Transparency subdomain enumeration module.

Queries crt.sh JSON endpoint for certificates matching the target domain.
Fixes bug §2.7: crt.sh returns 404 when no certificates are found; do not
retry on 404, return empty immediately.
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Subdomain
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.subdomain.crtsh",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Subdomain],
    active=False,
    requires_key=None,
)
class CrtshSubdomain(BaseModule):
    """Enumerates subdomains via crt.sh Certificate Transparency logs."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()
            url = f"https://crt.sh/?q=%.{domain}&output=json"
            try:
                resp = self.client.get(url, host_hint="crt.sh")
            except Exception:
                self.log.warning("crt.sh request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code == 404:
                # Bug §2.7 fix: 404 means no certificates exist, do not retry
                self.log.debug("crt.sh returned 404 for %s (no certificates)", domain)
                continue

            if resp.status_code != 200:
                self.log.warning("crt.sh returned status %d for %s", resp.status_code, domain)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.warning("crt.sh returned invalid JSON for %s", domain, exc_info=True)
                continue

            if not isinstance(data, list):
                continue

            seen: set[str] = set()
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                name_value = entry.get("name_value", "")
                for line in name_value.split("\n"):
                    sub = line.strip().lower()
                    while sub.startswith("*."):
                        sub = sub[2:]
                    sub = sub.strip()
                    if sub and sub.endswith("." + domain) and sub not in seen:
                        seen.add(sub)
                        yield Subdomain(
                            value=sub,
                            parent_id=entity.id,
                            source_module=self.name,
                        )

"""DNS AXFR (Zone Transfer) attempt module.

Active module that resolves authoritative nameservers for a domain and attempts
an AXFR zone transfer. If permitted, extracts all subdomains exposed in the zone.
Gracefully handles refused or timed out attempts.
"""

from __future__ import annotations

from collections.abc import Iterable

import dns.exception
import dns.query
import dns.resolver
import dns.zone

from tddt.core.entity import BaseEntity, Domain, Subdomain
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.dns.axfr_attempt",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Subdomain],
    active=True,
    requires_key=None,
)
class AxfrAttemptModule(BaseModule):
    """Attempts active DNS zone transfer (AXFR) on authoritative nameservers."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            try:
                ns_records = dns.resolver.resolve(domain, "NS", lifetime=self.settings.timeout)
                nameservers = [str(ns).rstrip(".") for ns in ns_records]
            except Exception:
                self.log.warning("AXFR: failed to resolve NS for %s", domain, exc_info=True)
                continue

            seen: set[str] = set()
            for ns in nameservers:
                try:
                    self.log.debug("Attempting AXFR for %s on nameserver %s", domain, ns)
                    zone = dns.zone.from_xfr(dns.query.xfr(ns, domain, timeout=5, lifetime=5))
                    for node in zone.nodes.keys():
                        node_str = str(node).strip()
                        if node_str == "@" or not node_str:
                            continue
                        sub = f"{node_str}.{domain}".lower()
                        if sub not in seen:
                            seen.add(sub)
                            yield Subdomain(
                                value=sub,
                                parent_id=entity.id,
                                source_module=self.name,
                            )
                except dns.exception.DNSException:
                    self.log.debug("AXFR refused or failed on %s for %s", ns, domain)
                except Exception:
                    self.log.warning("Unexpected error during AXFR on %s for %s", ns, domain, exc_info=True)

"""Wildcard DNS detection module.

Queries random high-entropy subdomain names. If any resolves, sets
`wildcard_dns = True` on the domain metadata, records the resolved wildcard IPs,
and emits a DNSRecord finding. Also provides confidence adjustment utilities for
subdomains found under wildcard zones.
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Iterable

import dns.resolver

from tddt.core.entity import BaseEntity, DNSRecord, Domain, Subdomain
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.dns.wildcard_detector",
    mode=["corporate"],
    consumes=[Domain],
    produces=[DNSRecord],
    active=False,
    requires_key=None,
)
class WildcardDetectorModule(BaseModule):
    """Detects wildcard DNS resolution by querying randomized subdomains."""

    def adjust_subdomain_for_wildcard(self, sub: Subdomain, domain: Domain) -> Subdomain:
        """Adjusts subdomain confidence if parent domain has wildcard DNS enabled."""
        if domain.metadata.get("wildcard_dns"):
            patch = dict(sub.metadata)
            patch["wildcard_suspect"] = True
            return dataclasses.replace(sub, confidence=min(sub.confidence, 0.4), metadata=patch)
        return sub

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            # Test 3 random long subdomains
            test_probes = [
                f"wcd-{uuid.uuid4().hex[:16]}.{domain}",
                f"wcd-{uuid.uuid4().hex[:16]}.{domain}",
                f"wcd-{uuid.uuid4().hex[:16]}.{domain}",
            ]

            resolved_ips: set[str] = set()
            for probe in test_probes:
                try:
                    ans = dns.resolver.resolve(probe, "A", lifetime=self.settings.timeout)
                    for r in ans:
                        resolved_ips.add(str(r).strip())
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                    self.log.debug("wildcard probe %s did not resolve", probe)
                except Exception:
                    self.log.warning("Wildcard probe %s failed", probe, exc_info=True)

            if resolved_ips:
                entity.metadata["wildcard_dns"] = True
                entity.metadata["wildcard_ips"] = sorted(resolved_ips)
                self.log.warning("Wildcard DNS detected on %s: %s", domain, resolved_ips)
                yield DNSRecord(
                    value=f"{domain}:wildcard:active",
                    metadata={
                        "wildcard": True,
                        "wildcard_ips": sorted(resolved_ips),
                        "domain": domain,
                    },
                    parent_id=entity.id,
                    source_module=self.name,
                )
            else:
                entity.metadata["wildcard_dns"] = False

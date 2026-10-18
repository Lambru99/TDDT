"""Multi-resolver DNS over HTTPS (DoH) cross-checking module.

Queries public DoH endpoints (Cloudflare, Google, Quad9, NextDNS) to resolve A
records for target domains. Cross-checks results and falls back gracefully if any
resolver is unreachable.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, IPAddress
from tddt.core.module import BaseModule, register_module

DOH_RESOLVERS = [
    {
        "name": "Cloudflare",
        "url": "https://cloudflare-dns.com/dns-query?name={domain}&type=A",
        "host": "cloudflare-dns.com",
        "headers": {"Accept": "application/dns-json"},
    },
    {
        "name": "Google",
        "url": "https://dns.google/resolve?name={domain}&type=A",
        "host": "dns.google",
        "headers": {"Accept": "application/json"},
    },
    {
        "name": "Quad9",
        "url": "https://dns.quad9.net/dns-query?name={domain}&type=A",
        "host": "dns.quad9.net",
        "headers": {"Accept": "application/dns-json"},
    },
    {
        "name": "NextDNS",
        "url": "https://dns.nextdns.io/dns-query?name={domain}&type=A",
        "host": "dns.nextdns.io",
        "headers": {"Accept": "application/dns-json"},
    },
]


@register_module(
    name="corporate.dns.doh_multi",
    mode=["corporate"],
    consumes=[Domain],
    produces=[IPAddress],
    active=False,
    requires_key=None,
)
class DohMultiModule(BaseModule):
    """Cross-checks DNS resolution across multiple DoH providers."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            ip_resolvers: dict[str, list[str]] = defaultdict(list)

            for resolver in DOH_RESOLVERS:
                endpoint = resolver["url"].format(domain=domain)
                try:
                    resp = self.client.get(
                        endpoint,
                        host_hint=resolver["host"],
                        headers=resolver["headers"],
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        answers = data.get("Answer", [])
                        for ans in answers:
                            if isinstance(ans, dict) and ans.get("type") == 1:
                                ip = ans.get("data", "").strip()
                                if ip:
                                    ip_resolvers[ip].append(resolver["name"])
                    else:
                        self.log.debug("DoH %s returned status %d", resolver["name"], resp.status_code)
                except Exception:
                    self.log.warning("DoH query to %s failed for %s", resolver["name"], domain, exc_info=True)

            for ip, resolvers in ip_resolvers.items():
                confidence = min(1.0, 0.7 + 0.1 * len(resolvers))
                yield IPAddress(
                    value=ip,
                    confidence=confidence,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"resolvers": resolvers, "domain": domain},
                )

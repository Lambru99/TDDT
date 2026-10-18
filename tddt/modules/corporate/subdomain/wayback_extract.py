"""Subdomain extraction from historical URLs (Wayback data reuse).

Consumes URL entities produced by web archives/crawlers and extracts new
Subdomain entities without making additional network calls.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from tddt.core.entity import BaseEntity, Subdomain, URL
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.subdomain.wayback_extract",
    mode=["corporate"],
    consumes=[URL],
    produces=[Subdomain],
    active=False,
    requires_key=None,
)
class WaybackExtractSubdomain(BaseModule):
    """Extracts subdomains from crawled or historical URLs."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        seen: set[str] = set()
        for entity in entities:
            if not isinstance(entity, URL):
                continue
            parsed = urlparse(entity.value)
            host = (parsed.hostname or "").strip().lower()
            if not host:
                continue

            target_domain = entity.metadata.get("domain")
            if target_domain:
                target_domain = target_domain.strip().lower()
                if host.endswith("." + target_domain) and host != target_domain and host not in seen:
                    seen.add(host)
                    yield Subdomain(
                        value=host,
                        parent_id=entity.id,
                        source_module=self.name,
                    )
            else:
                # No domain in metadata: extract if it looks like a valid multi-level FQDN
                # and not a raw IPv4/IPv6 address
                if host.count(".") >= 2 and not all(p.isdigit() for p in host.split(".")) and host not in seen:
                    seen.add(host)
                    yield Subdomain(
                        value=host,
                        parent_id=entity.id,
                        source_module=self.name,
                    )

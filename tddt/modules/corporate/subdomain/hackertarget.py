"""HackerTarget host search subdomain enumeration module.

Queries api.hackertarget.com/hostsearch for subdomains of the target domain.
Gracefully handles API quota limits.
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Subdomain
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.subdomain.hackertarget",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Subdomain],
    active=False,
    requires_key=None,
)
class HackerTargetSubdomain(BaseModule):
    """Enumerates subdomains using HackerTarget hostsearch API."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()
            url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
            try:
                resp = self.client.get(url, host_hint="api.hackertarget.com")
            except Exception:
                self.log.warning("hackertarget request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.warning("hackertarget returned status %d for %s", resp.status_code, domain)
                continue

            text = resp.text
            if "API count exceeded" in text:
                self.log.warning("hackertarget API quota exceeded for %s", domain)
                continue

            low_text = text.lower()
            if "error check your search parameter" in low_text or "no records found" in low_text:
                continue

            seen: set[str] = set()
            for line in text.splitlines():
                if not line.strip():
                    continue
                parts = line.split(",")
                sub = parts[0].strip().lower()
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

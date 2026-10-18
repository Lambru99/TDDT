"""RapidDNS scraping subdomain enumeration module.

Scrapes rapiddns.io for subdomains associated with the target domain.
"""

from __future__ import annotations

from collections.abc import Iterable

from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Domain, Subdomain
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.subdomain.rapiddns",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Subdomain],
    active=False,
    requires_key=None,
)
class RapidDnsSubdomain(BaseModule):
    """Enumerates subdomains by scraping RapidDNS."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()
            url = f"https://rapiddns.io/subdomain/{domain}?modules=subdomain"
            try:
                resp = self.client.get(url, host_hint="rapiddns.io")
            except Exception:
                self.log.warning("rapiddns request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.warning("rapiddns returned status %d for %s", resp.status_code, domain)
                continue

            try:
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception:
                self.log.warning("rapiddns failed to parse HTML for %s", domain, exc_info=True)
                continue

            seen: set[str] = set()
            for td in soup.find_all("td"):
                text = td.get_text().strip().lower()
                while text.startswith("*."):
                    text = text[2:]
                text = text.strip()
                if text and text.endswith("." + domain) and text not in seen:
                    seen.add(text)
                    yield Subdomain(
                        value=text,
                        parent_id=entity.id,
                        source_module=self.name,
                    )

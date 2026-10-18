"""Pastebin dorking discovery module.

Searches public paste archives (via site:pastebin.com search queries)
for leaked credentials, dump files, and configurations mentioning the target domain.
"""

from __future__ import annotations

from collections.abc import Iterable

from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Domain, Secret, URL
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.secrets.pastebin_dork",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Secret, URL],
    active=False,
    requires_key=None,
)
class PastebinDorkModule(BaseModule):
    """Searches for domain mentions in Pastebin leaks."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            url = "https://html.duckduckgo.com/html/"
            data = {"q": f'site:pastebin.com "{domain}"'}

            try:
                resp = self.client.post(url, data=data, host_hint="html.duckduckgo.com")
            except Exception:
                self.log.warning("pastebin_dork request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.debug("pastebin_dork status %d for %s", resp.status_code, domain)
                continue

            try:
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception:
                self.log.debug("pastebin_dork failed to parse HTML for %s", domain)
                continue

            seen: set[str] = set()
            for link in soup.find_all("a", class_="result__a"):
                href = link.get("href", "").strip()
                if href and "pastebin.com/" in href and "duckduckgo" not in href:
                    if href not in seen:
                        seen.add(href)
                        yield URL(
                            value=href,
                            parent_id=entity.id,
                            source_module=self.name,
                            metadata={"domain": domain, "source": "pastebin_dork"},
                        )
